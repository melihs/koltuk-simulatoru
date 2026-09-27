# PendingTabs (Henüz yapılmamış faz sekmeleri)

## Amaç

Faz 3–6'ya ait sekmeleri boş bırakmak yerine, her birinin **ne üreteceğini** ve
**neyi beklediğini** yazar. Böylece hangi fazda olduğunuz ve sırada ne olduğu ekrandan
anlaşılır; bir sekmeye girip boş sayfa görmeniz gerekmez.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `key` | `str` | Evet | — | `"dynamics"` \| `"optimize"` \| `"cueing"` \| `"pid"` \| `"report"` |

Geçersiz bir anahtar `KeyError` fırlatır — bu bir programlama hatasıdır, kullanıcı girdisi
değildir.

## Çıkış

Ekrana üç bölüm:

1. **Durum kutusu** — faz numarası, ön koşul ve ön koşulun *neden* gerekli olduğu
2. **"Bu sekme ne yapacak"** — madde madde kapsam
3. **Bu arada ne yapabilirsiniz** (varsa) — yalnızca Faz 3 için: motorun kilitlenme
   torkunu ölçme çağrısı

## Veri yapısı

Tüm içerik modül düzeyindeki `PHASES` sözlüğünde durur; `render()` yalnızca biçimlendirir.
Her kayıt:

| Alan | Anlamı |
|---|---|
| `title` | Sekme başlığı |
| `phase` | Faz numarası |
| `blocked_by` | Ön koşul (dosya veya başka faz) |
| `why` | Ön koşulun neden gerekli olduğu — varsayımla ilerlemenin niye amacı bozacağı |
| `will_do` | Kapsam maddeleri |
| `meanwhile` | (isteğe bağlı) Kullanıcının şimdi yapabileceği iş |

Bir faz tamamlandığında o anahtar `PHASES`'ten çıkarılır ve `app.py`'de ilgili sekme
gerçek modüle bağlanır.

## Faz durumu

| Anahtar | Faz | Ön koşul |
|---|---|---|
| `dynamics` | 3 | **`SMC3.ino` kaynak dosyası** |
| `optimize` | 4 | Faz 3 |
| `cueing` | 5 | Faz 3 |
| `pid` | 6 | Faz 3 ve Faz 5 |
| `report` | 6 | Faz 3–5 |

Faz 3'ün ön koşulu bilinçli bir karardır: PID formülü, ölçekleme ve limit mantığı
firmware'den birebir okunmalıdır, çünkü amaç bulunan Kp/Ki/Kd değerlerinin **doğrudan**
SMC3Utils'e girilebilmesidir. Varsayımla modellenen bir PID bu amacı bozar.

## Bağımlılıklar

Dış paketler: `streamlit`
Proje içi: yok — bu modül hiçbir çekirdek modülü import etmez, yalnızca metin gösterir.

## Kod Örneği

```python
from seatsim.ui import pending_tab

with tabs[3]:
    pending_tab.render("dynamics")
```

---
Son Güncelleme: 2026-09-12
Versiyon: 1.0.0
