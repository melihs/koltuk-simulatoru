# tests/test_config.py

## Amaç

`config.py`'nin yükleme, gidiş-dönüş, uzun biçim ayrıştırma, doğrulama ve profil
karşılaştırma davranışını doğrular. `config.py` kullanıcının **elle düzenlediği** şemayı
taşır; bozuk bir değer sessizce geçerse bütün sonuçlar yanlış olur, o yüzden doğrulama
kuralları tek tek denenir.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `cfg` | fixture | — | `config.yaml`'dan yüklenmiş, **değiştirilmeyen** yapılandırma | Oturum kapsamlı |
| `fresh_cfg` | fixture | — | Her test için taze kopya | Değiştirilebilir |
| `tmp_path` | pytest | — | Geçici dizin | Kaydetme testleri için |

## Çıkış

pytest sonucu — 53 test. Bölümler:

### Yükleme ve gidiş-dönüş

| Test | Ne doğrular |
|---|---|
| `test_load_defaults_match_dataclass` | `config.yaml` değerleri **dataclass varsayılanlarıyla aynı**. Ayrışırlarsa `config.yaml` silindiğinde program sessizce başka bir tasarımla çalışır — bu test `collision.exclude_pairs`'in boş varsayıldığı gerçek bir hatayı yakaladı |
| `test_dict_roundtrip` / `test_yaml_roundtrip` | `from_dict(to_dict(cfg))` ve YAML üzerinden gidiş-dönüş değeri korur |
| `test_save_load_roundtrip` | Kilit, güven rozeti ve not diske yazılıp geri okunur |
| `test_save_creates_parent_directory` | Olmayan dizin oluşturulur |
| `test_saved_yaml_has_header` | Kaydedilen dosya açıklayıcı başlıkla başlar |

### Uzun biçim (kilitleme)

| Test | Ne doğrular |
|---|---|
| `test_long_form_parsed` | `{value, locked, confidence, note}` ayrıştırılır |
| `test_long_form_inherits_default_how_to_measure` | Uzun biçim yazılırken kayıt defterindeki "nasıl ölçerim" bilgisi kaybolmaz |
| `test_short_form_is_unlocked` | Kısa biçim `locked=False` demektir |

### Hata yolları

| Test | Beklenen |
|---|---|
| `test_missing_file_raises_with_path` | `FileNotFoundError`, mesajda dosya adı |
| `test_unknown_key_raises_in_strict_mode` | `ValueError` |
| `test_unknown_key_ignored_in_lax_mode` | `strict=False` ile geçer |
| `test_non_dict_root_raises_type_error` | `TypeError` |
| `test_load_wraps_error_with_filename` | Hata mesajında dosya adı |
| `test_scalar_where_dict_expected_raises` | Anlaşılır `ValueError` |

### Doğrulama

`validate()` **hata fırlatmaz** — bu bir sözleşmedir ve testlerle korunur.

| Test | Ne doğrular |
|---|---|
| `test_initial_config_has_no_errors` | Başlangıç dosyası 0 ERROR üretir |
| `test_initial_config_warnings_are_the_known_ones` | [FINDINGS.md](../FINDINGS.md)'deki 4 çelişki UYARI olarak çıkar — sessiz kalmaz |
| `test_initial_config_reports_uncertain_count` | Tahmini parametre sayısı INFO olarak bildirilir |
| `test_non_positive_values_are_errors` | 8 ölçü için sıfır/negatif ERROR. **Sıfır krank `ZeroDivisionError` ile çöküyordu** — bu test yakaladı |
| `test_carried_fraction_out_of_range_is_error` · `test_follow_fraction_...` | Oranlar `[0,1]` dışında ERROR |
| `test_bad_backrest_mode_is_error` · `test_bad_outer_axis_is_error` | Geçersiz seçenek ERROR |
| `test_inconsistent_neutral_geometry_is_error` | Nötrde plaka yatay değilse ERROR, **gereken çubuk boyu mesajda yazılı** |
| `test_neutral_offset_changes_required_rod_length` | Krank nötr açısı değişince kontrol de değişir |
| `test_height_warning_disappears_when_limit_raised` | Uyarılar koşula bağlı, sabit değil |
| `test_rod_ratio_warning_disappears_when_ratio_ok` | Aynısı çubuk/krank oranı için |

### Yol ile erişim, üst veri, profil karşılaştırma

`get_by_path` / `set_by_path` iç içe yollarda çalışır; `uncertain_parameters()` yalnızca
TAHMİNİ olanları döndürür ve **hepsinde** not ya da ölçüm talimatı bulunur
(`test_uncertain_parameters_carry_how_to_measure` — üç parametrede eksikti, yakalandı);
`free_parameters()` kilitli olanları dışlar; `diff()` sayı, liste ve metin değişikliklerini
yakalar, kayan nokta gürültüsünü yoksayar.

### units.py dönüşümleri

`rpm_to_rad_s` / `rad_s_to_rpm` gidiş-dönüşü ve bilinen değer (60 rpm = 2π rad/s). Bu iki
fonksiyon Faz 3'te kullanılacak; şimdiden kilitlenmeleri ucuz.

## Bağımlılıklar

Dış paketler: `pytest`, `numpy`, `pyyaml`
Proje içi: [config.py](../files/config.md), [units.py](../files/units.md)

## Kod Örneği

```bash
uv run pytest tests/test_config.py -v
uv run pytest tests/test_config.py -k validate -v
```

---
Son Güncelleme: 2026-09-27
Versiyon: 1.0.0
