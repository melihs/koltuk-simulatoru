"""Statik kuvvet cozumu: elle hesap kabul testi, simetri, capraz dogrulama, ters sarkac.

Bkz. docs/tests/test_loads.md
"""

from __future__ import annotations

import numpy as np
import pytest

from seatsim import frames, loads
from seatsim.geometry import LEFT, RIGHT, Mechanism
from seatsim.units import G, cm_to_m, deg_to_rad

from .conftest import grid_poses

RNG = np.random.default_rng(20260912)


def ideal(**kw) -> loads.MassScenario:
    """Plaka ve koltuk kutlesi olmayan, idealize senaryo."""
    base = dict(
        user_kg=90.0,
        carried_fraction=1.0,
        plate_assembly_kg=0.0,
        backrest_mode="tilting",
        seat_kg=0.0,
        com_height_m=0.0,
        com_fore_aft_m=0.0,
        com_lateral_m=0.0,
    )
    base.update(kw)
    return loads.MassScenario(**base)


# --- Kabul testi: tanim bolum 2.2 elle hesabi ------------------------------------


@pytest.fixture
def manual_result(mech_nocol, manual_scenario):
    return loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), manual_scenario)


def test_manual_gravity_moment(manual_result):
    assert abs(manual_result.gravity_moment_nm[0]) == pytest.approx(44.145, rel=0.02)


def test_manual_total_rod_force(manual_result):
    assert manual_result.rod_force_n.sum() == pytest.approx(215.32, rel=0.02)


def test_manual_rod_force_each(manual_result):
    for f in manual_result.rod_force_n:
        assert f == pytest.approx(107.66, rel=0.02)


def test_manual_motor_torque(manual_result):
    for t in manual_result.motor_torque_nm:
        assert abs(t) == pytest.approx(4.3065, rel=0.02)


def test_manual_no_roll_moment(manual_result):
    assert manual_result.gravity_moment_nm[1] == pytest.approx(0.0, abs=1e-12)


# --- Simetri ---------------------------------------------------------------------


def test_pure_pitch_rod_forces_equal(mech_nocol):
    sc = ideal(com_fore_aft_m=0.05)
    for d in (0.0, 3.0, 5.0, -4.0):
        res = loads.solve(mech_nocol, mech_nocol.ik(float(deg_to_rad(d)), 0.0), sc)
        assert res.rod_force_n[RIGHT] == pytest.approx(res.rod_force_n[LEFT], abs=1e-9)


def test_pure_roll_rod_forces_opposite(mech_nocol):
    sc = ideal(com_lateral_m=0.05)
    res = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), sc)
    assert res.rod_force_n[RIGHT] == pytest.approx(-res.rod_force_n[LEFT], abs=1e-9)


def test_lateral_com_mirror(mech_nocol):
    a = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(com_lateral_m=0.05))
    b = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(com_lateral_m=-0.05))
    assert np.allclose(a.rod_force_n, b.rod_force_n[::-1], atol=1e-9)


def test_motor_torques_equal_in_pure_pitch(mech_nocol):
    sc = ideal(com_fore_aft_m=0.05)
    res = loads.solve(mech_nocol, mech_nocol.ik(float(deg_to_rad(4.0)), 0.0), sc)
    assert abs(res.motor_torque_nm[RIGHT]) == pytest.approx(
        abs(res.motor_torque_nm[LEFT]), abs=1e-9
    )


# --- Capraz dogrulama: sanal is --------------------------------------------------


def test_virtual_work_matches_direct_moment(mech):
    """Iki tamamen bagimsiz yontem ayni torku vermeli.

    Hem geometry.jacobian() hem loads.solve() ayni anda denetlenir.
    """
    scenarios = [
        loads.MassScenario.from_config(mech.cfg, user_kg=kg, com_fore_aft_m=f, com_lateral_m=lat)
        for kg, f, lat in [(60, 0.0, 0.0), (90, 0.05, 0.0), (120, 0.08, 0.05),
                           (120, -0.05, -0.05), (90, 0.0, 0.05)]
    ]
    n = 0
    for pose in grid_poses(mech, n=11):
        for sc in scenarios:
            res = loads.solve(mech, pose, sc, stiffness=False)
            if res.singular or not np.isfinite(res.cross_check_error):
                continue
            n += 1
            assert res.cross_check_error < 1e-6, (
                f"pitch={np.degrees(pose.pitch):.1f} roll={np.degrees(pose.roll):.1f} "
                f"hata={res.cross_check_error:.3e}"
            )
    assert n > 50, "yeterli ornek yok"


# --- Fizik tutarliligi -----------------------------------------------------------


def test_zero_mass_zero_force(mech_nocol):
    res = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(user_kg=0.0))
    assert np.allclose(res.rod_force_n, 0.0, atol=1e-12)
    assert np.allclose(res.motor_torque_nm, 0.0, atol=1e-12)
    assert np.allclose(res.gimbal_reaction_n, 0.0, atol=1e-12)


def test_linearity_in_mass(mech_nocol):
    pose = mech_nocol.ik(float(deg_to_rad(3.0)), float(deg_to_rad(2.0)))
    a = loads.solve(mech_nocol, pose, ideal(user_kg=90.0, com_fore_aft_m=0.05))
    b = loads.solve(mech_nocol, pose, ideal(user_kg=180.0, com_fore_aft_m=0.05))
    assert np.allclose(b.rod_force_n, 2.0 * a.rod_force_n, rtol=1e-9)
    assert np.allclose(b.motor_torque_nm, 2.0 * a.motor_torque_nm, rtol=1e-9)


def test_force_balance(mech, cfg):
    sc = loads.MassScenario.from_config(cfg, com_fore_aft_m=0.05, com_lateral_m=0.03)
    for pose in grid_poses(mech, n=7):
        res = loads.solve(mech, pose, sc, stiffness=False)
        if res.singular:
            continue
        weight = np.array([0.0, 0.0, -res.total_moving_mass_kg * G])
        rods = sum(res.rod_force_n[s] * pose.rod_unit[s] for s in (RIGHT, LEFT))
        assert np.linalg.norm(res.gimbal_reaction_n + rods + weight) < 1e-9


def test_moment_balance_about_gimbal(mech, cfg):
    sc = loads.MassScenario.from_config(cfg, com_fore_aft_m=0.05, com_lateral_m=0.03)
    for pose in grid_poses(mech, n=7):
        res = loads.solve(mech, pose, sc, stiffness=False)
        if res.singular:
            continue
        axes = np.stack(
            [frames.pitch_axis(), frames.roll_axis(pose.pitch, mech.outer_axis)]
        )
        rod_moment = sum(
            np.cross(pose.attach[s] - mech.G, res.rod_force_n[s] * pose.rod_unit[s])
            for s in (RIGHT, LEFT)
        )
        for k, ax in enumerate(axes):
            net = float(np.dot(rod_moment, ax)) + res.gravity_moment_nm[k]
            assert abs(net) < 1e-9


def test_gimbal_reaction_carries_weight(mech_nocol):
    """Notrde, AM kaymasi yokken mafsal tum agirligi tasir."""
    res = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(user_kg=100.0))
    assert res.gimbal_reaction_n[2] == pytest.approx(100.0 * G, rel=1e-9)
    assert np.allclose(res.rod_force_n, 0.0, atol=1e-9)


def test_rod_sign_convention(mech_nocol):
    """AM onde -> cubuklar BASMADA (+); AM arkada -> CEKMEDE (-)."""
    front = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(com_fore_aft_m=0.05))
    back = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(com_fore_aft_m=-0.05))
    assert np.all(front.rod_force_n > 0.0)
    assert np.all(back.rod_force_n < 0.0)


def test_rod_end_force_is_magnitude(mech_nocol):
    res = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(com_fore_aft_m=-0.05))
    assert np.all(res.rod_end_force_n >= 0.0)
    assert np.allclose(res.rod_end_force_n, np.abs(res.rod_force_n))


# --- Ters sarkac -----------------------------------------------------------------


def test_gravity_stiffness_equals_weight_times_height(mech_nocol, cfg):
    """Notrde sertlik TAM olarak W * h'dir (h = AM'nin mafsal ustundeki yuksekligi).

    En keskin test: sonlu farkla hesaplanan sayisal turev, analitik degerle makine
    hassasiyetinde uyusmak zorunda. Hem kutle modelini hem rotasyon isaretlerini dener.
    """
    g = cfg.geometry
    cushion_top = float(
        cm_to_m(
            g.top_plate.underside_above_gimbal_cm
            + g.top_plate.thickness_cm
            + g.cushion.thickness_cm
        )
    )
    mass = 102.0
    for h in (0.0, 0.15, 0.25, 0.35):
        res = loads.solve(
            mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(user_kg=mass, com_height_m=h)
        )
        expected = mass * G * (cushion_top + h)
        assert res.gravity_stiffness_nm_rad[0] == pytest.approx(expected, rel=1e-6)
        assert res.gravity_stiffness_nm_rad[1] == pytest.approx(expected, rel=1e-6)


def test_gravity_stiffness_positive_above_gimbal(mech_nocol):
    res = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(com_height_m=0.25))
    assert np.all(res.gravity_stiffness_nm_rad > 0.0)


def test_gravity_stiffness_negative_below_gimbal(mech_nocol):
    res = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(com_height_m=-0.20))
    assert np.all(res.gravity_stiffness_nm_rad < 0.0)


def test_moment_grows_with_com_height(mech_nocol):
    pose = mech_nocol.ik(float(deg_to_rad(-6.0)), 0.0)
    prev = -np.inf
    for h in (0.0, 0.1, 0.2, 0.3):
        res = loads.solve(mech_nocol, pose, ideal(com_height_m=h, com_fore_aft_m=0.08))
        cur = abs(res.gravity_moment_nm[0])
        assert cur > prev
        prev = cur


def test_moment_grows_with_tilt(mech_nocol):
    sc = ideal(com_height_m=0.25, com_fore_aft_m=0.08)
    prev = -np.inf
    for d in (0.0, -2.0, -4.0, -6.0, -8.0):
        res = loads.solve(mech_nocol, mech_nocol.ik(float(deg_to_rad(d)), 0.0), sc)
        cur = abs(res.gravity_moment_nm[0])
        assert cur > prev
        prev = cur


# --- Sirtlik senaryolari ---------------------------------------------------------


def test_follow_fraction_one_equals_tilting(mech_nocol, cfg):
    common = dict(user_kg=120.0, carried_fraction=0.85, plate_assembly_kg=8.0,
                  com_fore_aft_m=0.08, com_height_m=0.25)
    pose = mech_nocol.ik(float(deg_to_rad(-6.0)), 0.0)
    tilting = loads.solve(
        mech_nocol, pose,
        loads.MassScenario(backrest_mode="tilting", seat_kg=0.0, **common),
    )
    fixed = loads.solve(
        mech_nocol, pose,
        loads.MassScenario(backrest_mode="fixed", backrest_follow_fraction=1.0, **common),
    )
    assert np.allclose(tilting.rod_force_n, fixed.rod_force_n, atol=1e-9)
    assert np.allclose(
        tilting.gravity_stiffness_nm_rad, fixed.gravity_stiffness_nm_rad, atol=1e-9
    )


def test_follow_fraction_monotonic(mech_nocol):
    pose = mech_nocol.ik(float(deg_to_rad(-6.0)), 0.0)
    prev_t, prev_k = -np.inf, -np.inf
    for ff in (0.0, 0.3, 0.6, 1.0):
        res = loads.solve(
            mech_nocol, pose,
            loads.MassScenario(
                user_kg=120.0, carried_fraction=0.85, plate_assembly_kg=8.0,
                backrest_mode="fixed", backrest_follow_fraction=ff,
                com_fore_aft_m=0.08, com_height_m=0.25,
            ),
        )
        t = res.worst_torque_nm
        k = res.gravity_stiffness_nm_rad[0]
        assert t > prev_t and k > prev_k
        prev_t, prev_k = t, k


def test_follow_fraction_zero_no_pendulum(mech_nocol, cfg):
    """follow=0 -> ters sarkac etkisi yalnizca plakanin katkisi kadar."""
    res = loads.solve(
        mech_nocol, mech_nocol.ik(0.0, 0.0),
        loads.MassScenario(
            user_kg=120.0, carried_fraction=0.85, plate_assembly_kg=8.0,
            backrest_mode="fixed", backrest_follow_fraction=0.0,
            com_fore_aft_m=0.08, com_height_m=0.25,
        ),
    )
    plate_only = cfg.mass.plate_assembly_kg * G * float(cm_to_m(cfg.mass.plate_com_cm[1]))
    assert res.gravity_stiffness_nm_rad[0] == pytest.approx(plate_only, rel=0.05)


# --- Tekillik koruması -----------------------------------------------------------


def test_singular_geometry_does_not_crash(fresh_cfg):
    """Iki cubuk da merkez hatta olursa roll DOF kontrol edilemez -> singular.

    Tarama cokmemeli, istisna firlatmamali.
    """
    fresh_cfg.geometry.rod_attach_cm = [0.0, -0.5, 20.5]
    fresh_cfg.geometry.motor_shaft_cm = [0.0, 7.0, 24.5]
    m = Mechanism.from_config(fresh_cfg, check_collision=False)
    res = loads.solve(m, m.ik(0.0, 0.0), ideal(com_fore_aft_m=0.05), stiffness=False)
    assert res.singular
    assert np.allclose(res.rod_force_n, 0.0)


def test_solve_rejects_unreachable_pose(mech_nocol):
    pose = mech_nocol.ik(float(deg_to_rad(25.0)), 0.0)
    assert not pose.reachable
    with pytest.raises(ValueError, match="ulaşılamayan"):
        loads.solve(mech_nocol, pose, ideal())


def test_condition_number_is_small_near_neutral(mech_nocol):
    res = loads.solve(mech_nocol, mech_nocol.ik(0.0, 0.0), ideal(com_fore_aft_m=0.05))
    assert res.condition < 2.0


# --- Verdict esikleri (birim test, tarama gerektirmez) ---------------------------


@pytest.mark.parametrize(
    "sf,expected",
    [(2.5, "YETERLI"), (2.0, "YETERLI"), (1.9, "SINIRDA"), (1.5, "SINIRDA"),
     (1.49, "YETERSIZ"), (0.8, "YETERSIZ")],
)
def test_verdict_thresholds(cfg, sf, expected):
    wc = loads.WorstCase(max_motor_torque_nm=20.0, min_safety_factor=sf)
    loads._verdict(wc, cfg)
    assert wc.verdict == expected
    assert wc.explanation_tr


# --- En kotu durum taramasi ------------------------------------------------------


def test_worst_case_reports_scenario(worst):
    assert worst.at_scenario is not None
    assert worst.n_poses > 0
    assert worst.n_scenarios > 0
    assert worst.explanation_tr


def test_worst_case_scenario_reproduces(mech, worst):
    """Raporlanan poz + senaryo yeniden cozuldugunde ayni torku vermeli."""
    pose = mech.ik(
        float(deg_to_rad(worst.at_pitch_deg)), float(deg_to_rad(worst.at_roll_deg))
    )
    res = loads.solve(mech, pose, worst.at_scenario, stiffness=False)
    assert res.worst_torque_nm == pytest.approx(worst.max_motor_torque_nm, rel=1e-9)


def test_worst_case_is_upper_bound(mech, worst):
    """Tarama sonucu, tek tek cozumlerin hicbirinden kucuk olmamali."""
    sc = worst.at_scenario
    for pose in grid_poses(mech, n=11):
        res = loads.solve(mech, pose, sc, stiffness=False)
        if res.singular:
            continue
        assert res.worst_torque_nm <= worst.max_motor_torque_nm + 1e-9


def test_worst_case_needs_collision_check(mech):
    """check_collision=False, ulasilamayan pozlari dahil edip fizik disi tork bulur.

    Varsayilanin True oldugunu korur -- docs/files/loads.md'deki uyarinin testi.
    """
    spec = loads.SweepSpec(
        pitch_deg=np.linspace(-12.0, 12.0, 11),
        roll_deg=np.linspace(-12.0, 12.0, 11),
        user_kg=(120.0,),
        com_fore_aft_cm=(8.0,),
        com_lateral_cm=(5.0,),
        com_height_cm=(30.0,),
        backrest_modes=("tilting",),
    )
    safe = loads.worst_case(mech, spec, check_collision=True)
    unsafe = loads.worst_case(mech, spec, check_collision=False)
    assert unsafe.max_motor_torque_nm > 3.0 * safe.max_motor_torque_nm


# --- Regresyon -------------------------------------------------------------------


def test_regression_worst_case_torque(worst):
    assert worst.max_motor_torque_nm == pytest.approx(19.7, rel=0.05)


def test_regression_worst_case_location(worst):
    assert worst.at_pitch_deg == pytest.approx(-3.6, abs=1.5)
    assert worst.at_roll_deg == pytest.approx(-7.2, abs=1.5)


def test_regression_safety_factor(worst):
    assert worst.min_safety_factor == pytest.approx(1.52, rel=0.05)
    assert worst.verdict == "SINIRDA"


def test_regression_rod_forces(worst):
    assert worst.max_rod_compression_n == pytest.approx(597.0, rel=0.05)
    assert worst.max_rod_tension_n == pytest.approx(434.0, rel=0.05)


def test_regression_gimbal_force(worst):
    assert worst.max_gimbal_force_n == pytest.approx(1698.0, rel=0.05)


def test_regression_gimbal_post_bending(worst):
    """Bilincli olarak DUSUK bir deger sabitlenir.

    Ilk tahmin 136 N.m'ydi ve yanlisti: kardan mafsali pitch/roll momenti tasiyamadigi
    icin devrilme momentini cubuklar alir; direge yalnizca yatay kuvvet x yukseklik kalir.
    """
    assert worst.max_gimbal_post_bending_nm == pytest.approx(22.7, rel=0.10)
    assert worst.max_gimbal_post_bending_nm < 100.0
