"""config.yaml semasi: yukleme, gidis-donus, uzun bicim, dogrulama, profil karsilastirma.

config.py kullanicinin elle duzenledigi semayi tasir; bozuk bir deger sessizce gecerse
tum sonuclar yanlis olur. Bu yuzden dogrulama kurallari tek tek denenir.

Bkz. docs/tests/test_config.md
"""

from __future__ import annotations

import numpy as np
import pytest
import yaml

from seatsim import config
from seatsim.units import rad_s_to_rpm, rpm_to_rad_s

# --- Yukleme ve gidis-donus ------------------------------------------------------


def test_load_defaults_match_dataclass(cfg):
    """config.yaml'daki degerler dataclass varsayilanlariyla ayni olmali.

    Ikisi ayrisirsa, config.yaml silindiginde program sessizce baska bir tasarimla
    calisir.
    """
    assert not config.diff(cfg, config.SeatConfig())


def test_dict_roundtrip(cfg):
    assert not config.diff(cfg, config.from_dict(config.to_dict(cfg)))


def test_yaml_roundtrip(cfg):
    back = config.from_dict(yaml.safe_load(config.to_yaml(cfg)))
    assert not config.diff(cfg, back)


def test_save_load_roundtrip(fresh_cfg, tmp_path):
    fresh_cfg.geometry.crank.length_cm = 6.5
    fresh_cfg.meta["geometry.crank.length_cm"] = config.ParamMeta(
        confidence=config.OLCULDU, locked=True, note="kumpasla ölçüldü"
    )
    path = tmp_path / "profil.yaml"
    config.save(fresh_cfg, path)

    back = config.load(path)
    assert back.geometry.crank.length_cm == 6.5
    meta = back.get_meta("geometry.crank.length_cm")
    assert meta.locked
    assert meta.confidence == config.OLCULDU
    assert meta.note == "kumpasla ölçüldü"


def test_save_creates_parent_directory(cfg, tmp_path):
    path = tmp_path / "yeni" / "alt" / "profil.yaml"
    config.save(cfg, path)
    assert path.exists()


def test_saved_yaml_has_header(cfg, tmp_path):
    path = tmp_path / "p.yaml"
    config.save(cfg, path)
    assert path.read_text(encoding="utf-8").startswith("# 2DoF Hareketli Koltuk")


# --- Uzun bicim (kilitleme) ------------------------------------------------------


def test_long_form_parsed(fresh_cfg, tmp_path):
    raw = yaml.safe_load(config.to_yaml(fresh_cfg))
    raw["geometry"]["crank"]["length_cm"] = {
        "value": 7.0, "locked": True, "confidence": config.OLCULDU, "note": "elimde var",
    }
    cfg = config.from_dict(raw)
    assert cfg.geometry.crank.length_cm == 7.0
    assert cfg.get_meta("geometry.crank.length_cm").locked
    assert cfg.get_meta("geometry.crank.length_cm").note == "elimde var"


def test_long_form_inherits_default_how_to_measure(fresh_cfg):
    """Uzun bicim yazilirken kayit defteri bilgisi (nasil olcerim) kaybolmamali."""
    raw = yaml.safe_load(config.to_yaml(fresh_cfg))
    raw["motor"]["stall_torque_nm"] = {"value": 42.0, "locked": True}
    cfg = config.from_dict(raw)
    assert "bagaj kantari" in cfg.get_meta("motor.stall_torque_nm").how_to_measure


def test_short_form_is_unlocked(cfg):
    assert not cfg.get_meta("geometry.crank.length_cm").locked


# --- Hata yollari ----------------------------------------------------------------


def test_missing_file_raises_with_path():
    with pytest.raises(FileNotFoundError, match="yok.yaml"):
        config.load("yok.yaml")


def test_unknown_key_raises_in_strict_mode(cfg):
    raw = yaml.safe_load(config.to_yaml(cfg))
    raw["geometry"]["bilinmeyen_anahtar"] = 1.0
    with pytest.raises(ValueError, match="bilinmeyen"):
        config.from_dict(raw, strict=True)


def test_unknown_key_ignored_in_lax_mode(cfg):
    raw = yaml.safe_load(config.to_yaml(cfg))
    raw["geometry"]["bilinmeyen_anahtar"] = 1.0
    assert config.from_dict(raw, strict=False).geometry.crank.length_cm > 0.0


def test_non_dict_root_raises_type_error():
    with pytest.raises(TypeError, match="sozluk"):
        config.from_dict([1, 2, 3])


def test_load_wraps_error_with_filename(tmp_path):
    path = tmp_path / "bozuk.yaml"
    path.write_text("geometry:\n  saçmalık: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bozuk.yaml"):
        config.load(path)


def test_scalar_where_dict_expected_raises(cfg):
    raw = yaml.safe_load(config.to_yaml(cfg))
    raw["geometry"]["crank"] = 4.0
    with pytest.raises(ValueError, match="sozluk bekleniyordu"):
        config.from_dict(raw)


# --- Dogrulama: baslangic dosyasinin beklenen cikisi -----------------------------


def test_initial_config_has_no_errors(cfg):
    assert [i for i in config.validate(cfg) if i.severity == config.ERROR] == []


def test_initial_config_warnings_are_the_known_ones(cfg):
    """docs/FINDINGS.md'deki bilinen celiskiler UYARI olarak cikmali -- sessiz kalmamali."""
    warns = [i for i in config.validate(cfg) if i.severity == config.WARN]
    assert len(warns) == 4
    blob = " ".join(i.message for i in warns)
    assert "toplam yukseklik" in blob
    assert "cubuk/krank orani" in blob
    assert "izdusum" in blob


def test_initial_config_reports_uncertain_count(cfg):
    infos = [i for i in config.validate(cfg) if i.severity == config.INFO]
    assert len(infos) == 1
    assert "TAHMINI" in infos[0].message


@pytest.mark.parametrize(
    "path,value",
    [
        ("geometry.crank.length_cm", 0.0),
        ("geometry.crank.length_cm", -1.0),
        ("geometry.rod.length_cm", 0.0),
        ("geometry.top_plate.thickness_cm", -0.5),
        ("geometry.base_plate.thickness_cm", 0.0),
        ("geometry.cushion.thickness_cm", -1.0),
        ("hardware.gimbal_post_diameter_cm", 0.0),
        ("motor.stall_torque_nm", 0.0),
    ],
)
def test_non_positive_values_are_errors(fresh_cfg, path, value):
    config.set_by_path(fresh_cfg, path, value)
    errors = [i for i in config.validate(fresh_cfg) if i.severity == config.ERROR]
    assert any(i.path == path for i in errors), errors


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_carried_fraction_out_of_range_is_error(fresh_cfg, value):
    fresh_cfg.mass.carried_fraction = value
    errors = [i for i in config.validate(fresh_cfg) if i.severity == config.ERROR]
    assert any("carried_fraction" in i.path for i in errors)


@pytest.mark.parametrize("value", [-0.5, 2.0])
def test_follow_fraction_out_of_range_is_error(fresh_cfg, value):
    fresh_cfg.mass.backrest_follow_fraction = value
    errors = [i for i in config.validate(fresh_cfg) if i.severity == config.ERROR]
    assert any("backrest_follow_fraction" in i.path for i in errors)


def test_bad_backrest_mode_is_error(fresh_cfg):
    fresh_cfg.mass.backrest_mode = "yatiyor"
    errors = [i for i in config.validate(fresh_cfg) if i.severity == config.ERROR]
    assert any("backrest_mode" in i.path for i in errors)


def test_bad_outer_axis_is_error(fresh_cfg):
    fresh_cfg.geometry.gimbal.outer_axis = "yaw"
    errors = [i for i in config.validate(fresh_cfg) if i.severity == config.ERROR]
    assert any("outer_axis" in i.path for i in errors)


def test_inconsistent_neutral_geometry_is_error(fresh_cfg):
    """Notrde plaka yatay olmuyorsa bu bir ERROR -- gereken cubuk boyu mesajda yazili."""
    fresh_cfg.geometry.rod.length_cm = 9.0
    errors = [i for i in config.validate(fresh_cfg) if i.severity == config.ERROR]
    assert len(errors) == 1
    assert "notr pozda" in errors[0].message
    assert "5.50" in errors[0].message, errors[0].message


def test_neutral_offset_changes_required_rod_length(fresh_cfg):
    """Krank notr acisi degisince notr tutarliligi da degisir."""
    fresh_cfg.geometry.crank.neutral_offset_deg = 30.0
    errors = [i for i in config.validate(fresh_cfg) if i.severity == config.ERROR]
    assert any("notr pozda" in i.message for i in errors)


def test_height_warning_disappears_when_limit_raised(fresh_cfg):
    fresh_cfg.limits.total_height_max_cm = 25.0
    blob = " ".join(i.message for i in config.validate(fresh_cfg))
    assert "toplam yukseklik" not in blob


def test_rod_ratio_warning_disappears_when_ratio_ok(fresh_cfg):
    """Cubuk 12 cm + mil konumu uyumlu olunca oran uyarisi kalkar."""
    fresh_cfg.geometry.rod.length_cm = 12.0
    fresh_cfg.geometry.motor_shaft_cm = [18.2, 0.5, 24.5]
    blob = " ".join(i.message for i in config.validate(fresh_cfg))
    assert "cubuk/krank orani" not in blob


# --- Yol ile erisim --------------------------------------------------------------


def test_get_by_path_nested(cfg):
    assert config.get_by_path(cfg, "limits.pot.mechanical_range_deg") == 270.0
    assert config.get_by_path(cfg, "geometry.crank.length_cm") == 4.0


def test_set_by_path_nested(fresh_cfg):
    config.set_by_path(fresh_cfg, "limits.pot.mechanical_range_deg", 300.0)
    assert fresh_cfg.limits.pot.mechanical_range_deg == 300.0


def test_get_by_path_unknown_raises(cfg):
    with pytest.raises(AttributeError):
        config.get_by_path(cfg, "geometry.olmayan")


# --- Ust veri sorgulari ----------------------------------------------------------


def test_uncertain_parameters_finds_estimates(cfg):
    paths = [p for p, _, _ in cfg.uncertain_parameters()]
    assert "motor.stall_torque_nm" in paths
    assert "mass.carried_fraction" in paths
    assert "targets.pitch_deg" not in paths  # TASARIM, tahmin degil


def test_uncertain_parameters_carry_how_to_measure(cfg):
    for path, _, meta in cfg.uncertain_parameters():
        assert meta.confidence == config.TAHMINI
        assert meta.note or meta.how_to_measure, f"{path} icin yonlendirme yok"


def test_free_parameters_excludes_locked(fresh_cfg):
    assert "geometry.crank.length_cm" in fresh_cfg.free_parameters()
    fresh_cfg.meta["geometry.crank.length_cm"] = config.ParamMeta(locked=True)
    assert "geometry.crank.length_cm" not in fresh_cfg.free_parameters()


def test_free_parameters_are_numeric_only(cfg):
    for path in cfg.free_parameters():
        assert isinstance(config.get_by_path(cfg, path), (int, float))


def test_get_meta_defaults_to_tasarim(cfg):
    assert cfg.get_meta("targets.pitch_deg").confidence == config.TASARIM
    assert not cfg.get_meta("targets.pitch_deg").locked


def test_copy_is_independent(cfg):
    clone = cfg.copy()
    clone.geometry.crank.length_cm = 99.0
    assert cfg.geometry.crank.length_cm != 99.0


# --- Profil karsilastirma --------------------------------------------------------


def test_diff_detects_change(fresh_cfg, cfg):
    fresh_cfg.geometry.crank.length_cm = 7.0
    changes = config.diff(cfg, fresh_cfg)
    assert len(changes) == 1
    assert changes[0].path == "geometry.crank.length_cm"
    assert (changes[0].old, changes[0].new) == (4.0, 7.0)


def test_diff_ignores_float_noise(fresh_cfg, cfg):
    fresh_cfg.geometry.crank.length_cm = 4.0 + 1e-15
    assert config.diff(cfg, fresh_cfg) == []


def test_diff_detects_list_change(fresh_cfg, cfg):
    fresh_cfg.geometry.rod_attach_cm = [18.2, -0.5, 22.0]
    assert [c.path for c in config.diff(cfg, fresh_cfg)] == ["geometry.rod_attach_cm"]


def test_diff_detects_string_change(fresh_cfg, cfg):
    fresh_cfg.mass.backrest_mode = "tilting"
    assert [c.path for c in config.diff(cfg, fresh_cfg)] == ["mass.backrest_mode"]


# --- Yardimci yapilar ------------------------------------------------------------


def test_collision_excluded_is_direction_independent(cfg):
    excluded = cfg.collision.excluded()
    assert frozenset(("rod_right", "crank_right")) in excluded
    assert frozenset(("crank_right", "rod_right")) in excluded


def test_controller_section_is_empty(cfg):
    """SMC3.ino gorulmeden kontrolcu parametreleri doldurulmaz."""
    assert cfg.controller == {}


# --- units.py: Faz 3'te kullanilacak donusumler ----------------------------------


def test_rpm_conversion_roundtrip():
    for rpm in (0.0, 55.0, 120.5):
        assert float(rad_s_to_rpm(rpm_to_rad_s(rpm))) == pytest.approx(rpm, rel=1e-12)


def test_rpm_to_rad_s_known_value():
    assert float(rpm_to_rad_s(60.0)) == pytest.approx(2.0 * np.pi, rel=1e-12)
