"""Arayuzun bastan sona calistigini Streamlit AppTest ile dogrular.

Bu dosya olmadan ~600 satirlik arayuz katmani hic denenmemis kalir. Ozellikle
"profili yukle" / "baslangica don" gibi islemlerin GERCEKTEN etki ettigini dogrulayan
testler kritiktir: Streamlit'te `key` verilen bir widget'in durumu kalici oldugu icin
yapilandirmayi yeniden yuklemek tek basina yeterli DEGILDIR (bkz. common.replace_config).

Bkz. docs/tests/test_app.md
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from seatsim import config

from .conftest import ROOT

APP = str(ROOT / "app.py")
CRANK = "geometry.crank.length_cm"


def fresh_app() -> AppTest:
    """Her test kendi uygulama ornegiyle baslar (oturum durumu paylasilmaz)."""
    at = AppTest.from_file(APP, default_timeout=900)
    at.run()
    return at


def click(at: AppTest, needle: str) -> AppTest:
    """Etiketi `needle` iceren dugmeye basar ve betigi yeniden calistirir."""
    button = next(b for b in at.button if needle in b.label)
    button.click().run()
    return at


@pytest.fixture(scope="module")
def app() -> AppTest:
    """Etkilesim gerektirmeyen testler icin tek kez calistirilan uygulama."""
    return fresh_app()


@pytest.fixture(scope="module")
def app_with_map() -> AppTest:
    """Calisma alani haritasi hesaplanmis uygulama (pahali, tek kez)."""
    return click(fresh_app(), "Haritayı hesapla")


# --- Temel render ----------------------------------------------------------------


def test_app_renders_without_exception(app):
    assert list(app.exception) == [], [e.value for e in app.exception]


def test_all_eight_tabs_present(app):
    headers = [h.value for h in app.header]
    assert headers == [
        "Tasarım",
        "Çalışma alanı",
        "Yükler",
        "Dinamik test",
        "Optimizasyon",
        "Hareket (motion cueing)",
        "PID ayarı",
        "Rapor",
    ]


def test_sidebar_warns_about_unmeasured_parameters(app):
    blob = " ".join(w.value for w in app.warning)
    assert "parametre ölçülmedi" in blob


def test_known_design_conflicts_are_shown(app):
    """docs/FINDINGS.md'deki celiskiler ekranda gorunmeli, sessiz kalmamali."""
    blob = " ".join(w.value for w in app.warning)
    assert "toplam yukseklik" in blob
    assert "cubuk/krank orani" in blob


def test_constraint_violation_banner_is_shown(app):
    errors = " ".join(e.value for e in app.error)
    assert "hedeflerin bir kısmını sağlamıyor" in errors


def test_stall_torque_estimate_warning_is_shown(app):
    blob = " ".join(w.value for w in app.warning)
    assert "TAHMİNİDİR" in blob


# --- Calisma alani metrikleri: docs/FINDINGS.md A1 ile ayni olmali ---------------


def _metric(app: AppTest, label: str) -> str:
    for m in app.metric:
        if m.label == label:
            return m.value
    raise AssertionError(f"metrik bulunamadi: {label}")


def test_map_is_not_computed_until_requested(app):
    """Harita otomatik hesaplanmamali.

    Aksi halde Tasarim sekmesinde bir olcuyu degistirmek dakikalarca donmaya yol acar:
    olculdu, krank 4 -> 7,5 degisiminde 41x41 harita 900 saniyeyi asti.
    """
    with pytest.raises(AssertionError, match="metrik bulunamadi"):
        _metric(app, "Kullanılabilir açı kombinasyonu")
    assert any("Hesaplamak için" in i.value for i in app.info)


def test_workspace_metrics_match_findings(app_with_map):
    assert list(app_with_map.exception) == []
    assert _metric(app_with_map, "Kullanılabilir açı kombinasyonu") == "177 / 1681"
    assert _metric(app_with_map, "Maksimum pitch") == "+8.1° / -8.3°"
    assert _metric(app_with_map, "Maksimum roll") == "+9.0° / -9.0°"


def test_stale_map_is_flagged_not_silently_wrong():
    """Tasarim degisince harita bayat olarak isaretlenmeli, sessizce durmamali."""
    at = click(fresh_app(), "Haritayı hesapla")
    assert not any("bayat" in w.value for w in at.warning)

    at.number_input(key=CRANK).set_value(5.0).run()
    assert any("bayat" in w.value for w in at.warning)
    # Eski sonuc silinmez -- gorunmeye devam eder
    assert _metric(at, "Kullanılabilir açı kombinasyonu") == "177 / 1681"


# --- Etkilesim: kaydiricilar -----------------------------------------------------


def test_pitch_slider_moves_without_error():
    at = fresh_app()
    at.slider(key="d_pitch").set_value(6.0).run()
    assert list(at.exception) == []
    at.slider(key="d_roll").set_value(-5.0).run()
    assert list(at.exception) == []


def test_unreachable_angle_reports_reason():
    at = fresh_app()
    at.slider(key="d_pitch").set_value(19.0).run()
    assert list(at.exception) == []
    assert any("ulaşılamıyor" in e.value for e in at.error)


# --- Etkilesim: yapilandirma degistirme (bulgu #1 regresyonu) -------------------


def test_reset_button_actually_reverts_edited_value():
    """"Baslangic degerlerine don" GERCEKTEN geri almali.

    Streamlit'te `key` verilen widget'in durumu kalicidir ve `value=` argumanini
    ezer. C.replace_config bayat anahtarlari silmeseydi bu test kirilirdi -- dugme
    basilir, basari mesaji cikar, ama deger degismezdi.
    """
    at = fresh_app()
    original = at.number_input(key=CRANK).value
    assert original == pytest.approx(4.0)

    at.number_input(key=CRANK).set_value(9.0).run()
    assert at.number_input(key=CRANK).value == pytest.approx(9.0)

    reset = next(b for b in at.button if "Başlangıç değerlerine dön" in b.label)
    reset.click().run()

    assert list(at.exception) == []
    assert at.number_input(key=CRANK).value == pytest.approx(original)


def test_profile_save_and_load_roundtrip(tmp_path, monkeypatch):
    """Profil kaydet -> degistir -> yukle: deger geri gelmeli."""
    monkeypatch.chdir(tmp_path)
    config.save(config.load(ROOT / "config.yaml"), tmp_path / "config.yaml")

    at = AppTest.from_file(APP, default_timeout=900)
    at.run()
    assert list(at.exception) == []

    at.text_input(key="profile_name").set_value("kayit-1").run()
    next(b for b in at.button if b.label == "Profili kaydet").click().run()
    assert any("Kaydedildi" in s.value for s in at.success)

    at.number_input(key=CRANK).set_value(7.5).run()
    assert at.number_input(key=CRANK).value == pytest.approx(7.5)

    at.selectbox(key="profile_load").set_value("kayit-1.yaml").run()
    next(b for b in at.button if b.label == "Profili yükle").click().run()

    assert list(at.exception) == []
    assert at.number_input(key=CRANK).value == pytest.approx(4.0)


def test_invalid_profile_name_is_rejected(tmp_path, monkeypatch):
    """Yol ayraci iceren ad reddedilmeli -- aksi halde proje dosyalari ezilebilir."""
    monkeypatch.chdir(tmp_path)
    config.save(config.load(ROOT / "config.yaml"), tmp_path / "config.yaml")

    at = AppTest.from_file(APP, default_timeout=900)
    at.run()
    at.text_input(key="profile_name").set_value("../config").run()
    next(b for b in at.button if b.label == "Profili kaydet").click().run()

    assert list(at.exception) == []
    assert any("yalnızca harf" in e.value for e in at.error)
    # config.yaml EZILMEMIS olmali -- reddedilmeseydi "../config" onu hedef alirdi
    saved = config.load(tmp_path / "config.yaml")
    assert saved.geometry.crank.length_cm == pytest.approx(4.0)
    assert not list((tmp_path / "profiles").glob("*.yaml"))


def test_stop_height_button_writes_computed_values(tmp_path, monkeypatch):
    """Hesaplanan takoz yukseklikleri KALICI olmali, rerun'da kaybolmamali."""
    monkeypatch.chdir(tmp_path)
    config.save(config.load(ROOT / "config.yaml"), tmp_path / "config.yaml")

    at = AppTest.from_file(APP, default_timeout=900)
    at.run()
    at.number_input(key="stop_target").set_value(8.0).run()
    next(b for b in at.button if "Yükseklikleri" in b.label).click().run()

    assert list(at.exception) == []
    # 8 derecede devreye girecek yukseklikler, 12 derecelik varsayilandan YUKSEKTIR
    heights = at.session_state.cfg.stops.heights()
    assert all(h > 10.07 for h in heights[:2]), heights
    assert all(h > 7.78 for h in heights[2:]), heights


# --- Etkilesim: yukler sekmesi ---------------------------------------------------


def test_verification_button_matches_manual_calculation():
    at = fresh_app()
    next(b for b in at.button if "Doğrulama senaryosunu" in b.label).click().run()
    assert list(at.exception) == []
    assert any("±%2 içinde" in s.value for s in at.success)


def test_load_scenario_sliders_change_results():
    at = fresh_app()
    before = _metric(at, "Yerçekimi momenti")
    at.slider(key="l_fore").set_value(8.0).run()
    assert list(at.exception) == []
    assert _metric(at, "Yerçekimi momenti") != before


def test_torque_map_is_gated_and_renders_on_request():
    at = fresh_app()
    at.selectbox(key="l_n").set_value(15).run()
    click(at, "Tork haritasını hesapla")
    assert list(at.exception) == []


def test_backrest_mode_switch_enables_follow_slider():
    at = fresh_app()
    assert not at.slider(key="l_follow").disabled
    at.radio(key="l_mode").set_value("tilting").run()
    assert list(at.exception) == []
    assert at.slider(key="l_follow").disabled


# --- Etkilesim: calisma alani katmanlari ----------------------------------------


@pytest.mark.parametrize("layer", ["Transmisyon açısı", "Ölü nokta marjı"])
def test_workspace_layers_render(app_with_map, layer):
    app_with_map.radio(key="w_layer").set_value(layer).run()
    assert list(app_with_map.exception) == []
    app_with_map.radio(key="w_layer").set_value("Sınırlayan sebep").run()


def test_grid_change_is_reported_until_recomputed(app_with_map):
    app_with_map.selectbox(key="w_n").set_value(21).run()
    assert list(app_with_map.exception) == []
    assert any("yeniden hesaplamak" in c.value for c in app_with_map.caption)
    app_with_map.selectbox(key="w_n").set_value(41).run()


# --- Bozuk yapilandirma ----------------------------------------------------------


def test_broken_config_shows_message_not_traceback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("geometry:\n  saçmalık: 1\n", encoding="utf-8")

    at = AppTest.from_file(APP, default_timeout=900)
    at.run()
    assert list(at.exception) == []
    assert any("yüklenemedi" in e.value for e in at.error)


def test_zero_crank_does_not_crash_validation(tmp_path, monkeypatch):
    """validate() hata firlatmaz: sifir krank uyari olarak gorunmeli, cokme degil."""
    monkeypatch.chdir(tmp_path)
    cfg = config.load(ROOT / "config.yaml")
    cfg.geometry.crank.length_cm = 0.0
    config.save(cfg, tmp_path / "config.yaml")

    at = AppTest.from_file(APP, default_timeout=900)
    at.run()
    assert list(at.exception) == []
    assert any("pozitif olmali" in e.value for e in at.error)
