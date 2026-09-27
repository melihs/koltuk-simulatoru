# frames.py

## Amaç

İki koordinat sistemi arasındaki dönüşümü ve plakanın rotasyon matrislerini tanımlar.
Kullanıcının sol el sistemini (x=sağ, y=yukarı, z=ileri) çekirdeğin sağ el sistemine
(X=sağ, Y=ileri, Z=yukarı) çevirir ve pitch/roll işaret tanımlarını tek yerde sabitler.

## Neden iki sistem var

Tanımdaki sistem **sol eldir**. Sağ el sıralaması `(sağ, ileri, yukarı)` olurdu; kullanıcının
`(sağ, yukarı, ileri)` sıralaması iki ekseni takas ettiği için determinant −1'dir. Sol el
sisteminde çapraz çarpım ters işaret verir — moment, açısal hız ve atalet tensörü
hesaplarında sessiz, bulunması zor hatalar doğurur.

Çözüm: kullanıcının düzeni **dışarıda** aynen korunur (config, arayüz, rapor, atölye
ölçüleri değişmez), çekirdek **içeride** sağ el sisteminde çalışır.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `v_user` | `(3,) ndarray` | Evet | — | `(x=sağ, y=yukarı, z=ileri)`, **cm** |
| `v_int` | `(3,) ndarray` | Evet | — | `(X=sağ, Y=ileri, Z=yukarı)`, **m** |
| `pitch` | `float` | Evet | — | radyan, **pozitif = ön yukarı** |
| `roll` | `float` | Evet | — | radyan, **pozitif = sağ taraf yukarı** |
| `outer_axis` | `"pitch" \| "roll"` | Hayır | `"pitch"` | Kardan mafsalında tabana bağlı (dış) eksen |

## Çıkış

| Fonksiyon | Çıktı |
|---|---|
| `to_internal(v_user)` | `(3,)` iç sistem vektörü, m |
| `from_internal(v_int)` | `(3,)` kullanıcı sistemi vektörü, cm |
| `rotation(pitch, roll, outer_axis)` | `(3,3)` rotasyon matrisi, iç sistemde |
| `tilt_angle(R)` | Toplam eğim açısı (rad) — plaka normali ile düşey arasındaki açı |
| `pitch_axis()` | `(3,)` = `[1,0,0]` — pitch dönme ekseni, iç sistemde |
| `roll_axis(pitch, outer_axis)` | `(3,)` = `[0,−1,0]` (pitch ile döndürülmüş) — **roll dönme ekseni; işaretine dikkat, aşağıya bakın** |
| `rotation_derivatives(pitch, roll, outer_axis)` | `(dR/dpitch, dR/droll)` — Jacobian'ın analitik türevi için |
| `plate_normal(R)` | `(3,)` = `R @ Ẑ` — plakanın yukarı normali |

Hata: `outer_axis` geçersizse `ValueError`.

## Dönüşüm

```
X = x          Y = z          Z = y          ardından × 0.01  (cm → m)
```

Ters yönde `× 100` ve aynı takas. `to_internal(from_internal(v)) == v` (özdeşlik testi).

## Rotasyon tanımları

İç sistemde:

```
Rx(a) = [[1,      0,       0],       ← pitch ekseni (sağ)
         [0,  cos a,  −sin a],
         [0,  sin a,   cos a]]

Ry(b) = [[ cos b, 0, sin b],         ← roll ekseni (ileri)
         [     0, 1,     0],
         [−sin b, 0, cos b]]
```

**Pitch:** `R_pitch(p) = Rx(p)`. Doğrulama: ileri birim vektörü `(0,1,0)` → `(0, cos p, sin p)`.
`p > 0` için yukarı bileşen pozitif → **ön yukarı kalkar.** ✓

**Roll:** `R_roll(r) = Ry(−r)`. Doğrulama: sağ birim vektörü `(1,0,0)` → `Ry(−r)` ile
`(cos r, 0, sin r)`. `r > 0` için yukarı bileşen pozitif → **sağ taraf yukarı kalkar.** ✓

İşaret `Ry(−r)` olarak seçildi çünkü standart `Ry(+b)` sağ tarafı **aşağı** indirirdi.
Bu, tanımdaki "roll pozitif" sezgisiyle ters olurdu.

### Roll ekseninin işareti — dikkat

`roll_axis()` **`−ŷ` döndürür, `+ŷ` değil.** Sebebi:

Pozitif roll `R_roll(r) = Ry(−r)` olarak tanımlıdır. Bir rotasyon matrisi
`R = exp(θ·[n̂]×)` biçiminde yazıldığında buradaki eksen `n̂ = −ŷ`'dir:

```
Ry(−r) = exp(−r·[ŷ]×) = exp(r·[−ŷ]×)      →      n̂ = −ŷ
```

Yani **roll'e eş genelleştirilmiş moment `M · (−ŷ)` ile elde edilir**, `M · (+ŷ)` ile
değil. İşaret yanlış olursa:

| Etkilenen | Sonuç |
|---|---|
| Çubuk kuvvetleri | **etkilenmez** — `(M_rod + M_g)·ê = 0` denkleminin iki tarafı da işaret değiştirir |
| `gravity_moment_nm[1]` | ters işaretli raporlanır |
| Yerçekimi sertliği (roll) | ters işaretli → kararsız sistem kararlı görünür |
| Sanal iş çapraz doğrulaması | **kırılır** |

Bu hata geliştirme sırasında gerçekten yapıldı ve **yalnızca** sanal iş çapraz
doğrulaması (`tests/test_loads.py::test_virtual_work_matches_direct_moment`) tarafından
yakalandı — elle yapılan saf pitch kontrolünde roll satırı sıfır olduğu için görünmedi.
`tests/test_frames.py::test_roll_axis_is_rotation_axis_of_positive_roll` artık sözleşmeyi
doğrudan, küçük açı yaklaşımıyla `[n̂]×` matrisini geri okuyarak sabitler.

**Bileşim.** Kardan mafsalı iki ardışık eksendir: dış halka tabana sabit bir eksende,
iç halka dış halkanın taşıdığı eksende döner. Bu yüzden dış eksenin matrisi **solda** durur:

```
outer_axis = "pitch"  →  R = Rx(p) · Ry(−r)      (varsayılan)
outer_axis = "roll"   →  R = Ry(−r) · Rx(p)
```

İki sıra, aynı `(p, r)` çifti için **farklı** plaka pozu verir. Küçük açılarda fark
ihmal edilebilir, 10°+ açılarda ölçülebilir hale gelir. Mafsalın fiziksel yapısına göre
seçilmelidir — hangi halkanın tabana cıvatalandığına bakın.

## Bağımlılıklar

Dış paketler: `numpy`
Proje içi: [units.py](units.md)

## Kod Örneği

```python
import numpy as np
from seatsim import frames
from seatsim.units import deg_to_rad

# Mafsal merkezi: kullanıcı (0, 13, 0) cm  →  iç (0, 0, 0.13) m
g = frames.to_internal(np.array([0.0, 13.0, 0.0]))

# Plaka 10° ön yukarı, 5° sağ yukarı
R = frames.rotation(deg_to_rad(10), deg_to_rad(5), outer_axis="pitch")

# Sağ ön bağlantı noktası, plaka çerçevesinde (±18.2, −0.5, +20.5) cm
p_local = frames.to_internal(np.array([18.2, -0.5, 20.5]))
p_world = g + R @ p_local

print(frames.from_internal(p_world))     # cm, kullanıcı sisteminde
print(np.degrees(frames.tilt_angle(R)))  # toplam eğim ≈ 11.2°
```

---
Son Güncelleme: 2026-09-12
Versiyon: 2.0.0
