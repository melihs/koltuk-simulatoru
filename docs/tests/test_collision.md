# tests/test_collision.py

## Amaç

Mesafe fonksiyonlarının elle hesaplanabilir senaryolarda doğru sonuç verdiğini, çakışmayı
doğru işaretle bildirdiğini ve yaklaşık yöntemlerin (kapsül–kutu, kutu–kutu) belgelenen
hata sınırları içinde kaldığını doğrular.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| — | — | — | — | Fixture almaz; her test kendi ilkellerini elle kurar |

## Çıkış

pytest sonucu. Test listesi:

### Doğru parçası – doğru parçası (tam yöntem)

| Test | Senaryo | Beklenen |
|---|---|---|
| `test_parallel_segments` | İki paralel parça, 3 m ayrık | `3.0` |
| `test_crossing_segments` | Dik kesişen iki parça, aynı düzlemde | `0.0` |
| `test_skew_segments` | Çapraz (skew) iki parça, Z'de 2 m ayrık | `2.0` |
| `test_collinear_disjoint` | Aynı doğru üzerinde, uçları 1 m ayrık | `1.0` |
| `test_degenerate_point_segment` | Sıfır uzunluklu parça (nokta) | nokta–parça mesafesi |
| `test_endpoint_closest` | En yakın nokta uçta | doğru `s`, `t` parametreleri |

Bu yöntem **tam**tır, tolerans `1e-12`.

### Nokta – kutu

| Test | Senaryo | Beklenen |
|---|---|---|
| `test_point_outside_box_face` | Yüzün tam karşısında, 2 m | `2.0` |
| `test_point_outside_box_corner` | Köşe hizasında, `(1,1,1)` ötede | `√3` |
| `test_point_inside_box` | Kutu içinde | `0.0` |
| `test_point_rotated_box` | 45° döndürülmüş kutu, bilinen mesafe | analitik değer |

### Kapsül – kapsül

| Test | Senaryo | Beklenen |
|---|---|---|
| `test_capsule_capsule_gap` | Eksenler 5 m, yarıçaplar 1 + 1,5 | `2.5` |
| `test_capsule_capsule_touching` | Eksen mesafesi = yarıçap toplamı | `0.0` |
| `test_capsule_capsule_overlap` | Eksen mesafesi < yarıçap toplamı | **negatif**, tam penetrasyon |

### Kapsül – kutu (yaklaşık + iyileştirilmiş)

| Test | Ne doğrular | Tolerans |
|---|---|---|
| `test_capsule_box_axis_aligned` | Kutunun yüzüne paralel kapsül, bilinen boşluk | `1e-4` m |
| `test_capsule_box_refinement_accuracy` | Kaba örneklemeyle (`samples=4`) ve iyileştirmeyle sonuç aynı | `1e-4` m |
| `test_capsule_box_never_underestimates` | 200 rastgele yapılandırmada, yoğun örneklemeli referansa (`samples=2000`) karşı sonuç **asla daha küçük değil** | — |
| `test_capsule_box_documented_error_bound` | Hata, [collision.md](../files/collision.md)'de belirtilen `0,1 mm` sınırı içinde | `1e-4` m |

`test_capsule_box_never_underestimates` kritik testtir: örnekleme tabanlı yöntem gerçek
minimumu kaçırırsa mesafeyi **olduğundan büyük** gösterir, yani çarpışmayı kaçırabilir.
Bu testin amacı iyileştirme adımının o riski kapattığını kanıtlamaktır.

### Kutu – kutu

| Test | Ne doğrular |
|---|---|
| `test_box_box_separated` | Ayrık kutular, bilinen boşluk, `1e-3` m |
| `test_box_box_sat_overlap_exact` | SAT çakışmayı yanlış pozitif/negatif vermeden belirler, 300 rastgele çift |
| `test_box_box_rotated_separated` | Döndürülmüş kutular, ayrık; SAT doğru karar verir |
| `test_box_box_face_contact` | Yüz yüze temas, mesafe `0.0` civarı |

### Çift tarama (`pairwise`)

| Test | Ne doğrular |
|---|---|
| `test_exclude_pairs_respected` | Hariç tutulan çift sonuçta **yok** |
| `test_symmetric_pairs` | `(a,b)` ve `(b,a)` aynı çift sayılır, iki kez raporlanmaz |
| `test_sorted_by_distance` | Sonuç artan mesafeye göre sıralı |
| `test_aabb_prefilter_consistency` | AABB ön elemesi açık/kapalı aynı sonucu verir (performans optimizasyonu doğruluğu bozmuyor) |
| `test_neutral_pose_no_collision` | `config.yaml` nötr pozda hiçbir çakışma yok |
| `test_crank_gearbox_pair_is_checked` | Krank ↔ kendi redüktör kutusu çifti **denetleniyor** ([FINDINGS.md](../FINDINGS.md) B3) |

`test_aabb_prefilter_consistency`, performans için eklenen ön elemenin doğruluğu
bozmadığını garanti eder — optimizasyonların sessizce sonuç değiştirmesi bu projede
en tehlikeli hata sınıfıdır.

## Bağımlılıklar

Dış paketler: `pytest`, `numpy`
Proje içi: [collision.py](../files/collision.md), [bodies.py](../files/bodies.md),
[config.py](../files/config.md)

## Kod Örneği

```bash
uv run pytest tests/test_collision.py -v
uv run pytest tests/test_collision.py -k never_underestimates -v
```

---
Son Güncelleme: 2026-09-12
Versiyon: 1.0.0
