"""Ters/ileri kinematik, Jacobian, limit denetimi, calisma alani taramasi.

Ters kinematik KAPALI FORMDUR -- iterasyon veya kucuk aci yaklasimi kullanilmaz.
Krank pimi, motor miline dik bir duzlemde daire cizer; mil ic sistemde X eksenine
paralel oldugu icin problem cember-cember kesisimine iner.

Tum uzunluklar metre, acilar radyan.

Bkz. docs/files/geometry.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from scipy.optimize import least_squares

from . import frames
from .config import SeatConfig
from .units import cm_to_m, deg_to_rad, m_to_cm, rad_to_deg

RIGHT = 0
LEFT = 1
_EPS = 1e-12


class LimitReason(Enum):
    """Bir pozun neden ulasilamaz veya uygunsuz oldugunu soyler.

    Sira onceliklidir: erisilemezlik once, sonra mekanizma, sonra parca limitleri.
    """

    OK = ("OK", "Uygun")
    UNREACHABLE_ROD = ("UNREACHABLE_ROD", "Çubuk yanal açıklığı kapatamıyor")
    UNREACHABLE_CIRCLE = ("UNREACHABLE_CIRCLE", "Erişim dışı — krank yetişmiyor")
    DEAD_POINT = ("DEAD_POINT", "Krank ölü noktası")
    POT_RANGE = ("POT_RANGE", "Pot aralığı aşıldı — pot kırılır")
    GIMBAL_ANGLE = ("GIMBAL_ANGLE", "Kardan mafsalı açı limiti")
    ROD_END_ANGLE = ("ROD_END_ANGLE", "Rot başı sapma limiti")
    MECH_STOP = ("MECH_STOP", "Mekanik takoz")
    COLLISION = ("COLLISION", "Çarpışma")

    def __init__(self, code: str, label_tr: str) -> None:
        self.code = code
        self.label_tr = label_tr


# Oncelik sirasi: kucuk indis once raporlanir.
_REASON_ORDER = [
    LimitReason.UNREACHABLE_ROD,
    LimitReason.UNREACHABLE_CIRCLE,
    LimitReason.DEAD_POINT,
    LimitReason.POT_RANGE,
    LimitReason.GIMBAL_ANGLE,
    LimitReason.ROD_END_ANGLE,
    LimitReason.MECH_STOP,
    LimitReason.COLLISION,
]


@dataclass
class Pose:
    """Mekanizmanin tek bir konfigurasyonu ve tum limit olcutleri."""

    pitch: float
    roll: float
    R: np.ndarray = field(repr=False)
    theta: np.ndarray = field(default_factory=lambda: np.zeros(2))
    attach: np.ndarray = field(default_factory=lambda: np.zeros((2, 3)), repr=False)
    pin: np.ndarray = field(default_factory=lambda: np.zeros((2, 3)), repr=False)
    rod_unit: np.ndarray = field(default_factory=lambda: np.zeros((2, 3)), repr=False)
    transmission_deg: np.ndarray = field(default_factory=lambda: np.zeros(2))
    deadpoint_margin_deg: np.ndarray = field(default_factory=lambda: np.zeros(2))
    rod_end_misalign_deg: np.ndarray = field(default_factory=lambda: np.zeros((2, 2)))
    gimbal_tilt_deg: float = 0.0
    pot_angle_deg: np.ndarray = field(default_factory=lambda: np.zeros(2))
    stop_contact: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))
    min_clearance_m: float = float("inf")
    closest_pair: str = ""
    static_contacts: list = field(default_factory=list, repr=False)
    reachable: bool = True
    reason: LimitReason = LimitReason.OK

    @property
    def ok(self) -> bool:
        return self.reachable and self.reason is LimitReason.OK


@dataclass
class WorkspaceMap:
    """Pitch-roll duzleminde tarama sonucu."""

    pitch_deg: np.ndarray  # (n,) izgara eksenleri
    roll_deg: np.ndarray  # (m,)
    reason: np.ndarray  # (m, n) LimitReason nesneleri, object dtype
    reason_code: np.ndarray  # (m, n) int -- cizim icin
    ok: np.ndarray  # (m, n) bool
    transmission_deg: np.ndarray  # (m, n) iki krankin EN KOTUSU (90'a en uzak)
    deadpoint_margin_deg: np.ndarray  # (m, n) iki krankin en kucugu
    targets_met: dict[str, bool] = field(default_factory=dict)
    targets_detail: dict[str, str] = field(default_factory=dict)
    max_pitch_deg: tuple[float, float] = (0.0, 0.0)
    max_roll_deg: tuple[float, float] = (0.0, 0.0)

    @property
    def reason_legend(self) -> list[LimitReason]:
        """Haritada gercekten gorunen sebepler, oncelik sirasinda."""
        present = set(self.reason_code.ravel().tolist())
        order = [LimitReason.OK] + _REASON_ORDER
        return [r for i, r in enumerate(order) if i in present]


def reason_order() -> list[LimitReason]:
    """Sebepler, harita kodlariyla ayni sirada (indis 0 = OK)."""
    return [LimitReason.OK] + list(_REASON_ORDER)


def reason_code(reason: LimitReason) -> int:
    """Bir sebebin harita kodu. reason_order()[reason_code(r)] is r."""
    if reason is LimitReason.OK:
        return 0
    return _REASON_ORDER.index(reason) + 1


# Ic kullanim icin kisa ad
_reason_code = reason_code


def _wrap_pi(angle):
    """Aciyi (-pi, pi] araligina indirir."""
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


class Mechanism:
    """Mekanizmanin SI cinsinden ic gosterimi ve kinematik cozumleri."""

    def __init__(self, cfg: SeatConfig, *, check_collision: bool = True) -> None:
        self.cfg = cfg
        self.check_collision = check_collision
        g = cfg.geometry

        self.outer_axis: str = g.gimbal.outer_axis
        self.G = frames.to_internal(g.gimbal.position_cm)

        # Plaka baglanti noktalari, plaka cerceves, mafsala gore. x isareti tarafa gore.
        attach = np.asarray(g.rod_attach_cm, dtype=float)
        self.p_local = np.stack(
            [frames.to_internal(attach), frames.to_internal(attach * [-1.0, 1.0, 1.0])]
        )

        shaft = np.asarray(g.motor_shaft_cm, dtype=float)
        self.S = np.stack(
            [frames.to_internal(shaft), frames.to_internal(shaft * [-1.0, 1.0, 1.0])]
        )

        self.R_crank = float(cm_to_m(g.crank.length_cm))
        self.L_rod = float(cm_to_m(g.rod.length_cm))
        self.theta0 = float(deg_to_rad(g.crank.neutral_offset_deg))

        self.plate_underside = float(cm_to_m(g.top_plate.underside_above_gimbal_cm))

        lim = cfg.limits
        self.rod_end_limit = float(deg_to_rad(lim.rod_end_misalign_deg))
        self.gimbal_limit = float(deg_to_rad(lim.gimbal_max_deg))
        self.deadpoint_margin = float(deg_to_rad(lim.deadpoint_margin_deg))
        self.clearance_min = float(cm_to_m(lim.clearance_min_cm))
        self.pot_half_range = float(deg_to_rad(lim.pot.mechanical_range_deg)) / 2.0
        self.pot_offset = float(deg_to_rad(lim.pot.mount_offset_deg))

        # Takozlar: (x, z) kullanici -> (X, Y) ic sistem. Yukseklikler takoz basina.
        stops = np.asarray(cfg.stops.positions_cm, dtype=float)
        self.stop_xy = cm_to_m(stops) if len(stops) else np.zeros((0, 2))
        self.stop_top = (
            cm_to_m(np.asarray(cfg.stops.heights(), dtype=float))
            if len(stops)
            else np.zeros(0)
        )

        self._excluded = cfg.collision.excluded()
        self._collision_samples = cfg.collision.samples

        # Dal, notr pozdan bir kez belirlenir ve sabit kalir (bkz. _solve_crank).
        self.branch_sign = np.ones(2)
        self.branch_sign = self._resolve_branch()

    @classmethod
    def from_config(cls, cfg: SeatConfig, **kwargs) -> Mechanism:
        return cls(cfg, **kwargs)

    # --- Temel geometri ----------------------------------------------------------

    def attach_point(self, R: np.ndarray, side: int) -> np.ndarray:
        """Plaka baglanti noktasi, dunya cercevesi."""
        return self.G + R @ self.p_local[side]

    def pin_point(self, theta: float, side: int) -> np.ndarray:
        """Krank pimi konumu. theta=0 ve offset=0'da pim, mil merkezinin tam arkasinda."""
        phi = theta + self.theta0
        return self.S[side] + self.R_crank * np.array([0.0, -np.cos(phi), np.sin(phi)])

    def _pin_velocity_dir(self, theta: float) -> np.ndarray:
        """dC/dtheta -- krank pimi hiz yonu (buyukluk dahil)."""
        phi = theta + self.theta0
        return self.R_crank * np.array([0.0, np.sin(phi), np.cos(phi)])

    # --- Ters kinematik: kapali form ---------------------------------------------

    def _crank_roots(
        self, P: np.ndarray, side: int
    ) -> tuple[tuple[float, float] | None, LimitReason]:
        """|P - C(theta)| = L denkleminin iki kokunu kapali formda bulur.

        Kokler (s=+1 dali, s=-1 dali) sirasiyla dondurulur. Bkz. docs/files/geometry.md

        Returns:
            ((theta_plus, theta_minus), OK) veya (None, UNREACHABLE_*)
        """
        S = self.S[side]
        dx = P[0] - S[0]

        # Cubugun yanal (X) acikligi kapatmasi gerekiyor; kalan duzlem ici bosluk:
        l_eff_sq = self.L_rod**2 - dx**2
        if l_eff_sq <= _EPS:
            return None, LimitReason.UNREACHABLE_ROD

        # YZ duzleminde cember-cember kesisimi
        s_yz = S[1:]
        delta = P[1:] - s_yz
        D = float(np.hypot(delta[0], delta[1]))
        if D < _EPS:
            return None, LimitReason.UNREACHABLE_CIRCLE

        a = (D * D + self.R_crank**2 - l_eff_sq) / (2.0 * D)
        h_sq = self.R_crank**2 - a * a
        if h_sq < 0.0:
            return None, LimitReason.UNREACHABLE_CIRCLE
        h = np.sqrt(h_sq)

        u = delta / D
        n = np.array([-u[1], u[0]])  # YZ duzleminde 90 derece dondurulmus
        base = s_yz + a * u

        thetas = []
        for sign in (1.0, -1.0):
            c_yz = base + sign * h * n
            # C - S = R * (-cos(phi), sin(phi))  ->  phi = atan2(dZ, -dY)
            phi = float(np.arctan2(c_yz[1] - s_yz[1], -(c_yz[0] - s_yz[0])))
            thetas.append(float(_wrap_pi(phi - self.theta0)))
        return (thetas[0], thetas[1]), LimitReason.OK

    def _solve_crank(
        self, P: np.ndarray, side: int
    ) -> tuple[float | None, LimitReason]:
        """Montajin SABIT dalindaki krank acisini dondurur.

        Dal, montajin kalici bir ozelligidir: mekanizma sokulmeden dal degistiremez,
        cunku bunun icin olu noktadan (teget durumdan) gecmesi gerekirdi. Bu yuzden
        dal notr pozda bir kez belirlenir ve her yerde aynisi kullanilir.

        Onceki surum "bir onceki cozume en yakin kok" seciyordu; bu, izgara adimi
        olu nokta bandinin uzerinden atladiginda mekanizmayi aynalanmis dala
        gecirip fizik dis torklar uretiyordu.
        """
        roots, reason = self._crank_roots(P, side)
        if roots is None:
            return None, reason
        return roots[0 if self.branch_sign[side] > 0 else 1], LimitReason.OK

    def _resolve_branch(self) -> np.ndarray:
        """Notr pozda hangi kokun gecerli oldugunu belirler (taraf basina +1 / -1)."""
        R = frames.rotation(0.0, 0.0, self.outer_axis)
        signs = np.ones(2)
        for side in (RIGHT, LEFT):
            roots, reason = self._crank_roots(self.attach_point(R, side), side)
            if roots is None:
                raise ValueError(
                    f"notr poz ulasilamaz ({reason.label_tr}) -- geometri kendi icinde "
                    f"tutarsiz. config.validate() cikisina bakin."
                )
            # Notrde krank acisi 0 olmali; hangi kok buna yakinsa o dal gecerlidir.
            signs[side] = 1.0 if abs(roots[0]) <= abs(roots[1]) else -1.0
        return signs

    def ik(self, pitch: float, roll: float, *, check_collision: bool | None = None) -> Pose:
        """Ters kinematik: (pitch, roll) -> iki krank acisi ve tum limit olcutleri.

        Sonuc cagri sirasindan BAGIMSIZDIR: dal montajda sabitlenmistir, bir onceki
        cozume gore secilmez.

        Args:
            pitch: radyan, + = on yukari
            roll: radyan, + = sag taraf yukari
            check_collision: None ise ornegin varsayilani kullanilir
        """
        R = frames.rotation(pitch, roll, self.outer_axis)
        pose = Pose(pitch=pitch, roll=roll, R=R)

        theta = np.zeros(2)
        attach = np.zeros((2, 3))
        pin = np.zeros((2, 3))

        for side in (RIGHT, LEFT):
            P = self.attach_point(R, side)
            attach[side] = P
            th, reason = self._solve_crank(P, side)
            if th is None:
                pose.attach = attach
                pose.reachable = False
                pose.reason = reason
                pose.gimbal_tilt_deg = float(rad_to_deg(frames.tilt_angle(R)))
                return pose
            theta[side] = th
            pin[side] = self.pin_point(th, side)

        pose.theta = theta
        pose.attach = attach
        pose.pin = pin
        metrics = self._fill_metrics(pose)

        do_collision = self.check_collision if check_collision is None else check_collision
        self._classify(pose, metrics, do_collision)
        return pose

    def _fill_metrics(self, pose: Pose) -> dict[str, np.ndarray]:
        """Transmisyon acisi, rot basi sapmasi, mafsal egimi, pot acisi.

        Olcutler dogal olarak RADYAN uretilir (arccos/arcsin). Pose'a derece olarak
        yazilir cunku Pose bir raporlama nesnesidir ve arayuz dereceyle calisir; ayni
        degerlerin radyan hali limit karsilastirmasi icin geri dondurulur.

        Boylece limitler SI'da (radyan) kalir ve _classify icinde derece->radyan geri
        donusumu yapilmaz -- bkz. docs/ARCHITECTURE.md, birim politikasi.
        """
        trans = np.zeros(2)
        rod_unit = np.zeros((2, 3))
        misalign = np.zeros((2, 2))
        plate_bore = pose.R @ np.array([1.0, 0.0, 0.0])
        x_hat = np.array([1.0, 0.0, 0.0])

        for side in (RIGHT, LEFT):
            crank_vec = pose.pin[side] - self.S[side]
            rod_vec = pose.attach[side] - pose.pin[side]
            n_rod = float(np.linalg.norm(rod_vec))
            u = rod_vec / n_rod if n_rod > _EPS else np.zeros(3)
            rod_unit[side] = u

            n_crank = float(np.linalg.norm(crank_vec))
            if n_crank > _EPS and n_rod > _EPS:
                cos_mu = float(np.dot(crank_vec, rod_vec) / (n_crank * n_rod))
                trans[side] = np.arccos(np.clip(cos_mu, -1.0, 1.0))
            else:
                trans[side] = 0.0

            # Rot basi sapmasi: cubuk nominal olarak bilye deligi eksenine DIKTIR.
            misalign[side, 0] = np.arcsin(abs(float(np.dot(u, x_hat))))
            misalign[side, 1] = np.arcsin(abs(float(np.dot(u, plate_bore))))

        margin = np.minimum(trans, np.pi - trans)
        tilt = frames.tilt_angle(pose.R)
        pot = pose.theta + self.pot_offset

        pose.rod_unit = rod_unit
        pose.transmission_deg = rad_to_deg(trans)
        pose.deadpoint_margin_deg = rad_to_deg(margin)
        pose.rod_end_misalign_deg = rad_to_deg(misalign)
        pose.gimbal_tilt_deg = float(rad_to_deg(tilt))
        pose.pot_angle_deg = rad_to_deg(pot)
        pose.stop_contact = self._stop_contacts(pose.R)

        return {"margin": margin, "misalign": misalign, "tilt": tilt, "pot": pot}

    def plate_underside_height(self, R: np.ndarray, xy: np.ndarray) -> np.ndarray:
        """Plaka alt yuzey duzleminin verilen (X, Y) dikeylerindeki yuksekligi (m).

        Duzlem Q noktasindan gecer, normali n'dir:
            Z(X, Y) = Q_z - ( n_x (X - Q_x) + n_y (Y - Q_y) ) / n_z
        """
        Q = self.G + R @ np.array([0.0, 0.0, self.plate_underside])
        n = frames.plate_normal(R)
        if abs(n[2]) < _EPS:
            return np.full(len(xy), -np.inf)
        dx = xy[:, 0] - Q[0]
        dy = xy[:, 1] - Q[1]
        return Q[2] - (n[0] * dx + n[1] * dy) / n[2]

    def _stop_contacts(self, R: np.ndarray) -> np.ndarray:
        """Plakanin alt yuzey duzlemi hangi takozlara degiyor.

        Takoz acisini sabit varsaymak yerine geometrik olarak cozer: alt yuzey duzlemi,
        takozun (x, z) dikeyinde o takozun ust yuzeyinin altina inerse temas var.
        """
        if len(self.stop_xy) == 0:
            return np.zeros(0, dtype=bool)
        return self.plate_underside_height(R, self.stop_xy) <= self.stop_top

    def _stop_critical_signs(self, idx: int) -> tuple[float, float]:
        """Bir takozun bulundugu cadrana dogru egim yonu (pitch isareti, roll isareti).

        Takoz, plakanin o noktasi ALCALDIGINDA devreye girer. Arkadaki takoz (z<0) on
        yukari kalkinca alcalir; sagdaki takoz (x>0) sag asagi inince alcalir.
        """
        sx, sy = self.stop_xy[idx]
        return (1.0 if sy < 0 else -1.0), (-1.0 if sx > 0 else 1.0)

    def suggest_stop_heights_cm(self, target_deg: float = 12.0) -> list[float]:
        """Her takozun hedef acida devreye girmesi icin gereken ust yuzey yuksekligi (cm).

        Takoz konumunu degistirdiginizde yuksekligi yeniden hesaplamak icin kullanin;
        sabit bir yukseklik varsayimi, konum degisince yanlis aciya kayar.
        """
        out = []
        for idx in range(len(self.stop_xy)):
            sign_p, sign_r = self._stop_critical_signs(idx)
            R = frames.rotation(
                float(deg_to_rad(sign_p * target_deg)),
                float(deg_to_rad(sign_r * target_deg)),
                self.outer_axis,
            )
            z = self.plate_underside_height(R, self.stop_xy[idx : idx + 1])[0]
            out.append(round(float(m_to_cm(z)), 2))
        return out

    def stop_engagement_deg(self, n_steps: int = 900) -> list[dict]:
        """Her takozun hangi acida devreye girdigini bulur.

        Takoz konumu veya yuksekligi degistiginde devreye girme acisi degisir; sabit
        +-12 derece varsayilmaz. Her takoz icin en kritik yon taranir.
        """
        out = []
        for idx, (sx, sy) in enumerate(self.stop_xy):
            sign_p, sign_r = self._stop_critical_signs(idx)
            found = None
            for k in range(1, n_steps + 1):
                a = k * 0.05
                R = frames.rotation(
                    float(deg_to_rad(sign_p * a)),
                    float(deg_to_rad(sign_r * a)),
                    self.outer_axis,
                )
                if self.plate_underside_height(R, self.stop_xy[idx : idx + 1])[0] <= (
                    self.stop_top[idx]
                ):
                    found = a
                    break
            out.append(
                {
                    "index": idx,
                    "label_tr": f"Takoz {idx + 1}",
                    "x_cm": float(m_to_cm(sx)),
                    "z_cm": float(m_to_cm(sy)),
                    "top_height_cm": float(m_to_cm(self.stop_top[idx])),
                    "engages_at_deg": found,
                    "direction_tr": (
                        f"pitch {sign_p * 1:+.0f} / roll {sign_r * 1:+.0f} yonunde"
                    ),
                }
            )
        return out

    def _classify(
        self, pose: Pose, metrics: dict[str, np.ndarray], do_collision: bool
    ) -> None:
        """Limitleri oncelik sirasina gore denetler, ilk ihlali kaydeder.

        Karsilastirmalar RADYANDA yapilir: hem limitler hem metrikler SI'dadir, birim
        donusumu yoktur.
        """
        violations: list[LimitReason] = []

        if np.any(metrics["margin"] < self.deadpoint_margin):
            violations.append(LimitReason.DEAD_POINT)
        if np.any(np.abs(metrics["pot"]) > self.pot_half_range):
            violations.append(LimitReason.POT_RANGE)
        if metrics["tilt"] > self.gimbal_limit:
            violations.append(LimitReason.GIMBAL_ANGLE)
        if np.any(metrics["misalign"] > self.rod_end_limit):
            violations.append(LimitReason.ROD_END_ANGLE)
        if bool(np.any(pose.stop_contact)):
            violations.append(LimitReason.MECH_STOP)

        if do_collision:
            from . import bodies, collision  # dairesel import'u onlemek icin yerel

            # Yalnizca HAREKETLI govde iceren ciftler calisma alanini sinirlar.
            # Iki statik parcanin darligi poza BAGLI DEGILDIR -- o bir montaj sorunu
            # ve Tasarim sekmesinde ayrica raporlanir (static_assembly_report).
            # prefilter ve cutoff clearance_min'den TURETILIR. Sabit 5 cm birakmak,
            # clearance_min 5 cm'i astiginda gercek ihlalleri sessizce atlardi.
            margin = 3.0 * self.clearance_min
            moving = collision.pairwise(
                bodies.build(self.cfg, pose),
                exclude_pairs=self._excluded,
                samples=self._collision_samples,
                prefilter=max(0.05, margin),
                skip_static=True,
                cutoff=margin,
            )
            if moving:
                pose.min_clearance_m = moving[0].distance
                pose.closest_pair = moving[0].label_tr
                if moving[0].distance < self.clearance_min:
                    violations.append(LimitReason.COLLISION)

        if violations:
            pose.reason = min(violations, key=_REASON_ORDER.index)

    # --- Ileri kinematik ---------------------------------------------------------

    def fk(
        self, theta: np.ndarray, seed: np.ndarray | None = None
    ) -> tuple[float, float]:
        """Ileri kinematik: (theta_sag, theta_sol) -> (pitch, roll).

        Iki bilinmeyen, iki denklem: |P_i(pitch, roll) - C_i(theta_i)| = L.
        Analitik cozumu yoktur (plaka rotasyonu iki aciya birden bagli).

        Raises:
            ValueError: yakinsamazsa
        """
        theta = np.asarray(theta, dtype=float)
        pins = np.stack([self.pin_point(theta[s], s) for s in (RIGHT, LEFT)])

        def residual(x: np.ndarray) -> np.ndarray:
            R = frames.rotation(x[0], x[1], self.outer_axis)
            return np.array(
                [
                    np.linalg.norm(self.attach_point(R, s) - pins[s]) - self.L_rod
                    for s in (RIGHT, LEFT)
                ]
            )

        x0 = np.zeros(2) if seed is None else np.asarray(seed, dtype=float)
        sol = least_squares(residual, x0, xtol=1e-14, ftol=1e-14, gtol=1e-14)
        if not sol.success or float(np.max(np.abs(sol.fun))) > 1e-9:
            raise ValueError(
                f"ileri kinematik yakınsamadı: theta={rad_to_deg(theta)}°, "
                f"artık={sol.fun}"
            )
        return float(sol.x[0]), float(sol.x[1])

    # --- Jacobian ----------------------------------------------------------------

    def jacobian(self, pitch: float, roll: float) -> np.ndarray:
        """J = d(theta_sag, theta_sol) / d(pitch, roll), analitik.

        Ortuk fonksiyon teoremi: g(P, theta) = |P - C(theta)|^2 - L^2 = 0 uzerinden
            dtheta/dP = (P - C) / ((P - C) . C'(theta))
        Zincir kurali ile dP/dpitch = (dR/dpitch) @ p_local.

        Paydanin sifira gitmesi tam olarak olu noktadir (cubuk krankla ayni dogrultuda).
        """
        R = frames.rotation(pitch, roll, self.outer_axis)
        dR_dp, dR_dr = frames.rotation_derivatives(pitch, roll, self.outer_axis)
        J = np.zeros((2, 2))

        for side in (RIGHT, LEFT):
            P = self.attach_point(R, side)
            th, reason = self._solve_crank(P, side)
            if th is None:
                raise ValueError(
                    f"Jacobian: poz ulaşılamaz ({reason.label_tr}), "
                    f"pitch={rad_to_deg(pitch):.2f} roll={rad_to_deg(roll):.2f}"
                )
            C = self.pin_point(th, side)
            d = P - C
            denom = float(np.dot(d, self._pin_velocity_dir(th)))
            if abs(denom) < 1e-14:
                raise ValueError("Jacobian tekil: ölü nokta")
            J[side, 0] = float(np.dot(d, dR_dp @ self.p_local[side])) / denom
            J[side, 1] = float(np.dot(d, dR_dr @ self.p_local[side])) / denom

        return J

    # --- Kolay sorgular ----------------------------------------------------------

    def total_height_cm(self) -> float:
        """Alt plaka altindan minder ustune toplam yukseklik."""
        g = self.cfg.geometry
        return (
            g.gimbal.position_cm[1]
            + g.top_plate.underside_above_gimbal_cm
            + g.top_plate.thickness_cm
            + g.cushion.thickness_cm
        )

    def is_reachable(
        self, pitch_deg: float, roll_deg: float, *, check_collision: bool | None = None
    ) -> bool:
        """Verilen aci (derece) ulasilabilir ve tum limitler icinde mi."""
        pose = self.ik(
            float(deg_to_rad(pitch_deg)),
            float(deg_to_rad(roll_deg)),
            check_collision=check_collision,
        )
        return pose.ok

    def _scan_axis(self, axis: int, sign: float, limit_deg: float = 30.0) -> float:
        """Bir eksende, adim adim ilerleyerek ulasilabilen son aciyi bulur (derece)."""
        step = 0.1
        last = 0.0
        a = step
        while a <= limit_deg + 1e-9:
            pitch = deg_to_rad(sign * a) if axis == 0 else 0.0
            roll = 0.0 if axis == 0 else deg_to_rad(sign * a)
            if not self.ik(float(pitch), float(roll)).ok:
                break
            last = sign * a
            a += step
        return float(last)

    def max_pitch_deg(self) -> tuple[float, float]:
        """(yukari maksimum, asagi maksimum) derece."""
        return self._scan_axis(0, 1.0), self._scan_axis(0, -1.0)

    def max_roll_deg(self) -> tuple[float, float]:
        """(sag yukari maksimum, sag asagi maksimum) derece."""
        return self._scan_axis(1, 1.0), self._scan_axis(1, -1.0)

    # --- Calisma alani haritasi --------------------------------------------------

    def workspace_map(
        self,
        pitch_range_deg: tuple[float, float] = (-20.0, 20.0),
        roll_range_deg: tuple[float, float] = (-20.0, 20.0),
        n: int = 61,
        *,
        check_collision: bool | None = None,
    ) -> WorkspaceMap:
        """Pitch-roll duzleminde n x n izgara tarar, her dugumde sinirlayan sebebi kaydeder."""
        pitches = np.linspace(pitch_range_deg[0], pitch_range_deg[1], n)
        rolls = np.linspace(roll_range_deg[0], roll_range_deg[1], n)

        reason = np.empty((n, n), dtype=object)
        code = np.zeros((n, n), dtype=int)
        ok = np.zeros((n, n), dtype=bool)
        trans = np.full((n, n), np.nan)
        margin = np.full((n, n), np.nan)

        for i, r_deg in enumerate(rolls):
            for j, p_deg in enumerate(pitches):
                pose = self.ik(
                    float(deg_to_rad(p_deg)),
                    float(deg_to_rad(r_deg)),
                    check_collision=check_collision,
                )
                reason[i, j] = pose.reason
                code[i, j] = _reason_code(pose.reason)
                ok[i, j] = pose.ok
                if pose.reachable:
                    # Iki krankin EN KOTUSU: 90'a en uzak olan
                    worst = int(np.argmax(np.abs(pose.transmission_deg - 90.0)))
                    trans[i, j] = pose.transmission_deg[worst]
                    margin[i, j] = float(np.min(pose.deadpoint_margin_deg))

        wm = WorkspaceMap(
            pitch_deg=pitches,
            roll_deg=rolls,
            reason=reason,
            reason_code=code,
            ok=ok,
            transmission_deg=trans,
            deadpoint_margin_deg=margin,
        )
        wm.max_pitch_deg = self.max_pitch_deg()
        wm.max_roll_deg = self.max_roll_deg()
        wm.targets_met, wm.targets_detail = self.target_report(
            check_collision=check_collision, with_limits=False
        )
        # "ulasilan" sutununu, zaten hesaplanmis maksimum acilardan doldur
        keys = list(wm.targets_met)
        details = [
            f"ulaşılan: {wm.max_pitch_deg[0]:+.1f}°",
            f"ulaşılan: {wm.max_pitch_deg[1]:+.1f}°",
            f"ulaşılan: {wm.max_roll_deg[0]:+.1f}°",
            f"ulaşılan: {wm.max_roll_deg[1]:+.1f}°",
            "dört köşeyi birlikte dener",
        ]
        wm.targets_detail = dict(zip(keys, details, strict=True))
        return wm

    def target_report(
        self, *, check_collision: bool | None = None, with_limits: bool = False
    ) -> tuple[dict[str, bool], dict[str, str]]:
        """Hedef kisitlarin saglanip saglanmadigi: (met, detail).

        UCUZDUR: yalnizca 8 ters kinematik cagrisi yapar, izgara taramaz. Bu yuzden
        "KISIT IHLALI" uyarisi her yeniden cizimde gosterilebilir -- kullanicinin en
        cok ihtiyaci olan bilgi bir dugmenin arkasinda kalmamali.

        Args:
            with_limits: True ise "ulasilan" sutununa 0,1 derece adimli tarama ile
                bulunan maksimum acilar yazilir. Bu tarama PAHALIDIR (~5 s), o yuzden
                varsayilan olarak kapalidir ve yalnizca calisma alani haritasi
                hesaplanirken acilir.
        """
        t = self.cfg.targets
        cp, cr = t.combined_deg

        def reach(p: float, r: float) -> bool:
            return self.is_reachable(p, r, check_collision=check_collision)

        if with_limits:
            up, down = self.max_pitch_deg()
            rp, rn = self.max_roll_deg()
            detail_pitch_up = f"ulaşılan: +{up:.1f}°"
            detail_pitch_dn = f"ulaşılan: {down:.1f}°"
            detail_roll_up = f"ulaşılan: +{rp:.1f}°"
            detail_roll_dn = f"ulaşılan: {rn:.1f}°"
        else:
            detail_pitch_up = detail_pitch_dn = "haritayı hesaplayın"
            detail_roll_up = detail_roll_dn = "haritayı hesaplayın"

        checks = {
            f"pitch_+{t.pitch_deg:g}": (reach(t.pitch_deg, 0.0), detail_pitch_up),
            f"pitch_-{t.pitch_deg:g}": (reach(-t.pitch_deg, 0.0), detail_pitch_dn),
            f"roll_+{t.roll_deg:g}": (reach(0.0, t.roll_deg), detail_roll_up),
            f"roll_-{t.roll_deg:g}": (reach(0.0, -t.roll_deg), detail_roll_dn),
            f"combined_{cp:g}+{cr:g}": (
                all(reach(cp * sp, cr * sr) for sp in (1, -1) for sr in (1, -1)),
                "dört köşeyi birlikte dener",
            ),
        }
        return (
            {k: v[0] for k, v in checks.items()},
            {k: v[1] for k, v in checks.items()},
        )
