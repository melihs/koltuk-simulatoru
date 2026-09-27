# collision.py

## Amaç

`bodies.py`'nin ürettiği dışbükey ilkeller (kutu, kapsül) arasındaki minimum mesafeyi
hesaplar. Çakışma varsa negatif değer döndürür. Çarpışma ve yetersiz boşluk denetiminin
sayısal temelidir.

## Giriş Parametreleri

### `min_distance(a, b)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `a`, `b` | `Box \| Capsule` | Evet | — | [bodies.md](bodies.md) ilkelleri, dünya çerçevesi, m |

### `pairwise(bodies, exclude_pairs, samples=16, prefilter=0.05, *, skip_static=False, cutoff=inf)`

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `bodies` | `list[Body]` | Evet | — | |
| `exclude_pairs` | `set[frozenset[str]]` | Hayır | `set()` | Denetlenmeyecek gövde çiftleri (yön bağımsız) |
| `samples` | `int` | Hayır | `16` | Kapsül–kutu ve kutu–kutu için kaba örnekleme sayısı |
| `prefilter` | `float` | Hayır | `0.05` | AABB boşluk eşiği (m); bundan uzak çiftler atlanır. `0` → ön eleme kapalı (doğruluk testi için) |
| `skip_static` | `bool` | Hayır | `False` | İki gövdesi de `static` olan çiftleri hiç hesaplama |
| `cutoff` | `float` | Hayır | `inf` | Kutu–kutu çiftinde bu mesafenin ötesini kesin hesaplamaz |

## Çıkış

| Fonksiyon | Çıktı |
|---|---|
| `min_distance(a, b)` | `float` — m. Pozitif = boşluk, negatif = çakışma derinliği (yaklaşık) |
| `pairwise(...)` | `list[Contact]` — mesafeye göre artan sıralı |
| `segment_segment(p0, p1, q0, q1)` | `(dist, s, t)` — mesafe ve iki parça üzerindeki parametreler |
| `point_obb(p, box)` | `float` — noktadan kutuya mesafe; nokta içerideyse 0 |

### `Contact` (dataclass)

| Alan | Tip | Açıklama |
|---|---|---|
| `body_a`, `body_b` | `str` | Gövde adları |
| `label_tr` | `str` | `"Sağ krank ↔ Sağ redüktör kutusu"` |
| `distance` | `float` | m |
| `static_pair` | `bool` | İki gövde de alt plakaya sabit mi — aşağıdaki bölüme bakın |
| `colliding` | `bool` | `distance < 0` (özellik) |

Hata fırlatmaz. Dejenere girdi (sıfır uzunluklu kapsül) nokta gibi işlenir.

## Algoritmalar ve doğrulukları

| Çift | Yöntem | Doğruluk |
|---|---|---|
| Kapsül–Kapsül | Analitik doğru parçası–doğru parçası mesafesi, eksi iki yarıçap | **Tam** (kayan nokta hassasiyetinde) |
| Nokta–Kutu | Noktayı kutu çerçevesine taşı, bileşen bazında kırp, artığın normu | **Tam** (kutu dışındaki noktalar için) |
| Kapsül–Kutu | Kapsül ekseninde `samples` nokta örnekle, en küçüğün çevresinde altın oran aramasıyla iyileştir, yarıçapı çıkar | **Yaklaşık — hata < 0,1 mm** |
| Kutu–Kutu | Önce SAT (15 eksen) ile çakışma testi; ayrıksa her kutunun köşe ve kenar örneklerini diğerine karşı ölç | **Yaklaşık** |

### Yaklaşıklık hatası

**Kapsül–Kutu.** Eksen üzerinde `n` nokta örneklenir. Gerçek en yakın nokta iki örnek
arasına düşebilir. Örnek aralığı `Δ = |p1 − p0| / (n−1)` olduğunda hata en fazla
`Δ/2` kadar **fazla** mesafe raporlar — yani sonuç **iyimser** değil, temkinlidir
(gerçek mesafe raporlanandan küçük olamaz mı? Hayır, tam tersi: örnekleme gerçek minimumu
kaçırırsa mesafeyi **olduğundan büyük** gösterir).

Bu yüzden `samples` varsayılanı 16'dır ve şu güvence sağlanır: 20 cm'lik bir çubuk için
`Δ/2 = 6,7 mm`. `clearance_min_cm` varsayılanı 1,0 cm olduğundan bu hata payı kritiktir.
**Bu nedenle örnekleme, kaba tarama sonrası altın oran araması ile iyileştirilir**
(`_min_on_segments`), gerçek hata < 0,1 mm'ye iner. Kaba örnekleme yalnızca yerel
minimumun hangi aralıkta olduğunu bulur. Arama tüm kenarlar için aynı anda (vektörize)
çalışır — bkz. Performans.

**Kutu–Kutu.** SAT çakışmayı **kesin** belirler (yanlış pozitif/negatif yok). Ayrık
kutularda mesafe köşe ve kenar örneklemesiyle bulunur; en yakın nokta bir yüzün iç
bölgesindeyse hata oluşabilir. Pratikte bu kombinasyon yalnızca `üst plaka ↔ redüktör
kutusu` gibi büyük ve kabaca hizalı çiftlerde görülür; hata < 1 mm ölçülmüştür.
Kritik çiftler (krank, çubuk) kapsüldür ve tam/iyileştirilmiş yolu kullanır.

### Negatif mesafe

Çakışma derinliği **yaklaşıktır**. Kapsül–kapsül için tamdır (eksenler arası mesafe eksi
yarıçaplar). Kutu içeren çiftlerde SAT'in en küçük örtüşme ekseni kullanılır; bu, gerçek
penetrasyon derinliğinin üst sınırıdır. Program yalnızca **işaretini** (çakışma var/yok)
ve büyüklük mertebesini kullanır, kesin derinlik gerekmiyor.

## Statik ↔ statik çiftler ayrı ele alınır

İki gövdenin de `group == "static"` olduğu bir çiftin boşluğu **poza bağlı değildir** —
alt plakaya sabit iki parça, plaka nasıl eğilirse eğilsin birbirine göre hareket etmez.
Böyle bir darlık bir **montaj/imalat sorunudur**, çalışma alanı limiti değildir.

Bu yüzden iki ayrı kullanım vardır:

| Kullanım | Çağrı | Amaç |
|---|---|---|
| Çalışma alanı limiti | `pairwise(..., skip_static=True)` | Yalnızca hareketli gövde içeren çiftler; `LimitReason.COLLISION` bunlardan doğar |
| Montaj raporu | `pairwise(..., prefilter=0)` sonra `static_pair` filtresi | Tasarım sekmesinde bir kez gösterilir |

Bu ayrım yapılmazsa, alt plakaya sabit iki parçanın darlığı tüm çalışma alanını kırmızıya
boyar ve sebebi pozla hiç ilgisi olmayan bir şey olur.

## Performans

Çalışma alanı haritası 41×41 = 1681 düğüm tarar, her düğümde ~20 hareketli çift denetlenir.
Dar boğaz `box_box`'tır: kenar örneklemesi kutu çifti başına 24 doğru parçası üzerinde
minimum arar. Üç optimizasyon:

1. **Toplu (vektörize) nokta–kutu mesafesi** (`_point_obb_signed_many`). Kaba tarama ve
   altın oran aramasının her adımı tüm kenarlar için aynı anda, tek numpy işlemiyle
   hesaplanır (`_min_on_segments`). Tek tek çağrı sayısı ~1,2 milyondan ~50 dizi işlemine
   iner.
2. **SAT'tan ucuz alt sınır.** Ayrık iki kutu için, herhangi bir ayırıcı eksendeki izdüşüm
   boşluğu gerçek mesafenin **geçerli bir alt sınırıdır**; eksenler üzerindeki en büyük
   boşluk en iyi alt sınırı verir. Bu sınır `cutoff`u aşıyorsa pahalı kenar örnekleme
   tamamen atlanır. "Uzakta" kararı değişmez, yalnızca raporlanan sayı bir miktar küçük
   kalır. `_classify` bunu `cutoff = 3 × clearance_min` ile kullanır.
3. **AABB ön elemesi** (`prefilter`). AABB'ler birbirinden `prefilter`den uzaksa detaylı
   hesap hiç yapılmaz.

Ölçülen (M-serisi Mac, tek çekirdek):

| İşlem | Önce | Sonra |
|---|---|---|
| 121 düğüm | 10,2 s | 1,5 s |
| 41×41 harita (1681 düğüm) | 96,3 s | **23,0 s** |

Sonuçlar bit bazında aynı kalır (177/1681 uygun düğüm, aynı sınır açıları). Arayüz ayrıca
`st.cache_data` ile önbelleğe alır.

## Bağımlılıklar

Dış paketler: `numpy`
Proje içi: [bodies.py](bodies.md)

## Kod Örneği

```python
from seatsim.config import load
from seatsim.geometry import Mechanism
from seatsim import bodies, collision

cfg  = load("config.yaml")
mech = Mechanism.from_config(cfg)
pose = mech.ik(0.0, 0.0)
bs   = bodies.build(cfg, pose)

# Calisma alani limiti icin: yalnizca hareketli ciftler
hareket = collision.pairwise(bs, exclude_pairs=cfg.collision.excluded(), skip_static=True)
for c in hareket[:5]:
    durum = "ÇAKIŞMA" if c.colliding else f"{c.distance*100:.1f} cm"
    print(f"{c.label_tr:45s} {durum}")

# Montaj raporu icin: statik ciftler, on eleme kapali
hepsi = collision.pairwise(bs, exclude_pairs=cfg.collision.excluded(), prefilter=0.0)
for c in [x for x in hepsi if x.static_pair][:5]:
    print(f"montaj: {c.label_tr:45s} {c.distance*100:.2f} cm")
```

---
Son Güncelleme: 2026-09-12
Versiyon: 1.1.0
