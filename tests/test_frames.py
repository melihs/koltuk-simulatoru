"""Koordinat sistemi donusumu ve rotasyon isaret tanimlari.

Isaret hatalari bu projedeki en sinsi hata sinifidir: program calisir, sayi uretir, ama
koltuk ters yone egilir. Bu testler tanimi koda baglar.

Bkz. docs/tests/test_frames.md
"""

from __future__ import annotations

import numpy as np
import pytest

from seatsim import frames
from seatsim.units import deg_to_rad

RNG = np.random.default_rng(20260912)


# --- Donusum ---------------------------------------------------------------------


def test_roundtrip():
    for v in RNG.uniform(-50.0, 50.0, size=(100, 3)):
        back = frames.from_internal(frames.to_internal(v))
        assert np.allclose(back, v, atol=1e-12)


def test_axis_swap():
    # Kullanici (x=sag, y=yukari, z=ileri) cm -> ic (X=sag, Y=ileri, Z=yukari) m
    got = frames.to_internal([0.0, 13.0, 0.0])
    assert np.allclose(got, [0.0, 0.0, 0.13], atol=1e-12)

    got = frames.to_internal([18.2, -0.5, 20.5])
    assert np.allclose(got, [0.182, 0.205, -0.005], atol=1e-12)


def test_internal_is_right_handed():
    x = np.array([1.0, 0.0, 0.0])  # sag
    y = np.array([0.0, 1.0, 0.0])  # ileri
    z = np.array([0.0, 0.0, 1.0])  # yukari
    assert np.allclose(np.cross(x, y), z)


def test_user_frame_is_left_handed():
    """Kullanici sistemi neden donusturuluyor sorusunun cevabini kodda tutar.

    (sag, yukari, ileri) sirasi, (sag, ileri, yukari) sirasinin iki ekseni takas
    edilmis halidir -> determinant -1 -> sol el sistemi.
    """
    basis = np.zeros((3, 3))
    basis[:, 0] = [1.0, 0.0, 0.0]  # x = sag
    basis[:, 1] = [0.0, 0.0, 1.0]  # y = yukari  (ic sistemde Z)
    basis[:, 2] = [0.0, 1.0, 0.0]  # z = ileri   (ic sistemde Y)
    assert np.linalg.det(basis) == pytest.approx(-1.0)


# --- Rotasyon --------------------------------------------------------------------


@pytest.mark.parametrize("outer", ["pitch", "roll"])
def test_rotation_orthonormal(outer):
    for p, r in RNG.uniform(-0.4, 0.4, size=(50, 2)):
        R = frames.rotation(float(p), float(r), outer)
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
        assert np.linalg.det(R) == pytest.approx(1.0, abs=1e-12)


def test_zero_rotation_is_identity():
    assert np.allclose(frames.rotation(0.0, 0.0), np.eye(3), atol=1e-15)


def test_pitch_positive_lifts_front():
    forward = np.array([0.0, 1.0, 0.0])
    assert (frames.rotation(float(deg_to_rad(10)), 0.0) @ forward)[2] > 0.0


def test_pitch_negative_drops_front():
    forward = np.array([0.0, 1.0, 0.0])
    assert (frames.rotation(float(deg_to_rad(-10)), 0.0) @ forward)[2] < 0.0


def test_roll_positive_lifts_right():
    right = np.array([1.0, 0.0, 0.0])
    assert (frames.rotation(0.0, float(deg_to_rad(10))) @ right)[2] > 0.0


def test_roll_negative_drops_right():
    right = np.array([1.0, 0.0, 0.0])
    assert (frames.rotation(0.0, float(deg_to_rad(-10))) @ right)[2] < 0.0


def test_tilt_angle():
    R = frames.rotation(float(deg_to_rad(10)), 0.0)
    assert np.degrees(frames.tilt_angle(R)) == pytest.approx(10.0, abs=1e-9)

    R = frames.rotation(float(deg_to_rad(7)), float(deg_to_rad(7)))
    assert np.degrees(frames.tilt_angle(R)) == pytest.approx(9.9, abs=0.05)


def test_tilt_angle_zero_at_neutral():
    assert frames.tilt_angle(frames.rotation(0.0, 0.0)) == pytest.approx(0.0, abs=1e-15)


# --- Kardan mafsali eksen sirasi --------------------------------------------------


def test_outer_axis_matters():
    a = frames.rotation(float(deg_to_rad(15)), float(deg_to_rad(15)), "pitch")
    b = frames.rotation(float(deg_to_rad(15)), float(deg_to_rad(15)), "roll")
    assert np.max(np.abs(a - b)) > 1e-3


def _outer_axis_gap(angle_deg: float) -> float:
    a = frames.rotation(
        float(deg_to_rad(angle_deg)), float(deg_to_rad(angle_deg)), "pitch"
    )
    b = frames.rotation(
        float(deg_to_rad(angle_deg)), float(deg_to_rad(angle_deg)), "roll"
    )
    return float(np.max(np.abs(a - b)))


def test_outer_axis_difference_is_second_order():
    """Iki eksen sirasi IKINCI MERTEBEDEN uyusur: fark ~ sin(p)*sin(r).

    Keyfi bir tolerans yerine mertebesi olculur. 1 derecede fark sin^2(1) = 3,05e-4'tur;
    aci yarilandiginda fark dorde bolunur.
    """
    assert _outer_axis_gap(1.0) == pytest.approx(np.sin(deg_to_rad(1.0)) ** 2, rel=1e-9)

    gap1 = _outer_axis_gap(2.0)
    gap2 = _outer_axis_gap(1.0)
    assert gap1 / gap2 == pytest.approx(4.0, rel=0.01)


def test_invalid_outer_axis_raises():
    with pytest.raises(ValueError, match="outer_axis"):
        frames.rotation(0.0, 0.0, "yaw")
    with pytest.raises(ValueError, match="outer_axis"):
        frames.roll_axis(0.0, "yaw")
    with pytest.raises(ValueError, match="outer_axis"):
        frames.rotation_derivatives(0.0, 0.0, "yaw")


# --- Eksenler ve turevler ---------------------------------------------------------


def test_roll_axis_is_rotation_axis_of_positive_roll():
    """roll_axis(), pozitif roll'un SAG EL donme eksenini vermeli.

    R_roll(r) = exp(r [n]x) olacak sekilde n aranir. Pozitif roll _ry(-r) oldugu icin
    n = -Yhat'tir. Yanlis isaret, roll momentini ve yercekimi sertligini ters cevirir
    ve sanal is capraz dogrulamasini kirar.
    """
    r = 1e-6
    n = frames.roll_axis(0.0, "pitch")
    # Kucuk aci icin R ~ I + r [n]x ; [n]x matrisini geri okuyalim
    R = frames.rotation(0.0, r)
    skew = (R - np.eye(3)) / r
    recovered = np.array([skew[2, 1], skew[0, 2], skew[1, 0]])
    assert np.allclose(recovered, n, atol=1e-6), f"beklenen {n}, bulunan {recovered}"


def test_pitch_axis_is_rotation_axis_of_positive_pitch():
    p = 1e-6
    R = frames.rotation(p, 0.0)
    skew = (R - np.eye(3)) / p
    recovered = np.array([skew[2, 1], skew[0, 2], skew[1, 0]])
    assert np.allclose(recovered, frames.pitch_axis(), atol=1e-6)


def test_roll_axis_follows_pitch_when_outer_is_pitch():
    """Dis eksen pitch ise ic (roll) eksen pitch ile birlikte doner."""
    at_zero = frames.roll_axis(0.0, "pitch")
    tilted = frames.roll_axis(float(deg_to_rad(20)), "pitch")
    assert np.allclose(at_zero, [0.0, -1.0, 0.0])
    assert not np.allclose(tilted, at_zero)
    assert np.linalg.norm(tilted) == pytest.approx(1.0)


def test_roll_axis_fixed_when_outer_is_roll():
    for p in (0.0, 0.2, -0.3):
        assert np.allclose(frames.roll_axis(p, "roll"), [0.0, -1.0, 0.0])


@pytest.mark.parametrize("outer", ["pitch", "roll"])
def test_rotation_derivatives_match_finite_difference(outer):
    h = 1e-7
    for p, r in [(0.0, 0.0), (0.1, -0.05), (-0.2, 0.15)]:
        d_p, d_r = frames.rotation_derivatives(p, r, outer)
        num_p = (
            frames.rotation(p + h, r, outer) - frames.rotation(p - h, r, outer)
        ) / (2 * h)
        num_r = (
            frames.rotation(p, r + h, outer) - frames.rotation(p, r - h, outer)
        ) / (2 * h)
        assert np.allclose(d_p, num_p, atol=1e-6)
        assert np.allclose(d_r, num_r, atol=1e-6)


def test_plate_normal_is_up_at_neutral():
    assert np.allclose(frames.plate_normal(frames.rotation(0.0, 0.0)), [0.0, 0.0, 1.0])
