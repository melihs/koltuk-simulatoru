# Koltuk Simülatörü — 2DoF Hareketli Koltuk Tasarım Aracı

2 serbestlik dereceli (pitch + roll) hareketli koltuğu **atölyede kesip delmeden önce**
bilgisayarda doğrulamak ve ölçülerini optimize etmek için geliştirilmiş bir araç.

Mekanizma: sabit koltuğun üstüne konan alt plaka, ortada kardan mafsalı üzerinde duran üst
plaka + minder, ön iki köşeden itme çubuklarıyla iki adet 24 V silecek motorunun krank
koluna bağlı. Geri besleme mil ucundaki potansiyometrelerle, kontrol Arduino UNO + SMC3
firmware + 2× BTS7960 ile.

## Kurulum

Gereksinim: Python 3.11 veya 3.12 (3.13+ henüz desteklenmiyor — `streamlit` ve `pymoo`
tekerlekleri yok). [uv](https://docs.astral.sh/uv/) önerilir.

```bash
git clone <depo>
cd koltuk-simulatoru

uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
```

`pip` ile:

```bash
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Faz 4 ve 6 bağımlılıkları (şimdilik gerekmiyor):

```bash
uv pip install -e ".[optimize,report]"
```

## Çalıştırma

```bash
uv run streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır. Windows ve macOS'ta aynı komut çalışır.

Testler ve lint:

```bash
uv run pytest -v                      # 153 test, ~60 saniye
uv run pytest -k regression -v        # bilinen tasarım sınırlarını doğrulayan testler
uv run ruff check seatsim/ tests/ app.py
```

Kalite kontrol zinciri: `/quality-check`

## Ekranlar

| Sekme | Ne işe yarar |
|---|---|
| **Tasarım** | Tüm ölçüleri girdiğin yer. Sağda mekanizmanın 3D görünümü; pitch/roll kaydırıcılarıyla canlı hareket ettirirsin. Çarpışan veya limite yaklaşan parçalar renk değiştirir. Profil kaydedip iki tasarımı karşılaştırabilirsin. |
| **Çalışma alanı** | Koltuğun hangi eğim kombinasyonlarına ulaşabildiğini renkli harita olarak gösterir. Ulaşamadığı yerlerde **sebebini** renkle ayırır: krank yetişmiyor, ölü nokta, rot başı açısı, mafsal limiti, çarpışma, takoz, pot aralığı. |
| **Yükler** | Her motorun ne kadar tork vermesi gerektiğini, çubuk ve mafsal kuvvetlerini hesaplar. Tüm senaryoları tarayıp **en kötü durumu** bulur ve emniyet katsayısını söyler. Ters sarkaç etkisini ayrı gösterir. |
| **Dinamik test** | *(Faz 3 — `SMC3.ino` bekleniyor)* Motor, PID ve mekanizmayı zamanda simüle eder. |
| **Optimizasyon** | *(Faz 4)* Ölçüleri otomatik iyileştirir, Pareto cephesi üretir, ±2 mm yapım hatasına duyarlılığı gösterir. |
| **PID ayarı** | *(Faz 6)* SMC3Utils'e girilecek Kp/Ki/Kd değerlerini önerir. |
| **Rapor** | *(Faz 6)* Atölye ölçü listesi ve ölçülü 2D çizimlerle Markdown + PDF rapor üretir. |

Her grafiğin üstünde bir cümlelik "bu ne gösteriyor" açıklaması ve sağlıklı değer aralığı
vardır. Emin olunmayan her parametrenin yanında **TAHMİNİ** rozeti ve "nasıl ölçerim" notu
bulunur.

## Önce bunu oku

### Başlangıç ölçüleri, hedeflerin bir kısmını sağlamıyor

Bu **bilinçli** bir durumdur. Senin verdiğin ölçüler korundu, hiçbiri sessizce
değiştirilmedi. Program bunları açıkça "KISIT İHLALİ" olarak raporlar:

| Hedef | Gerçek | Bağlayan limit |
|---|---|---|
| Pitch +10° | **+8,1°** | krank ölü noktası |
| Pitch −10° | **−8,3°** | üst plaka ↔ redüktör kutusu çarpışması |
| Roll ±10° | **±9,0°** | rot başı sapma açısı |
| Pitch 7° + Roll 7° eşzamanlı | **ulaşılamıyor** | krank yetişmiyor |
| Toplam yükseklik ≤ 18 cm | **20,8 cm** | — |

41×41 ızgarada 1681 açı kombinasyonundan yalnızca **177'si (%10,5)** kullanılabilir.

Sebep: çubuk/krank oranı 5,5 / 4 = 1,375, çok düşük. Ayrıntı, sayısal kanıt ve çıkış
yolları: **[docs/FINDINGS.md](docs/FINDINGS.md)**

### Motorun stall torkunu ölç — her şey buna bağlı

Program, mevcut 4 cm krankla bile en kötü durumda **19,7 N·m** gerektiğini buluyor →
emniyet katsayısı **1,52**, hedef 2,0. En kötü durum saf pitch'te değil, **eşzamanlı
pitch + roll**'de: orada bir çubuğun moment kolu küçülüyor ve yük büyük ölçüde tek çubuğa
biniyor. Çalışma alanını büyütmek için krank uzatılırsa tork daha da artıyor.

Motor gerçekte 40 N·m veriyorsa katsayı 2,0'ye çıkıyor. **Ölçmeden bu projenin yapılabilir
olup olmadığı bilinmiyor.** Ölçüm yöntemi (10 cm kol + bagaj kantarı):
**[docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md)** §1

### Güç kaynağı iki motoru stall'da besleyemiyor

2 × 20 A = 40 A stall akımına karşı LRS-350-24 yalnızca 14,6 A sürekli verir. Sigortalar
(2 × 20 A) kaynağı korumuyor — kaynak, sigortalardan önce devreye giren asıl limit.
Faz 3'te modellenecek.

## Dokümantasyon

```
docs/
├── ARCHITECTURE.md        mimari, katmanlar, birim politikası, koordinat sistemi
├── ASSUMPTIONS.md         her varsayım + güven rozeti + nasıl ölçülür
├── FINDINGS.md            başlangıç tasarımının kısıt analizi (A1–A4, B1–B9)
├── files/                 her kaynak dosya için ayrı doküman
├── components/            her arayüz sekmesi için ayrı doküman
└── tests/                 her test dosyası için ayrı doküman
```

Okuma sırası önerisi:

```
ARCHITECTURE.md  →  FINDINGS.md  →  ASSUMPTIONS.md  →  files/frames.md  →  files/geometry.md
```

Yeni bir geliştirmeye başlarken önce `ARCHITECTURE.md`, sonra ilgili `files/*.md` okunur.

## Birimler

| Nerede | Uzunluk | Açı |
|---|---|---|
| `config.yaml`, arayüz, rapor | **cm** | **derece** |
| Kodun içi | **m** | **radyan** |

Dönüşüm yalnızca `units.py` ve `frames.py` üzerinden yapılır.

Koordinat sistemi dışarıda `x = sağ, y = yukarı, z = ileri` (senin tanımın), içeride sağ el
`X = sağ, Y = ileri, Z = yukarı`. Nedeni: senin sıralaman sol el sistemidir ve moment
hesaplarında sessiz işaret hatası üretir. Ayrıntı: [docs/files/frames.md](docs/files/frames.md)

**Pitch pozitif = ön yukarı. Roll pozitif = sağ taraf yukarı.**

## Proje durumu

| Faz | Kapsam | Durum |
|---|---|---|
| 0 | Ortam, dokümantasyon | ✅ |
| 1 | Kinematik, 3D görünüm, çalışma alanı haritası | ✅ |
| 2 | Statik yük ve tork analizi | ✅ |
| 3 | Motor, SMC3 kontrolcü, dinamik simülasyon | ⏸ **`SMC3.ino` bekleniyor** |
| 4 | Optimizasyon ve duyarlılık analizi | ⏳ |
| 5 | Motion cueing ve telemetri oynatma | ⏳ |
| 6 | PID otomatik ayarı ve rapor | ⏳ |

Faz 3, `SMC3.ino` kaynak dosyası görülmeden başlatılmaz — PID formülü, ölçekleme ve limit
mantığı varsayımla modellenmez, çünkü amaç bulunan Kp/Ki/Kd değerlerinin doğrudan
SMC3Utils'e girilebilmesi.

## Yapılandırma

Tüm parametreler `config.yaml`'da. Arayüzden düzenlenir, `profiles/` altına kaydedilir,
iki profil yan yana karşılaştırılır.

Satın aldığın bir parçanın ölçüsünü "sabitle (elimde var)" kutusuyla kilitlersen Faz 4
optimizasyonu o ölçüye dokunmaz.

Şema: [docs/files/config.md](docs/files/config.md)

---
Son Güncelleme: 2026-09-12
Versiyon: 1.2.0
