# units.py

## Amaç

Arayüz birimleri (cm, derece) ile çekirdek birimleri (m, radyan) arasındaki ölçek
dönüşümlerini tek noktada toplar. Çekirdek modüllerin içinde `* 0.01` veya `math.radians`
görülmemesini sağlar.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `value` | `float \| np.ndarray` | Evet | — | Dönüştürülecek skaler veya dizi |

Her fonksiyon tek bir değer alır; dizi girdisinde eleman bazında çalışır.

## Çıkış

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

Bu modül **yalnızca** şu sınırlarda çağrılır:

- `config.py` — `config.yaml` okunurken cm/derece → SI
- `frames.py` — koordinat dönüşümü içinde
- `seatsim/ui/*` — ekrana yazarken SI → cm/derece
- `report.py` — rapora yazarken SI → cm/derece

`geometry.py`, `loads.py`, `dynamics.py` gibi çekirdek modüller bu modülü import **etmez**.
Bu kural `/quality-check` adım 6 (mimari uygunluk) tarafından denetlenir.

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
Son Güncelleme: 2026-09-11
Versiyon: 1.0.0
