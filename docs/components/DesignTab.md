# DesignTab (Tasarım sekmesi)

## Amaç

Tüm tasarım parametrelerini düzenlenebilir biçimde sunar ve mekanizmayı Plotly 3D olarak
canlı gösterir. Pitch/roll kaydırıcılarıyla mekanizma hareket ettirilir; limite yaklaşan
veya çarpışan parçalar renk değiştirir. Profil kaydetme/yükleme ve karşılaştırma burada yapılır.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `cfg` | `SeatConfig` | Evet | oturum durumundaki aktif profil | Düzenlenen yapılandırma |

Parametre listesi `common.GROUPS` içinde bildirimsel olarak tanımlıdır (`Group` ve
`Param` dataclass'ları): yol, etiket, birim, adım, yardım metni, kilitlenebilirlik ve
liste parametreleri için **bileşen etiketleri**. Yeni bir parametreyi arayüze eklemek
için bu listeye bir satır yazmak yeterlidir. Ayrıntı: [Common.md](Common.md).

Bileşen etiketleri olmadan etiket yalnızca ilk bileşene düşerdi: "Mafsal yüksekliği (y)"
yazan kutu aslında `x`'i düzenler, kullanıcı yüksekliği değiştirdiğini sanırken mafsalı
yana kaydırırdı.

Kullanıcı girdileri (widget):

| Widget | Aralık | Birim | Açıklama |
|---|---|---|---|
| Pitch kaydırıcısı | −20 … +20 | derece | + = ön yukarı |
| Roll kaydırıcısı | −20 … +20 | derece | + = sağ yukarı |
| Parametre alanları | grup bazlı | cm / derece / kg | [config.md](../files/config.md) şeması |
| "Sabitle (elimde var)" | — | — | Parametreyi Faz 4 optimizasyonunda kilitler |
| Profil adı | metin | — | `profiles/<ad>.yaml`. Yalnızca `[\w-]`, en fazla 64 karakter — **yol ayracı kabul edilmez**: `../config` gibi bir ad proje kökündeki `config.yaml`'ı ezerdi |

## Çıkış

- Güncellenmiş `SeatConfig` (oturum durumuna yazılır)
- `profiles/*.yaml` dosyaları
- Ekranda: 3D görünüm, canlı durum kartı, doğrulama uyarıları listesi

Hata: geçersiz parametre girildiğinde `config.validate()` sorunları kırmızı kutuda
gösterilir; 3D görünüm son geçerli duruma düşer.

## Ekran düzeni

```
┌─ Sol kolon (parametreler) ────────┬─ Sağ kolon (3D + durum) ──────────────┐
│ Doğrulama uyarıları (ERROR/WARN)  │  [Pitch ▁▂▃▄▅]  [Roll ▁▂▃▄▅]         │
│ ▸ Mafsal ve plakalar              │                                       │
│ ▸ Krank, çubuk ve motor mili      │        ╭──────────────────╮           │
│ ▸ Bağlantı noktaları              │        │  Plotly 3D       │           │
│ ▸ Donanım ölçüleri      2 tahmini │        │  mekanizma       │           │
│ ▸ Kütle ve kullanıcı    5 tahmini │        ╰──────────────────╯           │
│ ▸ Limitler                        │                                       │
│ ▸ Takozlar (mekanik stop)         │  "Bu konumun durumu" tablosu:         │
│ ▸ Motor                 4 tahmini │   🟢 Krank açıları    +26,9°/+26,9°   │
│ ▸ Hedefler                        │   🟢 Transmisyon açısı 74°/74°        │
│ ─────────────────────────────     │   🟢 Ölü nokta marjı   74°            │
│ Profiller                         │   🟢 Rot başı sapması  0,0°           │
│ [Profili kaydet] [Profili yükle]  │   🟢 Kardan mafsalı    5,0°           │
│ [config.yaml'a yaz] [Karşılaştır] │   🟢 Pot açısı         27°            │
│ [Başlangıç değerlerine dön]       │   🟢 En dar boşluk     1,3 cm         │
│                                   │   🟢 Takoz teması      yok            │
│                                   │  ▸ Montaj boşlukları (poza bağlı değil)│
│                                   │  ▸ Takozlar — hangi açıda devreye girer│
└───────────────────────────────────┴───────────────────────────────────────┘
```

Grup başlıklarında kaç **tahmini** parametre olduğu yazılır — ölçülmesi gereken yerler
kapalı bölümün içinde kaybolmasın diye.

## Renk kuralı

`bodies.py` renk bilmez; renklendirme burada yapılır.

| Durum | Renk | Koşul |
|---|---|---|
| Normal | Açık gri / ahşap tonu | Tüm limitler rahat |
| Dikkat | Turuncu | Mesafe `clearance_min` ile `2 × clearance_min` arasında, veya ölü nokta marjı `margin` ile `1,5 × margin` arasında |
| Sorun | Kırmızı | Çarpışma, limit aşımı |
| Sabit parçalar | Koyu gri | `group == "static"` |

Durum kartındaki her satırın yanında **🟢 İYİ / 🟠 DİKKAT / 🔴 SORUN** rozeti ve hangi
aralığın sağlıklı olduğunu söyleyen bir cümle bulunur.

### İki ayrı boşluk kavramı

| Bölüm | Ne gösterir |
|---|---|
| "En dar hareket boşluğu" (durum tablosunda) | **Hareketli** bir gövde içeren en dar çift. Çalışma alanı limiti budur. |
| "Montaj boşlukları" (açılır bölüm) | İki gövdesi de alt plakaya **sabit** olan çiftler. Poza bağlı değildir — montaj/imalat konusu. |

Bu ayrım yapılmazsa, alt plakaya sabit iki parçanın darlığı tüm çalışma alanını kırmızıya
boyar ve sebebi pozla hiç ilgisi olmayan bir şey olur. Bkz.
[collision.md](../files/collision.md).

### Takoz paneli

Her takozun konumu, üst yüzey yüksekliği ve **gerçekte hangi açıda devreye girdiği**
listelenir. Hedef bir açı girip "Yükseklikleri bu açıya göre hesapla" düğmesine basmak
`Mechanism.suggest_stop_heights_cm()` çağırır ve yükseklikleri yazar — takoz konumunu
değiştirdikten sonra yüksekliği elle uydurmak gerekmez.

### Profil paneli ve widget durumu

Profiller `profiles/*.yaml` altına kaydedilir; "config.yaml'a yaz" ana yapılandırmayı
günceller; "Başlangıç değerlerine dön" diskten yeniden yükler; "Karşılaştır"
`config.diff()` çıktısını tablo olarak gösterir.

Profil adı `[\w-]` ile sınırlıdır ve en fazla 64 karakterdir. **Yol ayracı kabul
edilmez**: `../config` gibi bir ad, doğrulanmasaydı proje kökündeki `config.yaml`'ı
ezerdi.

> Yapılandırmayı değiştiren **her** yol `common.replace_config()`'ten geçer. Streamlit'te
> `key` verilen bir widget'ın durumu kalıcıdır ve `value=` argümanını **ezer**; bu
> fonksiyon bayat widget anahtarlarını silmeseydi "Profili yükle", "Başlangıç değerlerine
> dön" ve "Yükseklikleri hesapla" düğmeleri **hiçbir şey yapmazdı** — başarı mesajı çıkar,
> değer değişmezdi. `tests/test_app.py` üçünü de regresyon olarak kilitler.

## Sade dil kuralı

Her parametre grubunun başında bir cümlelik açıklama, her belirsiz parametrenin yanında
**TAHMİNİ** rozeti ve tıklanınca açılan "nasıl ölçerim" notu vardır
([ASSUMPTIONS.md](../ASSUMPTIONS.md) içeriğinden okunur).

Örnek: *"Transmisyon açısı, krank ile itme çubuğu arasındaki açıdır. 90°'ye yakınken motor
gücünün tamamı plakaya gider. 30°'nin altına veya 150°'nin üstüne çıkarsa motor zorlanır,
0°/180°'de plakayı hiç hareket ettiremez. Sağlıklı aralık: 60°–120°."*

## Bağımlılıklar

Dış paketler: `streamlit`, `plotly`, `numpy`
Proje içi: [config.py](../files/config.md), [geometry.py](../files/geometry.md),
[bodies.py](../files/bodies.md), [collision.py](../files/collision.md),
[units.py](../files/units.md), `ui/common.py`

## Kod Örneği

```python
# app.py içinden
import streamlit as st
from seatsim.ui import design_tab

tabs = st.tabs(["Tasarım", "Çalışma alanı", "Yükler", ...])
with tabs[0]:
    design_tab.render(st.session_state.cfg)
```

---
Son Güncelleme: 2026-09-27
Versiyon: 1.2.0
