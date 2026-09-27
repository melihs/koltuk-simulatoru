"""Olcek donusumleri: arayuz birimleri (cm, derece) <-> cekirdek birimleri (m, radyan).

Mimarinin "TEK DONUSUM NOKTASI" dedigi modul budur: projede cm/m veya derece/radyan
cevrimi YALNIZCA burada (ve eksen sirasi da degistiren frames.py icinde) yapilir.

Cekirdek modullerin icinde ciplak `* 0.01`, `/ 100`, `math.radians` veya `np.radians`
GORULMEZ; bunun yerine buradaki fonksiyonlar cagrilir. Yani cekirdek moduller bu modulu
import EDER -- etmemeleri gerektigi anlamina gelmez. Kural, donusumun dagilmamasidir.

Bkz. docs/files/units.md, docs/ARCHITECTURE.md (birim politikasi)
"""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
from numpy.typing import ArrayLike

CM_PER_M = 100.0
G = 9.81  # m/s^2, yercekimi ivmesi

_RPM_TO_RAD_S = 2.0 * np.pi / 60.0

Scalar: TypeAlias = np.floating | np.ndarray
"""Donusum fonksiyonlarinin cikisi: skaler girdide 0-boyutlu, dizi girdide dizi."""


def cm_to_m(value: ArrayLike) -> Scalar:
    """cm -> m."""
    return np.asarray(value, dtype=float) / CM_PER_M


def m_to_cm(value: ArrayLike) -> Scalar:
    """m -> cm."""
    return np.asarray(value, dtype=float) * CM_PER_M


def deg_to_rad(value: ArrayLike) -> Scalar:
    """derece -> radyan."""
    return np.radians(np.asarray(value, dtype=float))


def rad_to_deg(value: ArrayLike) -> Scalar:
    """radyan -> derece."""
    return np.degrees(np.asarray(value, dtype=float))


def rpm_to_rad_s(value: ArrayLike) -> Scalar:
    """dev/dk -> rad/s."""
    return np.asarray(value, dtype=float) * _RPM_TO_RAD_S


def rad_s_to_rpm(value: ArrayLike) -> Scalar:
    """rad/s -> dev/dk."""
    return np.asarray(value, dtype=float) / _RPM_TO_RAD_S
