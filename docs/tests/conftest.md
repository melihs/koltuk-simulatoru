# tests/conftest.py

## Amaç

Test kümesinin ortak fixture'larını ve yardımcılarını tanımlar. Pahalı hesaplar
(41×41 çalışma alanı haritası, en kötü durum taraması) **oturum kapsamında bir kez**
yapılır ve ilgili testler paylaşır; aksi halde tek bir test koşusu dakikalarca sürerdi.

## Giriş Parametreleri

Bu dosya doğrudan çağrılmaz; pytest tarafından otomatik yüklenir.

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| — | — | — | — | Girdi yok |

## Çıkış

### Fixture'lar

| Fixture | Kapsam | Ne verir | Maliyet |
|---|---|---|---|
| `cfg` | session | `config.yaml`'dan yüklenmiş, **değiştirilmemesi gereken** yapılandırma | ~0 |
| `fresh_cfg` | function | Her test için taze kopya — değiştirilebilir | ~0 |
| `mech` | session | Tüm limitler dahil (çarpışma da) `Mechanism` | ~0 |
| `mech_nocol` | session | Çarpışma denetimi kapalı; parça limitleri yine aktif | ~0 |
| `wmap` | session | 41×41 çalışma alanı haritası | **~23 s** |
| `worst` | session | Tam en kötü durum taraması | **~20 s** |
| `manual_scenario` | function | Tanım §2.2 doğrulama senaryosu | ~0 |

`cfg` ile `fresh_cfg` ayrımı kasıtlıdır: oturum kapsamlı bir nesneyi değiştiren bir test,
sonraki testleri sessizce bozar. Yapılandırmayı değiştiren her test `fresh_cfg` alır.

### Yardımcılar

| Fonksiyon | Ne yapar |
|---|---|
| `scan_limit(mech, axis, sign, predicate, limit_deg)` | Bir eksende 0,1° adımlarla ilerleyip `predicate`'in sağlandığı son açıyı bulur |
| `reachable(pose)` / `usable(pose)` | `scan_limit` için hazır yüklemler: yalnızca IK erişimi / tüm limitler |
| `grid_poses(mech, n, span)` | Izgaradan uygun pozları toplar |

`scan_limit` + `reachable`/`usable` ikilisi, [FINDINGS.md](../FINDINGS.md) A1'deki **üç
kademeli** çalışma alanı tablosunu test edilebilir kılar: aynı tarama, farklı yüklemle
çağrılınca "yalnızca mekanizma erişimi" ile "tüm limitler" sınırlarını ayrı ayrı verir.

### Sabitler

`ROOT` — proje kök dizini. `CONFIG` — `config.yaml` yolu. Testler çalışma dizininden
bağımsız olsun diye mutlak yol kullanılır (`tests/test_app.py` bazı testlerde
`monkeypatch.chdir` yapar).

## Bağımlılıklar

Dış paketler: `pytest`, `numpy`
Proje içi: [config.py](../files/config.md), [geometry.py](../files/geometry.md),
[loads.py](../files/loads.md)

## Kod Örneği

```python
def test_ornek(mech_nocol, fresh_cfg):
    fresh_cfg.limits.gimbal_max_deg = 3.0   # cfg degil, fresh_cfg degistirilir
    assert scan_limit(mech_nocol, 0, 1.0, usable) < 8.5
```

---
Son Güncelleme: 2026-09-27
Versiyon: 1.0.0
