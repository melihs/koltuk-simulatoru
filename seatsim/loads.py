"""Statik kuvvet ve tork cozumu.

Ust plaka + ustundeki her sey icin mafsal etrafinda moment dengesi kurularak iki
itme cubugu kuvveti, mafsal tepkisi, direk taban momenti ve motor torklari cozulur.
Sonuc, tamamen bagimsiz bir ikinci yolla (sanal is, Jacobian uzerinden) capraz
dogrulanir.

Bkz. docs/files/loads.md
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np

from . import frames
from .config import SeatConfig
from .geometry import LEFT, RIGHT, Mechanism, Pose
from .units import G, cm_to_m, deg_to_rad, m_to_cm, rad_to_deg

_GRAVITY = np.array([0.0, 0.0, -G])
_EPS = 1e-12


@dataclass
class MassScenario:
    """Bir yuk senaryosu. Uzunluklar METRE."""

    user_kg: float = 120.0
    carried_fraction: float = 0.85
    backrest_mode: str = "fixed"
    backrest_follow_fraction: float = 0.60
    seat_kg: float = 12.0
    plate_assembly_kg: float = 8.0
    com_height_m: float = 0.25
    com_fore_aft_m: float = 0.0
    com_lateral_m: float = 0.0

    @classmethod
    def from_config(cls, cfg: SeatConfig, **overrides) -> MassScenario:
        m = cfg.mass
        base = dict(
            user_kg=m.user_kg,
            carried_fraction=m.carried_fraction,
            backrest_mode=m.backrest_mode,
            backrest_follow_fraction=m.backrest_follow_fraction,
            seat_kg=m.seat_kg,
            plate_assembly_kg=m.plate_assembly_kg,
            com_height_m=float(cm_to_m(m.user_com_height_cm)),
            com_fore_aft_m=float(cm_to_m(m.user_com_fore_aft_cm)),
            com_lateral_m=float(cm_to_m(m.user_com_lateral_cm)),
        )
        base.update(overrides)
        return cls(**base)

    def describe_tr(self) -> str:
        mode = (
            "sırtlık sabit" if self.backrest_mode == "fixed" else "koltuğun tamamı eğiliyor"
        )
        extra = (
            f", takip oranı {self.backrest_follow_fraction:.2f}"
            if self.backrest_mode == "fixed"
            else ""
        )
        return (
            f"{self.user_kg:.0f} kg kullanıcı "
            f"(taşınan %{self.carried_fraction * 100.0:.0f}), "
            f"ağırlık merkezi {m_to_cm(self.com_fore_aft_m):+.0f} cm ileri, "
            f"{m_to_cm(self.com_lateral_m):+.0f} cm yan, "
            f"{m_to_cm(self.com_height_m):.0f} cm yukarıda, {mode}{extra}"
        )


@dataclass
class PointMass:
    """Noktasal kutle. rotating=True ise plaka cercevesinde tanimli."""

    mass: float
    local: np.ndarray  # plaka cercevesinde, mafsala gore (rotating=True)
    rotating: bool = True


@dataclass
class StaticResult:
    """Tek bir poz + senaryo icin statik cozum."""

    rod_force_n: np.ndarray = field(default_factory=lambda: np.zeros(2))
    gimbal_reaction_n: np.ndarray = field(default_factory=lambda: np.zeros(3))
    gimbal_post_bending_nm: float = 0.0
    gimbal_post_torsion_nm: float = 0.0
    motor_torque_nm: np.ndarray = field(default_factory=lambda: np.zeros(2))
    safety_factor: np.ndarray = field(default_factory=lambda: np.zeros(2))
    gravity_moment_nm: np.ndarray = field(default_factory=lambda: np.zeros(2))
    gravity_stiffness_nm_rad: np.ndarray = field(default_factory=lambda: np.zeros(2))
    total_moving_mass_kg: float = 0.0
    cross_check_error: float = 0.0
    condition: float = 1.0
    """Kuvvet matrisinin kondisyon sayisi.

    Notr civarinda ~1,1. Calisma alani kenarinda 20-30'a cikar (bir cubugun moment
    kolu kuculur, motor gercekten zorlanir). 1e4 ustu kullanilamaz kabul edilir.
    """
    singular: bool = False

    @property
    def rod_end_force_n(self) -> np.ndarray:
        return np.abs(self.rod_force_n)

    @property
    def worst_torque_nm(self) -> float:
        return float(np.max(np.abs(self.motor_torque_nm)))

    @property
    def min_safety_factor(self) -> float:
        return float(np.min(self.safety_factor))


_SWEEP_MARGIN = 1.2
"""Poz izgarasi, hedef acinin bu kati kadar tarar -- hedefin biraz otesi de gorulsun."""

_SWEEP_STEPS = 21


@dataclass
class SweepSpec:
    """En kotu durum taramasinin boyutlari. Aci derece, uzunluk cm."""

    pitch_deg: np.ndarray = field(default_factory=lambda: np.linspace(-12.0, 12.0, 21))
    roll_deg: np.ndarray = field(default_factory=lambda: np.linspace(-12.0, 12.0, 21))
    user_kg: tuple[float, ...] = (60.0, 90.0, 120.0)
    com_fore_aft_cm: tuple[float, ...] = (-5.0, 0.0, 4.0, 8.0)
    com_lateral_cm: tuple[float, ...] = (-5.0, 0.0, 5.0)
    com_height_cm: tuple[float, ...] = (20.0, 25.0, 30.0)
    backrest_modes: tuple[str, ...] = ("fixed", "tilting")
    follow_fractions: tuple[float, ...] = (0.4, 0.6, 0.8, 1.0)

    @classmethod
    def from_config(cls, cfg: SeatConfig) -> SweepSpec:
        """Tarama boyutlarini config.yaml'dan tureten kurucu.

        `mass.user_sweep_kg` ve `targets` boylece gercekten etkili olur; sabit sayilar
        birakmak, kullanicinin duzenledigi parametrenin hicbir ise yaramamasi demekti.
        """
        pitch = cls._axis(cfg.targets.pitch_deg)
        roll = cls._axis(cfg.targets.roll_deg)
        return cls(
            pitch_deg=pitch,
            roll_deg=roll,
            user_kg=tuple(float(v) for v in cfg.mass.user_sweep_kg),
        )

    @staticmethod
    def _axis(target_deg: float) -> np.ndarray:
        span = _SWEEP_MARGIN * abs(float(target_deg))
        return np.linspace(-span, span, _SWEEP_STEPS)


@dataclass
class WorstCase:
    """Tarama sonucu: en kotu durum ve yorumu."""

    max_motor_torque_nm: float = 0.0
    at_pitch_deg: float = 0.0
    at_roll_deg: float = 0.0
    at_scenario: MassScenario | None = None
    min_safety_factor: float = float("inf")
    verdict: str = "YETERLI"
    explanation_tr: str = ""
    max_rod_tension_n: float = 0.0
    max_rod_compression_n: float = 0.0
    max_gimbal_force_n: float = 0.0
    max_gimbal_post_bending_nm: float = 0.0
    n_poses: int = 0
    n_scenarios: int = 0


# --- Kutle modeli ---------------------------------------------------------------


def _point_masses(cfg: SeatConfig, sc: MassScenario) -> list[PointMass]:
    """Senaryoyu noktasal kutle listesine cevirir.

    backrest_mode="fixed": kullanici kutlesinin yalnizca follow_fraction kadari plakayla
    doner. Kalani sirtlik tarafindan tutulur; agirligi plakaya biner ama kolu egimle
    buyumez -- ters sarkac etkisi bu oranda zayiflar.
    """
    g = cfg.geometry
    masses: list[PointMass] = []

    # Plaka takimi (her zaman plakayla doner)
    if sc.plate_assembly_kg > 0.0:
        masses.append(
            PointMass(sc.plate_assembly_kg, frames.to_internal(cfg.mass.plate_com_cm))
        )

    # Kullanici AM'si: minder ustunden yukseklik + mafsala gore ileri/yan kayma
    cushion_top = float(
        cm_to_m(
            g.top_plate.underside_above_gimbal_cm
            + g.top_plate.thickness_cm
            + g.cushion.thickness_cm
        )
    )
    user_local = np.array(
        [sc.com_lateral_m, sc.com_fore_aft_m, cushion_top + sc.com_height_m]
    )

    m_carried = sc.user_kg * sc.carried_fraction
    if sc.backrest_mode == "tilting":
        masses.append(PointMass(m_carried, user_local))
        if sc.seat_kg > 0.0:
            masses.append(PointMass(sc.seat_kg, frames.to_internal(cfg.mass.seat_com_cm)))
    else:
        follow = float(np.clip(sc.backrest_follow_fraction, 0.0, 1.0))
        if m_carried * follow > 0.0:
            masses.append(PointMass(m_carried * follow, user_local))
        if m_carried * (1.0 - follow) > 0.0:
            masses.append(
                PointMass(m_carried * (1.0 - follow), user_local, rotating=False)
            )

    return masses


def _gravity_moment(
    mech: Mechanism, R: np.ndarray, masses: list[PointMass]
) -> tuple[np.ndarray, float]:
    """Yercekiminin mafsal etrafindaki momenti (3,) ve toplam hareketli kutle."""
    M = np.zeros(3)
    total = 0.0
    for pm in masses:
        arm = R @ pm.local if pm.rotating else pm.local
        M += np.cross(arm, pm.mass * _GRAVITY)
        total += pm.mass
    return M, total


def _free_axes(mech: Mechanism, pitch: float) -> np.ndarray:
    """Mafsalin moment TASIYAMADIGI iki eksen, (2, 3)."""
    return np.stack(
        [frames.pitch_axis(), frames.roll_axis(pitch, mech.outer_axis)]
    )


# --- Tek nokta cozumu -----------------------------------------------------------


def solve(
    mech: Mechanism, pose: Pose, scenario: MassScenario, *, stiffness: bool = True
) -> StaticResult:
    """Verilen poz ve senaryo icin statik cozum.

    Raises:
        ValueError: pose.reachable False ise
    """
    if not pose.reachable:
        raise ValueError(f"ulaşılamayan poz için yük çözülemez: {pose.reason.label_tr}")

    cfg = mech.cfg
    masses = _point_masses(cfg, scenario)
    M_g, total_mass = _gravity_moment(mech, pose.R, masses)
    axes = _free_axes(mech, pose.pitch)

    res = StaticResult(total_moving_mass_kg=total_mass)
    res.gravity_moment_nm = np.array([float(np.dot(M_g, ax)) for ax in axes])

    # --- Cubuk kuvvetleri: iki denklem, iki bilinmeyen
    # Cubuk plakayi +f * u ile iter (u = pimden plakaya). Serbest eksenlerde net
    # moment sifir olmali: A @ f = -(M_g izdusumu)
    A = np.zeros((2, 2))
    for k, ax in enumerate(axes):
        for side in (RIGHT, LEFT):
            lever = pose.attach[side] - mech.G
            A[k, side] = float(np.dot(np.cross(lever, pose.rod_unit[side]), ax))

    rhs = -res.gravity_moment_nm
    res.condition = float(np.linalg.cond(A))
    if res.condition > 1e4 or not np.isfinite(res.condition):
        # Kuvvet tekilligi: bir cubugun moment katkisi yok olmus. Bu pozda motor
        # plakayi tutamaz; sayisal sonuc anlamsiz olurdu.
        res.singular = True
        return res
    f = np.linalg.solve(A, rhs)
    res.rod_force_n = f

    # --- Mafsal tepkisi ve direk taban momenti
    weight = sum(pm.mass for pm in masses) * _GRAVITY
    rod_total = sum(f[s] * pose.rod_unit[s] for s in (RIGHT, LEFT))
    res.gimbal_reaction_n = -(weight + rod_total)

    base = np.array([0.0, 0.0, float(cm_to_m(cfg.geometry.base_plate.thickness_cm))])
    M_base = np.cross(mech.G - base, res.gimbal_reaction_n)
    res.gimbal_post_bending_nm = float(np.linalg.norm(M_base[:2]))
    res.gimbal_post_torsion_nm = float(abs(M_base[2]))

    # --- Motor torku: pime gelen tepki kuvvetinin mil ekseni etrafindaki momenti
    x_hat = np.array([1.0, 0.0, 0.0])
    torque = np.zeros(2)
    for side in (RIGHT, LEFT):
        crank_vec = pose.pin[side] - mech.S[side]
        force_on_pin = -f[side] * pose.rod_unit[side]
        torque[side] = float(np.dot(np.cross(crank_vec, force_on_pin), x_hat))
    res.motor_torque_nm = torque

    stall = cfg.motor.stall_torque_nm
    res.safety_factor = np.array(
        [stall / abs(t) if abs(t) > _EPS else np.inf for t in torque]
    )

    # --- Capraz dogrulama: sanal is (tamamen bagimsiz yol)
    try:
        J = mech.jacobian(pose.pitch, pose.roll)
        J_x = np.linalg.inv(J)  # d(pitch, roll) / d(theta)
        tau_vw = -J_x.T @ res.gravity_moment_nm
        res.cross_check_error = float(np.max(np.abs(tau_vw - torque)))
    except (ValueError, np.linalg.LinAlgError):
        res.cross_check_error = float("nan")

    # --- Yercekimi sertligi: d(moment)/d(aci), merkezi sonlu fark
    if stiffness:
        res.gravity_stiffness_nm_rad = _gravity_stiffness(mech, pose, masses)

    return res


def _gravity_stiffness(
    mech: Mechanism, pose: Pose, masses: list[PointMass]
) -> np.ndarray:
    """dM/dtheta, merkezi sonlu fark (adim 0,1 derece).

    POZITIF deger sistemin statik KARARSIZ oldugunu soyler: +yonde kucuk bir sapma,
    yine +yonde bir moment dogurur ve sapmayi buyutur. Notr pozda analitik deger
    W * h'tir (h = AM'nin mafsal ustundeki yuksekligi), yani AM mafsalin altinda
    olsaydi negatif (kararli sarkac) olurdu.
    """
    h = float(deg_to_rad(0.1))
    out = np.zeros(2)
    for k in range(2):
        vals = []
        for sign in (1.0, -1.0):
            p = pose.pitch + sign * h if k == 0 else pose.pitch
            r = pose.roll if k == 0 else pose.roll + sign * h
            R = frames.rotation(p, r, mech.outer_axis)
            M, _ = _gravity_moment(mech, R, masses)
            ax = _free_axes(mech, p)[k]
            vals.append(float(np.dot(M, ax)))
        out[k] = (vals[0] - vals[1]) / (2.0 * h)
    return out


# --- En kotu durum taramasi -----------------------------------------------------


def worst_case(
    mech: Mechanism,
    sweep: SweepSpec | None = None,
    *,
    check_collision: bool = True,
    progress=None,
) -> WorstCase:
    """Tum poz ve senaryo kombinasyonlarini tarayip en kotu durumu bulur.

    Poz toplama ve senaryo taramasi ayrilmistir: carpisma denetimi yalnizca izgara
    basina bir kez (senaryo basina degil) yapilir, bu yuzden acik olmasi pahali degil.

    KAPATMAYIN: carpisan pozlar mekanizmanin gercekte ulasamadigi yerlerdir ve
    oralarda kuvvet matrisi tekilleserek fizik disi torklar uretir.

    Args:
        check_collision: poz toplamada carpisma denetimi. Varsayilan ACIK.
        progress: 0..1 arasinda ilerleme bildiren cagrilabilir (arayuz icin)
    """
    spec = sweep or SweepSpec.from_config(mech.cfg)
    cfg = mech.cfg
    wc = WorstCase()

    scenarios = _build_scenarios(cfg, spec)
    wc.n_scenarios = len(scenarios)

    # Ulasilabilir pozlari bir kez topla
    poses: list[Pose] = []
    for r_deg in spec.roll_deg:
        for p_deg in spec.pitch_deg:
            pose = mech.ik(
                float(deg_to_rad(p_deg)),
                float(deg_to_rad(r_deg)),
                check_collision=check_collision,
            )
            if pose.ok:
                poses.append(pose)
    wc.n_poses = len(poses)

    if not poses:
        wc.verdict = "YETERSIZ"
        wc.explanation_tr = (
            "Taranan aralıkta uygun hiçbir poz bulunamadı — mekanizma bu hedeflere hiç "
            "ulaşamıyor. Önce çalışma alanı sorununu çözün (bkz. docs/FINDINGS.md)."
        )
        return wc

    total = len(poses)
    for idx, pose in enumerate(poses):
        for sc in scenarios:
            res = solve(mech, pose, sc, stiffness=False)
            if res.singular:
                continue
            t = res.worst_torque_nm
            if t > wc.max_motor_torque_nm:
                wc.max_motor_torque_nm = t
                wc.at_pitch_deg = float(rad_to_deg(pose.pitch))
                wc.at_roll_deg = float(rad_to_deg(pose.roll))
                wc.at_scenario = sc
            wc.min_safety_factor = min(wc.min_safety_factor, res.min_safety_factor)
            wc.max_rod_tension_n = max(
                wc.max_rod_tension_n, float(-np.min(res.rod_force_n))
            )
            wc.max_rod_compression_n = max(
                wc.max_rod_compression_n, float(np.max(res.rod_force_n))
            )
            wc.max_gimbal_force_n = max(
                wc.max_gimbal_force_n, float(np.linalg.norm(res.gimbal_reaction_n))
            )
            wc.max_gimbal_post_bending_nm = max(
                wc.max_gimbal_post_bending_nm, res.gimbal_post_bending_nm
            )
        if progress is not None:
            progress((idx + 1) / total)

    if wc.at_scenario is None:
        # Her poz/senaryo tekil cikti: hicbir cozum yok. min_safety_factor sonsuz
        # kaldigi icin _verdict bunu YETERLI sayar ve yesil gosterirdi.
        wc.verdict = "YETERSIZ"
        wc.min_safety_factor = 0.0
        wc.explanation_tr = (
            "Taranan hiçbir poz ve senaryo kombinasyonunda kuvvet denklemi "
            "çözülemedi — her konumda kuvvet matrisi tekil, yani bir çubuğun moment "
            "katkısı yok oluyor. Mekanizma bu geometriyle plakayı kontrol edemez. "
            "Önce çalışma alanı ve bağlantı noktası geometrisini düzeltin "
            "(bkz. docs/FINDINGS.md)."
        )
        return wc

    _verdict(wc, cfg)
    return wc


def _build_scenarios(cfg: SeatConfig, spec: SweepSpec) -> list[MassScenario]:
    """Senaryo kombinasyonlarini uretir (tekrarli olanlari ayiklar)."""
    out: list[MassScenario] = []
    for mass, fore, lat, height, mode in itertools.product(
        spec.user_kg,
        spec.com_fore_aft_cm,
        spec.com_lateral_cm,
        spec.com_height_cm,
        spec.backrest_modes,
    ):
        follows = spec.follow_fractions if mode == "fixed" else (1.0,)
        for follow in follows:
            out.append(
                MassScenario.from_config(
                    cfg,
                    user_kg=mass,
                    com_fore_aft_m=float(cm_to_m(fore)),
                    com_lateral_m=float(cm_to_m(lat)),
                    com_height_m=float(cm_to_m(height)),
                    backrest_mode=mode,
                    backrest_follow_fraction=follow,
                )
            )
    return out


def _verdict(wc: WorstCase, cfg: SeatConfig) -> None:
    """En kotu durumu sade Turkce yorumlar."""
    stall = cfg.motor.stall_torque_nm
    target = cfg.targets.torque_safety_factor
    sf = wc.min_safety_factor

    if sf >= target:
        wc.verdict = "YETERLI"
        head = (
            f"Motor en kötü durumda bile {sf:.2f} kat pay bırakıyor "
            f"(hedef en az {target:.1f})."
        )
    elif sf >= 1.5:
        wc.verdict = "SINIRDA"
        head = (
            f"Pay {sf:.2f} kat — hedef {target:.1f}. Çalışır ama ısınma ve yavaşlama "
            f"beklenir; ölçüm hatası bunu daha da aşağı çekebilir."
        )
    else:
        wc.verdict = "YETERSIZ"
        head = (
            f"Pay yalnızca {sf:.2f} kat — hedef {target:.1f}. Motor bu açıyı ya hiç "
            f"tutturamaz ya da çok yavaş ve ısınarak tutturur."
        )

    sc_txt = wc.at_scenario.describe_tr() if wc.at_scenario else "(senaryo yok)"
    wc.explanation_tr = (
        f"En kötü durum: {wc.max_motor_torque_nm:.1f} N·m tork gerekiyor, "
        f"tahmini kilitlenme torku {stall:.0f} N·m. {head}\n\n"
        f"Nerede: pitch {wc.at_pitch_deg:+.1f}°, roll {wc.at_roll_deg:+.1f}°\n"
        f"Hangi senaryoda: {sc_txt}\n\n"
        f"Not: {stall:.0f} N·m bir **TAHMİNDİR**. Gerçek değeri ölçmeden bu sonuç "
        f"kesinleşmez — ölçüm yöntemi docs/ASSUMPTIONS.md bölüm 1'de."
    )


# --- Tanim bolum 2.2 dogrulama senaryosu ----------------------------------------


def manual_check_scenario() -> MassScenario:
    """Tanim bolum 2.2'deki elle hesap senaryosu.

    90 kg tasinan kutle, AM mafsalin 5 cm onunde, plaka yatay, krank yatay,
    cubuklar dikey. Beklenen: mafsal momenti 44,1 N.m, cubuk basina 108 N,
    motor basina 4,3 N.m.
    """
    return MassScenario(
        user_kg=90.0,
        carried_fraction=1.0,
        plate_assembly_kg=0.0,
        backrest_mode="tilting",
        seat_kg=0.0,
        com_fore_aft_m=0.05,
        com_lateral_m=0.0,
        com_height_m=0.0,
    )
