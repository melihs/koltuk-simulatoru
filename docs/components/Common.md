# Common (ui/common.py)

## Amaç

Arayüz katmanının ortak yardımcıları: Plotly mesh üretimi, bildirimsel parametre editörü,
durum rozetleri, oturum durumu yönetimi ve pahalı hesapların düğme arkasına alınması.
Bu modül **fizik hesabı yapmaz**; çekirdeği çağırır ve sonucu biçimlendirir.

## Giriş Parametreleri

Modül düzeyinde bir API'dir; her fonksiyonun kendi girdisi vardır.

| Fonksiyon | Girdi |
|---|---|
| `explain(text, healthy)` | Grafiğin üstüne yazılacak açıklama ve sağlıklı aralık |
| `chip(status, text)` | Durum (`İYİ`/`DİKKAT`/`SORUN`) ve etiket |
| `classify(value, good_above, warn_above)` | Büyük iyi olan ölçüt |
| `classify_inverse(value, good_below, warn_below)` | Küçük iyi olan ölçüt |
| `render_param(cfg, param)` | Tek parametreyi düzenlenebilir çizer |
| `render_groups(cfg)` | Tüm parametre gruplarını açılır bölümler halinde çizer |
| `mechanism_figure(bodies, status)` | Gövde listesi ve gövde başına durum → 3D figür |
| `replace_config(cfg)` | Aktif yapılandırmayı değiştirir |
| `expensive_result(slot, cfg, label, help)` | Pahalı hesabı düğme arkasına alır |
| `store_expensive_result(slot, cfg, value)` | Sonucu üretildiği yapılandırmayla saklar |

## Çıkış

Streamlit bileşenleri (yan etki) ve yukarıdaki dönüş değerleri.

---

## Bildirimsel parametre editörü

Parametreler `GROUPS` sabitinde tanımlıdır: `Group(ad, giriş, params)` ve
`Param(path, label, unit, step, help, lockable, components)`. Arayüze yeni bir parametre
eklemek için bu listeye **bir satır** yazmak yeterlidir; çizim, rozet, kilit kutusu ve
"nasıl ölçerim" notu otomatik gelir.

`components` alanı liste parametreleri içindir:

```python
Param("geometry.gimbal.position_cm", "Mafsal dönme merkezi", "cm", 0.5,
      components=("x — sağ", "y — yukarı", "z — ileri"))
```

Bu alan olmadan etiket yalnızca **ilk** bileşene düşerdi: "Mafsal yüksekliği (y)" yazan
kutu aslında `x`'i düzenler ve kullanıcı yüksekliği değiştirdiğini sanırken mafsalı yana
kaydırırdı.

Her parametrenin altında güven rozeti (`⚠️ TAHMİNİ` vb.), varsa not ve ölçüm talimatı
görünür; kaynağı [config.py](../files/config.md)'nin `PARAM_META_DEFAULTS` kayıt defteri
ve [ASSUMPTIONS.md](../ASSUMPTIONS.md)'dir. Grup başlığında kaç tahmini değer olduğu yazar.

## Yapılandırma değiştirme — `replace_config()`

> **Streamlit'te `key` verilen bir widget'ın durumu kalıcıdır ve `value=` argümanını
> EZER.** Bu yüzden `st.session_state.cfg = config.load(...)` tek başına hiçbir işe
> yaramaz: bir sonraki çizimde eski widget değerleri yeni yapılandırmanın üzerine geri
> yazılır.

`replace_config()` önce `param_widget_keys()`'in verdiği tüm bayat anahtarları
`session_state`'ten siler, sonra yeni yapılandırmayı yazar. Böylece widget'lar yeni
değerlerden yeniden doğar.

Yapılandırmayı değiştiren **her** yol bu fonksiyondan geçmelidir: "Profili yükle",
"Başlangıç değerlerine dön", "Yükseklikleri hesapla". Üçü de
`tests/test_app.py` içinde regresyon olarak kilitlenmiştir.

## Pahalı hesaplar — `expensive_result()`

Streamlit her etkileşimde **tüm betiği**, dolayısıyla tüm sekmeleri yeniden çalıştırır.
Çalışma alanı haritası gibi bir hesap her çizimde yapılırsa, kullanıcı Tasarım sekmesinde
bir ölçüyü değiştirdiğinde — haritaya bakmıyor olsa bile — dakikalarca bekler.
Ölçüldü: krank 4 → 7,5 değişiminde 41×41 harita **900 saniyeyi aştı**.

Bu yüzden pahalı sonuçlar açık bir düğmeyle hesaplanır ve oturum durumunda, üretildikleri
yapılandırmanın YAML metniyle birlikte saklanır:

| Durum | Ekranda |
|---|---|
| Henüz hesaplanmadı | Bilgi kutusu + "hesapla" düğmesi |
| Hesaplandı, tasarım aynı | Sonuç |
| Hesaplandı, tasarım değişti | **"bayat" uyarısı + eski sonuç** — silinmez, yalnızca güncel olmadığı bilinir |

Ucuz olan şeyler düğme arkasına **alınmaz**: "KISIT İHLALİ" tablosu yalnızca 8 ters
kinematik çağrısı gerektirir (`Mechanism.target_report()`) ve her zaman görünür.

## 3D mesh üretimi

| Fonksiyon | Üretim |
|---|---|
| `box_mesh(box, ...)` | 8 köşe, 12 üçgen |
| `capsule_mesh(capsule, ...)` | Dönel yüzey: iki yarımküre + silindir, 14 çevresel × 9 enlem |

`capsule_mesh` içindeki `np.cross` çağrıları bir **çizim tabanı** kurar (kapsül eksenine
dik iki birim vektör), fizik hesabı değildir — mimarinin "arayüz fizik yapmaz" kuralı
korunur.

Renklendirme `body_color()` ile yapılır: önce durum (kırmızı/turuncu), sonra grup
(hareketli/bağlantı/sabit/takoz). `bodies.py` renk bilmez.

Eksen etiketleri kullanıcı sisteminde yazılır (`x — sağ`, `z — ileri`, `y — yukarı`) ama
koordinatlar iç sistemdedir; `aspectmode="data"` ile ölçek korunur.

## Bağımlılıklar

Dış paketler: `streamlit`, `plotly`, `numpy`
Proje içi: [config.py](../files/config.md), [bodies.py](../files/bodies.md)

## Kod Örneği

```python
from seatsim.ui import common as C

C.explain("Bu grafik ne gösteriyor.", "Sağlıklı aralık: 60°–120°")
st.dataframe([[C.chip(C.classify(sf, 2.0, 1.5), f"{sf:.2f}")]])

sonuc, istendi = C.expensive_result("wmap", cfg, "Haritayı hesapla", "~20 saniye.")
if istendi:
    C.store_expensive_result("wmap", cfg, pahali_hesap())
    st.rerun()
```

---
Son Güncelleme: 2026-09-27
Versiyon: 1.0.0
