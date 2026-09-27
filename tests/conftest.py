"""Ortak fixture'lar.

Pahali hesaplar (41x41 calisma alani haritasi, en kotu durum taramasi) oturum
kapsaminda bir kez yapilir ve ilgili testler paylasir.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from seatsim import config, loads
from seatsim.geometry import Mechanism
from seatsim.units import deg_to_rad

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.yaml"


@pytest.fixture(scope="session")
def cfg():
    """Degistirilmeyen baslangic yapilandirmasi."""
    return config.load(CONFIG)


@pytest.fixture
def fresh_cfg():
    """Her test icin taze kopya -- degistirmek icin."""
    return config.load(CONFIG)


@pytest.fixture(scope="session")
def mech(cfg):
    """Tum limitler dahil (carpisma da) mekanizma."""
    return Mechanism.from_config(cfg, check_collision=True)


@pytest.fixture(scope="session")
def mech_nocol(cfg):
    """Carpisma denetimi kapali -- parca limitleri yine aktif."""
    return Mechanism.from_config(cfg, check_collision=False)


@pytest.fixture(scope="session")
def wmap(mech):
    """41x41 calisma alani haritasi (~23 s, bir kez)."""
    return mech.workspace_map(n=41)


@pytest.fixture(scope="session")
def worst(mech):
    """Tam en kotu durum taramasi (~40 s, bir kez)."""
    return loads.worst_case(mech)


def scan_limit(mech, axis: int, sign: float, predicate, limit_deg: float = 40.0) -> float:
    """Bir eksende 0,1 derece adimlarla ilerleyip predicate'in saglandigi son aciyi bulur.

    Args:
        axis: 0 = pitch, 1 = roll
        sign: +1 veya -1
        predicate: Pose -> bool (ornegin `lambda p: p.reachable` veya `lambda p: p.ok`)
    """
    last = 0.0
    a = 0.1
    while a <= limit_deg:
        pitch = float(deg_to_rad(sign * a)) if axis == 0 else 0.0
        roll = 0.0 if axis == 0 else float(deg_to_rad(sign * a))
        if not predicate(mech.ik(pitch, roll)):
            break
        last = sign * a
        a += 0.1
    return round(last, 1)


def reachable(pose) -> bool:
    return pose.reachable


def usable(pose) -> bool:
    return pose.ok


def manual_scenario_obj():
    """Tanim bolum 2.2 dogrulama senaryosu."""
    return loads.manual_check_scenario()


@pytest.fixture
def manual_scenario():
    return loads.manual_check_scenario()


def grid_poses(mech, n: int = 15, span: float = 12.0):
    """Uygun pozlari izgaradan toplar."""
    out = []
    for r in np.linspace(-span, span, n):
        for p in np.linspace(-span, span, n):
            pose = mech.ik(float(deg_to_rad(p)), float(deg_to_rad(r)))
            if pose.ok:
                out.append(pose)
    return out
