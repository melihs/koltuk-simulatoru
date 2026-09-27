# LoadsTab (Yükler sekmesi)

## Amaç

Seçilen poz ve kütle senaryosu için kuvvet/tork tablosunu, tüm çalışma alanı için tork ve
emniyet katsayısı haritalarını, en kötü durum kartını ve ters sarkaç analizini gösterir.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `cfg` | `SeatConfig` | Evet | aktif profil | |
| Kullanıcı kütlesi | `float` | Hayır | `120` kg | Kaydırıcı, 50–150 |
| Sırtlık modu | `str` | Hayır | `fixed` | `fixed` \| `tilting` |
| Takip oranı | `float` | Hayır | `0.60` | Yalnızca `fixed` modda görünür |
| AM ileri-geri | `float` | Hayır | `0` cm | −5 … +8 |
| AM yanal | `float` | Hayır | `0` cm | −5 … +5 |
| AM yüksekliği | `float` | Hayır | `25` cm | 20 … 30 |
| Pitch / Roll | `float` | Hayır | `0` | Tek nokta analizi için |

## Çıkış

Sayfanın başında kalıcı bir uyarı: emniyet katsayısı hesabının `motor.stall_torque_nm`
değerine dayandığı ve bunun **TAHMİNİ** olduğu. Ölçmeden hiçbir emniyet kararı kesin
değildir.

Altı bölüm:

### 0. Yük senaryosu kontrolleri

Kullanıcı kütlesi, taşınan oran, **sırtlık modu** (sırtlık sabit / koltuğun tamamı
eğiliyor), plakayla dönen oran (yalnız sırtlık sabitken etkin) ve ağırlık merkezinin üç
ekseni. Bu değerler yalnızca tek nokta analizini ve ısı haritasını etkiler; en kötü durum
taraması kendi aralıklarını kullanır.

### 1. Tek nokta tablosu

| Büyüklük | Sağ | Sol | Ne demek |
|---|---|---|---|
| Çubuk kuvveti | … N (basma/çekme) | … N | Rot başının taşıması gereken yük |
| Motor torku | … N·m | … N·m | Tahmini kilitlenme torkuyla karşılaştırma |
| Emniyet katsayısı | 🟢/🟠/🔴 … | … | Hedef ile karşılaştırma |

Altında dört metrik: mafsal bileşke kuvveti, direk taban eğilmesi, hareketli kütle,
yerçekimi momenti (pitch / roll).

Tablonun altında **iç tutarlılık satırı**: sanal iş yöntemi ile doğrudan moment yöntemi
arasındaki fark (ölçülen `9e-16` N·m). İki bağımsız hesabın uyuştuğunu her konumda
görürsünüz.

Poz ulaşılabilir ama bir limit aşılıyorsa kuvvetler yine hesaplanır, hangi limitin
aşıldığı turuncu kutuda yazılır. Kuvvet matrisi tekilse (bir çubuğun moment katkısı yok
olmuşsa) sayı üretilmez, sebebi yazılır.

### 2. Doğrulama senaryosu düğmesi

Aşağıda ayrıca anlatıldı. Sırası tek nokta analizinden hemen sonradır — kullanıcının
rakamlara güvenmeye karar verdiği yer.

### 3. Isı haritaları

Yan yana iki harita, yalnızca **uygun** pozlarda doldurulur (ulaşılamayan açılar boş kalır):

- Motor torku (iki motorun en kötüsü)
- Emniyet katsayısı — hedef değerde **kalın kontur** çizilir, çizginin dış tarafı yetersiz

### 4. En kötü durum kartı

Düğmeye basılınca tüm uygun pozlar × tüm senaryolar taranır (~40 s, sonuç önbelleğe
alınır). Başlangıç tasarımında çıkan sonuç:

> 🟠 **SINIRDA**
>
> En kötü durum: 19,7 N·m tork gerekiyor, tahmini kilitlenme torku 30 N·m. Pay 1,52 kat —
> hedef 2,0. Çalışır ama ısınma ve yavaşlama beklenir; ölçüm hatası bunu daha da aşağı
> çekebilir.
>
> Nerede: pitch −3,6°, roll −7,2°
> Hangi senaryoda: 120 kg kullanıcı (taşınan %85), ağırlık merkezi +8 cm ileri, +5 cm yan,
> 30 cm yukarıda, koltuğun tamamı eğiliyor
>
> Not: 30 N·m bir **TAHMİNDİR**. Gerçek değeri ölçmeden bu sonuç kesinleşmez — ölçüm
> yöntemi `docs/ASSUMPTIONS.md` bölüm 1'de.

Altında dört metrik (en kötü tork, emniyet katsayısı, taranan poz ve senaryo sayısı) ve
bir tablo: en yüksek çubuk basma/çekme kuvveti, mafsal bileşke kuvveti, direk taban
eğilmesi — her biri için **ne ile karşılaştırılacağı** yazılı.

### 5. Ters sarkaç analizi

- Eğime karşı yerçekimi momenti eğrisi; "kendi kendini artıran" bölge taralı
- Yerçekimi sertliği `∂M/∂θ` değeri ve yorumu:

> *"Yerçekimi sertliği +346 N·m/rad — Pozitif olması, plaka eğildikçe onu **daha da**
> eğmeye çalışan momentin büyüdüğü anlamına gelir; sistem ters sarkaç gibi davranır ve
> statik olarak **kararsızdır**. Motor durduğunda sonsuz vida redüktörü bunu tutar, ama
> PID'in kapalı çevrimde yenmesi gereken şey budur. Faz 3'te PID ayarının en kritik
> girdisi olacak."*

Ağırlık merkezi mafsalın **altına** indirilirse (negatif yükseklik) değer negatife döner
ve metin "kararlı sarkaç" olarak değişir. Nötr pozda analitik değeri `W · h`'dir.

### 6. Doğrulama senaryosu düğmesi

Tek tıkla tanım §2.2'deki elle hesabı çalıştırır ve beklenen değerlerle yan yana gösterir:

| Büyüklük | Elle hesap | Program | Fark |
|---|---|---|---|
| Mafsal momenti | 44,145 N·m | 44,145 N·m | %0,000 |
| Toplam çubuk kuvveti | 215,320 N | 215,341 N | %0,010 |
| Çubuk başına kuvvet | 107,660 N | 107,671 N | %0,010 |
| Motor başına tork | 4,307 N·m | 4,307 N·m | %0,008 |

Altında tek satırlık karar: *"Tüm değerler ±%2 içinde (en büyük fark %0,010)."*

Bu, kullanıcının programa güvenip güvenemeyeceğini kendi gözüyle doğruladığı yerdir.

## Bağımlılıklar

Dış paketler: `streamlit`, `plotly`, `numpy`, `pandas`
Proje içi: [loads.py](../files/loads.md), [geometry.py](../files/geometry.md),
[config.py](../files/config.md), [units.py](../files/units.md), `ui/common.py`

## Kod Örneği

```python
from seatsim.ui import loads_tab
loads_tab.render(st.session_state.cfg)
```

---
Son Güncelleme: 2026-09-12
Versiyon: 1.1.0
