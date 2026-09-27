"""Ters/ileri kinematik, Jacobian, simetri, limitler ve dal sabitligi.

Bkz. docs/tests/test_geometry.md
"""

from __future__ import annotations

import numpy as np
import pytest

from seatsim import loads
from seatsim.geometry import LEFT, RIGHT, LimitReason, Mechanism
from seatsim.units import cm_to_m, deg_to_rad

from .conftest import grid_poses, reachable, scan_limit, usable

RNG = np.random.default_rng(20260912)


# --- Temel dogruluk --------------------------------------------------------------


def test_neutral_cranks_are_zero(mech_nocol):
    assert np.allclose(mech_nocol.ik(0.0, 0.0).theta, 0.0, atol=1e-9)


def test_neutral_rod_length(mech_nocol, cfg):
    pose = mech_nocol.ik(0.0, 0.0)
    expected = float(cm_to_m(cfg.geometry.rod.length_cm))
    for s in (RIGHT, LEFT):
        span = np.linalg.norm(pose.attach[s] - pose.pin[s])
        assert span == pytest.approx(expected, abs=1e-12)


def test_neutral_rod_is_vertical(mech_nocol):
    pose = mech_nocol.ik(0.0, 0.0)
    for s in (RIGHT, LEFT):
        assert np.allclose(pose.rod_unit[s], [0.0, 0.0, 1.0], atol=1e-9)


def test_neutral_crank_is_horizontal(mech_nocol):
    """Notrde pim, mil merkezinin tam arkasinda (-Y yonunde)."""
    pose = mech_nocol.ik(0.0, 0.0)
    for s in (RIGHT, LEFT):
        offset = pose.pin[s] - mech_nocol.S[s]
        assert offset[0] == pytest.approx(0.0, abs=1e-12)
        assert offset[1] == pytest.approx(-mech_nocol.R_crank, abs=1e-12)
        assert offset[2] == pytest.approx(0.0, abs=1e-12)


def test_neutral_transmission_is_90(mech_nocol):
    assert np.allclose(mech_nocol.ik(0.0, 0.0).transmission_deg, 90.0, atol=1e-6)


# --- Simetri ---------------------------------------------------------------------


def test_pure_pitch_cranks_equal(mech_nocol):
    for d in np.linspace(-8.0, 8.0, 15):
        pose = mech_nocol.ik(float(deg_to_rad(d)), 0.0)
        assert pose.reachable
        assert pose.theta[RIGHT] == pytest.approx(pose.theta[LEFT], abs=1e-12)


def test_pure_roll_cranks_opposite_sign(mech_nocol):
    for d in np.linspace(0.5, 9.0, 15):
        pose = mech_nocol.ik(0.0, float(deg_to_rad(d)))
        assert pose.reachable
        assert pose.theta[RIGHT] * pose.theta[LEFT] < 0.0, f"roll={d}"


def test_roll_mirror_symmetry(mech_nocol):
    """Sag/sol aynalama TAM tutar: ik(0, +r).theta == ik(0, -r).theta[::-1]."""
    for d in np.linspace(0.5, 9.0, 10):
        plus = mech_nocol.ik(0.0, float(deg_to_rad(d))).theta
        minus = mech_nocol.ik(0.0, float(deg_to_rad(-d))).theta
        assert np.allclose(plus, minus[::-1], atol=1e-12), f"roll={d}"


def test_roll_antisymmetric_on_centre_plane(mech_nocol):
    """roll=0 duzleminde Jacobian'in roll kolonu TAM antisimetriktir.

    Bu, "iki krank zit yone doner" ifadesinin kesin halidir ve yalnizca notrde degil,
    roll=0 olan HER pitch degerinde tutar -- cunku geometri x=0 duzlemine gore
    simetriktir. roll != 0'da mekanizmanin dogrusal olmayisi devreye girer ve
    antisimetri bozulur (bkz. test_roll_antisymmetry_breaks_off_centre).
    """
    for p_deg in (-6.0, -3.0, 0.0, 3.0, 6.0, 8.0):
        J = mech_nocol.jacobian(float(deg_to_rad(p_deg)), 0.0)
        assert J[0, 1] == pytest.approx(-J[1, 1], abs=1e-12), f"pitch={p_deg}"
        assert J[0, 0] == pytest.approx(J[1, 0], abs=1e-12), f"pitch={p_deg}"


def test_roll_antisymmetry_breaks_off_centre(mech_nocol):
    """roll != 0'da antisimetri bozulur -- bu bir hata degil, mekanizmanin dogasi.

    Testin amaci: yukaridaki ozdesligin nerede GECERLI OLMADIGINI da sabitlemek,
    boylece ileride yanlis yere genellenmesin.
    """
    J = mech_nocol.jacobian(0.0, float(deg_to_rad(6.0)))
    assert J[0, 1] != pytest.approx(-J[1, 1], abs=1e-3)


def test_roll_magnitudes_converge_at_small_angle(mech_nocol):
    theta = mech_nocol.ik(0.0, float(deg_to_rad(1.0))).theta
    a, b = abs(theta[RIGHT]), abs(theta[LEFT])
    assert abs(a - b) / max(a, b) < 0.005


def test_roll_magnitudes_diverge_at_large_angle(mech_nocol):
    """Buyuk acida buyuklukler ayrisir -- mekanizmanin dogrusal olmayisi, hata degil."""
    theta = mech_nocol.ik(0.0, float(deg_to_rad(8.0))).theta
    a, b = abs(theta[RIGHT]), abs(theta[LEFT])
    assert 0.03 < abs(a - b) / max(a, b) < 0.15


# --- FK <-> IK -------------------------------------------------------------------


def test_fk_at_neutral(mech_nocol):
    p, r = mech_nocol.fk(np.zeros(2))
    assert p == pytest.approx(0.0, abs=1e-9)
    assert r == pytest.approx(0.0, abs=1e-9)


def test_fk_inverts_ik(mech_nocol):
    ok = 0
    for p_deg, r_deg in RNG.uniform(-8.0, 8.0, size=(200, 2)):
        pose = mech_nocol.ik(float(deg_to_rad(p_deg)), float(deg_to_rad(r_deg)))
        if not pose.reachable:
            continue
        ok += 1
        p_back, r_back = mech_nocol.fk(
            pose.theta, seed=[deg_to_rad(p_deg), deg_to_rad(r_deg)]
        )
        assert np.degrees(p_back) == pytest.approx(p_deg, abs=1e-6)
        assert np.degrees(r_back) == pytest.approx(r_deg, abs=1e-6)
    assert ok > 100, "yeterli ulasilabilir ornek yok"


def test_fk_seed_independence(mech_nocol):
    target = (float(deg_to_rad(4.0)), float(deg_to_rad(3.0)))
    theta = mech_nocol.ik(*target).theta
    a = mech_nocol.fk(theta, seed=[0.0, 0.0])
    b = mech_nocol.fk(theta, seed=[deg_to_rad(6), deg_to_rad(5)])
    assert np.allclose(a, b, atol=1e-8)


# --- Jacobian --------------------------------------------------------------------


def test_jacobian_matches_finite_difference(mech_nocol):
    h = 1e-6
    n = 0
    for p_deg, r_deg in RNG.uniform(-7.0, 7.0, size=(50, 2)):
        p, r = float(deg_to_rad(p_deg)), float(deg_to_rad(r_deg))
        if not mech_nocol.ik(p, r).reachable:
            continue
        n += 1
        J = mech_nocol.jacobian(p, r)
        num = np.zeros((2, 2))
        num[:, 0] = (mech_nocol.ik(p + h, r).theta - mech_nocol.ik(p - h, r).theta) / (2 * h)
        num[:, 1] = (mech_nocol.ik(p, r + h).theta - mech_nocol.ik(p, r - h).theta) / (2 * h)
        assert np.max(np.abs(J - num)) < 1e-5
    assert n > 20


def test_jacobian_at_neutral_is_diagonal_pattern(mech_nocol):
    J = mech_nocol.jacobian(0.0, 0.0)
    assert J[0, 0] == pytest.approx(J[1, 0], abs=1e-12)  # pitch simetrik
    assert J[0, 1] == pytest.approx(-J[1, 1], abs=1e-12)  # roll antisimetrik


def test_jacobian_ratio_at_neutral(mech_nocol, cfg):
    expected = cfg.geometry.rod_attach_cm[2] / cfg.geometry.crank.length_cm
    assert mech_nocol.jacobian(0.0, 0.0)[0, 0] == pytest.approx(expected, rel=0.02)


def test_det_jacobian_nonzero_in_workspace(mech_nocol):
    for p_deg, r_deg in RNG.uniform(-7.0, 7.0, size=(40, 2)):
        p, r = float(deg_to_rad(p_deg)), float(deg_to_rad(r_deg))
        if not mech_nocol.ik(p, r).reachable:
            continue
        assert abs(np.linalg.det(mech_nocol.jacobian(p, r))) > 1e-6


# --- Limit siniflandirmasi -------------------------------------------------------


def test_unreachable_returns_reason(mech_nocol):
    pose = mech_nocol.ik(float(deg_to_rad(20.0)), 0.0)
    assert not pose.reachable
    assert pose.reason in (
        LimitReason.UNREACHABLE_CIRCLE,
        LimitReason.UNREACHABLE_ROD,
    )


def test_gimbal_limit_triggers(fresh_cfg):
    fresh_cfg.limits.gimbal_max_deg = 3.0
    m = Mechanism.from_config(fresh_cfg, check_collision=False)
    assert m.ik(float(deg_to_rad(5.0)), 0.0).reason is LimitReason.GIMBAL_ANGLE


def test_pot_range_triggers(fresh_cfg):
    fresh_cfg.limits.pot.mechanical_range_deg = 20.0  # +-10 derece
    fresh_cfg.limits.gimbal_max_deg = 90.0
    m = Mechanism.from_config(fresh_cfg, check_collision=False)
    assert m.ik(float(deg_to_rad(5.0)), 0.0).reason is LimitReason.POT_RANGE


def test_deadpoint_margin_triggers(fresh_cfg):
    fresh_cfg.limits.deadpoint_margin_deg = 89.0
    m = Mechanism.from_config(fresh_cfg, check_collision=False)
    assert m.ik(float(deg_to_rad(5.0)), 0.0).reason is LimitReason.DEAD_POINT


def test_reason_priority(fresh_cfg):
    """Birden fazla limit asilirsa oncelik sirasi korunur: olu nokta pot'tan once."""
    fresh_cfg.limits.deadpoint_margin_deg = 89.0
    fresh_cfg.limits.pot.mechanical_range_deg = 20.0
    m = Mechanism.from_config(fresh_cfg, check_collision=False)
    assert m.ik(float(deg_to_rad(5.0)), 0.0).reason is LimitReason.DEAD_POINT


def test_rod_end_misalign_zero_in_pure_pitch(mech_nocol):
    """Saf pitch'te cubuk YZ duzleminde kalir -> sapma sifir."""
    for d in (2.0, 5.0, 8.0):
        pose = mech_nocol.ik(float(deg_to_rad(d)), 0.0)
        assert np.max(pose.rod_end_misalign_deg) < 1e-9


def test_rod_end_misalign_grows_with_roll(mech_nocol):
    prev = -1.0
    for d in (1.0, 3.0, 5.0, 7.0, 8.5):
        pose = mech_nocol.ik(0.0, float(deg_to_rad(d)))
        assert pose.reachable
        cur = float(np.max(pose.rod_end_misalign_deg))
        assert cur > prev
        prev = cur


# --- Dal sabitligi ---------------------------------------------------------------


def test_branch_sign_resolved_from_neutral(mech_nocol):
    assert mech_nocol.branch_sign.shape == (2,)
    assert set(np.abs(mech_nocol.branch_sign)) == {1.0}
    assert np.allclose(mech_nocol.ik(0.0, 0.0).theta, 0.0, atol=1e-9)


def test_ik_is_order_independent(mech_nocol):
    """Izgarayi ileri ve geri taramak birebir ayni theta verir."""
    angles = [float(deg_to_rad(d)) for d in np.linspace(-8.0, 8.0, 25)]
    forward = {a: mech_nocol.ik(a, 0.0).theta.copy() for a in angles}
    backward = {a: mech_nocol.ik(a, 0.0).theta.copy() for a in reversed(angles)}
    for a in angles:
        assert np.array_equal(forward[a], backward[a])


def test_ik_matches_single_call(mech_nocol):
    """Izgara taramasindaki her dugum, tek basina cagrildiginda ayni sonucu verir."""
    for r in np.linspace(-8.0, 8.0, 9):
        for p in np.linspace(-8.0, 8.0, 9):
            pr, rr = float(deg_to_rad(p)), float(deg_to_rad(r))
            a = mech_nocol.ik(pr, rr)
            b = Mechanism.from_config(mech_nocol.cfg, check_collision=False).ik(pr, rr)
            assert np.array_equal(a.theta, b.theta)


def test_branch_continuity(mech_nocol):
    prev = None
    for d in np.arange(0.0, 8.1, 0.2):
        pose = mech_nocol.ik(float(deg_to_rad(d)), 0.0)
        if not pose.reachable:
            break
        if prev is not None:
            assert np.max(np.abs(np.degrees(pose.theta - prev))) < 5.0
        prev = pose.theta


def test_no_absurd_torque_over_grid(mech):
    """Aynalanmis dal 9600 N.m uretiyordu; sabit dal ile tork makul kalir."""
    scenarios = [
        loads.MassScenario.from_config(mech.cfg, user_kg=kg, com_fore_aft_m=0.08)
        for kg in (60.0, 120.0)
    ]
    n = 0
    for pose in grid_poses(mech, n=15):
        for sc in scenarios:
            res = loads.solve(mech, pose, sc, stiffness=False)
            if res.singular:
                continue
            n += 1
            assert res.worst_torque_nm < 100.0, (
                f"pitch={np.degrees(pose.pitch):.1f} roll={np.degrees(pose.roll):.1f} "
                f"-> {res.worst_torque_nm:.1f} N.m"
            )
    assert n > 50


# --- Takozlar --------------------------------------------------------------------


def test_suggest_stop_heights_round_trip(fresh_cfg):
    m = Mechanism.from_config(fresh_cfg, check_collision=False)
    fresh_cfg.stops.top_height_cm = m.suggest_stop_heights_cm(12.0)
    m2 = Mechanism.from_config(fresh_cfg, check_collision=False)
    for s in m2.stop_engagement_deg():
        assert s["engages_at_deg"] == pytest.approx(12.0, abs=0.1), s


def test_stop_engagement_changes_with_position(fresh_cfg):
    base = Mechanism.from_config(fresh_cfg, check_collision=False)
    before = [s["engages_at_deg"] for s in base.stop_engagement_deg()]

    fresh_cfg.stops.positions_cm = [[p[0] * 0.5, p[1] * 0.5] for p in fresh_cfg.stops.positions_cm]
    after = [
        s["engages_at_deg"]
        for s in Mechanism.from_config(fresh_cfg, check_collision=False).stop_engagement_deg()
    ]
    assert before != after, "takoz konumu degisti ama devreye girme acisi degismedi"


def test_stop_heights_scalar_expands(fresh_cfg):
    fresh_cfg.stops.top_height_cm = 9.0
    assert fresh_cfg.stops.heights() == [9.0] * len(fresh_cfg.stops.positions_cm)


def test_stop_heights_length_mismatch_raises(fresh_cfg):
    fresh_cfg.stops.top_height_cm = [9.0, 9.0]
    with pytest.raises(ValueError, match="takoz"):
        fresh_cfg.stops.heights()


def test_mech_stop_triggers(fresh_cfg):
    """Takozlari cok yukari alirsak MECH_STOP kucuk acida devreye girer."""
    fresh_cfg.stops.top_height_cm = 14.0
    m = Mechanism.from_config(fresh_cfg, check_collision=False)
    assert m.ik(float(deg_to_rad(3.0)), float(deg_to_rad(3.0))).reason is LimitReason.MECH_STOP


# --- Regresyon: baslangic geometrisinin bilinen sinirlari ------------------------
# docs/FINDINGS.md A1'i koda baglar. Geometri degisirse KASITLI olarak kirilirlar.


def test_regression_raw_reach_pitch(mech_nocol):
    assert scan_limit(mech_nocol, 0, 1.0, reachable) == pytest.approx(8.5, abs=0.2)
    assert scan_limit(mech_nocol, 0, -1.0, reachable) == pytest.approx(-33.2, abs=0.3)


def test_regression_raw_reach_roll(mech_nocol):
    assert scan_limit(mech_nocol, 1, 1.0, reachable) == pytest.approx(9.8, abs=0.2)
    assert scan_limit(mech_nocol, 1, -1.0, reachable) == pytest.approx(-9.8, abs=0.2)


def test_regression_limited_pitch(mech_nocol):
    """Parca limitleri dahil, carpisma haric."""
    assert scan_limit(mech_nocol, 0, 1.0, usable) == pytest.approx(8.1, abs=0.2)
    assert scan_limit(mech_nocol, 0, -1.0, usable) == pytest.approx(-15.5, abs=0.2)


def test_regression_full_pitch(mech):
    assert mech.max_pitch_deg()[0] == pytest.approx(8.1, abs=0.2)
    assert mech.max_pitch_deg()[1] == pytest.approx(-8.3, abs=0.2)


def test_regression_full_roll(mech):
    up, down = mech.max_roll_deg()
    assert up == pytest.approx(9.0, abs=0.2)
    assert down == pytest.approx(-9.0, abs=0.2)


def test_regression_binding_reasons(mech):
    """Siniri hangi limitin bagladigi tasarim kararini degistirir."""
    assert mech.ik(float(deg_to_rad(8.3)), 0.0).reason is LimitReason.DEAD_POINT
    assert mech.ik(float(deg_to_rad(-8.6)), 0.0).reason is LimitReason.COLLISION
    assert mech.ik(0.0, float(deg_to_rad(9.3))).reason is LimitReason.ROD_END_ANGLE


def test_regression_pitch_10_unreachable(mech):
    assert not mech.is_reachable(10.0, 0.0)
    assert not mech.is_reachable(-10.0, 0.0)


def test_regression_roll_10_unreachable(mech):
    assert not mech.is_reachable(0.0, 10.0)
    assert not mech.is_reachable(0.0, -10.0)


def test_regression_combined_7_7_unreachable(mech):
    assert not mech.is_reachable(7.0, 7.0)


def test_regression_total_height(mech):
    assert mech.total_height_cm() == pytest.approx(20.8, abs=1e-9)


def test_regression_all_targets_fail(wmap):
    assert len(wmap.targets_met) == 5
    assert not any(wmap.targets_met.values()), wmap.targets_met


def test_regression_workspace_ok_count(wmap):
    assert int(wmap.ok.sum()) == pytest.approx(177, abs=2)


# --- Sayisal dayaniklilik --------------------------------------------------------


def test_ik_no_exceptions_over_grid(mech):
    for r in np.linspace(-20.0, 20.0, 21):
        for p in np.linspace(-20.0, 20.0, 21):
            mech.ik(float(deg_to_rad(p)), float(deg_to_rad(r)))


def test_workspace_map_shape(wmap):
    n = len(wmap.pitch_deg)
    assert wmap.roll_deg.shape == (n,)
    for arr in (wmap.reason, wmap.reason_code, wmap.ok, wmap.transmission_deg):
        assert arr.shape == (n, n)


def test_reason_legend(wmap):
    legend = wmap.reason_legend
    assert LimitReason.OK in legend
    assert LimitReason.UNREACHABLE_CIRCLE in legend
    # Haritada gorunmeyen bir sebep efsanede de olmamali
    present = set(wmap.reason_code.ravel().tolist())
    assert len(legend) == len(present)


def test_total_height_matches_config(mech, cfg):
    g = cfg.geometry
    expected = (
        g.gimbal.position_cm[1]
        + g.top_plate.underside_above_gimbal_cm
        + g.top_plate.thickness_cm
        + g.cushion.thickness_cm
    )
    assert mech.total_height_cm() == pytest.approx(expected)


def test_inconsistent_neutral_geometry_raises(fresh_cfg):
    """Notrde plaka yatay olmuyorsa Mechanism kurulurken anlasilir hata verir."""
    fresh_cfg.geometry.rod.length_cm = 30.0
    with pytest.raises(ValueError, match="notr"):
        Mechanism.from_config(fresh_cfg, check_collision=False)
