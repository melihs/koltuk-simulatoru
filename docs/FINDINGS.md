# Bulgular — Başlangıç Tasarımının Kısıt Analizi

## Amaç

Kullanıcının tanımladığı başlangıç ölçülerinin, yine kullanıcının tanımladığı kısıtları
sağlayıp sağlamadığını sayısal olarak kaydeder. Bu dosya kalıcı kayıttır: tasarım
değiştikçe güncellenmez, yeni bulgular altına eklenir.

## Giriş Parametreleri

Bu doküman kod içermez. Analiz, tanımdaki §1.2 başlangıç ölçüleriyle yapılmıştır.

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| — | — | — | — | Girdi yok; bulgular `config.yaml` başlangıç değerlerine dayanır |

## Çıkış

Dört kritik çelişki (A1–A4), dokuz pratik sorun (B1–B9), sayısal kanıt ve çıkış yolları.

## Bağımlılıklar

- [ARCHITECTURE.md](ARCHITECTURE.md) — faz planı
- [ASSUMPTIONS.md](ASSUMPTIONS.md) — bu analizde kullanılan tahmini değerler
- [files/geometry.md](files/geometry.md) — ters kinematik yöntemi
- [files/loads.md](files/loads.md) — tork hesabı yöntemi

---

## A. Kritik çelişkiler

### A1 — Başlangıç geometrisi istenen çalışma alanına ulaşamıyor

Programın ters kinematiği, tanımdaki ölçülerle (krank 4 cm, çubuk 5,5 cm, plaka bağlantısı
mafsalın 20,5 cm önünde, motor mili `(±18,2 ; 7 ; 24,5)` cm) çözüldü. Sınır **üç kademede**
raporlanıyor, çünkü hangi limitin bağladığı tasarım kararını değiştiriyor:

| Kademe | Pitch yukarı | Pitch aşağı | Roll | Bağlayan limit |
|---|---|---|---|---|
| 1. Yalnızca mekanizma erişimi (krank/çubuk çözülebiliyor mu) | **+8,5°** | −33,2° | **±9,8°** | krank yetişmiyor |
| 2. + parça limitleri (ölü nokta, rot başı, mafsal, pot, takoz) | **+8,1°** | −15,5° | **±9,0°** | yukarı: ölü nokta · roll: rot başı |
| 3. + çarpışma (gerçek sınır) | **+8,1°** | **−8,3°** | **±9,0°** | aşağı: üst plaka ↔ redüktör kutusu |

Hedeflerin **beşi de** sağlanmıyor:

| Hedef | Sonuç | Ulaşılan |
|---|---|---|
| Pitch +10° | **İHLAL** | +8,1° |
| Pitch −10° | **İHLAL** | −8,3° |
| Roll +10° | **İHLAL** | +9,0° |
| Roll −10° | **İHLAL** | −9,0° |
| Pitch 7° + Roll 7° (dört köşe) | **İHLAL** | ulaşılamıyor |

41×41 ızgarada taranan 1681 düğümden yalnızca **177'si (%10,5)** kullanılabilir. Kalanların
sebep dağılımı:

| Sebep | Düğüm |
|---|---|
| Erişim dışı — krank yetişmiyor | 872 |
| Çarpışma | 253 |
| Kardan mafsalı açı limiti | 170 |
| Mekanik takoz | 145 |
| Rot başı sapma limiti | 46 |
| Krank ölü noktası | 18 |

**Sebep:** Çubuk/krank oranı 5,5 / 4 = **1,375**. Bu oran çok düşük. Krank yukarı döndükçe
hareketin giderek artan kısmı çubuğun yatmasına gidiyor, plakaya aktarılan dikey hareket
azalıyor. Tipik krank-biyel mekanizmalarında bu oran 3'ün üzerindedir.

**İkincil sebep:** Nötr konumda krank tam yatay. Mekanizmanın erişimi yukarı +8,5°, aşağı
−33,2° — yaklaşık 4 kat asimetrik. Nötr konum, kullanılabilir yayın ortasına oturmuyor.

### A2 — Toplam yükseklik kısıtı ihlal ediliyor

```
13,0  mafsal dönme merkezi yüksekliği
 2,0  üst plaka alt yüzeyi, mafsal merkezinin üstünde
 1,8  üst plaka kalınlığı
 4,0  minder
─────
20,8 cm       kısıt: ≤ 18 cm        →  2,8 cm FAZLA
```

### A3 — Çalışma alanı ile tork emniyet katsayısı birbirini dışlıyor

Bu, projenin merkezî mühendislik gerilimidir.

**En kötü durum statik momenti** (120 kg × %85 = 102 kg taşınan, AM mafsalın 8 cm önünde ve
32,8 cm üstünde, pitch −10°'de ters sarkaç etkisiyle yatay kol 13,6 cm'e çıkıyor):

```
M = 102 × 9,81 × 0,136 ≈ 136 N·m
çubuk başına kuvvet ≈ 136 / 0,205 / 2 ≈ 331 N
```

| Krank boyu | Motor başına tork | SF (30 N·m stall ile) | Çalışma alanı |
|---|---|---|---|
| 4,0 cm (mevcut) | 13,3 N·m | 2,25 | **yetersiz ✗** |
| 6,5 cm | 21,6 N·m | **1,39 ✗** | yeterli ✓ |
| 7,0 cm | 23,2 N·m | **1,29 ✗** | yeterli ✓ |

**Programın ölçtüğü gerçek değer** (119 ulaşılabilir poz × 540 senaryo taraması):

| | Değer |
|---|---|
| En kötü motor torku | **19,7 N·m** |
| Nerede | pitch −3,6°, roll −7,2° |
| Hangi senaryoda | 120 kg, AM +8 cm ileri / +5 cm yan / 30 cm yukarı, koltuk da eğiliyor |
| **Emniyet katsayısı** | **1,52 → SINIRDA** |

Yukarıdaki 13,3 N·m'lik kaba tahmin, saf pitch varsayımıyla yapılmıştı. Gerçek en kötü
durum **eşzamanlı pitch + roll**'dedir: orada bir çubuğun moment kolu küçülür, yük büyük
ölçüde tek çubuğa biner ve tork 1,5 kat artar. Yani mevcut 4 cm krankla bile emniyet
katsayısı hedefin altında.

**Bağlantı noktasını kaydırmak bu çelişkiyi çözmez.** Temel ilişki:

```
motor torku = plaka momenti × krank boyu / bağlantı kolu
```

Bağlantı kolunu büyütmek kuvveti azaltır, ama aynı açıyı elde etmek için gereken krank
boyunu **aynı oranda** büyütür. İkisi sadeleşir, tork değişmez. Bu bir modelleme kusuru
değil, mekanizmanın enerji korunumundan gelen bir kısıttır.

**Çıkış yolları (etkilerine göre sıralı):**

1. **Gerçek stall torkunu ölç.** 30 N·m bir tahmindir. Motor 45 N·m verirse krank 7 cm'de
   SF = 1,94 olur ve çelişki neredeyse kapanır. **Ölçülene kadar projenin kapanıp
   kapanmadığı bilinmiyor.** Ölçüm yöntemi: [ASSUMPTIONS.md](ASSUMPTIONS.md).
2. **AM ileri kayma sınırını daralt.** +8 cm yerine +5 cm → M = 106 N·m, gereken krank
   5,8 cm'e iner. Statik momentin yarısından fazlası bu terimden geliyor.
3. **Tasarım yükünü düşür.** 120 → 100 kg → M = 113 N·m.
4. **Hedef açıyı düşür.** ±10° yerine ±8° → gereken krank ~5,5 cm.
5. **Statik momenti dengele.** Plakayı öne doğru çeken bir yay/gaz amortisörü, sabit
   bileşeni (AM ileri kayması) motordan alır. Motor sadece dinamik yükü karşılar.

### A4 — Güç kaynağı iki motoru stall'da besleyemiyor

| Kalem | Değer |
|---|---|
| İki motor stall akımı | 2 × 20 A = **40 A** |
| Meanwell LRS-350-24 sürekli | **14,6 A** |
| LRS-350-24 tepe (~%120, kısa süreli) | ~17,5 A |
| Sigortalar | 2 × 20 A |

Stall'da kaynak çöker veya koruma atar; sigortalar atmaz (her biri 20 A'i görür).
**Faz 3'te kaynağın akım limiti ve gerilim düşümü modellenmeden akım ve ısı tahminleri
gerçeği yansıtmaz.** Ayrıca sigorta seçimi kaynağı korumuyor — kaynak, sigortalardan önce
devreye giren asıl limit.

---

## B. Pratik sorunlar

| # | Sorun | Ayrıntı |
|---|---|---|
| B1 | Motor mili plaka izdüşümünün dışında | Mil z = +24,5 cm, üst plakanın ön kenarı z = +24,0 cm. Kısıt "motorlar üst plakanın izdüşümü içinde kalmalı" diyor — 0,5 cm ihlal. |
| B2 | 5,5 cm çubuk boyu M10 rot başları için alt sınırda | İki M10 rot başı için tipik minimum merkez-merkez ~4–5 cm. 5,5 cm mümkün ama nötr ayarı için diş boşluğu neredeyse kalmıyor. A1'in çözümü (daha uzun çubuk) bunu da düzeltir. |
| B3 | Krank, kendi redüktör kutusunun izdüşümü içinde dönüyor | Krank 4 cm, redüktör kutusu mil ekseninden 3,5 cm yukarı/aşağı uzanıyor. Krank ancak kutunun **yanından** (mil ekseni boyunca dışta) dönebilir — bkz. B9. Program krank ↔ kendi kutusu çiftini çarpışma kontrolünde tutar, hariç tutmaz. |
| B4 | Mekanik takoz yukarı yönde hiç devreye girmiyor | Mekanizma yukarı zaten +8,1° yapabiliyor, takoz 12°'de. Aşağı yönde mekanizmanın ham erişimi −33,2°'ye kadar gidiyor; orada takoz gerçek bir koruma katmanı. |
| B5 | Takozlar ~6–8 cm boyunda olmak zorunda | ±12°'de devreye girmesi için ön takozların üst yüzeyi y ≈ 10,1 cm, arka takozların y ≈ 7,8 cm'de olmalı. Alt plakanın üstü y = 1,8 cm olduğuna göre takoz + altlık 6–8,3 cm. Yani lastik tampon değil, üstü lastik kaplı bir **direk** gerekiyor. Program her takozun devreye girme açısını hesaplayıp raporlar (`Mechanism.stop_engagement_deg()`), sabit ±12° varsaymaz. |
| B6 | Tek turlu pot doğrudan mile bağlı | Krank pot aralığını aşarsa pot fiziksel olarak kırılır. Yazılımsal limitten **önce** mekanik durdurucu şart. Çalışma alanı haritasına ayrı bir sınırlayıcı sebep olarak eklendi. |
| B7 | Mafsal direği ve mafsalın kendisi yüksek **kuvvet** görüyor (eğilme değil) | Program ölçtü: direk tabanında **1698 N** bileşke kuvvet ama yalnızca **22,7 N·m** eğilme. İlk tahminim 136 N·m'ydi ve **yanlıştı**: kardan mafsalı pitch/roll momenti taşıyamaz, devrilme momentini iki itme çubuğu alır. Direğe kalan eğilme sadece `yatay kuvvet × direk yüksekliği` kadardır. Kritik olan **eksenel/radyal kuvvettir**: ucuz bir U-joint 1700 N taşımayabilir. Rapora hem kuvvet hem eğilme eklendi. |
| B8 | Ön takozlar motorların içine denk geliyor | Motor takımı `\|x\| = 9,5…15,9 cm` bandını kaplıyor (redüktör kutusu + silindir). Ön takozlar bu yüzden **içe alınmak zorunda** (`x = ±5,5 cm`), bu da roll'ü sınırlama yeteneklerini zayıflatıyor — roll kolu yalnızca 5,5 cm. Arka takozlar motorların arkasında olduğu için serbest (`x = ±18 cm`). |
| B9 | Krank, motor silindirini aşmak için yeterli mil çıkıntısı ister | Motor silindiri Ø6,4 cm, redüktör kutusu 6,0 cm — silindir kutunun yanından 0,2 cm taşıyor. Krank düzleminin kutudan **en az 2,5 cm** dışta olması gerekiyor (`hardware.shaft_protrusion_cm`), yoksa krank dönerken motor gövdesine çarpar. 1,5 cm ile boşluk 0,7 cm'ye düşüyor, 1 cm kısıtının altında. |

---

## C. Modelleme notu — verim çift sayımı

Tanımda hem "stall torku 30 N·m" (mile 10 cm kol takıp kantarla ölçülür) hem "ileri yön
verimi %50" veriliyor. **Mil ucunda ölçülen stall torku redüktör kayıplarını zaten
içerir.** Üstüne ayrıca %50 verim uygulamak kaybı iki kez sayar.

Karar: `gearbox.forward_efficiency` parametresi yalnızca motor tarafı verilerinden çıkış
torku türetilirken kullanılır. Ölçülmüş çıkış torku girildiğinde uygulanmaz. Geri sürme
(back-drive) tarafı ayrı parametredir (`gearbox.reverse_efficiency`, varsayılan 0 =
tam kendiliğinden kilitlenme).

---

## Kod Örneği

Bulguları programda yeniden üretmek için:

```python
from seatsim.config import load
from seatsim.geometry import Mechanism

mech = Mechanism.from_config(load("config.yaml"))

# Tum limitler dahil (carpisma da) gercek sinir
mech = Mechanism.from_config(load("config.yaml"), check_collision=True)
print(mech.max_pitch_deg())        # (+8.1, -8.3)
print(mech.max_roll_deg())         # (+9.0, -9.0)
print(mech.is_reachable(7, 7))     # False

# Yalnizca mekanizma erisimi (parca limitleri olmadan)
raw = Mechanism.from_config(load("config.yaml"), check_collision=False)
print(raw.ik(deg_to_rad(8.5), 0.0).reachable)   # True
print(raw.ik(deg_to_rad(8.6), 0.0).reason)      # UNREACHABLE_CIRCLE

# Takozlarin gercekte hangi acida devreye girdigi
for s in mech.stop_engagement_deg():
    print(s["label_tr"], s["engages_at_deg"], "derece")
```

---
Son Güncelleme: 2026-09-12
Versiyon: 2.0.0
