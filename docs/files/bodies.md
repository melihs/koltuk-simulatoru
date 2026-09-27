# bodies.py

## Amaç

Mekanizmanın fiziksel parçalarını, verilen bir poz için basit dışbükey geometrik hacimlere
(yönlendirilmiş kutu ve kapsül) dönüştürür. Bu hacimler hem çarpışma kontrolünde hem
Plotly 3D görünümünde kullanılır — tek kaynaktan üretildikleri için ekranda görünen ile
hesaplanan **aynı** geometridir.

## Giriş Parametreleri

### `build(cfg, pose)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `cfg` | `SeatConfig` | Evet | — | [config.md](config.md) |
| `pose` | `Pose` | Evet | — | `geometry.ik()` çıktısı |

## Çıkış

`list[Body]`. Her `Body`:

| Alan | Tip | Açıklama |
|---|---|---|
| `name` | `str` | Makine adı, ör. `"crank_right"` |
| `label_tr` | `str` | Arayüzde gösterilen ad, ör. `"Sağ krank"` |
| `group` | `str` | `"static"` (alt plakaya sabit) \| `"moving"` (plakayla döner) \| `"linkage"` (krank/çubuk) |
| `primitives` | `list[Box \| Capsule]` | Gövdeyi oluşturan dışbükey hacimler |
| `collidable` | `bool` | Çarpışma kontrolüne katılır mı |

### İlkel tipler

**`Box`** — yönlendirilmiş kutu (OBB)

| Alan | Tip | Açıklama |
|---|---|---|
| `center` | `(3,)` | Merkez, dünya çerçevesi, m |
| `half` | `(3,)` | Yarı boyutlar, m |
| `R` | `(3,3)` | Yönelim; birim matris = eksene hizalı |

**`Capsule`** — doğru parçası + yarıçap

| Alan | Tip | Açıklama |
|---|---|---|
| `p0`, `p1` | `(3,)` | Eksen uçları, m |
| `radius` | `float` | m |

Hata: `pose.reachable == False` ise `ValueError` — ulaşılamayan poz için gövde üretilmez.

## Gövde listesi

| `name` | `label_tr` | İlkel | Grup | Boyut kaynağı |
|---|---|---|---|---|
| `base_plate` | Alt plaka | Box | static | `geometry.base_plate` |
| `gimbal_post` | Mafsal direği | Capsule | static | `hardware.gimbal_post`, alt plaka üstünden `gimbal.position_cm`'e |
| `top_plate` | Üst plaka | Box | moving | `geometry.top_plate`, `pose.R` ile döner |
| `cushion` | Minder | Box | moving | `geometry.cushion`, plakanın üstünde |
| `user_body` | Kullanıcı (atalet kutusu) | Box | moving | `hardware.user_box_cm`; kutu **yük modelinin kullandığı ağırlık merkezine ortalanır**, böylece ekranda görünen kutu ile hesaptaki AM aynı yerdedir. `collidable=False` |
| `crank_right` / `crank_left` | Sağ/Sol krank | Capsule | linkage | `S → pose.pin[i]`, yarıçap `crank.thickness_cm/2` |
| `rod_right` / `rod_left` | Sağ/Sol itme çubuğu | Capsule | linkage | `pose.pin[i] → pose.attach[i]`, yarıçap `rod.diameter_cm/2` |
| `gearbox_right` / `gearbox_left` | Sağ/Sol redüktör kutusu | Box | static | `hardware.gearbox_box_cm`, krank düzleminin **içinde** — aşağıya bakın |
| `motor_right` / `motor_left` | Sağ/Sol motor gövdesi | Capsule | static | `hardware.motor_cylinder_*`, kutunun arka yüzünden arkaya uzanır |
| `pot_right` / `pot_left` | Sağ/Sol pot braketi | Box | static | `hardware.pot_bracket_cm`, krank düzleminin **dışında** |
| `stop_0..3` | Takoz 1–4 | Box | static | `stops.positions_cm`, takoz başına `stops.heights()` |

### Mil ekseni (x) boyunca yerleşim

Bu, çarpışma sonuçlarını doğrudan belirleyen ve kolayca yanlış modellenen kısımdır.
Krank, redüktör kutusunun **dışında** döner — kutuyu mil noktasına ortalamak krankı
kutunun içinde döndürürdü ve mekanizma hiçbir açıya ulaşamazdı.

```
  mafsal                                    krank         pot
  tarafı                                    düzlemi      braketi
    ←─────────── x yönünde dışa ───────────────→
           ┌──────────────┐
           │  redüktör    │◄── gearbox_box_cm[0] ──►│        │
           │   kutusu     │                         │        │
           └──────────────┘                         │        │
                      ▲                             ▲        ▲
                 kutunun                   shaft_protrusion_cm
                 dış yüzü                            │   pot_offset_cm
                                      motor_shaft_cm[0] (krank burada döner)
```

- `gearbox` merkezi: `|x| = |motor_shaft_cm[0]| − shaft_protrusion_cm − gearbox_box_cm[0]/2`
- `motor` silindiri: kutunun arka yüzünden (`−y`) başlar, kutunun **x merkezinde** durur
- `pot` braketi: `|x| = |motor_shaft_cm[0]| + pot_offset_cm + pot_bracket_cm[0]/2`

Motor silindiri (Ø6,4 cm) redüktör kutusundan (6,0 cm) yana taştığı için
`shaft_protrusion_cm` 2 cm'in altına inerse krank motor gövdesine çarpar —
bkz. [FINDINGS.md](../FINDINGS.md) B9.

## Çarpışma çifti kuralları

Birbirine **bağlı** parçalar çarpışma kontrolünden çıkarılır — temas etmeleri normaldir:

```
crank_right  ↔ gearbox_right       bağlı (mil)          → HARİÇ DEĞİL, bkz. not
rod_right    ↔ crank_right         bağlı (rot başı)     → hariç
rod_right    ↔ top_plate           bağlı (rot başı)     → hariç
top_plate    ↔ cushion             bağlı                → hariç
top_plate    ↔ gimbal_post         bağlı (mafsal)       → hariç
cushion      ↔ user_body           bağlı                → hariç
base_plate   ↔ gearbox_*, motor_*, pot_*, stop_*, gimbal_post   → hariç (hepsi üstüne monte)
```

**Not — krank ↔ kendi redüktör kutusu hariç tutulmaz.** Krank mile takılıdır ama dönerken
kutunun gövdesine çarpabilir. Bu, [FINDINGS.md](../FINDINGS.md) B3'te işaret edilen gerçek
bir risktir ve denetlenmelidir. Yukarıdaki x-yerleşimi sayesinde krank kutunun yanından
geçer; `shaft_protrusion_cm` küçültülürse çarpışma kontrolü bunu yakalar.

**Statik ↔ statik çiftler ayrı ele alınır.** İki gövdenin de `group == "static"` olduğu
çiftler (ör. motor gövdesi ↔ takoz) **poza bağlı değildir** — bunlar montaj/imalat
sorunudur, çalışma alanını kısıtlamaz. `geometry.Mechanism._classify` bu çiftleri
`skip_static=True` ile hiç hesaplamaz; Tasarım sekmesi onları ayrı bir "montaj boşlukları"
tablosunda gösterir. Bkz. [collision.md](collision.md).

Takozlar iki rolde birden görünür: `MECH_STOP` limiti ayrı hesaplanır (plaka alt yüzeyinin
takoz üstüne değmesi), ayrıca normal çarpışma çifti olarak da denetlenir.

**Ön takozlar içe alınmak zorundadır.** Motor takımı `|x| = 9,5…15,9 cm` bandını kapladığı
için ön takozlar `x = ±5,5 cm`'de durur; bu, roll'ü sınırlama yeteneklerini zayıflatır
(roll kolu yalnızca 5,5 cm). Arka takozlar motorların arkasında olduğu için serbesttir
(`x = ±18 cm`). Bkz. [FINDINGS.md](../FINDINGS.md) B8.

Hariç tutulan çiftler `config.yaml`'daki `collision.exclude_pairs` listesinden okunur;
kullanıcı ekleyip çıkarabilir.

## Takoz temas modeli

Takozun "±12°'de devreye girer" kuralı sabit bir açı olarak değil, **geometrik olarak**
modellenir: plakanın alt yüzey düzlemi, takozun `(x, z)` konumunda `top_height_cm`'in
altına inerse temas vardır.

Plaka alt yüzeyi, `Q = G + R·(0, 0, underside_above_gimbal)` noktasından geçen ve normali
`n̂ = R·Ẑ` olan düzlemdir. Takozun bulunduğu `(x_t, y_t)` dikeyinde düzlemin yüksekliği:

```
Z(x_t, y_t) = Q_z − ( n_x·(x_t − Q_x) + n_y·(y_t − Q_y) ) / n_z
```

`Z ≤ top_height[i]` ise temas. Yükseklik takoz **başınadır** (`StopsCfg.heights()`).

Bu hesabı `Mechanism.plate_underside_height(R, xy)` yapar ve iki yerde kullanılır:

| Fonksiyon | Ne yapar |
|---|---|
| `Mechanism.suggest_stop_heights_cm(target_deg)` | Her takozun hedef açıda devreye girmesi için gereken yüksekliği verir. Takoz konumunu değiştirdiğinizde bunu çağırın. |
| `Mechanism.stop_engagement_deg()` | Her takozun **gerçekte** hangi açıda devreye girdiğini tarar. Sabit ±12° varsayılmaz. |

Yön seçimi `Mechanism._stop_critical_signs()` ile yapılır: takoz, plakanın o noktası
alçaldığında devreye girer — arkadaki takoz (`z < 0`) ön yukarı kalkınca, sağdaki takoz
(`x > 0`) sağ aşağı inince.

## Plotly görünümü

`Box` → 12 üçgenden `Mesh3d`. `Capsule` → gövde için silindir yüzeyi, uçlar için yarımküre;
`plotly.graph_objects.Mesh3d`, varsayılan 12 çevresel bölüm.

Renklendirme çağıran tarafın (`ui/design_tab.py`) sorumluluğudur; `bodies.py` renk bilmez.

## Bağımlılıklar

Dış paketler: `numpy`
Proje içi: [frames.py](frames.md), [config.py](config.md)

`bodies.py`, `collision.py`'yi import **etmez** — mesafe hesabı ayrı katmandır.

## Kod Örneği

```python
from seatsim.config import load
from seatsim.geometry import Mechanism
from seatsim import bodies

cfg  = load("config.yaml")
mech = Mechanism.from_config(cfg)
pose = mech.ik(0.0, 0.0)

for b in bodies.build(cfg, pose):
    print(f"{b.label_tr:22s} {b.group:8s} {len(b.primitives)} ilkel")

# Sağ krank kapsülünün uçları (m)
crank = next(b for b in bodies.build(cfg, pose) if b.name == "crank_right")
print(crank.primitives[0].p0, crank.primitives[0].p1)
```

---
Son Güncelleme: 2026-09-12
Versiyon: 1.1.0
