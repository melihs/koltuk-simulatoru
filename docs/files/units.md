# units.py

## Amaç

Arayüz birimleri (cm, derece) ile çekirdek birimleri (m, radyan) arasındaki ölçek
dönüşümlerini tek noktada toplar. Çekirdek modüllerin içinde `* 0.01` veya `math.radians`
görülmemesini sağlar.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `value` | `ArrayLike` | Evet | — | Dönüştürülecek skaler veya dizi |

Her fonksiyon tek bir değer alır; dizi girdisinde eleman bazında çalışır.

## Çıkış

Tüm fonksiyonlar `ArrayLike` alır ve `np.floating | np.ndarray` döndürür (skaler girdide
0 boyutlu dizi, dizi girdide dizi).

| Fonksiyon | Girdi | Çıktı |
|---|---|---|
| `cm_to_m(v)` | cm | m |
| `m_to_cm(v)` | m | cm |
| `deg_to_rad(v)` | derece | radyan |
| `rad_to_deg(v)` | radyan | derece |
| `rpm_to_rad_s(v)` | dev/dk | rad/s |
| `rad_s_to_rpm(v)` | rad/s | dev/dk |

Sabitler: `CM_PER_M = 100.0`, `G = 9.81` (m/s², yerçekimi ivmesi).

Hata fırlatmaz. `None` girdisinde `TypeError` yükselir (numpy davranışı).

## Bağımlılıklar

Dış paketler: `numpy`
Proje içi modüller: yok — bu modül hiçbir şey import etmez, bağımlılık zincirinin dibindedir.

## Kullanım kuralı

Mimarinin "**TEK DÖNÜŞÜM NOKTASI**" dediği modül budur. Kural şudur:

> Projede cm/m veya derece/radyan çevrimi yalnızca burada (ve eksen sırasını da değiştiren
> `frames.py` içinde) yapılır. Çekirdek modüllerin içinde **çıplak** `* 0.01`, `/ 100`,
> `math.radians` veya `np.radians` görülmez.

Kural, dönüşümün **dağılmamasıdır** — çekirdek modüllerin bu modülü import etmemesi değil.
`geometry.py`, `loads.py` ve `bodies.py` bu modülü import **eder** ve etmelidir; yasak
olan, aynı işi elle yapmaktır.

Bu ayrım önemli: modülün docstring'i bir süre "çekirdek modüller bu modülü import etmez"
diyordu ve bu **gerçeğe aykırıydı** — ileride birini yanlış yöne iter. `/quality-check`
adım 6 çıplak dönüşümleri denetler.

## Kod Örneği

```python
from seatsim.units import cm_to_m, deg_to_rad, G

crank_r = cm_to_m(4.0)        # 0.04 m
pitch   = deg_to_rad(10.0)    # 0.17453... rad
weight  = 102.0 * G           # 1000.6 N
```

Vektör dönüşümü için `frames.to_internal()` kullanılır — o hem ölçeği hem eksen sırasını
değiştirir. Bu modül yalnızca ölçek değiştirir, eksen sırasına dokunmaz.

---
Son Güncelleme: 2026-09-27
Versiyon: 1.1.0
