# geometry.py

## Amaç

Mekanizmanın ters ve ileri kinematiğini, Jacobian'ını, limit denetimlerini ve çalışma alanı
taramasını içerir. Ters kinematik **kapalı formdur** — iterasyon veya küçük açı yaklaşımı
kullanılmaz.

## Giriş Parametreleri

### `Mechanism.from_config(cfg)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `cfg` | `SeatConfig` | Evet | — | [config.md](config.md) şeması |

### `Mechanism.ik(pitch, roll, *, check_collision=None)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `pitch` | `float` | Evet | — | radyan, + = ön yukarı |
| `roll` | `float` | Evet | — | radyan, + = sağ yukarı |
| `check_collision` | `bool \| None` | Hayır | `None` | `None` → örneğin varsayılanı (`Mechanism(check_collision=...)`) |

Sonuç **çağrı sırasından bağımsızdır**: dal montajda sabitlenmiştir (aşağıya bakın).

### `Mechanism.fk(theta, seed=None)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `theta` | `(2,) ndarray` | Evet | — | `[sağ, sol]` krank açıları, radyan |
| `seed` | `(2,) ndarray \| None` | Hayır | `None` | Başlangıç tahmini `(pitch, roll)`. `None` → `(0, 0)` |

### `Mechanism.workspace_map(pitch_range, roll_range, n)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `pitch_range` | `(float, float)` | Hayır | `(−0.35, 0.35)` | radyan (±20°) |
| `roll_range` | `(float, float)` | Hayır | `(−0.35, 0.35)` | radyan |
| `n` | `int` | Hayır | `61` | Izgara çözünürlüğü (her eksende) |

## Çıkış

| Fonksiyon | Çıktı |
|---|---|
| `ik(...)` | `Pose` — aşağıda |
| `fk(...)` | `(pitch, roll)` radyan; yakınsamazsa `ValueError` |
| `jacobian(pitch, roll)` | `(2,2)` — `∂(θ_sağ, θ_sol) / ∂(pitch, roll)` |
| `workspace_map(...)` | `WorkspaceMap` — ızgara + sebep kodu + transmisyon açısı |
| `max_pitch_deg()` / `max_roll_deg()` | `(pozitif_max, negatif_max)` derece — tüm limitler dahil |
| `is_reachable(pitch_deg, roll_deg)` | `bool` |
| `total_height_cm()` | Alt plaka altından minder üstüne, cm |
| `plate_underside_height(R, xy)` | Plaka alt yüzey düzleminin verilen `(X, Y)` dikeylerindeki yüksekliği, m |
| `suggest_stop_heights_cm(target_deg)` | Her takozun hedef açıda devreye girmesi için gereken üst yüzey yüksekliği, cm |
| `stop_engagement_deg()` | Her takozun **gerçekte** hangi açıda devreye girdiği + konumu ve yönü |
| `branch_sign` | `(2,)` — montajın sabit dal işareti, nötrden türetilir |

Modül düzeyinde iki yardımcı (arayüzün renk/efsane üretmesi için):

| Fonksiyon | Çıktı |
|---|---|
| `reason_order()` | `list[LimitReason]` — harita kodlarıyla aynı sırada (indis 0 = `OK`) |
| `reason_code(reason)` | `int` — o sebebin harita kodu; `reason_order()[reason_code(r)] is r` |

### `Pose` (dataclass)

| Alan | Tip | Açıklama |
|---|---|---|
| `pitch`, `roll` | `float` | radyan |
| `R` | `(3,3)` | Plaka rotasyon matrisi |
| `theta` | `(2,)` | Krank açıları `[sağ, sol]`, radyan. Nötrde `(0, 0)` |
| `attach` | `(2,3)` | Plaka bağlantı noktaları, dünya çerçevesi, m |
| `pin` | `(2,3)` | Krank pimi konumları, m |
| `rod_unit` | `(2,3)` | Çubuk birim vektörleri, pimden plakaya (C→P) |
| `transmission_deg` | `(2,)` | Krank ile çubuk arası açı, derece. 90° ideal |
| `deadpoint_margin_deg` | `(2,)` | `min(μ, 180−μ)` — ölü noktaya uzaklık |
| `rod_end_misalign_deg` | `(2,2)` | `[taraf][uç]` — uç 0 = krank pimi, uç 1 = plaka |
| `gimbal_tilt_deg` | `float` | Toplam eğim |
| `pot_angle_deg` | `(2,)` | Pot mili açısı, mekanik merkeze göre |
| `stop_contact` | `(n,) bool` | Hangi takozlara temas var |
| `min_clearance_m` | `float` | En dar **hareketli** çift mesafesi, m. Çarpışma denetimi kapalıysa `inf` |
| `closest_pair` | `str` | O çiftin Türkçe etiketi |
| `ok` | `bool` | `reachable and reason is OK` (özellik) |
| `reachable` | `bool` | IK çözümü var mı (limitlere bakmaz) |
| `reason` | `LimitReason` | Ulaşılamıyorsa veya limit aşıldıysa sebep |

### `LimitReason` (enum)

| Değer | Türkçe etiket | Anlam |
|---|---|---|
| `OK` | Uygun | Tüm limitler içinde |
| `UNREACHABLE_ROD` | Çubuk yetişmiyor | Çubuk, yanal (X) açıklığı kapatamıyor: `L² < d_x²` |
| `UNREACHABLE_CIRCLE` | Erişim dışı | Krank dairesi ile çubuk küresi kesişmiyor |
| `DEAD_POINT` | Krank ölü noktası | Transmisyon açısı marjı `deadpoint_margin_deg` altında |
| `ROD_END_ANGLE` | Rot başı açısı | Küresel mafsal sapma limiti aşıldı |
| `GIMBAL_ANGLE` | Kardan mafsalı açısı | Toplam eğim `gimbal_max_deg` üstünde |
| `COLLISION` | Çarpışma | **Hareketli** bir gövde içeren bir çiftin mesafesi `clearance_min_cm` altında. Statik ↔ statik çiftler buraya girmez — onlar poza bağlı olmayan montaj sorunudur, bkz. [collision.md](collision.md) |
| `MECH_STOP` | Mekanik takoz | Plaka alt yüzeyi bir takoza değdi |
| `POT_RANGE` | Pot aralığı | Krank açısı potun mekanik aralığını aşıyor — **pot kırılır** |

Birden fazla limit aynı anda aşılmışsa yukarıdaki **sıra** önceliklidir (erişilemezlik
önce, sonra mekanizma, sonra parça limitleri).

## Ters kinematik — kapalı form

Krank pimi, motor miline dik bir düzlemde daire çizer. Mil iç sistemde `X` eksenine
paraleldir, bu yüzden problem 2 boyuta iner.

**Adım 1 — Plaka bağlantı noktası.**

```
P = G + R(pitch, roll) · p_local
```

`G` mafsal merkezi, `p_local` bağlantı noktasının plaka çerçevesindeki konumu.
Tam rotasyon matrisi kullanılır, küçük açı yaklaşımı yok.

**Adım 2 — Yanal bileşeni ayır.**

```
d = P − S                        S = motor mili merkezi
d_x = d[0]                       bu bileşen krank hareketinden bağımsız
L_eff = √(L² − d_x²)             düzlem içi etkin çubuk boyu
```

`L² < d_x²` ise çubuk yanal açıklığı kapatamaz → `UNREACHABLE_ROD`.

**Adım 3 — Çember–çember kesişimi** (YZ düzleminde):

```
merkez₁ = S_yz,  yarıçap₁ = R_krank
merkez₂ = P_yz,  yarıçap₂ = L_eff

D = |P_yz − S_yz|
a = (D² + R_krank² − L_eff²) / (2D)
h² = R_krank² − a²
```

`h² < 0` ise çemberler kesişmiyor → `UNREACHABLE_CIRCLE`.
`h ≈ 0` ise teğet — krank ile çubuk aynı doğrultuda, **ölü nokta**.

```
û    = (P_yz − S_yz) / D
n̂    = (−û_z, û_y)                90° döndürülmüş
C±   = S_yz + a·û ± h·n̂
```

**Adım 4 — Krank açısı.** Pim konumu `C − S = R_krank · (−cos φ, sin φ)` biçimindedir
(nötrde `φ = 0` → pim mil merkezinin **arkasında**):

```
φ = atan2(C_z − S_z, −(C_y − S_y))
θ = φ − neutral_offset
```

**Adım 5 — Dal seçimi: montajda sabit.** İki kök vardır (`C₊` ve `C₋`), pimin `S→P`
doğrusunun hangi yanında olduğuna karşılık gelirler.

Mekanizma **sökülmeden dal değiştiremez**: bunun için teğet duruma (ölü noktaya) gelip
karşı tarafa geçmesi gerekirdi. Yani dal, montajın kalıcı bir özelliğidir, her pozda
yeniden keşfedilecek bir şey değildir. `_resolve_branch()` nötr pozda hangi kökün `θ = 0`
verdiğine bakarak `branch_sign`'ı bir kez belirler; `_solve_crank` her yerde onu kullanır.

> **Neden böyle:** İlk sürüm "bir önceki çözüme en yakın kök"ü seçiyordu. Izgara adımı ölü
> nokta bandının üzerinden atladığında bu, mekanizmayı aynalanmış dala geçiriyor ve orada
> transmisyon açısı çöktüğü için **fizik dışı torklar** (9600 N·m, 254 kN çubuk kuvveti)
> üretiyordu. Dalı sabitlemek hem bu hatayı ortadan kaldırır hem sonucu çağrı sırasından
> bağımsız yapar.

Sol ve sağ taraf birbirinden **bağımsız** çözülür. `x` işareti taraf başına çevrilir.
İç fonksiyon `_crank_roots()` iki kökü birlikte döndürür; testler bunu kullanabilir.

## Simetri özellikleri

Geometri `x = 0` düzlemine göre simetrik olduğu ve iki krank açısı **aynı yönde**
(her ikisi de `+X` etrafında) ölçüldüğü için:

- **Saf pitch** (`roll = 0`): iki bağlantı noktası eşit yükselir → `θ_sağ = θ_sol` **tam**
- **Saf roll** (`pitch = 0`): biri yükselir biri alçalır → `θ_sağ` ve `θ_sol` **zıt
  işaretli**, ama büyüklükleri tam eşit **değildir**

Roll'deki eşitsizlik bir hata değil, krank-biyel mekanizmasının doğal **doğrusal
olmayışıdır**: bağlantı noktası nötrde motor milinin 5,5 cm üstündedir; sağ taraf bu
referansın üstüne çıkarken sol taraf altına iner ve krank açısı yüksekliğin doğrusal
fonksiyonu değildir. Ölçülen fark roll 3°'de %0,4, roll 8°'de %8'dir.

**Birinci mertebeden antisimetri tamdır** ve testlerde bu kullanılır: Jacobian'ın roll
kolonu tam olarak `J[0,1] = −J[1,1]`'dir. Nötrde `J = [[5,125, 4,55], [5,125, −4,55]]`.

## İleri kinematik

`(θ_sağ, θ_sol) → (pitch, roll)`. İki bilinmeyen, iki denklem:

```
f_i(pitch, roll) = |P_i(pitch, roll) − C_i(θ_i)| − L = 0     i ∈ {sağ, sol}
```

`scipy.optimize.least_squares` ile çözülür, `seed`den başlar. Analitik çözümü yoktur
(plaka rotasyonu iki açıya birden bağlı), sayısal çözüm tanım gereği kabul edilebilir.

**Doğrulama:** `fk(ik(p, r).theta) == (p, r)`, çalışma alanı boyunca 1e-6° içinde.

## Jacobian

`J = ∂(θ_sağ, θ_sol) / ∂(pitch, roll)`, `(2,2)`.

Kapalı form IK üzerinden **analitik** türetilir: `P`'nin `(pitch, roll)`'a göre türevi
rotasyon matrisinin türevinden, `θ`'nın `P`'ye göre türevi çember–çember çözümünün
zincir kuralıyla alınmasından gelir. Sonlu farkla 1e-5 içinde doğrulanır.

Kullanım alanları:
- Statik tork (sanal iş): `τ = Jᵀ · M` — bkz. [loads.md](loads.md)
- Hız aktarımı: `θ̇ = J · (ṗ, ṙ)`
- Tekillik ölçütü: `det(J) → 0` ölü noktayı gösterir

## Transmisyon açısı

Krank vektörü `(S → C)` ile çubuk vektörü `(C → P)` arasındaki açı `μ`.

| `μ` | Anlam |
|---|---|
| 90° | İdeal — motor torkunun tamamı çubuğa aktarılır |
| 60°–120° | İyi |
| 30°–60° veya 120°–150° | Zayıf — aynı iş için daha yüksek çubuk kuvveti |
| 0° veya 180° | **Ölü nokta** — motor plakayı hareket ettiremez |

Ölü nokta marjı: `min(μ, 180° − μ)`.

## Rot başı sapma açısı

Küresel rot başı, bilye deliği ekseninden (`bore axis`) belirli bir açıya kadar sapmaya
izin verir. Çubuk nominal olarak bu eksene **diktir**.

```
sapma = asin( |ĉubuk · bore_ekseni| )
```

| Uç | Bore ekseni |
|---|---|
| Krank pimi | `X̂` — pim mile paraleldir, sabit |
| Plaka | `R · X̂` — plaka ile birlikte döner |

Saf pitch'te iki eksen de `X̂` yönünde kalır ve çubuk YZ düzleminde hareket eder → sapma
sıfıra yakındır. Saf roll'de çubuk bir `X` bileşeni kazanır → sapma büyür. Yani rot başı
limiti pratikte **roll ekseninde** belirleyicidir.

## Çalışma alanı haritası

Pitch–roll düzleminde `n × n` ızgara. Her düğümde `ik()` çağrılır, `reason` kaydedilir.
Ek katman olarak transmisyon açısı ve `det(J)` haritalanır.

`WorkspaceMap` alanları: `pitch_grid`, `roll_grid`, `reason` (`(n,n)` enum), `transmission_deg`
(`(n,n,2)`), `reachable` (`(n,n)` bool), `targets_met` (`dict[str, bool]`).

## Bağımlılıklar

Dış paketler: `numpy`, `scipy`
Proje içi: [frames.py](frames.md), [config.py](config.md), [bodies.py](bodies.md),
[collision.py](collision.md)

## Kod Örneği

```python
import numpy as np
from seatsim.config import load
from seatsim.geometry import Mechanism
from seatsim.units import deg_to_rad

mech = Mechanism.from_config(load("config.yaml"))

pose = mech.ik(deg_to_rad(5.0), deg_to_rad(0.0))
print(np.degrees(pose.theta))              # [26.9, 26.9]  saf pitch → tam esit
print(pose.reason.label_tr)                # "Uygun"

pose = mech.ik(deg_to_rad(10.0), deg_to_rad(0.0))
print(pose.reachable, pose.reason.code)    # False, UNREACHABLE_CIRCLE

print(mech.max_pitch_deg())   # (8.1, -8.3)   tum limitler dahil
print(mech.max_roll_deg())    # (9.0, -9.0)

wm = mech.workspace_map(n=41)
print(wm.ok.sum(), "/", wm.ok.size)        # 177 / 1681
print(wm.targets_met)                      # hepsi False
for r in wm.reason_legend:
    print(" -", r.label_tr)

for s in mech.stop_engagement_deg():
    print(s["label_tr"], s["engages_at_deg"], "derece")
```

---
Son Güncelleme: 2026-09-12
Versiyon: 2.1.0
