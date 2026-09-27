# tests/test_loads.py

## Amaç

Statik kuvvet çözümünün fiziksel olarak tutarlı olduğunu, iki bağımsız tork hesabının
uyuştuğunu ve tanım §2.2'deki elle hesabın ±%2 içinde tutturulduğunu doğrular.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `mech` | fixture | — | `config.yaml`'dan kurulan `Mechanism` | Modül kapsamlı |
| `manual_scenario` | fixture | — | Tanım §2.2 senaryosu | Aşağıda |

## Çıkış

pytest sonucu. Test listesi:

### Kabul testi — tanım §2.2 elle hesabı

**En önemli test.** Kullanıcının elle yaptığı hesabı programın tutturması gerekir.

```python
MassScenario(
    user_kg=90.0, carried_fraction=1.0,
    plate_assembly_kg=0.0, backrest_mode="tilting",
    com_fore_aft_m=0.05, com_height_m=0.0, com_lateral_m=0.0,
)
# plaka yatay, krank yatay, çubuklar dikey
```

| Test | Beklenen | Tolerans | Ölçülen fark |
|---|---|---|---|
| `test_manual_gravity_moment` | `44,145 N·m` | **%2** | %0,000 |
| `test_manual_total_rod_force` | `215,3 N` | **%2** | %0,010 |
| `test_manual_rod_force_each` | `107,7 N` her biri | **%2** | %0,010 |
| `test_manual_motor_torque` | `4,305 N·m` her biri | **%2** | %0,008 |

Plaka kütlesi ve AM yüksekliği sıfırlanır, `carried_fraction=1`, `backrest_mode="tilting"`
seçilir — böylece senaryo tanımdaki idealize hesapla birebir örtüşür.

### Simetri

| Test | Ne doğrular |
|---|---|
| `test_pure_pitch_rod_forces_equal` | Yanal AM kayması yokken `f₁ == f₂` |
| `test_pure_roll_rod_forces_opposite` | Yalnızca yanal AM kayması varken `f₁ == −f₂` |
| `test_lateral_com_mirror` | AM `+5 cm` ile `−5 cm`, kuvvetleri aynada yansıtır |
| `test_motor_torques_equal_in_pure_pitch` | Saf pitch'te iki motor torku eşit |

### Çapraz doğrulama — sanal iş

| Test | Ne doğrular | Tolerans | Ölçülen |
|---|---|---|---|
| `test_virtual_work_matches_direct_moment` | `τ = −J_xᵀ Q_grav` ile doğrudan `((C−S) × −fû)·X̂` aynı sonucu verir, tüm uygun pozlar × 5 senaryoda | `1e-6` N·m | `9e-16` N·m |

Bu test hem `geometry.jacobian()`'ı hem `loads.solve()`'u aynı anda denetler: ikisi
birbirinden tamamen farklı yolla hesaplanır ve uyuşmaları tesadüf olamaz. Projedeki en
güçlü iç tutarlılık kontrolü.

### Fizik tutarlılığı

| Test | Ne doğrular |
|---|---|
| `test_zero_mass_zero_force` | Tüm kütleler 0 → tüm kuvvetler ve torklar 0 |
| `test_linearity_in_mass` | Kütle 2× → kuvvetler tam 2× (`1e-9` bağıl) |
| `test_force_balance` | `Σ F = 0`: mafsal tepkisi + çubuk kuvvetleri + ağırlık = 0 (`1e-9` N) |
| `test_moment_balance_about_gimbal` | Serbest eksenlerde net moment 0 (`1e-9` N·m) |
| `test_gimbal_reaction_carries_weight` | Nötrde mafsal tepkisinin düşey bileşeni ≈ toplam ağırlık |
| `test_rod_sign_convention` | AM önde → çubuklar **basmada** (pozitif); AM arkada → **çekmede** (negatif) |

### Ters sarkaç

| Test | Ne doğrular | Tolerans |
|---|---|---|
| `test_gravity_stiffness_equals_weight_times_height` | **Nötrde sertlik tam olarak `W · h`** — 4 farklı AM yüksekliğinde | `1e-6` bağıl |
| `test_gravity_stiffness_positive_above_gimbal` | AM mafsalın üstünde → `> 0` (kararsız) | — |
| `test_gravity_stiffness_negative_below_gimbal` | AM mafsalın altında → `< 0` (kararlı, sarkaç) | — |
| `test_moment_grows_with_com_height` | Aynı eğimde AM yüksekliği arttıkça moment monoton artar | — |
| `test_moment_grows_with_tilt` | Aynı AM'de eğim arttıkça moment monoton artar (ileri kayan AM için) | — |

`test_gravity_stiffness_equals_weight_times_height` en keskin testtir: sonlu farkla
hesaplanan sayısal türev, analitik `W · h` ile makine hassasiyetinde uyuşmak zorundadır.
Hem kütle modelini hem rotasyon işaretlerini aynı anda denetler.

### Sırtlık senaryoları

| Test | Ne doğrular | Tolerans |
|---|---|---|
| `test_follow_fraction_one_equals_tilting` | `fixed` + `follow_fraction=1.0`, `seat_kg=0` olan `tilting` ile **aynı** sonucu verir | `1e-9` |
| `test_follow_fraction_monotonic` | `follow_fraction` arttıkça hem tork hem yerçekimi sertliği monoton artar | — |
| `test_follow_fraction_zero_no_pendulum` | `follow_fraction=0` → yerçekimi sertliği yalnızca plakanın katkısı kadar (`≈ 2 N·m/rad`) | `%5` |

> `tilting` modunun `fixed`'den **her zaman** daha kötü olduğu **doğru değildir** ve
> test edilmez. `tilting`, koltuk kütlesini (`seat_kg`) de ekler; koltuğun AM'si mafsalın
> arkasındaysa (varsayılan `z = −5 cm`) bu, kullanıcının öne kayan AM'sini kısmen
> dengeler. Ölçülen: pitch −8°, 120 kg, AM +8 cm → `tilting` 11,81 N·m, `fixed`
> (`follow=1`) 11,97 N·m. Doğru ve test edilebilir ifade yukarıdaki üç satırdır.

### En kötü durum taraması

| Test | Ne doğrular |
|---|---|
| `test_worst_case_finds_maximum` | Tarama sonucu, ızgaradaki tüm tek tek çözümlerin maksimumundan küçük değil |
| `test_worst_case_scenario_is_reported` | `at_pose` ve `at_scenario` alanları dolu ve yeniden çözüldüğünde aynı torku veriyor |
| `test_worst_case_verdict_thresholds` | SF 2,5 → `YETERLI`; 1,7 → `SINIRDA`; 1,2 → `YETERSIZ` |
| `test_singular_pose_does_not_crash` | Ölü noktadaki poz istisna fırlatmaz, `singular=True` döner |

### Regresyon

| Test | Beklenen | Tolerans |
|---|---|---|
| `test_regression_worst_case_torque` | En kötü tork `19,7 N·m` | `%5` |
| `test_regression_worst_case_location` | pitch `−3,6°`, roll `−7,2°` | `±1,5°` |
| `test_regression_safety_factor` | `SF ≈ 1,52` → `SINIRDA` | `%5` |
| `test_regression_rod_forces` | basma `597 N`, çekme `434 N` | `%5` |
| `test_regression_gimbal_force` | Mafsal bileşke kuvveti `1698 N` | `%5` |
| `test_regression_gimbal_post_bending` | Direk taban eğilmesi `22,7 N·m` — **100 N·m'nin çok altında** | `%10` |
| `test_worst_case_needs_collision_check` | `check_collision=False` ile tork belirgin biçimde **daha yüksek** çıkar; varsayılanın `True` olduğunu korur | — |

`test_regression_gimbal_post_bending` bilinçli olarak düşük bir değeri sabitler: ilk
tahmin 136 N·m'ydi ve yanlıştı. Kardan mafsalı pitch/roll momenti taşıyamadığı için
devrilme momentini çubuklar alır; direğe yalnızca `yatay kuvvet × yükseklik` kalır.
Test, bu anlayışın geri gitmesini engeller.

## Bağımlılıklar

Dış paketler: `pytest`, `numpy`
Proje içi: [loads.py](../files/loads.md), [geometry.py](../files/geometry.md),
[config.py](../files/config.md), [frames.py](../files/frames.md)

## Kod Örneği

```bash
uv run pytest tests/test_loads.py -v
uv run pytest tests/test_loads.py -k manual -v           # kabul testi
uv run pytest tests/test_loads.py -k virtual_work -v     # çapraz doğrulama
```

---
Son Güncelleme: 2026-09-12
Versiyon: 2.0.0
