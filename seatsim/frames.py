"""Koordinat sistemi donusumu ve plaka rotasyon matrisleri.

Kullanicinin sistemi (x=sag, y=yukari, z=ileri) SOL EL sistemidir. Capraz carpim,
moment ve atalet tensoru hesaplarinda sessiz isaret hatasi uretir. Bu yuzden
cekirdek ic sistemde calisir: (X=sag, Y=ileri, Z=yukari), sag el, metre.

Donusum bir bilesen takasidir:  X = x,  Y = z,  Z = y   (ardindan cm -> m)

ISARET TANIMLARI
    pitch + = on yukari
    roll  + = sag taraf yukari

Bkz. docs/files/frames.md
"""

from __future__ import annotations

import numpy as np

from .units import cm_to_m, m_to_cm

# Kullanici sirasindan ic siraya gecis indisleri: (x, y, z) -> (x, z, y)
_USER_TO_INT = (0, 2, 1)


def to_internal(v_user) -> np.ndarray:
    """Kullanici vektoru (x=sag, y=yukari, z=ileri; cm) -> ic vektor (X, Y, Z; m)."""
    v = np.asarray(v_user, dtype=float)
    return cm_to_m(v[..., _USER_TO_INT])


def from_internal(v_int) -> np.ndarray:
    """Ic vektor (X=sag, Y=ileri, Z=yukari; m) -> kullanici vektoru (x, y, z; cm)."""
    v = np.asarray(v_int, dtype=float)
    # Takas kendisinin tersidir: (X, Y, Z) -> (X, Z, Y)
    return m_to_cm(v[..., _USER_TO_INT])


def pitch_axis() -> np.ndarray:
    """Pitch donme ekseni, ic sistemde. Tabana sabittir."""
    return np.array([1.0, 0.0, 0.0])


def _rx(angle: float) -> np.ndarray:
    """X ekseni (sag) etrafinda donme. Pitch ekseni."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _ry(angle: float) -> np.ndarray:
    """Y ekseni (ileri) etrafinda donme."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _drx(angle: float) -> np.ndarray:
    """d/dangle _rx(angle)."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[0.0, 0.0, 0.0], [0.0, -s, -c], [0.0, c, -s]])


def _dry(angle: float) -> np.ndarray:
    """d/dangle _ry(angle)."""
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[-s, 0.0, c], [0.0, 0.0, 0.0], [-c, 0.0, -s]])


def _roll_matrix(roll: float) -> np.ndarray:
    """Roll matrisi. _ry(-roll) secildi: boylece roll>0 sag tarafi YUKARI kaldirir."""
    return _ry(-roll)


def _droll_matrix(roll: float) -> np.ndarray:
    """d/droll _roll_matrix(roll)."""
    return -_dry(-roll)


def rotation(pitch: float, roll: float, outer_axis: str = "pitch") -> np.ndarray:
    """Plaka rotasyon matrisi, ic sistemde.

    Kardan mafsali iki ardisik eksendir: dis halka tabana sabit bir eksende, ic halka
    dis halkanin tasidigi eksende doner. Dis eksenin matrisi SOLDA durur.

    Args:
        pitch: radyan, + = on yukari
        roll: radyan, + = sag taraf yukari
        outer_axis: "pitch" (varsayilan) veya "roll" -- tabana bagli eksen

    Raises:
        ValueError: outer_axis gecersizse
    """
    if outer_axis == "pitch":
        return _rx(pitch) @ _roll_matrix(roll)
    if outer_axis == "roll":
        return _roll_matrix(roll) @ _rx(pitch)
    raise ValueError(f"geçersiz outer_axis: {outer_axis!r} ('pitch' veya 'roll' olmalı)")


def rotation_derivatives(
    pitch: float, roll: float, outer_axis: str = "pitch"
) -> tuple[np.ndarray, np.ndarray]:
    """(dR/dpitch, dR/droll) -- Jacobian'in analitik turevi icin.

    Raises:
        ValueError: outer_axis gecersizse
    """
    if outer_axis == "pitch":
        d_pitch = _drx(pitch) @ _roll_matrix(roll)
        d_roll = _rx(pitch) @ _droll_matrix(roll)
    elif outer_axis == "roll":
        d_pitch = _roll_matrix(roll) @ _drx(pitch)
        d_roll = _droll_matrix(roll) @ _rx(pitch)
    else:
        raise ValueError(f"geçersiz outer_axis: {outer_axis!r}")
    return d_pitch, d_roll


def roll_axis(pitch: float, outer_axis: str = "pitch") -> np.ndarray:
    """Roll donme ekseni, ic sistemde.

    DIKKAT -- ISARET: Pozitif roll, _roll_matrix(r) = _ry(-r) olarak tanimlidir, yani
    +r kadar SAG EL donusu `-Yhat` ekseni etrafindadir. Dolayisiyla roll'e es bir
    genellestirilmis moment `M . (-Yhat)` ile elde edilir, `M . (+Yhat)` ile degil.

    Bu fonksiyon `-Yhat`i (gerekiyorsa pitch ile dondurulmus halini) dondurur. `+Yhat`
    dondurmek, roll etrafindaki momenti ve yercekimi sertligini TERS ISARETLI yapar;
    cubuk kuvvetleri etkilenmez (denklemin iki tarafi da isaret degistirir) ama sanal
    is capraz dogrulamasi kirilir.

    Dis eksen pitch ise roll ekseni pitch ile birlikte doner (ic halka dis halkanin
    uzerinde tasinir). Dis eksen roll ise tabana sabittir.
    """
    axis = np.array([0.0, -1.0, 0.0])
    if outer_axis == "pitch":
        return _rx(pitch) @ axis
    if outer_axis == "roll":
        return axis
    raise ValueError(f"geçersiz outer_axis: {outer_axis!r}")


def plate_normal(R: np.ndarray) -> np.ndarray:
    """Plakanin yukari normali: R @ Zhat."""
    return R[:, 2]


def tilt_angle(R: np.ndarray) -> float:
    """Toplam egim: plaka normali ile dusey arasindaki aci (radyan)."""
    return float(np.arccos(np.clip(R[2, 2], -1.0, 1.0)))
