"""Mekanizmanin fiziksel parcalarini basit disbukey hacimlere (kutu, kapsul) cevirir.

Ayni hacimler hem carpisma kontrolunde hem 3D gorunumde kullanilir -- tek kaynaktan
uretildikleri icin ekranda gorunen ile hesaplanan AYNI geometridir.

Bu modul renk bilmez; renklendirme arayuz katmaninin isidir.

Bkz. docs/files/bodies.md
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import frames
from .config import SeatConfig
from .units import cm_to_m

_I3 = np.eye(3)


@dataclass
class Box:
    """Yonlendirilmis kutu (OBB). center ve half metre, R yonelim."""

    center: np.ndarray
    half: np.ndarray
    R: np.ndarray = field(default_factory=lambda: _I3.copy())

    def corners(self) -> np.ndarray:
        """8 kose, dunya cercevesi. (8, 3)"""
        signs = np.array(
            [
                [sx, sy, sz]
                for sx in (-1.0, 1.0)
                for sy in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ]
        )
        return self.center + (signs * self.half) @ self.R.T

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        c = self.corners()
        return c.min(axis=0), c.max(axis=0)


@dataclass
class Capsule:
    """Dogru parcasi + yaricap. p0, p1, radius metre."""

    p0: np.ndarray
    p1: np.ndarray
    radius: float

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        lo = np.minimum(self.p0, self.p1) - self.radius
        hi = np.maximum(self.p0, self.p1) + self.radius
        return lo, hi


@dataclass
class Body:
    """Adlandirilmis bir parca ve onu olusturan disbukey hacimler."""

    name: str
    label_tr: str
    group: str  # "static" | "moving" | "linkage"
    primitives: list[Box | Capsule]
    collidable: bool = True

    def aabb(self) -> tuple[np.ndarray, np.ndarray]:
        los, his = zip(*(p.aabb() for p in self.primitives), strict=True)
        return np.min(los, axis=0), np.max(his, axis=0)


def _plate_box(
    size_cm: list[float], thickness_cm: float, center: np.ndarray, R: np.ndarray
) -> Box:
    """Yatay plaka: size_cm = [genislik(x), derinlik(z)], kalinlik dusey."""
    half = np.array(
        [
            cm_to_m(size_cm[0]) / 2.0,
            cm_to_m(size_cm[1]) / 2.0,
            cm_to_m(thickness_cm) / 2.0,
        ]
    )
    return Box(center=center, half=half, R=R)


def build(cfg: SeatConfig, pose) -> list[Body]:
    """Verilen poz icin tum govdeleri uretir.

    Raises:
        ValueError: pose.reachable False ise
    """
    if not pose.reachable:
        raise ValueError(
            f"ulaşılamayan poz için gövde üretilemez: {pose.reason.label_tr}"
        )

    g = cfg.geometry
    hw = cfg.hardware
    R = pose.R
    G = frames.to_internal(g.gimbal.position_cm)
    bodies: list[Body] = []

    # --- Alt plaka: taban, y=0'dan kalinligi kadar yukari
    base_t = cm_to_m(g.base_plate.thickness_cm)
    base_center = np.array(
        [0.0, cm_to_m(g.base_plate.center_z_cm), base_t / 2.0]
    )
    bodies.append(
        Body(
            "base_plate",
            "Alt plaka",
            "static",
            [_plate_box(g.base_plate.size_cm, g.base_plate.thickness_cm, base_center, _I3)],
        )
    )

    # --- Mafsal diregi: alt plakanin ustunden mafsal merkezine
    post_base = np.array([0.0, 0.0, float(base_t)])
    bodies.append(
        Body(
            "gimbal_post",
            "Mafsal direği",
            "static",
            [
                Capsule(
                    p0=post_base,
                    p1=G,
                    radius=float(cm_to_m(hw.gimbal_post_diameter_cm)) / 2.0,
                )
            ],
        )
    )

    # --- Ust plaka: alt yuzeyi mafsalin uzerinde, plaka cercevesinde kayik
    plate_t = cm_to_m(g.top_plate.thickness_cm)
    plate_local = np.array(
        [
            0.0,
            float(cm_to_m(g.top_plate.center_offset_z_cm)),
            float(cm_to_m(g.top_plate.underside_above_gimbal_cm) + plate_t / 2.0),
        ]
    )
    bodies.append(
        Body(
            "top_plate",
            "Üst plaka",
            "moving",
            [
                _plate_box(
                    g.top_plate.size_cm, g.top_plate.thickness_cm, G + R @ plate_local, R
                )
            ],
        )
    )

    # --- Minder: plakanin ustunde
    cush_t = cm_to_m(g.cushion.thickness_cm)
    cush_local = np.array(
        [
            0.0,
            float(cm_to_m(g.top_plate.center_offset_z_cm)),
            float(
                cm_to_m(g.top_plate.underside_above_gimbal_cm)
                + plate_t
                + cush_t / 2.0
            ),
        ]
    )
    bodies.append(
        Body(
            "cushion",
            "Minder",
            "moving",
            [_plate_box(g.cushion.size_cm, g.cushion.thickness_cm, G + R @ cush_local, R)],
        )
    )

    # --- Krank ve cubuk (her iki taraf)
    crank_r = float(cm_to_m(g.crank.thickness_cm)) / 2.0
    rod_r = float(cm_to_m(g.rod.diameter_cm)) / 2.0
    shaft = np.asarray(g.motor_shaft_cm, dtype=float)
    for side, tag, tr in ((0, "right", "Sağ"), (1, "left", "Sol")):
        S = frames.to_internal(shaft * ([1.0, 1.0, 1.0] if side == 0 else [-1.0, 1.0, 1.0]))
        bodies.append(
            Body(
                f"crank_{tag}",
                f"{tr} krank",
                "linkage",
                [Capsule(p0=S, p1=pose.pin[side], radius=crank_r)],
            )
        )
        bodies.append(
            Body(
                f"rod_{tag}",
                f"{tr} itme çubuğu",
                "linkage",
                [Capsule(p0=pose.pin[side], p1=pose.attach[side], radius=rod_r)],
            )
        )

        # Mil ekseni (x) boyunca yerlesim. Krank, reduktor kutusunun DISINDA doner:
        # kutunun dis yuzu krank duzleminden shaft_protrusion_cm kadar iceride.
        # Kutuyu mil noktasina ortalamak, kranki kutunun icinde dondurur.
        outward = 1.0 if side == 0 else -1.0
        gb = np.asarray(hw.gearbox_box_cm, dtype=float)
        gb_half = cm_to_m(gb) / 2.0
        protrusion = float(cm_to_m(hw.shaft_protrusion_cm))
        gb_center_x = S[0] - outward * (protrusion + gb_half[0])

        bodies.append(
            Body(
                f"gearbox_{tag}",
                f"{tr} redüktör kutusu",
                "static",
                [
                    Box(
                        center=np.array([gb_center_x, S[1], S[2]]),
                        half=gb_half,
                        R=_I3.copy(),
                    )
                ],
            )
        )

        # Motor silindiri: kutunun arka yuzunden ARKAYA (-Y), kutunun x merkezinde
        motor_len = float(cm_to_m(hw.motor_cylinder_length_cm))
        m0 = np.array([gb_center_x, S[1] - gb_half[1], S[2]])
        m1 = m0 + np.array([0.0, -motor_len, 0.0])
        bodies.append(
            Body(
                f"motor_{tag}",
                f"{tr} motor gövdesi",
                "static",
                [
                    Capsule(
                        p0=m0,
                        p1=m1,
                        radius=float(cm_to_m(hw.motor_cylinder_diameter_cm)) / 2.0,
                    )
                ],
            )
        )

        # Pot braketi: krank duzleminin DISINDA, mil uzantisinin ucunda
        pb = cm_to_m(np.asarray(hw.pot_bracket_cm, dtype=float))
        pot_x = S[0] + outward * (float(cm_to_m(hw.pot_offset_cm)) + pb[0] / 2.0)
        bodies.append(
            Body(
                f"pot_{tag}",
                f"{tr} pot braketi",
                "static",
                [
                    Box(
                        center=np.array([pot_x, S[1], S[2]]),
                        half=pb / 2.0,
                        R=_I3.copy(),
                    )
                ],
            )
        )

    # --- Takozlar
    stop_size = cm_to_m(np.asarray(cfg.stops.size_cm, dtype=float))
    stop_tops = cfg.stops.heights()
    for idx, (sx, sz) in enumerate(cfg.stops.positions_cm):
        pos = frames.to_internal([sx, 0.0, sz])
        height = float(cm_to_m(stop_tops[idx])) - float(base_t)
        if height <= 0:
            continue
        center = np.array([pos[0], pos[1], float(base_t) + height / 2.0])
        half = np.array([stop_size[0] / 2.0, stop_size[1] / 2.0, height / 2.0])
        bodies.append(
            Body(
                f"stop_{idx}",
                f"Takoz {idx + 1}",
                "static",
                [Box(center=center, half=half, R=_I3.copy())],
            )
        )

    # --- Kullanici govdesi: atalet ve gorsel icin; carpismaya katilmaz.
    #     Kutu, kutle modelinin kullandigi AM noktasina ORTALANIR -- boylece ekranda
    #     gorunen kutu ile yuk hesabindaki agirlik merkezi ayni yerdedir.
    user_half = cm_to_m(np.asarray(hw.user_box_cm, dtype=float)) / 2.0
    cushion_top_local = float(
        cm_to_m(g.top_plate.underside_above_gimbal_cm) + plate_t + cush_t
    )
    user_local = np.array(
        [
            float(cm_to_m(cfg.mass.user_com_lateral_cm)),
            float(cm_to_m(cfg.mass.user_com_fore_aft_cm)),
            cushion_top_local + float(cm_to_m(cfg.mass.user_com_height_cm)),
        ]
    )
    bodies.append(
        Body(
            "user_body",
            "Kullanıcı (atalet kutusu)",
            "moving",
            [Box(center=G + R @ user_local, half=user_half, R=R)],
            collidable=False,
        )
    )

    return bodies
