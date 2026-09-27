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

Kısıt tablosu + üç metrik + seçilen katmanın haritası + sebep açıklama tablosu + takoz
paneli. Hesap `Mechanism.workspace_map()` çağrısıyla yapılır; sonuç `st.cache_data` ile
**yapılandırmanın YAML metni üzerinden** anahtarlanarak önbelleklenir (`config.to_yaml()`
— bkz. [config.md](../files/config.md)), yani parametre değişmedikçe yeniden hesaplanmaz.

Ölçülen süre: 41×41 için ~23 s (ilk hesap), sonrası önbellekten anında.

Metrik satırı: kullanılabilir açı kombinasyonu sayısı ve yüzdesi, maksimum pitch,
maksimum roll.

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
Son Güncelleme: 2026-09-12
Versiyon: 1.1.0
