# loads.py

## Amaç

Verilen bir poz ve kütle senaryosu için iki itme çubuğundaki kuvvetleri, mafsal tepki
kuvvetini, mafsal direği taban momentini ve her motorun sağlaması gereken torku çözer.
Tüm çalışma alanı ve tüm senaryolar üzerinde en kötü durumu tarayıp emniyet katsayısını
raporlar.

## Giriş Parametreleri

### `solve(mech, pose, scenario)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `mech` | `Mechanism` | Evet | — | [geometry.md](geometry.md) |
| `pose` | `Pose` | Evet | — | `mech.ik()` çıktısı; `reachable` olmalı |
| `scenario` | `MassScenario` | Evet | — | Aşağıda |

### `MassScenario` (dataclass)

| Alan | Tip | Birim | Varsayılan | Açıklama |
|---|---|---|---|---|
| `user_kg` | `float` | kg | `120` | Kullanıcının toplam kütlesi |
| `carried_fraction` | `float` | — | `0.85` | Koltuğun taşıdığı oran (ayaklar yerde) |
| `backrest_mode` | `str` | — | `"fixed"` | `"fixed"` \| `"tilting"` |
| `backrest_follow_fraction` | `float` | — | `0.60` | `fixed` modda plakayla dönen oran |
| `seat_kg` | `float` | kg | `12.0` | `tilting` modda eklenen koltuk kütlesi |
| `plate_assembly_kg` | `float` | kg | `8.0` | Üst plaka + minder + braketler |
| `com_height_m` | `float` | m | `0.25` | Kullanıcı AM'si, minder üstünden |
| `com_fore_aft_m` | `float` | m | `0.0` | + = ileri |
| `com_lateral_m` | `float` | m | `0.0` | + = sağ |

### `worst_case(mech, sweep, *, check_collision=True, progress=None)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `mech` | `Mechanism` | Evet | — | |
| `sweep` | `SweepSpec` | Hayır | `SweepSpec()` | Taranacak poz ızgarası ve senaryo aralıkları |
| `check_collision` | `bool` | Hayır | **`True`** | Poz toplamada çarpışma denetimi |
| `progress` | `callable` | Hayır | `None` | `0..1` ilerleme bildirir (arayüz için) |

> **`check_collision`'ı kapatmayın.** Çarpışan pozlar mekanizmanın gerçekte ulaşamadığı
> yerlerdir; orada kuvvet matrisi tekilleşir ve tarama fizik dışı en kötü durumlar bulur.
> Ölçüldü: kapalıyken 605 N·m, açıkken 19,7 N·m. Maliyeti düşüktür çünkü çarpışma ızgara
> düğümü başına **bir kez** denetlenir, senaryo başına değil.

## Çıkış

### `StaticResult` (dataclass)

| Alan | Tip | Birim | Açıklama |
|---|---|---|---|
| `rod_force_n` | `(2,)` | N | Çubuk eksenel kuvveti. **+ = basma** (iter), **− = çekme** |
| `rod_end_force_n` | `(2,)` | N | Rot başına gelen kuvvet (= `\|rod_force\|`) |
| `gimbal_reaction_n` | `(3,)` | N | Mafsala gelen kuvvet, iç sistemde |
| `gimbal_post_bending_nm` | `float` | N·m | Direk tabanındaki eğilme momenti |
| `gimbal_post_torsion_nm` | `float` | N·m | Direk tabanındaki burulma |
| `motor_torque_nm` | `(2,)` | N·m | Motorun sağlaması gereken tork, `[sağ, sol]` |
| `safety_factor` | `(2,)` | — | `stall_torque / \|motor_torque\|` |
| `gravity_moment_nm` | `(2,)` | N·m | Yerçekiminin mafsal etrafındaki momenti `(pitch, roll)` |
| `gravity_stiffness_nm_rad` | `(2,)` | N·m/rad | `∂M/∂θ` — **pozitifse sistem statik kararsız** |
| `total_moving_mass_kg` | `float` | kg | |
| `condition` | `float` | — | Kuvvet matrisinin kondisyon sayısı. Nötr civarında ~1,1; çalışma alanı kenarında 20–30 (bir çubuğun moment kolu küçülür, motor gerçekten zorlanır). `1e4` üstü kullanılamaz → `singular=True` |
| `cross_check_error` | `float` | N·m | Sanal iş ile doğrudan moment yönteminin farkı. Ölçülen: `9e-16` |
| `singular` | `bool` | — | Kuvvet tekilliği; diğer alanlar anlamsız |

### `WorstCase` (dataclass)

| Alan | Açıklama |
|---|---|
| `max_motor_torque_nm` | En kötü tork |
| `at_pose` | Hangi `(pitch, roll)` |
| `at_scenario` | Hangi `MassScenario` |
| `min_safety_factor` | |
| `verdict` | `"YETERLI"` (SF≥2) \| `"SINIRDA"` (1,5–2) \| `"YETERSIZ"` (<1,5) |
| `explanation_tr` | Sade Türkçe açıklama |
| `max_rod_tension_n` / `max_rod_compression_n` | |
| `max_gimbal_force_n` / `max_gimbal_post_bending_nm` | |

Hatalar: `pose.reachable == False` ise `ValueError`. Kuvvet matrisi tekilse
(`cond(A) > 1e4`) istisna fırlatılmaz; `StaticResult(singular=True)` döndürülür ve diğer
alanlar sıfır kalır — tarama çökmemelidir.

## Yöntem

### 1. Kütle modeli

Hareketli sistem, plakayla birlikte dönen noktasal kütlelerin toplamıdır:

| Bileşen | Kütle | AM konumu |
|---|---|---|
| Plaka takımı | `plate_assembly_kg` | `plate_com` — plaka çerçevesinde, mafsala göre |
| Koltuk (`tilting` modda) | `seat_kg` | `seat_com` — plaka çerçevesinde |
| Kullanıcı (dönen kısım) | `m_f` | `user_com` — plaka çerçevesinde |
| Kullanıcı (dönmeyen kısım) | `m_s` | nötr konumdaki `user_com`, **sabit** |

```
m_carried = user_kg × carried_fraction

backrest_mode = "tilting":   m_f = m_carried,                      m_s = 0
backrest_mode = "fixed":     m_f = m_carried × follow_fraction,
                             m_s = m_carried × (1 − follow_fraction)
```

`m_s`, sırtlık tarafından tutulan ve plaka eğilse de yatay konumunu koruyan kütleyi temsil
eder. Ağırlığı plakaya biner ama **kolu eğimle büyümez** — ters sarkaç etkisi bu oranda
zayıflar. Bu, sırtlığın sabit olduğu senaryonun en basit savunulabilir modelidir;
`follow_fraction` ölçülmesi zor bir değerdir, tarama 0,4–1,0 aralığını kapsar.

### 2. Kuvvet çözümü

Serbest cisim: üst plaka + üstündeki her şey. Etkiyen kuvvetler:

- Yerçekimi: her kütle bileşeni için `m_j · g`, `g = (0, 0, −9.81)` iç sistemde
- İki çubuk kuvveti: `f_i · û_i`, `û_i` = pimden plakaya birim vektör (`pose.rod_unit`)
- Mafsal tepkisi: konumu `G` olduğu için `G` etrafındaki momente katkısı **yok**

Kardan mafsalı iki eksende serbesttir, bu iki eksende moment taşıyamaz:

```
eksen₁ = X̂                          (pitch ekseni)
eksen₂ = roll_axis(pitch, outer)     (roll ekseni; dış eksen pitch ise pitch ile döner)
```

İki denklem, iki bilinmeyen (`f₁`, `f₂`):

```
[ ((P₁−G) × û₁)·ê₁    ((P₂−G) × û₂)·ê₁ ] [f₁]     [ M_g · ê₁ ]
[ ((P₁−G) × û₂)·ê₂    ((P₂−G) × û₂)·ê₂ ] [f₂]  =  [ M_g · ê₂ ]
                                                    (işaret: yerçekimini dengele)
```

`M_g = Σ_j (com_j − G) × (m_j g)`. Sistem lineerdir, `numpy.linalg.solve` ile çözülür.

### 3. Mafsal tepkisi ve direk momenti

```
F_gimbal = − ( Σ_j m_j g  +  Σ_i f_i û_i )
M_taban  = (G − B) × F_gimbal          B = direk tabanı (alt plaka üstü)
eğilme   = |M_taban'ın yatay bileşeni|
burulma  = |M_taban'ın düşey bileşeni|
```

**Direğin kritik yükü eğilme değil, kuvvettir.** Kardan mafsalı iki eksende serbest
olduğu için pitch ve roll momenti **taşıyamaz** — ağırlık merkezinin kaymasından doğan
devrilme momentini tamamen iki itme çubuğu alır. Direğe kalan eğilme yalnızca
`yatay kuvvet × direk yüksekliği` kadardır.

Ölçülen en kötü durum: mafsalda **1698 N** bileşke kuvvet, direk tabanında yalnızca
**22,7 N·m** eğilme. Yani ucuz bir U-joint'in asıl sınavı eksenel/radyal yük
kapasitesidir. Bkz. [FINDINGS.md](../FINDINGS.md) B7.

### 4. Motor torku

Çubuk plakayı `+f û` ile iter; etki-tepki gereği krank pimini `−f û` ile iter.

```
τ_i = ( (C_i − S_i) × (−f_i û_i) ) · X̂
```

`C_i` krank pimi, `S_i` mil merkezi. Motorun sağlaması gereken tork bunun büyüklüğüdür.

### 5. Çapraz doğrulama — sanal iş

Aynı sonuç ikinci ve bağımsız bir yolla hesaplanır:

```
Q_grav = ( M_g · ê₁ ,  M_g · ê₂ )            plaka DOF'larına izdüşüm
J_x    = inv( mech.jacobian(pitch, roll) )   ∂(pitch,roll)/∂(θ₁,θ₂)
τ      = − J_xᵀ · Q_grav
```

İki yöntem 1e-6 içinde uyuşmalıdır. Uyuşmuyorsa `StaticResult.cross_check_error` alanı
sıfırdan farklı gelir ve test kırılır. Bu, hem Jacobian'ı hem kuvvet çözümünü aynı anda
denetleyen en güçlü iç tutarlılık kontrolüdür.

### 6. Yerçekimi sertliği (ters sarkaç ölçütü)

```
gravity_stiffness = ∂(M_g · ê) / ∂θ        merkezi sonlu fark, adım 0.1°
```

**Pozitif değer, sistemin statik olarak kararsız olduğu anlamına gelir**: plaka eğildikçe
onu daha da eğmeye çalışan moment büyür. Motor durduğunda sonsuz vida redüktörü bunu tutar,
ama PID'in kapalı çevrimde yenmesi gereken şey budur. Faz 3 PID ayarının en kritik girdisi.

AM mafsalın **altında** olsaydı bu değer negatif (kararlı, sarkaç gibi) olurdu.

Nötr pozda analitik değeri **`W · h`**'dir (`W` = ağırlık, `h` = AM'nin mafsal üstündeki
yüksekliği). Program bunu tam olarak tutturur — testlerde kullanılan en keskin
doğrulamalardan biri:

| AM, mafsalın üstünde | Ölçülen | `W · h` |
|---|---|---|
| 7,8 cm | +78,0 | +78,0 |
| 22,8 cm | +228,1 | +228,1 |
| 32,8 cm | +328,2 | +328,2 |
| −20 cm (altında) | −122,1 | negatif, kararlı |

## Doğrulama — tanım §2.2 elle hesabı

| Girdi | Değer |
|---|---|
| Taşınan kütle | 90 kg |
| AM, mafsalın önünde | 5 cm |
| Plaka | yatay (pitch = roll = 0) |
| Krank | yatay, çubuklar dikey |

| Beklenen | Değer |
|---|---|
| Mafsal momenti | 90 × 9,81 × 0,05 = **44,1 N·m** |
| Toplam çubuk kuvveti | 44,1 / 0,205 = **215 N** |
| Çubuk başına | **108 N** |
| Motor başına tork | 108 × 0,04 = **4,3 N·m** |

`tests/test_loads.py::test_manual_calculation` bunu **±%2** içinde tutturur.
Arayüzdeki "Doğrulama senaryosu" düğmesi aynı hesabı tek tıkla üretir.

## En kötü durum taraması

`SweepSpec` boyutları:

| Boyut | Varsayılan tarama |
|---|---|
| Poz | Ulaşılabilir çalışma alanı, 21×21 ızgara |
| `user_kg` | `[60, 90, 120]` |
| `com_fore_aft_cm` | `[−5, 0, +4, +8]` |
| `com_lateral_cm` | `[−5, 0, +5]` |
| `com_height_cm` | `[20, 25, 30]` |
| `backrest_mode` | `["fixed", "tilting"]` |
| `follow_fraction` | `[0.4, 0.6, 0.8, 1.0]` (yalnızca `fixed`) |

Izgarada 441 poz denenir; başlangıç geometrisinde bunlardan yalnızca **119'u** uygundur
(gerisi erişim dışı, çarpışma veya limit ihlali). 540 senaryo ile toplam ~64.000 çözüm.
Ölçülen süre **~40 s** (M-serisi Mac, tek çekirdek).

### Ölçülen en kötü durum (başlangıç geometrisi)

| | Değer |
|---|---|
| En kötü motor torku | **19,7 N·m** |
| Nerede | pitch −3,6°, roll −7,2° |
| Senaryo | 120 kg, AM +8 cm ileri / +5 cm yan / 30 cm yukarı, koltuk da eğiliyor |
| Emniyet katsayısı | **1,52 → SINIRDA** |
| En yüksek çubuk basma | 597 N |
| En yüksek çubuk çekme | 434 N |
| Mafsal bileşke kuvveti | 1698 N |
| Direk taban eğilmesi | 22,7 N·m |

En kötü durumun **saf pitch'te değil, eşzamanlı pitch + roll'de** çıkması önemlidir:
orada bir çubuğun moment kolu küçülür ve yük büyük ölçüde tek çubuğa biner. Saf pitch
varsayımıyla yapılan kaba hesap 13,3 N·m verir ve gerçeği %33 eksik gösterir.

## Emniyet katsayısı yorumu

| SF | Renk | Anlam |
|---|---|---|
| ≥ 2,0 | Yeşil | Hedef sağlanıyor. Motor en kötü durumda bile iki kat pay bırakıyor. |
| 1,5 – 2,0 | Turuncu | Çalışır ama pay dar. Isınma ve yavaşlama beklenir; ölçüm hatası bunu altına düşürebilir. |
| < 1,5 | Kırmızı | **Yetersiz.** Motor en kötü durumda plakayı kaldıramaz veya çok yavaş kaldırır. |

Bu eşiklerin dayandığı `stall_torque_nm` bir **TAHMİNDİR** — bkz.
[ASSUMPTIONS.md](../ASSUMPTIONS.md) §1. Arayüz, SF'yi gösterirken bunu her seferinde hatırlatır.

## Bağımlılıklar

Dış paketler: `numpy`
Proje içi: [geometry.py](geometry.md), [frames.py](frames.md), [config.py](config.md)

## Kod Örneği

```python
from seatsim.config import load
from seatsim.geometry import Mechanism
from seatsim import loads

cfg  = load("config.yaml")
mech = Mechanism.from_config(cfg)

# Tanım §2.2 doğrulama senaryosu
sc = loads.MassScenario(
    user_kg=90.0, carried_fraction=1.0, plate_assembly_kg=0.0,
    backrest_mode="tilting", com_fore_aft_m=0.05, com_height_m=0.0,
)
res = loads.solve(mech, mech.ik(0.0, 0.0), sc)
print(res.rod_force_n)        # [107.6, 107.6]  N
print(res.motor_torque_nm)    # [4.30, 4.30]    N·m

wc = loads.worst_case(mech)
print(wc.verdict, wc.min_safety_factor)
print(wc.explanation_tr)
```

---
Son Güncelleme: 2026-09-12
Versiyon: 1.1.0
