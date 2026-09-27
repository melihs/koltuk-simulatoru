# config.py

## Amaç

`config.yaml` dosyasının şemasını tanımlar, yükler, doğrular ve kaydeder. Her parametrenin
değeri yanında birimini, güven rozetini ("TAHMİNİ" vb.), nasıl ölçüleceğini ve optimizasyonda
sabitlenip sabitlenmediğini taşır. Tasarım profillerinin karşılaştırılmasını sağlar.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `path` | `str \| Path` | Hayır | `"config.yaml"` | Yüklenecek YAML dosyası |
| `cfg` | `SeatConfig` | Evet (`save`) | — | Kaydedilecek yapılandırma |
| `strict` | `bool` | Hayır | `True` | `True` ise bilinmeyen anahtar `ValueError` fırlatır |

## Çıkış

| Fonksiyon | Çıktı |
|---|---|
| `load(path)` | `SeatConfig` — iç içe dataclass ağacı |
| `from_dict(raw, strict)` | `SeatConfig` — düz sözlükten kurar |
| `to_dict(cfg)` | `dict` — kilitli parametreler uzun biçimde; `from_dict(to_dict(cfg))` değeri korur |
| `to_yaml(cfg)` | `str` — YAML metni. Arayüzde `st.cache_data` **önbellek anahtarı** olarak da kullanılır |
| `save(cfg, path)` | `None`, YAML yazar (başlık yorumu eklenir) |
| `get_by_path(cfg, path)` / `set_by_path(cfg, path, value)` | Noktalı yol ile oku/yaz |
| `validate(cfg)` | `list[Issue]` — her biri `(severity, path, message)` |
| `diff(cfg_a, cfg_b)` | `list[Change]` — iki profil arasındaki farklar |
| `SeatConfig.uncertain_parameters()` | Rozeti `TAHMİNİ` olan parametrelerin listesi |
| `SeatConfig.free_parameters()` | `locked=False` olan, Faz 4'te optimize edilebilir parametreler |

Hatalar: dosya yoksa `FileNotFoundError`; şema uyuşmazlığında `ValueError` (dosya adı
mesaja eklenir); kök bir sözlük değilse `TypeError`. `validate()` hata **fırlatmaz**,
sorun listesi döndürür.

`to_yaml()` neden var: Streamlit'in `st.cache_data` önbelleği hashlenebilir bir anahtar
ister; `SeatConfig` bir dataclass ağacı olduğu için hashlenemez. Arayüz, pahalı
hesaplamaları (çalışma alanı haritası, tork haritası, en kötü durum taraması)
yapılandırmanın YAML metni üzerinden anahtarlar.

## Parametre grupları

Değerler `config.yaml`'da **cm ve derece** cinsindendir. `load()` bunları SI'ya çevirmez —
çevirim `Mechanism.from_config()` içinde `frames.to_internal()` ile yapılır.

### `geometry` — TASARIM

| Anahtar | Varsayılan | Açıklama |
|---|---|---|
| `base_plate.size_cm` | `[46, 50]` | Alt plaka genişlik × derinlik |
| `base_plate.thickness_cm` | `1.8` | |
| `base_plate.center_z_cm` | `4.0` | Merkezinin ileri-geri konumu |
| `top_plate.size_cm` | `[42, 42]` | |
| `top_plate.thickness_cm` | `1.8` | |
| `top_plate.center_offset_z_cm` | `3.0` | Merkezi mafsalın kaç cm önünde |
| `top_plate.underside_above_gimbal_cm` | `2.0` | Alt yüzeyi mafsal merkezinin kaç cm üstünde |
| `cushion.size_cm` | `[40, 40]` | |
| `cushion.thickness_cm` | `4.0` | |
| `gimbal.position_cm` | `[0, 13, 0]` | Dönme merkezi |
| `gimbal.outer_axis` | `pitch` | Tabana bağlı eksen — bkz. [frames.md](frames.md) |
| `rod_attach_cm` | `[18.2, -0.5, 20.5]` | Plaka çerçevesinde, mafsala göre. `x` işareti taraf başına çevrilir |
| `motor_shaft_cm` | `[18.2, 7.0, 24.5]` | Aynı kural |
| `crank.length_cm` | `4.0` | |
| `crank.neutral_offset_deg` | `0.0` | Nötrde krankın yataydan sapması. 0 = tam yatay, arkaya bakıyor |
| `rod.length_cm` | `5.5` | Rot başı merkezleri arası |

### `hardware` — TAHMİNİ (motorlar elde olduğunda ölçülmeli)

| Anahtar | Varsayılan | Açıklama |
|---|---|---|
| `gearbox_box_cm` | `[6, 8, 7]` | Redüktör kutusu `[x, z, y]` |
| `motor_cylinder_diameter_cm` | `6.4` | |
| `motor_cylinder_length_cm` | `13.0` | Mile dik, arkaya uzanır |
| `pot_bracket_cm` | `[4, 4, 2]` | |
| `gimbal_post_diameter_cm` | `5.0` | Mafsal direği, çarpışma ve eğilme hesabı için |
| `shaft_protrusion_cm` | `2.5` | **Mil ekseni boyunca yerleşim.** Redüktör kutusunun dış yüzü ile krank düzlemi arası. Krank kutunun **dışında** döner; kutuyu mil noktasına ortalamak krankı kutunun içinde döndürürdü. Motor silindiri (Ø6,4) kutudan (6,0) yana taştığı için bu değer 2 cm'in altına inerse krank motor gövdesine çarpar — bkz. [FINDINGS.md](../FINDINGS.md) B9 |
| `pot_offset_cm` | `2.0` | Pot braketi krank düzleminden ne kadar dışta |
| `user_box_cm` | `[40, 30, 50]` | Kullanıcı atalet kutusu `[genişlik, derinlik, boy]`. Kutu, yük modelinin kullandığı ağırlık merkezine ortalanır |

### `mass` — karışık, bkz. [ASSUMPTIONS.md](../ASSUMPTIONS.md)

| Anahtar | Varsayılan | Rozet |
|---|---|---|
| `user_kg` | `120` | TASARIM |
| `user_sweep_kg` | `[60, 90, 120]` | TASARIM |
| `carried_fraction` | `0.85` | TAHMİNİ |
| `plate_assembly_kg` | `8.0` | TAHMİNİ |
| `plate_com_cm` | `[0, 3.0, 4.0]` | TAHMİNİ — plaka çerçevesinde, mafsala göre |
| `seat_kg` | `12.0` | TAHMİNİ — yalnızca `backrest: tilting` |
| `backrest_mode` | `fixed` | TASARIM — `fixed` \| `tilting` |
| `backrest_follow_fraction` | `0.60` | TAHMİNİ — yalnızca `backrest: fixed` |
| `user_com_height_cm` | `25.0` | TAHMİNİ — minder üstünden |
| `user_com_fore_aft_cm` | `0.0` | TASARIM |
| `user_com_lateral_cm` | `0.0` | TASARIM |

### `limits`

| Anahtar | Varsayılan | Rozet |
|---|---|---|
| `rod_end_misalign_deg` | `12.0` | TAHMİNİ |
| `gimbal_max_deg` | `20.0` | TAHMİNİ |
| `deadpoint_margin_deg` | `20.0` | TASARIM |
| `clearance_min_cm` | `1.0` | TASARIM |
| `total_height_max_cm` | `18.0` | TASARIM |
| `pot.mechanical_range_deg` | `270.0` | TAHMİNİ |
| `pot.mount_offset_deg` | `0.0` | TASARIM — pot elektriksel merkezi nötrden kaç derece kaydırılmış |

### `stops`

| Anahtar | Varsayılan | Açıklama |
|---|---|---|
| `positions_cm` | `[[5.5,18], [-5.5,18], [18,-16], [-18,-16]]` | `(x, z)` çiftleri, alt plaka üstünde. Ön takozlar içe alınmak zorunda: motor takımı `\|x\| = 9,5…15,9 cm` bandını kaplıyor ([FINDINGS.md](../FINDINGS.md) B8) |
| `top_height_cm` | `[10.07, 10.07, 7.78, 7.78]` | Takoz **başına** üst yüzey yüksekliği. Tek sayı verilirse hepsine uygulanır. `StopsCfg.heights()` listeye normalize eder; uzunluk uyuşmazsa `ValueError`. Bkz. [FINDINGS.md](../FINDINGS.md) B5 |
| `size_cm` | `[4, 4]` | Yatay kesit |

Takoz yüksekliğini elle uydurmayın: konumu değiştirdiğinizde
`Mechanism.suggest_stop_heights_cm(12.0)` gereken yükseklikleri hesaplar,
`Mechanism.stop_engagement_deg()` ise her takozun gerçekte hangi açıda devreye girdiğini
raporlar. Sabit bir ±12° varsayımı konum değişince yanlış açıya kayar.

### `targets` — TASARIM (kısıt hedefleri)

| Anahtar | Varsayılan |
|---|---|
| `pitch_deg` | `10.0` |
| `roll_deg` | `10.0` |
| `combined_deg` | `[7.0, 7.0]` |
| `torque_safety_factor` | `2.0` |

### `motor`, `power`, `controller` — Faz 3

Şema tanımlı, değerler [ASSUMPTIONS.md](../ASSUMPTIONS.md) §1'de. `controller` bölümü
`SMC3.ino` görülene kadar **boş bırakılmıştır**; varsayımla doldurulmaz.

## Kilitleme (`locked`)

Her sayısal parametre uzun biçimde de yazılabilir:

```yaml
crank:
  length_cm:
    value: 4.0
    locked: true          # "elimde var" — Faz 4 optimizasyonunda değişmez
    confidence: OLCULDU
    note: "Mevcut krank, kumpasla ölçüldü"
```

Kısa biçim (`length_cm: 4.0`) `locked: false`, `confidence: TASARIM` anlamına gelir.
Arayüzdeki "sabitle (elimde var)" kutusu bu alanı yazar.

## Doğrulama kuralları

`validate()` şunları denetler ve **hata fırlatmaz, listeler**:

| Ağırlık | Kural |
|---|---|
| `ERROR` | Negatif uzunluk, sıfır krank/çubuk boyu, `carried_fraction ∉ [0,1]` |
| `ERROR` | Nötr pozda `\|P − C\| ≠ rod.length_cm` (geometri kendi içinde tutarsız) |
| `WARN` | Toplam yükseklik `limits.total_height_max_cm`'i aşıyor |
| `WARN` | Çubuk/krank oranı < 2 (ölü noktaya yakın çalışma, [FINDINGS.md](../FINDINGS.md) A1) |
| `WARN` | Motor mili üst plaka izdüşümünün dışında |
| `WARN` | Redüktör kutusu yan yönde izdüşümün dışında |
| `INFO` | Rozeti `TAHMİNİ` olan parametre sayısı |

Başlangıç `config.yaml` dosyası **4 WARN + 1 INFO üretir** — bu beklenen davranıştır, bkz.
[FINDINGS.md](../FINDINGS.md).

## Bağımlılıklar

Dış paketler: `pyyaml`, `numpy`
Proje içi: [units.py](units.md)

`config.py` hiçbir çekirdek modülü import etmez.

## Kod Örneği

```python
from seatsim import config

cfg = config.load("config.yaml")

for issue in config.validate(cfg):
    print(f"[{issue.severity}] {issue.path}: {issue.message}")

# Profil karşılaştırma
opt = config.load("profiles/optimized.yaml")
for ch in config.diff(cfg, opt):
    print(f"{ch.path}: {ch.old} → {ch.new}")

cfg.geometry.crank.length_cm = 7.0
config.save(cfg, "profiles/crank7.yaml")
```

---
Son Güncelleme: 2026-09-12
Versiyon: 1.2.0
