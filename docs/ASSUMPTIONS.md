# Varsayımlar ve Belirsizlikler

## Amaç

Programda kullanılan ve **ölçülmemiş** her fiziksel değeri, güven düzeyini ve nasıl
ölçüleceğini listeler. Tanımdaki "emin olmadığın fiziksel değerleri uydurma; tahmini diye
işaretle ve nasıl ölçebileceğimi söyle" maddesinin karşılığıdır.

## Giriş Parametreleri

Bu doküman kod içermez.

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| — | — | — | — | Girdi yok |

## Çıkış

Güven düzeyi etiketli varsayım listesi. Arayüzde her parametrenin yanında aynı rozet
gösterilir.

## Bağımlılıklar

- [files/config.md](files/config.md) — parametrelerin tam şeması
- [FINDINGS.md](FINDINGS.md) — bu varsayımlara dayanan çelişki analizi

---

## Güven düzeyi rozetleri

| Rozet | Anlamı |
|---|---|
| **ÖLÇÜLDÜ** | Kullanıcı kendi sisteminde ölçtü, girdi. Program bu değeri sorgulamaz. |
| **TAHMİNİ** | Benzer sistemlerden veya fizikten türetilmiş makul değer. **Ölçülmeli.** Sonuçlar buna duyarlıysa arayüz uyarır. |
| **TASARIM** | Kullanıcının seçtiği hedef/ölçü. Ölçülecek bir şey değil, karar. |
| **TÜRETİLDİ** | Başka parametrelerden hesaplanır, doğrudan girilmez. |

Programın başlangıç durumunda **ÖLÇÜLDÜ olan hiçbir değer yoktur.**

---

## 1. Motor — en kritik belirsizlik

Tork emniyet katsayısı doğrudan bu üç değere bağlı. [FINDINGS.md](FINDINGS.md) A3'te
gösterildiği gibi projenin kapanıp kapanmadığını belirleyen sayı **stall torkudur**.

| Parametre | Varsayılan | Rozet | Nasıl ölçülür |
|---|---|---|---|
| `motor.no_load_rpm` | 55 rpm | **TAHMİNİ** | Motoru 24 V'a yüksüz bağla, mile bir işaret koy, telefonla 30 sn video çek, tur say, ×2 = rpm. |
| `motor.stall_torque_nm` | 30 N·m | **TAHMİNİ** | Mile **10 cm**'lik sağlam bir kol kaynakla/cıvatala. Kolun ucuna el tipi bagaj kantarı bağla. Motoru 24 V'a ver, kantarı motor **duruncaya kadar** çek, en yüksek okumayı kaydet. `Tork = kg × 9,81 × 0,10`. Kolun tam yatay, çekmenin tam dikey olmasına dikkat et. 2–3 sn'den uzun tutma, motor yanar. |
| `motor.stall_current_a` | 20 A | **TAHMİNİ** | Yukarıdaki ölçüm sırasında besleme hattına pens ampermetre tak. Not: LRS-350-24 bu akımı veremez ([FINDINGS.md](FINDINGS.md) A4) — ölçüm için akü veya güçlü bir kaynak gerekir. |
| `motor.no_load_current_a` | 2 A | **TAHMİNİ** | Yüksüz dönerken pens ampermetre. |
| `motor.winding_resistance_ohm` | — | **TÜRETİLDİ** | `R = V / I_stall` |
| `motor.back_emf_constant` | — | **TÜRETİLDİ** | `ke = (V − I_noload·R) / ω_noload` |
| `gearbox.forward_efficiency` | 0,50 | **TAHMİNİ** | Yalnızca motor tarafı verisinden çıkış torku türetilirken kullanılır. Ölçülmüş çıkış stall torku girildiğinde **uygulanmaz** ([FINDINGS.md](FINDINGS.md) C). |
| `gearbox.reverse_efficiency` | 0,0 | **TAHMİNİ** | 0 = tam kendiliğinden kilitlenme. Ölçüm: motoru sürmeden plakaya ağırlık koy, kayıyor mu bak. Kayıyorsa 0 değil. |

**İki motorun birbirinden farklı olabileceğini unutma.** Aynı model olsalar bile silecek
motorlarında %10–20 fark normaldir. Faz 3'te iki motor ayrı parametre seti alacak.

## 2. Kütle ve ağırlık merkezi

| Parametre | Varsayılan | Rozet | Not |
|---|---|---|---|
| `mass.user_kg` | 120 kg (tasarım) | **TASARIM** | Analiz 60 / 90 / 120 kg'ı tarar. |
| `mass.carried_fraction` | 0,85 | **TAHMİNİ** | Bacakların bir kısmı yere/pedallara bastığı için koltuğun taşıdığı oran. Ölçüm: banyo terazisine oturma pozisyonunda otur, ayakların yerde, teraziyi koltuğun altına koy. |
| `mass.plate_assembly_kg` | 8 kg | **TAHMİNİ** | Üst plaka + minder + braketler. Ölçüm: parçaları tartıp topla. Kolay ölçülür, mutlaka ölç. |
| `mass.seat_kg` | 12 kg | **TAHMİNİ** | Yalnızca `backrest: tilting` senaryosunda kullanılır. Koltuğu tart. |
| `mass.user_com_height_cm` | 25 cm | **TAHMİNİ** | Minder yüzeyinin üstünde. Oturan bir yetişkin için 20–30 cm tipik. Analiz bu aralığı tarar. |
| `mass.user_com_fore_aft_cm` | 0 (aralık −5…+8) | **TASARIM** | Öne eğilme senaryosu. En kötü durum taramasının en etkili terimi. |
| `mass.user_com_lateral_cm` | 0 (aralık ±5) | **TASARIM** | Virajda yana yaslanma. |
| `mass.backrest_follow_fraction` | 0,60 | **TAHMİNİ** | `backrest: fixed` senaryosunda kullanıcı kütlesinin plakayla birlikte dönen oranı. Ölçülmesi zor bir değer; en kötü durum taraması 0,4–1,0 aralığını tarar. |

## 3. Atalet (Faz 3'te kullanılacak)

| Parametre | Varsayılan | Rozet | Not |
|---|---|---|---|
| `inertia.user_body_shape` | kutu 40×30×60 cm | **TAHMİNİ** | Kullanıcıyı atalet için basit kutu olarak modelliyoruz. Gerçek insan rijit değildir. |
| `inertia.rigid_user` | true | **TAHMİNİ** | Kullanıcının plakaya rijit bağlı olduğu varsayımı. Gerçekte insan vücudu yaylanır ve plakanın hareketini sönümler. Bu varsayım **bant genişliğini olduğundan yüksek** tahmin ettirir. |

## 4. Mekanik limitler

| Parametre | Varsayılan | Rozet | Not |
|---|---|---|---|
| `limits.rod_end_misalign_deg` | 12° | **TAHMİNİ** | Üretici verisi yoksa M10 küresel rot başı için tipik değer. Rot başının kataloğunda "misalignment angle" olarak geçer. |
| `limits.gimbal_max_deg` | 20° | **TAHMİNİ** | Kardan mafsalının fiziksel açı limiti. Ölçüm: mafsalı elinle yat, takıldığı açıyı açıölçerle ölç. |
| `limits.deadpoint_margin_deg` | 20° | **TASARIM** | Transmisyon açısının 0° veya 180°'ye asgari uzaklığı. |
| `limits.clearance_min_cm` | 1,0 cm | **TASARIM** | Parçalar arası asgari boşluk. |
| `pot.mechanical_range_deg` | 270° | **TAHMİNİ** | Tek turlu potansiyometrenin mekanik açısı. Üreticiye göre 270° veya 300°. Ölçüm: potu uçtan uca çevirip açıölçerle ölç. |
| `stops.top_height_cm` | `[10,07; 10,07; 7,78; 7,78]` | **TÜRETİLDİ** | Takoz **başına** üst yüzey yüksekliği; ±12° hedefine göre hesaplandı. Konum değişirse `Mechanism.suggest_stop_heights_cm(12.0)` ile yeniden hesaplayın — program her takozun gerçek devreye girme açısını raporlar. |
| `stops.positions_cm` | `[[±5,5; 18], [±18; −16]]` | **TASARIM** | Ön takozlar içe alınmak zorunda: motor takımı `\|x\| = 9,5…15,9 cm` bandını kaplıyor (bkz. [FINDINGS.md](FINDINGS.md) B8). |

## 5. Geometri

Tüm geometrik ölçüler **TASARIM** rozetlidir: kullanıcının kararıdır, ölçülecek bir şey
değildir. Faz 4 optimizasyonunda değişecek olanlar bunlardır. Ancak:

- Halihazırda satın alınmış parçaların ölçüleri **ÖLÇÜLDÜ** olarak işaretlenmeli ve
  arayüzdeki "sabitle (elimde var)" kutusu işaretlenmelidir. Bu parametreler optimizasyonda
  değişmez.
- Redüktör kutusu, motor silindiri ve pot braketi ölçüleri **TAHMİNİ**'dir (6×8×7 cm,
  Ø6,4×13 cm). Motorlar elde olduğunda kumpasla ölçülüp girilmelidir; çarpışma analizi
  doğrudan bunlara dayanıyor.
- Mil ekseni boyunca yerleşim de **TAHMİNİ**'dir ve çarpışma sonuçlarını doğrudan belirler:

| Parametre | Varsayılan | Rozet | Nasıl ölçülür |
|---|---|---|---|
| `hardware.shaft_protrusion_cm` | 2,5 cm | **TAHMİNİ** | Redüktör kutusunun dış yüzünden mil ucuna kadar kumpasla ölç. Krank bu düzlemde döner; çok küçükse krank motor gövdesine çarpar (bkz. [FINDINGS.md](FINDINGS.md) B9). |
| `hardware.pot_offset_cm` | 2,0 cm | **TASARIM** | Pot braketini krank düzleminden ne kadar dışta konumlandıracağınız. |
| `hardware.user_box_cm` | 40×30×50 cm | **TAHMİNİ** | Kullanıcıyı atalet için temsil eden kutu. Kutu, yük modelinin kullandığı ağırlık merkezine ortalanır. Faz 3'te önem kazanır. |

## 6. Modelin yapısal varsayımları

Bunlar sayı değil, **modelin kendisiyle ilgili** varsayımlardır:

1. **Tüm parçalar rijit.** Plaka esnemesi, çubuk uzaması, mafsal boşluğu modellenmiyor.
   Gerçek sistemde bunlar takip hatası ve titreşim üretir.
2. **Rot başlarında boşluk (backlash) yok.** Gerçek rot başlarında 0,1–0,5 mm boşluk olur;
   bu, küçük genlikli hareketlerde ölü bölge gibi davranır.
3. **Sürtünme yok** (Faz 3'te redüktör kilitlenmesi dışında). Mafsal ve rot başı sürtünmesi
   ihmal ediliyor.
4. **Kullanıcı pasif.** Gerçekte kullanıcı direksiyona ve pedala tutunur, gövdesini
   dengeler; bu hem yükü hem hareketi değiştirir.
5. **İki motor özdeş.** Faz 3'te ayrılacak.
6. **Plaka ile minder arasında kayma yok.**
7. **Ayaklar yerde/pedalda sabit.** `carried_fraction` bunu tek bir oranla temsil ediyor;
   gerçekte plaka eğildikçe bu oran değişir.

Bu varsayımların tamamı, programın sonuçlarını **iyimser** yönde etkiler. Gerçek sistemin
biraz daha yavaş, biraz daha titrek ve biraz daha yüksek akımlı olmasını bekleyin.

## Kod Örneği

```python
from seatsim.config import load

cfg = load("config.yaml")
for path, param in cfg.uncertain_parameters():      # rozeti TAHMİNİ olanlar
    print(f"{path:40s} {param.value:>8} {param.unit:6s} → {param.how_to_measure}")
```

---
Son Güncelleme: 2026-09-12
Versiyon: 1.1.0
