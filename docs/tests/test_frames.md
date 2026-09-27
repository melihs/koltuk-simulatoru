# tests/test_frames.py

## Amaç

Koordinat sistemi dönüşümünün tersinir olduğunu, iç sistemin gerçekten sağ el olduğunu ve
pitch/roll işaret tanımlarının fiziksel sezgiyle uyuştuğunu doğrular.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| — | — | — | — | Fixture almaz; sabit vektörler ve açılar kullanır |

## Çıkış

pytest sonucu. Test listesi:

| Test | Ne doğrular | Tolerans |
|---|---|---|
| `test_roundtrip` | `from_internal(to_internal(v)) == v`, rastgele 100 vektör | `1e-12` |
| `test_axis_swap` | `(0,13,0) cm` kullanıcı → `(0, 0, 0.13) m` iç | `1e-12` |
| `test_internal_is_right_handed` | `X̂ × Ŷ == Ẑ` iç sistemde | tam |
| `test_user_frame_is_left_handed` | Kullanıcı sisteminin determinantının −1 olduğu — dönüşümün neden gerekli olduğunu belgeleyen test | tam |
| `test_rotation_orthonormal` | `R @ R.T == I` ve `det(R) == +1`, 50 rastgele `(p, r)` çifti | `1e-12` |
| `test_pitch_positive_lifts_front` | `rotation(+10°, 0) @ (0,1,0)` → Z bileşeni **pozitif** | — |
| `test_pitch_negative_drops_front` | `rotation(−10°, 0) @ (0,1,0)` → Z bileşeni **negatif** | — |
| `test_roll_positive_lifts_right` | `rotation(0, +10°) @ (1,0,0)` → Z bileşeni **pozitif** | — |
| `test_roll_negative_drops_right` | `rotation(0, −10°) @ (1,0,0)` → Z bileşeni **negatif** | — |
| `test_zero_rotation_is_identity` | `rotation(0, 0) == I` | `1e-15` |
| `test_tilt_angle` | Saf 10° pitch → `tilt_angle == 10°`; 7°+7° → ≈ 9,9° | `1e-9` / `0.05°` |
| `test_outer_axis_matters` | `outer_axis="pitch"` ve `"roll"`, 15°+15°'de **farklı** matris üretir | fark > `1e-3` |
| `test_outer_axis_difference_is_second_order` | İki eksen sırası **ikinci mertebeden** uyuşur: 1°'de fark tam olarak `sin²(1°)`, açı yarılandığında fark dörde bölünür | `rel 1e-9` / `%1` |
| `test_invalid_outer_axis_raises` | Geçersiz değer `rotation`, `roll_axis` ve `rotation_derivatives`'te `ValueError` fırlatır | — |

`test_outer_axis_difference_is_second_order`, keyfi bir tolerans yerine **mertebeyi**
ölçer. İlk yazımda `fark < 1e-4` denmişti ve bu **yanlıştı**: 1°+1°'de gerçek fark
`sin²(1°) = 3,05e-4`'tür. Kuplaj teriminin ikinci mertebeden olduğunu doğrulamak, bir
eşik uydurmaktan hem daha bilgilendirici hem daha sağlamdır.

### Dönme ekseni sözleşmesi

| Test | Ne doğrular |
|---|---|
| `test_roll_axis_is_rotation_axis_of_positive_roll` | `roll_axis()`, pozitif roll'un **sağ el dönme eksenini** verir. Küçük açı için `R ≈ I + r·[n̂]×` ilişkisinden `[n̂]×` geri okunup karşılaştırılır → `n̂ = −ŷ` |
| `test_pitch_axis_is_rotation_axis_of_positive_pitch` | Aynısı pitch için → `n̂ = +x̂` |
| `test_roll_axis_follows_pitch_when_outer_is_pitch` | Dış eksen pitch ise roll ekseni pitch ile birlikte döner, normu 1 kalır |
| `test_roll_axis_fixed_when_outer_is_roll` | Dış eksen roll ise tabana sabit |
| `test_rotation_derivatives_match_finite_difference` | `dR/dpitch` ve `dR/droll`, merkezi sonlu farkla uyuşur, iki eksen sırası için | 
| `test_plate_normal_is_up_at_neutral` | Nötrde plaka normali `(0,0,1)` |
| `test_tilt_angle_zero_at_neutral` | Nötrde toplam eğim tam sıfır |

Bu bölüm kritiktir: roll ekseninin işareti yanlış olduğunda çubuk kuvvetleri **doğru**
kalır ama yerçekimi sertliği ve sanal iş çapraz doğrulaması bozulur. Geliştirme sırasında
bu hata gerçekten yapıldı — ayrıntı [files/frames.md](../files/frames.md).

## Neden bu testler

İşaret hataları bu projedeki en sinsi hata sınıfıdır: program çalışır, sayı üretir, ama
koltuk ters yöne eğilir. `test_pitch_positive_lifts_front` gibi testler tanımı koda
bağlar — birisi `Ry(−r)`'yi `Ry(+r)` yaparsa test anında kırılır.

`test_user_frame_is_left_handed` bir "regresyon" testi değil, **belgeleme** testidir:
kullanıcının sistemi neden dönüştürülüyor sorusunun cevabını kodda tutar.

## Bağımlılıklar

Dış paketler: `pytest`, `numpy`
Proje içi: [frames.py](../files/frames.md)

## Kod Örneği

```bash
uv run pytest tests/test_frames.py -v
```

---
Son Güncelleme: 2026-09-12
Versiyon: 2.0.0
