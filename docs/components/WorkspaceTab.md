# WorkspaceTab (Çalışma alanı sekmesi)

## Amaç

Pitch–roll düzleminde hangi açı kombinasyonlarına ulaşılabildiğini renkli harita olarak
gösterir; ulaşılamayan her bölgede **sınırlayan sebebi** ayrı renkle ayırır. Hedef
kısıtların sağlanıp sağlanmadığını açıkça raporlar.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `cfg` | `SeatConfig` | Evet | aktif profil | |
| Izgara çözünürlüğü | `int` | Hayır | `41` | 21 / 31 / 41 / 61 seçenekleri |
| Tarama aralığı | `float` | Hayır | `20.0` | ± derece, her iki eksende |
| Katman seçimi | `str` | Hayır | `"Sınırlayan sebep"` | Aşağıdaki katmanlar |

## Çıkış

İki katmanlı: **ucuz** kısım her zaman, **pahalı** kısım düğme arkasında.

| Kısım | Maliyet | Ne zaman |
|---|---|---|
| Kısıt tablosu + "KISIT İHLALİ" uyarısı | 8 ters kinematik, ~0,1 s | **Her zaman** |
| Harita + metrikler + sebep tablosu + takoz paneli | 41×41 için ~23 s | "Haritayı hesapla" düğmesiyle |

Kullanıcının en çok ihtiyaç duyduğu bilgi — hedeflerin sağlanıp sağlanmadığı — bir düğmenin
arkasında kalmaz; `Mechanism.target_report()` bunu ızgara taramadan verir.

Harita neden düğme arkasında: Streamlit her etkileşimde tüm sekmeleri yeniden çalıştırır.
Otomatik hesaplansaydı, Tasarım sekmesinde bir ölçüyü değiştirmek — haritaya bakılmıyor
olsa bile — uzun bir donma yaratırdı. **Ölçüldü: krank 4 → 7,5 değişiminde 41×41 harita
900 saniyeyi aştı.** Bkz. [Common.md](Common.md), `expensive_result()`.

Tasarım değişince sonuç **silinmez**, "bayat" olarak işaretlenir — eski harita görünmeye
devam eder, yalnızca güncel olmadığı bilinir. Izgara ayarı değişirse hangi ayarla
hesaplandığı yazılır.

Metrik satırı (harita hesaplandıktan sonra): kullanılabilir açı kombinasyonu sayısı ve
yüzdesi, maksimum pitch, maksimum roll.

## Katmanlar

| Katman | Ne gösterir | Sağlıklı görünüm |
|---|---|---|
| **Sınırlayan sebep** | Her noktada hangi limitin devreye girdiği | Ortada geniş yeşil bölge, hedef konturları içeride |
| **Transmisyon açısı** | Krank–çubuk açısı ısı haritası (iki krankın en kötüsü) | Çalışma bölgesinin tamamında 60°–120° |
| **Ölü nokta marjı** | `min(μ, 180−μ)` | Çalışma bölgesinde her yerde > 20° |

## Sebep renkleri

| Renk | `LimitReason` | Türkçe |
|---|---|---|
| Yeşil | `OK` | Uygun |
| Koyu gri | `UNREACHABLE_CIRCLE` | Erişim dışı — krank yetişmiyor |
| Açık gri | `UNREACHABLE_ROD` | Çubuk yanal açıklığı kapatamıyor |
| Kırmızı | `DEAD_POINT` | Krank ölü noktası |
| Turuncu | `ROD_END_ANGLE` | Rot başı sapma limiti |
| Sarı | `GIMBAL_ANGLE` | Kardan mafsalı açı limiti |
| Mor | `COLLISION` | Çarpışma |
| Mavi | `MECH_STOP` | Mekanik takoz |
| Pembe | `POT_RANGE` | Pot aralığı aşıldı (**pot kırılır**) |

## Hedef kısıt tablosu

Haritanın üstünde, geçme/kalma durumu ile:

**Beş** hedef ayrı ayrı denetlenir (pitch'in iki yönü, roll'ün iki yönü, eşzamanlı):

| Durum | Hedef | Ulaşılan |
|---|---|---|
| ❌ KISIT İHLALİ | pitch +10 | ulaşılan: +8,1° |
| ❌ KISIT İHLALİ | pitch −10 | ulaşılan: −8,3° |
| ❌ KISIT İHLALİ | roll +10 | ulaşılan: +9,0° |
| ❌ KISIT İHLALİ | roll −10 | ulaşılan: −9,0° |
| ❌ KISIT İHLALİ | combined 7+7 | dört köşeyi birlikte dener |

Eşzamanlı hedef **dört köşeyi** (`±7°, ±7°`) birlikte dener; yalnızca bir köşenin
ulaşılabilir olması yetmez.

Bir veya daha fazla hedef sağlanmıyorsa sayfanın başına şu uyarı kutusu düşer:

> **Bu tasarım hedeflerin bir kısmını sağlamıyor.** Bu beklenen bir durumdur — başlangıç
> ölçüleri bilinçli olarak değiştirilmemiştir. Sebebi ve çıkış yolları: `docs/FINDINGS.md`.
> Düzeltilmiş geometri Faz 4 (Optimizasyon) sekmesinde üretilecektir.

Ayrıca hedef dikdörtgenleri haritanın üzerine kesikli (eksen hedefleri) ve noktalı
(eşzamanlı hedef) çizgiyle çizilir — hedefin gerçek çalışma alanının neresine düştüğü
görsel olarak anlaşılır.

### Sebep tablosu: "Ne yapmalı" kolonu

Efsane yalnızca rengin adını değil, o sınırı açmak için **ne değiştirileceğini** de
yazar. Örneğin `POT_RANGE` için: *"Pot aralığı aşılıyor — pot kırılır. Krank boyunu
artırıp açı ihtiyacını düşürün veya potu dişli/kayışla yavaşlatın."* Haritada görünmeyen
sebepler tabloda da görünmez (`WorkspaceMap.reason_legend`).

## Sade dil

Harita üstünde: *"Bu harita, koltuğun hangi eğim kombinasyonlarına ulaşabildiğini
gösteriyor. Yeşil bölge çalışabilir alan. Renkli bölgelerde mekanizma o açıya ulaşamıyor
veya bir parça limitine takılıyor — rengin anlamı yandaki listede."*

Transmisyon haritası üstünde: *"Bu harita, motorun plakayı ne kadar verimli ittiğini
gösteriyor. 90°'ye yakın renkler iyi. Koyu bölgelerde motor aynı iş için daha fazla
zorlanır."*

## Bağımlılıklar

Dış paketler: `streamlit`, `plotly`, `numpy`
Proje içi: [geometry.py](../files/geometry.md), [config.py](../files/config.md),
[units.py](../files/units.md), `ui/common.py`

## Kod Örneği

```python
from seatsim.ui import workspace_tab
workspace_tab.render(st.session_state.cfg)
```

---
Son Güncelleme: 2026-09-27
Versiyon: 1.2.0
