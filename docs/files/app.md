# app.py

## Amaç

Streamlit uygulamasının giriş noktası. Kenar çubuğunu ve sekmeleri kurar, aktif
yapılandırmayı yükler, her sekmeyi ilgili modüle devreder. **Fizik hesabı yapmaz,
çizim yapmaz** — yalnızca düzen kurar ve hata yollarını yönetir.

## Giriş Parametreleri

| Ad | Tip | Zorunlu | Varsayılan | Açıklama |
|----|-----|---------|------------|----------|
| `config.yaml` | dosya | Hayır | proje kökü | Yoksa veya bozuksa anlaşılır hata gösterilir |

Komut satırı argümanı almaz. Çalıştırma: `streamlit run app.py`

## Çıkış

Tarayıcıda 8 sekmelik arayüz. Sekme → modül eşlemesi:

| # | Sekme | Modül |
|---|---|---|
| 1 | Tasarım | [DesignTab](../components/DesignTab.md) |
| 2 | Çalışma alanı | [WorkspaceTab](../components/WorkspaceTab.md) |
| 3 | Yükler | [LoadsTab](../components/LoadsTab.md) |
| 4–8 | Dinamik test, Optimizasyon, Hareket, PID ayarı, Rapor | [PendingTabs](../components/PendingTabs.md) |

## Kenar çubuğu

Her sekmede görünür ve şunları taşır:

1. **Faz durumu** — hangi fazın bittiği, hangisinin neyi beklediği (⏸ = `SMC3.ino`)
2. **Birimler ve işaretler** — ekranda cm/derece, kodun içinde SI; `pitch +` = ön yukarı,
   `roll +` = sağ taraf yukarı. Bu iki satır, işaret hatasının en sık kaynağıdır
3. **Ölçülmemiş parametreler** — kaç tane olduğu ve açılır listede her biri için
   "nasıl ölçerim" notu. Program başlangıç durumunda 21 tahmini değer taşır

## Hata yönetimi

`config.yaml` yüklenemezse (`FileNotFoundError`, `ValueError`, `TypeError`) sayfa bir hata
kutusu gösterip durur — yığın izi değil. Sekmelerin kendi hataları kendi modüllerinde
yakalanır; `Mechanism` kurulamayan bir yapılandırmada ilgili sekme "Geometri kurulamadı"
mesajı verir ve diğer sekmeler çalışmaya devam eder.

## Bağımlılıklar

Dış paketler: `streamlit`
Proje içi: [config.py](config.md), `seatsim/ui/*`

## Kod Örneği

```bash
uv run streamlit run app.py
```

Testten çalıştırmak için:

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py", default_timeout=900)
at.run()
assert list(at.exception) == []
```

---
Son Güncelleme: 2026-09-27
Versiyon: 1.0.0
