# Mimari

## Amaç

2 serbestlik dereceli (pitch + roll) hareketli koltuğun kinematiğini, statik yüklerini,
dinamiğini ve kontrolünü simüle eden, tasarım ölçülerini optimize eden Streamlit
uygulamasının genel yapısını tanımlar. Hangi modülün neyi bildiğini, katman sınırlarını ve
birim politikasını belirler.

## Giriş Parametreleri

Bu doküman kod içermez; sistemin tamamının girdisi tek bir `config.yaml` dosyasıdır.

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `config.yaml` | dosya | Hayır | proje kökündeki dosya | Tüm tasarım, yük, motor ve kontrol parametreleri. Şeması: [config.md](files/config.md) |

## Çıkış

Streamlit arayüzü (8 sekme), `profiles/*.yaml` tasarım profilleri ve (Faz 6'dan sonra)
`reports/*.md` + `reports/*.pdf` rapor dosyaları.

## Bağımlılıklar

Dış paketler: `numpy`, `scipy`, `plotly`, `streamlit`, `pyyaml`, `pandas`.
Opsiyonel: `pymoo` (Faz 4), `reportlab` (Faz 6). Test: `pytest`.

---

## Fiziksel sistem

Sabit koltuğun üstüne konan **alt plaka**; ortada bir **kardan mafsalı** üzerinde duran
**üst plaka** + minder. Üst plakanın ön sağ ve ön sol köşesi birer **itme çubuğu** ile
birer **krank koluna**, kranklar da birer **24V silecek motoruna** bağlı. İki krank aynı
yöne dönerse pitch, zıt yöne dönerse roll oluşur. Geri besleme: mil ucundaki tek turlu
potansiyometreler. Kontrol: Arduino UNO + SMC3 firmware + 2× BTS7960.

Sistem **ters sarkaç** karakterindedir: ağırlık merkezi mafsalın üstündedir, eğim arttıkça
eğimi daha da artıran bir moment doğar. Bu, hem yük analizinin hem PID ayarının merkezindedir.

## Katmanlar

```
                 ┌──────────────────────────────────────────────┐
   ARAYÜZ        │  app.py  +  seatsim/ui/*.py                  │
   (cm, derece)  │  Streamlit sekmeleri, Plotly grafikleri      │
                 └───────────────┬──────────────────────────────┘
                                 │  units.py / frames.py  ← TEK DÖNÜŞÜM NOKTASI
                 ┌───────────────▼──────────────────────────────┐
   ÇEKİRDEK      │  geometry · loads · motor · controller       │
   (SI: m, rad,  │  dynamics · cueing · optimize · report       │
    kg, N, s)    │                                              │
                 └───────────────┬──────────────────────────────┘
                 ┌───────────────▼──────────────────────────────┐
   TEMEL         │  config.py (şema) · bodies.py · collision.py │
                 └──────────────────────────────────────────────┘
```

**Katman kuralı:** Çekirdek modüller `streamlit`, `plotly` veya cm/derece bilmez.
Arayüz modülleri fizik hesabı yapmaz. Bu kuralın ihlali `/quality-check` adım 6'da yakalanır.

### Bağımlılık yönü

`ui → (geometry, loads, dynamics, optimize, report) → (bodies, collision, frames) → (config, units)`

Ters yönde import yoktur. `config.py` hiçbir çekirdek modülü import etmez.

## Birim politikası

| Katman | Uzunluk | Açı | Kütle | Kuvvet |
|---|---|---|---|---|
| `config.yaml`, arayüz, rapor | **cm** | **derece** | kg | N |
| Çekirdek modüller | **m** | **radyan** | kg | N |

Dönüşüm **yalnızca** `units.py` ve `frames.py` üzerinden yapılır. Çekirdek modüllerin içinde
`* 0.01` veya `math.radians` görülmez. Parametre isimlerinde birim son eki zorunludur:
`crank_length_cm`, `pitch_limit_deg`, `rod_length_cm`.

## Koordinat sistemi

Kullanıcının tanımladığı sistem **x = sağ, y = yukarı, z = ileri**. Bu bir **sol el
sistemidir** (standart sağ el sırası `sağ, ileri, yukarı` olurdu). Sol el sisteminde çapraz
çarpım, moment ve atalet tensörü hesapları sessiz işaret hatası üretir.

Karar:

- **Dış sistem** (`config.yaml`, arayüz, rapor, atölye ölçü listesi): kullanıcının düzeni
  korunur — `(x=sağ, y=yukarı, z=ileri)`, cm.
- **İç sistem** (tüm çekirdek hesaplar): sağ el `(X=sağ, Y=ileri, Z=yukarı)`, metre.
- Dönüşüm bir bileşen takasıdır: `X=x, Y=z, Z=y`, ardından `× 0.01`.
- Tek giriş/çıkış noktası: `frames.to_internal()` / `frames.from_internal()`.

Ayrıntı ve işaret tanımları: [frames.md](files/frames.md).

## Modüller

| Modül | Sorumluluk | Faz |
|---|---|---|
| `units.py` | Ölçek dönüşümleri (cm↔m, derece↔radyan) | 0 |
| `config.py` | `config.yaml` şeması, yükle/kaydet/doğrula, profil karşılaştırma | 0 |
| `frames.py` | Koordinat sistemi dönüşümü, rotasyon matrisleri, işaret tanımları | 1 |
| `bodies.py` | Mekanizmanın geometrik gövdelerini (kutu/kapsül) verilen poza göre üretir | 1 |
| `collision.py` | İlkel cisimler arası minimum mesafe | 1 |
| `geometry.py` | Ters/ileri kinematik, Jacobian, limit denetimi, çalışma alanı taraması | 1 |
| `loads.py` | Statik kuvvet/moment çözümü, tork, emniyet katsayısı, en kötü durum taraması | 2 |
| `motor.py` | Tork-hız eğrisi, elektriksel model, sonsuz vida kilitlenmesi | 3 |
| `controller.py` | SMC3 firmware'inin birebir ayrık modeli | 3 |
| `dynamics.py` | Zaman entegrasyonu (RK4), motor + kontrolcü + mekanizma birleşik | 3 |
| `optimize.py` | NSGA-II Pareto, tek amaçlı DE, duyarlılık analizi | 4 |
| `cueing.py` | Motion cueing filtreleri, test profilleri, CSV telemetri | 5 |
| `report.py` | Markdown + PDF rapor, atölye ölçü listesi, 2D çizimler | 6 |
| `ui/common.py` | Mesh üretimi, bildirimsel parametre editörü, durum rozetleri, pahalı hesapların kapısı — [Common.md](components/Common.md) | 1 |
| `ui/design_tab.py` | Tasarım sekmesi — [DesignTab.md](components/DesignTab.md) | 1 |
| `ui/workspace_tab.py` | Çalışma alanı sekmesi — [WorkspaceTab.md](components/WorkspaceTab.md) | 1 |
| `ui/loads_tab.py` | Yükler sekmesi — [LoadsTab.md](components/LoadsTab.md) | 2 |
| `ui/pending_tab.py` | Henüz yapılmamış fazların sekmeleri — [PendingTabs.md](components/PendingTabs.md) | 1 |

## Veri akışı (Faz 1–2)

```
config.yaml
    │
    ▼
config.load()  ──►  SeatConfig (dataclass, cm/derece)
    │
    ▼ frames.to_internal()
Mechanism (geometry.py, SI)
    │
    ├─► ik(pitch, roll) ──► CrankSolution(theta, transmission_angle, limits, reason)
    │                              │
    │                              ▼
    ├─► bodies.build(pose) ──► [Box|Capsule] ──► collision.min_distances()
    │
    ├─► workspace_map() ──► ızgara + sınırlayan sebep kodu   ──► WorkspaceTab
    │
    └─► loads.solve(pose, MassModel) ──► StaticResult         ──► LoadsTab
                                          (çubuk kuvvetleri, mafsal tepkisi,
                                           motor torkları, emniyet katsayısı)
```

## Faz durumu

| Faz | Kapsam | Durum |
|---|---|---|
| 0 | Ortam, dizin yapısı, dokümantasyon | ✅ Tamamlandı |
| 1 | Kinematik, 3D görünüm, çalışma alanı haritası | ✅ Tamamlandı |
| 2 | Statik yük ve tork analizi | ✅ Tamamlandı |
| 3 | Motor, SMC3 kontrolcü, dinamik simülasyon | **Bloke — `SMC3.ino` bekleniyor** |
| 4 | Optimizasyon ve duyarlılık analizi | Beklemede |
| 5 | Motion cueing ve telemetri oynatma | Beklemede |
| 6 | PID otomatik ayarı ve rapor | Beklemede |

Faz 3, tanım gereği `SMC3.ino` kaynak dosyası görülmeden başlatılmaz — PID formülü,
ölçekleme ve limit mantığı varsayımla modellenmez.

## Bilinen tasarım çelişkileri

Başlangıç `config.yaml` değerleri, tanımdaki kısıtların bir kısmını **sağlamıyor**. Bu
bilinçli bir durumdur: kullanıcı kararıyla orijinal ölçüler korunmuş, düzeltme Faz 4
optimizasyonuna bırakılmıştır. Program bunları "KISIT İHLALİ" olarak raporlar.
Ayrıntı ve sayısal kanıt: [FINDINGS.md](FINDINGS.md).

## Kalite standardı

| Araç | Yapılandırma | Komut |
|---|---|---|
| `ruff` | `pyproject.toml` → `[tool.ruff]`; `E, F, W, I, UP, B, C4, ISC, RET, SIM` | `uv run ruff check seatsim/ tests/ app.py` |
| `pytest` | `pyproject.toml` → `[tool.pytest.ini_options]` | `uv run pytest` |

Kural seti bilinçli olarak `pyproject.toml`'a yazılmıştır: `/quality-check` her makinede
aynı sonucu vermeli, çalıştıranın global ruff yapılandırmasına bağlı olmamalı.

Bilinçli muafiyetler: `C408` (`dict(...)` kwarg biçimi okunurluğu artırıyor), `E501`
(satır uzunluğu insan kararı), `SIM108` (üçlük ifade her zaman daha okunur değil).

## Test stratejisi

- **Analitik testler:** nötr poz, saf pitch/roll simetrisi, FK∘IK özdeşliği, Jacobian
  doğrulaması — tam sayısal beklenti ile.
- **Kabul testi:** tanım §2.2'deki elle hesap (4,3 N·m) ±%2 içinde tutturulur
  (ölçülen fark %0,01).
- **Regresyon testi:** başlangıç geometrisinin ulaşamadığı açılar ve en kötü durum
  değerleri sabitlenir; geometri değişirse test uyarır.
- **Fizik tutarlılık testleri:** doğrusallık, simetri, kuvvet ve moment dengesi, ters
  sarkaç sertliğinin analitik `W · h` değerini tutturması.
- **Çapraz doğrulama:** iki bağımsız yöntem (doğrudan moment vs sanal iş/Jacobian) aynı
  torku vermeli. Ölçülen fark `9e-16` N·m.

Toplam **231 test**, satır kapsamı **%94** (çekirdek modüller %96–100). Test dokümanları:
`docs/tests/`.

| Dosya | Test | Neyi korur |
|---|---|---|
| `test_geometry.py` | 53 | Kinematik, Jacobian, simetri, limitler, dal sabitliği |
| `test_config.py` | 53 | Şema, doğrulama kuralları, gidiş-dönüş |
| `test_loads.py` | 44 | Statik çözüm, çapraz doğrulama, ters sarkaç |
| `test_collision.py` | 34 | Mesafe fonksiyonları ve hata sınırları |
| `test_app.py` | 24 | Arayüzün baştan sona çalışması |
| `test_frames.py` | 23 | Koordinat ve işaret sözleşmeleri |

### Pahalı hesaplar arayüzde kapı arkasındadır

Streamlit her etkileşimde tüm betiği (dolayısıyla tüm sekmeleri) yeniden çalıştırır.
Çalışma alanı haritası ve tork haritası bu yüzden açık bir düğmeyle hesaplanır ve sonuç,
üretildiği yapılandırmanın YAML metniyle birlikte oturum durumunda saklanır; tasarım
değişince "bayat" işaretlenir ama silinmez. Ölçüldü: krank 4 → 7,5 değişiminde 41×41
harita **900 saniyeyi aştı** — otomatik hesaplansaydı tek bir ölçü değişikliği arayüzü
kilitlerdi. Ucuz olan "KISIT İHLALİ" tablosu (8 ters kinematik) her zaman görünür.
Ayrıntı: [components/Common.md](components/Common.md).

### Çapraz doğrulama neden en değerli test

Geliştirme sırasında `frames.roll_axis()` ters işaret döndürüyordu. Bu hata **çubuk
kuvvetlerini etkilemiyordu** (denklemin iki tarafı da işaret değiştirdiği için) ve elle
yapılan saf pitch kontrolünde roll satırı sıfır olduğu için görünmüyordu. Yalnızca
`test_virtual_work_matches_direct_moment` yakaladı. Ayrıntı:
[files/frames.md](files/frames.md) — "Roll ekseninin işareti".

Benzer şekilde, ters kinematikte dal seçimi "bir önceki çözüme en yakın kök" olarak
yapıldığında ızgara adımı ölü nokta bandını atlayıp mekanizmayı aynalanmış dala
geçiriyor ve **9600 N·m** gibi fizik dışı torklar üretiyordu. Dal artık montajda
sabitlenir. Ayrıntı: [files/geometry.md](files/geometry.md) — Adım 5.

---
Son Güncelleme: 2026-09-27
Versiyon: 1.2.0
