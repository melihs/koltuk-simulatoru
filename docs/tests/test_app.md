# tests/test_app.py

## Amaç

Arayüzün baştan sona çalıştığını Streamlit `AppTest` ile doğrular. Bu dosya olmadan
~600 satırlık arayüz katmanı hiç denenmemiş kalır — ve nitekim bu dosya yazılmadan önce
arayüzde tüm profil işlemlerini sessizce kıran bir hata vardı.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `app` | fixture (module) | — | Bir kez çalıştırılmış uygulama | Etkileşim gerektirmeyen testler |
| `app_with_map` | fixture (module) | — | Çalışma alanı haritası hesaplanmış uygulama | Pahalı, bir kez |
| `tmp_path`, `monkeypatch` | pytest | — | — | Çalışma dizinini izole eden testler |

`fresh_app()` her çağrıda yeni bir `AppTest` örneği verir — oturum durumu paylaşılmaz.
`click(at, needle)` etiketinde `needle` geçen düğmeye basıp betiği yeniden çalıştırır.

## Çıkış

pytest sonucu — 24 test.

### Temel render

`test_app_renders_without_exception`, sekme başlıklarının tam listesi, kenar çubuğundaki
"ölçülmedi" uyarısı, [FINDINGS.md](../FINDINGS.md) çelişkilerinin ekranda görünmesi,
"KISIT İHLALİ" bandı ve stall torkunun **TAHMİNİ** olduğu uyarısı.

### Çalışma alanı metrikleri

`test_workspace_metrics_match_findings` haritayı hesaplatır ve `177 / 1681`, `+8.1°/-8.3°`,
`+9.0°/-9.0°` değerlerini [FINDINGS.md](../FINDINGS.md) A1 ile karşılaştırır. Arayüzün
gösterdiği sayı ile dokümandaki sayı böylece birbirine bağlanır.

### Pahalı hesapların kapısı

| Test | Ne doğrular |
|---|---|
| `test_map_is_not_computed_until_requested` | Harita **otomatik hesaplanmaz**. Ölçüldü: krank 4 → 7,5 değişiminde 41×41 harita 900 saniyeyi aştı; otomatik olsaydı Tasarım sekmesinde ölçü değiştirmek arayüzü dakikalarca kilitlerdi |
| `test_stale_map_is_flagged_not_silently_wrong` | Tasarım değişince harita "bayat" olarak işaretlenir ama **silinmez** — eski sonuç görünmeye devam eder, yalnızca güncel olmadığı bilinir |
| `test_grid_change_is_reported_until_recomputed` | Izgara ayarı değişince hangi ayarla hesaplandığı yazılır |
| `test_torque_map_is_gated_and_renders_on_request` | Tork haritası da düğme arkasında ve basınca çiziliyor |

### Yapılandırma değiştirme — bulgu #1 regresyonu

Bu üç test projedeki en değerli arayüz testleridir. Streamlit'te `key` verilen bir
widget'ın durumu **kalıcıdır ve `value=` argümanını ezer**; bu yüzden yapılandırmayı
yeniden yüklemek tek başına yeterli değildir. `common.replace_config()` bayat widget
anahtarlarını silmeseydi üçü de kırılırdı — düğmeye basılır, başarı mesajı çıkar, değer
değişmezdi.

| Test | Ne doğrular |
|---|---|
| `test_reset_button_actually_reverts_edited_value` | 4,0 → 9,0 düzenle, "Başlangıç değerlerine dön" bas, **gerçekten** 4,0'a döner |
| `test_profile_save_and_load_roundtrip` | Kaydet → değiştir → yükle, değer geri gelir |
| `test_stop_height_button_writes_computed_values` | Hesaplanan takoz yükseklikleri kalıcı olur, rerun'da kaybolmaz |

### Güvenlik

| Test | Ne doğrular |
|---|---|
| `test_invalid_profile_name_is_rejected` | `../config` adı reddedilir; `config.yaml` **ezilmemiş** kalır ve `profiles/` boş kalır |

### Bozuk yapılandırma

| Test | Ne doğrular |
|---|---|
| `test_broken_config_shows_message_not_traceback` | Hatalı `config.yaml` anlaşılır mesaj verir, yığın izi değil |
| `test_zero_crank_does_not_crash_validation` | Sıfır krank uyarı olarak görünür — `validate()` çökmez |

## Süre

Her `AppTest.run()` tüm betiği (dolayısıyla tüm sekmeleri) çalıştırır. Pahalı hesaplar
düğme arkasına alındığı için bir koşu ~2 saniyedir; `app_with_map` fixture'ı haritayı
modül başına bir kez hesaplar.

## Bağımlılıklar

Dış paketler: `pytest`, `streamlit`
Proje içi: `app.py`, [config.py](../files/config.md), `seatsim/ui/*`

## Kod Örneği

```bash
uv run pytest tests/test_app.py -v
uv run pytest tests/test_app.py -k reset -v     # bulgu #1 regresyonu
```

---
Son Güncelleme: 2026-09-27
Versiyon: 1.0.0
