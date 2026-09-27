"""Mesafe fonksiyonlari: tam yontemler, yaklasik yontemlerin hata sinirlari, cift tarama.

Bkz. docs/tests/test_collision.md
"""

from __future__ import annotations

import numpy as np
import pytest

from seatsim import bodies, collision
from seatsim.bodies import Box, Capsule

RNG = np.random.default_rng(20260912)
I3 = np.eye(3)


def box(center, half, R=None) -> Box:
    return Box(
        center=np.asarray(center, dtype=float),
        half=np.asarray(half, dtype=float),
        R=I3.copy() if R is None else R,
    )


def cap(p0, p1, radius) -> Capsule:
    return Capsule(p0=np.asarray(p0, dtype=float), p1=np.asarray(p1, dtype=float),
                   radius=float(radius))


def rot_z(angle: float) -> np.ndarray:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


# --- Dogru parcasi - dogru parcasi (TAM) -----------------------------------------


def test_parallel_segments():
    d, _, _ = collision.segment_segment(
        np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 3.0, 0.0]), np.array([1.0, 3.0, 0.0]),
    )
    assert d == pytest.approx(3.0, abs=1e-12)


def test_crossing_segments():
    d, s, t = collision.segment_segment(
        np.array([-1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]),
        np.array([0.0, -1.0, 0.0]), np.array([0.0, 1.0, 0.0]),
    )
    assert d == pytest.approx(0.0, abs=1e-12)
    assert s == pytest.approx(0.5, abs=1e-12)
    assert t == pytest.approx(0.5, abs=1e-12)


def test_skew_segments():
    d, _, _ = collision.segment_segment(
        np.array([-1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]),
        np.array([0.0, -1.0, 2.0]), np.array([0.0, 1.0, 2.0]),
    )
    assert d == pytest.approx(2.0, abs=1e-12)


def test_collinear_disjoint():
    d, _, _ = collision.segment_segment(
        np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]),
        np.array([2.0, 0.0, 0.0]), np.array([3.0, 0.0, 0.0]),
    )
    assert d == pytest.approx(1.0, abs=1e-12)


def test_degenerate_point_segment():
    p = np.array([0.0, 2.0, 0.0])
    d, _, _ = collision.segment_segment(
        p, p, np.array([-1.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])
    )
    assert d == pytest.approx(2.0, abs=1e-12)


def test_degenerate_two_points():
    d, _, _ = collision.segment_segment(
        np.zeros(3), np.zeros(3), np.array([3.0, 4.0, 0.0]), np.array([3.0, 4.0, 0.0])
    )
    assert d == pytest.approx(5.0, abs=1e-12)


def test_endpoint_closest():
    d, s, t = collision.segment_segment(
        np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]),
        np.array([3.0, 0.0, 0.0]), np.array([4.0, 0.0, 0.0]),
    )
    assert d == pytest.approx(2.0, abs=1e-12)
    assert s == pytest.approx(1.0, abs=1e-12)
    assert t == pytest.approx(0.0, abs=1e-12)


# --- Nokta - kutu (TAM) ----------------------------------------------------------


def test_point_outside_box_face():
    b = box([0, 0, 0], [1, 1, 1])
    assert collision.point_obb(np.array([3.0, 0.0, 0.0]), b) == pytest.approx(2.0, abs=1e-12)


def test_point_outside_box_corner():
    b = box([0, 0, 0], [1, 1, 1])
    d = collision.point_obb(np.array([2.0, 2.0, 2.0]), b)
    assert d == pytest.approx(np.sqrt(3.0), abs=1e-12)


def test_point_inside_box():
    b = box([0, 0, 0], [1, 1, 1])
    assert collision.point_obb(np.array([0.2, -0.3, 0.5]), b) == 0.0


def test_point_rotated_box():
    b = box([0, 0, 0], [1, 1, 1], rot_z(np.pi / 4))
    # 45 derece donmus kutunun kosesi +x yonunde sqrt(2) mesafede
    d = collision.point_obb(np.array([np.sqrt(2.0) + 1.0, 0.0, 0.0]), b)
    assert d == pytest.approx(1.0, abs=1e-12)


def test_point_obb_many_matches_single():
    b = box([0.1, -0.2, 0.3], [1, 2, 0.5], rot_z(0.7))
    pts = RNG.uniform(-5.0, 5.0, size=(50, 3))
    many = collision._point_obb_signed_many(pts, b)
    for i, p in enumerate(pts):
        assert many[i] == pytest.approx(collision._point_obb_signed(p, b), abs=1e-12)


# --- Kapsul - kapsul (TAM) -------------------------------------------------------


def test_capsule_capsule_gap():
    a = cap([0, 0, 0], [1, 0, 0], 1.0)
    b = cap([0, 5, 0], [1, 5, 0], 1.5)
    assert collision.capsule_capsule(a, b) == pytest.approx(2.5, abs=1e-12)


def test_capsule_capsule_touching():
    a = cap([0, 0, 0], [1, 0, 0], 1.0)
    b = cap([0, 2.5, 0], [1, 2.5, 0], 1.5)
    assert collision.capsule_capsule(a, b) == pytest.approx(0.0, abs=1e-12)


def test_capsule_capsule_overlap():
    a = cap([0, 0, 0], [1, 0, 0], 1.0)
    b = cap([0, 2.0, 0], [1, 2.0, 0], 1.5)
    assert collision.capsule_capsule(a, b) == pytest.approx(-0.5, abs=1e-12)


# --- Kapsul - kutu (yaklasik + iyilestirilmis) -----------------------------------


def test_capsule_box_axis_aligned():
    b = box([0, 0, 0], [1, 1, 1])
    c = cap([-2, 3, 0], [2, 3, 0], 0.5)
    assert collision.capsule_box(c, b) == pytest.approx(1.5, abs=1e-4)


def test_capsule_box_refinement_accuracy():
    """Kaba ornekleme sayisi degisse de iyilestirme ayni sonuca gotururur."""
    b = box([0.3, -0.2, 0.1], [1, 0.5, 2], rot_z(0.4))
    c = cap([-3, 1.7, 0.2], [2.5, 2.1, -0.4], 0.3)
    coarse = collision.capsule_box(c, b, samples=5)
    fine = collision.capsule_box(c, b, samples=64)
    assert coarse == pytest.approx(fine, abs=1e-4)


def test_capsule_box_never_underestimates():
    """Ornekleme gercek minimumu kacirirsa mesafe OLDUGUNDAN BUYUK gosterilir.

    Bu testin amaci iyilestirme adiminin o riski kapattigini kanitlamak: yogun
    ornekleme referansina karsi sonuc asla 0,1 mm'den fazla buyuk olmamali.
    """
    worst = 0.0
    for _ in range(200):
        b = box(
            RNG.uniform(-1, 1, 3), RNG.uniform(0.2, 1.5, 3), rot_z(RNG.uniform(0, np.pi))
        )
        c = cap(RNG.uniform(-4, 4, 3), RNG.uniform(-4, 4, 3), RNG.uniform(0.05, 0.5))
        ref = collision._min_on_segments(
            c.p0[None, :], c.p1[None, :], b, 2000
        )[0] - c.radius
        got = collision.capsule_box(c, b, samples=16)
        worst = max(worst, got - ref)
    assert worst < 1e-4, f"en kotu fazla tahmin {worst * 1000:.3f} mm"


# --- Kutu - kutu -----------------------------------------------------------------


def test_box_box_separated():
    a = box([0, 0, 0], [1, 1, 1])
    b = box([4, 0, 0], [1, 1, 1])
    assert collision.box_box(a, b) == pytest.approx(2.0, abs=1e-3)


def test_box_box_face_contact():
    a = box([0, 0, 0], [1, 1, 1])
    b = box([2, 0, 0], [1, 1, 1])
    assert abs(collision.box_box(a, b)) < 1e-6


def test_box_box_sat_overlap_exact():
    """SAT cakismayi yanlis pozitif/negatif vermeden belirler."""
    for _ in range(300):
        a = box([0, 0, 0], RNG.uniform(0.3, 1.2, 3), rot_z(RNG.uniform(0, np.pi)))
        b = box(RNG.uniform(-3, 3, 3), RNG.uniform(0.3, 1.2, 3), rot_z(RNG.uniform(0, np.pi)))
        overlapping, _, _ = collision._sat(a, b)
        d = collision.box_box(a, b)
        assert overlapping == (d < 0.0)


def test_box_box_rotated_separated():
    a = box([0, 0, 0], [1, 1, 1], rot_z(0.3))
    b = box([5, 0, 0], [1, 1, 1], rot_z(-0.5))
    assert collision.box_box(a, b) > 2.0


def test_box_box_sat_lower_bound_is_valid():
    """SAT alt siniri gercek mesafeyi asla asmaz -- cutoff'un dayanagi budur."""
    for _ in range(200):
        a = box([0, 0, 0], RNG.uniform(0.3, 1.0, 3), rot_z(RNG.uniform(0, np.pi)))
        b = box(RNG.uniform(-5, 5, 3), RNG.uniform(0.3, 1.0, 3), rot_z(RNG.uniform(0, np.pi)))
        overlapping, _, lower = collision._sat(a, b)
        if overlapping:
            continue
        exact = collision.box_box(a, b, cutoff=np.inf)
        assert lower <= exact + 1e-9


def test_box_box_cutoff_preserves_far_decision():
    """cutoff, 'uzakta' kararini degistirmez."""
    for _ in range(200):
        a = box([0, 0, 0], RNG.uniform(0.3, 1.0, 3), rot_z(RNG.uniform(0, np.pi)))
        b = box(RNG.uniform(-5, 5, 3), RNG.uniform(0.3, 1.0, 3), rot_z(RNG.uniform(0, np.pi)))
        exact = collision.box_box(a, b, cutoff=np.inf)
        fast = collision.box_box(a, b, cutoff=0.03)
        assert (exact < 0.03) == (fast < 0.03)
        if exact < 0.03:
            assert fast == pytest.approx(exact, abs=1e-6)


# --- min_distance yonlendirmesi --------------------------------------------------


def test_min_distance_is_symmetric():
    b = box([0, 0, 0], [1, 1, 1])
    c = cap([-2, 3, 0], [2, 3, 0], 0.5)
    assert collision.min_distance(c, b) == pytest.approx(collision.min_distance(b, c))


# --- Cift tarama -----------------------------------------------------------------


@pytest.fixture
def neutral_bodies(cfg, mech_nocol):
    return bodies.build(cfg, mech_nocol.ik(0.0, 0.0))


def test_exclude_pairs_respected(neutral_bodies, cfg):
    excluded = cfg.collision.excluded()
    for c in collision.pairwise(neutral_bodies, exclude_pairs=excluded, prefilter=0.0):
        assert frozenset((c.body_a, c.body_b)) not in excluded


def test_symmetric_pairs_reported_once(neutral_bodies, cfg):
    contacts = collision.pairwise(
        neutral_bodies, exclude_pairs=cfg.collision.excluded(), prefilter=0.0
    )
    keys = [frozenset((c.body_a, c.body_b)) for c in contacts]
    assert len(keys) == len(set(keys))


def test_sorted_by_distance(neutral_bodies, cfg):
    contacts = collision.pairwise(
        neutral_bodies, exclude_pairs=cfg.collision.excluded(), prefilter=0.0
    )
    d = [c.distance for c in contacts]
    assert d == sorted(d)


def test_aabb_prefilter_consistency(neutral_bodies, cfg):
    """On eleme, yakin ciftlerin mesafesini degistirmez."""
    excluded = cfg.collision.excluded()
    full = {
        frozenset((c.body_a, c.body_b)): c.distance
        for c in collision.pairwise(neutral_bodies, exclude_pairs=excluded, prefilter=0.0)
    }
    fast = collision.pairwise(neutral_bodies, exclude_pairs=excluded, prefilter=0.05)
    assert fast, "on eleme her seyi elemis"
    for c in fast:
        assert c.distance == pytest.approx(full[frozenset((c.body_a, c.body_b))], abs=1e-9)


def test_skip_static_excludes_static_pairs(neutral_bodies, cfg):
    excluded = cfg.collision.excluded()
    moving = collision.pairwise(
        neutral_bodies, exclude_pairs=excluded, prefilter=0.0, skip_static=True
    )
    assert moving
    assert all(not c.static_pair for c in moving)

    everything = collision.pairwise(neutral_bodies, exclude_pairs=excluded, prefilter=0.0)
    assert any(c.static_pair for c in everything), "hic statik cift yok, test anlamsiz"


def test_neutral_pose_no_collision(neutral_bodies, cfg):
    contacts = collision.pairwise(
        neutral_bodies, exclude_pairs=cfg.collision.excluded(), prefilter=0.0
    )
    colliding = [c for c in contacts if c.colliding]
    assert not colliding, [f"{c.label_tr}: {c.distance * 100:.2f} cm" for c in colliding]


def test_crank_gearbox_pair_is_checked(neutral_bodies, cfg):
    """docs/FINDINGS.md B3: krank kendi kutusuna carpabilir, cift HARIC TUTULMAZ."""
    pairs = {
        frozenset((c.body_a, c.body_b))
        for c in collision.pairwise(
            neutral_bodies, exclude_pairs=cfg.collision.excluded(), prefilter=0.0
        )
    }
    assert frozenset(("crank_right", "gearbox_right")) in pairs
    assert frozenset(("crank_left", "gearbox_left")) in pairs


def test_user_body_not_collidable(neutral_bodies):
    user = next(b for b in neutral_bodies if b.name == "user_body")
    assert not user.collidable


def test_bodies_rejects_unreachable_pose(cfg, mech_nocol):
    from seatsim.units import deg_to_rad

    pose = mech_nocol.ik(float(deg_to_rad(25.0)), 0.0)
    assert not pose.reachable
    with pytest.raises(ValueError, match="ulaşılamayan"):
        bodies.build(cfg, pose)
