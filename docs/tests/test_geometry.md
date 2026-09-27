# tests/test_geometry.py

## Amaç

Ters kinematiğin kapalı form çözümünü, ileri kinematikle tutarlılığını, Jacobian'ın
doğruluğunu, simetri özelliklerini ve limit sınıflandırmasını doğrular. Ayrıca başlangıç
geometrisinin bilinen kısıtlamalarını regresyon olarak sabitler.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `mech` | fixture | — | `config.yaml`'dan kurulan `Mechanism` | Modül kapsamlı fixture |

## Çıkış

pytest sonucu. Test listesi:

### Temel doğruluk

| Test | Ne doğrular | Tolerans |
|---|---|---|
| `test_neutral_cranks_are_zero` | Nötr pozda iki krank açısı da 0 | `1e-9` rad |
| `test_neutral_rod_length` | Nötrde `\|P − C\|` tam olarak `rod.length` | `1e-12` m |
| `test_neutral_rod_is_vertical` | Nötrde çubuk birim vektörü `(0,0,1)` | `1e-9` |
| `test_neutral_crank_is_horizontal` | Nötrde pim, mil merkezinin tam arkasında | `1e-12` |
| `test_neutral_transmission_is_90` | Nötrde transmisyon açısı 90° | `1e-6°` |

### Simetri

| Test | Ne doğrular | Tolerans |
|---|---|---|
| `test_pure_pitch_cranks_equal` | `roll=0` için `θ_sağ == θ_sol`, 15 farklı pitch değerinde | `1e-12` |
| `test_pure_roll_cranks_opposite_sign` | `pitch=0` için `θ_sağ` ve `θ_sol` **zıt işaretli**, ulaşılabilir roll aralığı boyunca | — |
| `test_roll_mirror_symmetry` | `ik(0, +r).theta == ik(0, −r).theta[::-1]` — sağ/sol aynalama **tam** | `1e-12` |
| `test_roll_antisymmetric_to_first_order` | Jacobian'ın roll kolonu tam antisimetrik: `J[0,1] == −J[1,1]` | `1e-12` |
| `test_roll_magnitudes_converge_at_small_angle` | Roll 1°'de `\|θ_sağ\|` ve `\|θ_sol\|` %0,5 içinde | — |

Bu testler mekanizmanın tanımdaki en temel davranışını sabitler: *"İki krank aynı yöne
dönerse pitch, zıt yöne dönerse roll oluşur."*

> **Saf roll'de büyüklükler tam eşit DEĞİLDİR** ve bu bir hata değildir. Bağlantı noktası
> nötrde motor milinin 5,5 cm üstündedir; sağ taraf bu referansın üstüne çıkarken sol
> taraf altına iner ve krank açısı yüksekliğin doğrusal fonksiyonu olmadığı için
> büyüklükler ayrışır (roll 3°'de %0,4, roll 8°'de %8). Kesin ve test edilebilir ifade
> **birinci mertebeden antisimetridir** (Jacobian kolonu), artı sağ/sol **aynalama
> simetrisi** — ikisi de makine hassasiyetinde tutar.

### FK ↔ IK tutarlılığı

| Test | Ne doğrular | Tolerans |
|---|---|---|
| `test_fk_inverts_ik` | Ulaşılabilir alanda 200 rastgele `(p, r)` için `fk(ik(p,r).theta) == (p,r)` | `1e-6°` |
| `test_fk_at_neutral` | `fk([0,0]) == (0, 0)` | `1e-9` |
| `test_fk_seed_independence` | Farklı `seed` değerleri aynı çözüme yakınsar | `1e-8` |

### Jacobian

| Test | Ne doğrular | Tolerans |
|---|---|---|
| `test_jacobian_matches_finite_difference` | Analitik `J` = merkezi sonlu fark (adım `1e-6` rad), 50 noktada | `1e-5` |
| `test_jacobian_at_neutral_is_diagonal_pattern` | Nötrde `J = [[a, b], [a, −b]]` biçiminde (pitch simetrik, roll antisimetrik). Ölçülen: `[[5,125, 4,55], [5,125, −4,55]]` | `1e-12` |
| `test_jacobian_ratio_at_neutral` | `∂θ/∂pitch ≈ L_attach / R_crank = 20,5/4 = 5,125` | `%2` |
| `test_det_jacobian_nonzero_in_workspace` | Ulaşılabilir alanda `det(J) != 0` | `> 1e-6` |

### Limit sınıflandırması

| Test | Ne doğrular |
|---|---|
| `test_unreachable_returns_reason` | Ulaşılamayan poz `reachable=False` ve `UNREACHABLE_*` sebebi döndürür |
| `test_gimbal_limit_triggers` | `gimbal_max_deg` küçültülünce `GIMBAL_ANGLE` sebebi çıkar |
| `test_pot_range_triggers` | `pot.mechanical_range_deg` küçültülünce `POT_RANGE` sebebi çıkar |
| `test_deadpoint_margin_triggers` | `deadpoint_margin_deg` büyütülünce `DEAD_POINT` sebebi çıkar |
| `test_reason_priority` | Birden fazla limit aşıldığında öncelik sırası korunur |
| `test_rod_end_misalign_zero_in_pure_pitch` | Saf pitch'te rot başı sapması ≈ 0 (çubuk hep YZ düzleminde) |
| `test_rod_end_misalign_grows_with_roll` | Roll arttıkça sapma monoton artar |

### Regresyon — başlangıç geometrisinin bilinen sınırları

Bunlar [FINDINGS.md](../FINDINGS.md) A1'i koda bağlar. Geometri değişirse bu testler
kırılır ve **kasıtlı olarak** kırılmaları beklenir — Faz 4'te güncellenecekler.

Sınır **üç kademede** sabitlenir, çünkü hangi limitin bağladığı tasarım kararını değiştirir:

| Test | Kademe | Beklenen | Tolerans |
|---|---|---|---|
| `test_regression_raw_reach_pitch` | yalnızca IK erişimi | `+8,5° / −33,2°` | `±0,2°` |
| `test_regression_raw_reach_roll` | yalnızca IK erişimi | `±9,8°` | `±0,2°` |
| `test_regression_limited_pitch` | + parça limitleri | `+8,1° / −15,5°` | `±0,2°` |
| `test_regression_full_pitch` | + çarpışma | `+8,1° / −8,3°` | `±0,2°` |
| `test_regression_full_roll` | + çarpışma | `±9,0°` | `±0,2°` |
| `test_regression_binding_reasons` | sınırı bağlayan sebepler | yukarı `DEAD_POINT`, aşağı `COLLISION`, roll `ROD_END_ANGLE` | — |
| `test_regression_pitch_10_unreachable` | | `is_reachable(10, 0) == False` | — |
| `test_regression_combined_7_7_unreachable` | | `is_reachable(7, 7) == False` | — |
| `test_regression_total_height` | | `total_height_cm() == 20,8` | `1e-9` |
| `test_regression_all_targets_fail` | | `workspace_map().targets_met` **beş** hedefte de `False` | — |
| `test_regression_workspace_ok_count` | | 41×41 ızgarada `177` uygun düğüm | `±2` |

### Dal sabitliği

Ters kinematiğin iki kökü vardır; dal montajda sabitlenir. Bu testler, ızgara adımının
ölü nokta bandını atlayıp mekanizmayı aynalanmış dala geçirmesini önleyen düzeltmeyi
korur ([geometry.md](../files/geometry.md), Adım 5).

| Test | Ne doğrular |
|---|---|
| `test_branch_sign_resolved_from_neutral` | `branch_sign` nötrde `θ = 0` veren kökü seçer |
| `test_ik_is_order_independent` | Izgarayı ileri ve geri taramak **birebir aynı** `θ` verir |
| `test_ik_matches_single_call` | Izgara taramasındaki her düğüm, tek başına çağrıldığında aynı sonucu verir |
| `test_branch_continuity` | Pitch 0'dan 8°'ye küçük adımlarla giderken `θ` sıçrama yapmaz (ardışık fark < 5°) |
| `test_no_absurd_torque_over_grid` | Tüm ızgarada `loads.solve` torku 100 N·m'nin altında kalır — aynalanmış dal 9600 N·m üretiyordu |

### Sayısal dayanıklılık

| Test | Ne doğrular |
|---|---|
| `test_ik_no_exceptions_over_grid` | 41×41 ızgarada hiçbir düğüm istisna fırlatmaz |
| `test_workspace_map_shape` | Çıktı dizilerinin boyutları tutarlı |
| `test_reason_legend` | `reason_legend` yalnızca haritada gerçekten görünen sebepleri döndürür |

### Takozlar

| Test | Ne doğrular |
|---|---|
| `test_suggest_stop_heights_round_trip` | `suggest_stop_heights_cm(12)` ile ayarlanan yükseklikler, `stop_engagement_deg()`'de 12° ± 0,1 verir |
| `test_stop_engagement_changes_with_position` | Takoz konumu değişince devreye girme açısı değişir (sabit varsayım yok) |
| `test_stop_heights_scalar_expands` | `top_height_cm` tek sayı verilirse tüm takozlara uygulanır |
| `test_stop_heights_length_mismatch_raises` | Uzunluk uyuşmazsa `ValueError` |

## Bağımlılıklar

Dış paketler: `pytest`, `numpy`
Proje içi: [geometry.py](../files/geometry.md), [config.py](../files/config.md),
[frames.py](../files/frames.md)

## Kod Örneği

```bash
uv run pytest tests/test_geometry.py -v
uv run pytest tests/test_geometry.py -k regression -v   # sadece regresyon testleri
```

---
Son Güncelleme: 2026-09-12
Versiyon: 2.0.0
