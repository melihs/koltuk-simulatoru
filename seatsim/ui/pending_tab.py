"""Henuz yapilmamis fazlarin sekmeleri: ne gelecek, neyi bekliyor.

Bos bir sekme gostermek yerine, o fazin ne uretecegini ve on kosulunun ne oldugunu
yazar. Boylece hangi fazda oldugunuz ve sirada ne oldugu ekrandan anlasilir.
"""

from __future__ import annotations

import streamlit as st

PHASES: dict[str, dict] = {
    "dynamics": {
        "title": "Dinamik test",
        "phase": 3,
        "blocked_by": "`SMC3.ino` kaynak dosyası",
        "why": (
            "PID formülü, ölçekleme ve limit mantığı firmware'den **birebir** okunmalı. "
            "Amaç, bulunan Kp/Ki/Kd değerlerinin doğrudan SMC3Utils'e girilebilmesi; "
            "varsayımla modellenen bir PID bu amacı bozar."
        ),
        "will_do": [
            "Motorun tork-hız eğrisi, eşdeğer sargı direnci ve zıt EMK sabiti — ölçtüğünüz üç değerden türetilir",
            "Sonsuz vida redüktörünün kendiliğinden kilitlenmesi: motor sürülmezken plaka yük altında sabit kalmalı",
            "SMC3'ün ayrık PID döngüsü, ölü bölge, min/max PWM ve yazılımsal limitleri",
            "RK4 ile en az 1 kHz zaman entegrasyonu; kontrolcü kendi hızında ayrık çalışır",
            "Güç kaynağının akım limiti ve gerilim düşümü — **bu olmadan akım ve ısı tahminleri gerçeği yansıtmaz** (bkz. `docs/FINDINGS.md` A4)",
            "Çıktılar: hedef/gerçek açı, takip hatası, motor torkları ve akımları, toplam kaynak akımı, maksimum açısal hız ve ivme, bant genişliği (−3 dB)",
        ],
        "meanwhile": (
            "Bu arada **motorun kilitlenme torkunu ölçün** — `docs/ASSUMPTIONS.md` §1. "
            "Projenin yapılabilir olup olmadığını belirleyen tek sayı o."
        ),
    },
    "optimize": {
        "title": "Optimizasyon",
        "phase": 4,
        "blocked_by": "Faz 3",
        "why": "Amaç fonksiyonları bant genişliği ve tepe akımı gibi dinamik çıktıları içerir.",
        "will_do": [
            "pymoo NSGA-II ile Pareto cephesi: maksimum açısal hız ve bant genişliğini artır, en kötü durum torkunu ve tepe akımını azalt, toplam yüksekliği azalt",
            "Ağırlık verebileceğiniz tek amaçlı mod (scipy differential_evolution)",
            "Tasarım değişkenleri: mafsal konumu, bağlantı noktaları, motor mili konumu, krank boyu, çubuk boyu — **'Sabitle' kutusu işaretli olanlar hariç**",
            "Sonuçların başlangıç tasarımıyla yan yana karşılaştırması",
            "Duyarlılık analizi: her ölçüde ±2 mm yapım hatası sonucu ne kadar değiştirir? Atölyede en dikkat edeceğiniz ölçüler sıralanır",
        ],
    },
    "cueing": {
        "title": "Hareket (motion cueing)",
        "phase": 5,
        "blocked_by": "Faz 3",
        "why": "Filtrelerin etkisi ancak dinamik model üzerinde değerlendirilebilir.",
        "will_do": [
            "Girdiler: boyuna ivme (fren/gaz), yanal ivme (viraj), araç pitch ve roll açıları",
            "Yüksek geçiren washout filtresi ve düşük geçiren tilt coordination; kazançlar, açı ve açısal hız limitleri parametre",
            "Test profilleri: basamak, 0,1–5 Hz sinüs taraması, sert fren, şikan, rastgele yol titreşimi",
            "CSV telemetri yükleme ve sütun eşleştirme ekranı — Assetto Corsa gibi oyunlardan kaydedilmiş veriyi oynatma",
            "Dinamik testin 3D görünümde animasyon olarak oynatılması",
        ],
    },
    "pid": {
        "title": "PID ayarı",
        "phase": 6,
        "blocked_by": "Faz 3 ve Faz 5",
        "why": "Ayar, gerçek kontrolcü modeli ve gerçekçi giriş profilleri üzerinde yapılır.",
        "will_do": [
            "Kp, Ki, Kd ve ölü bölgenin otomatik ayarı (ITAE minimizasyonu, aşım ≤ %5, titreşim yok kısıtıyla)",
            "60 / 90 / 120 kg'da sağlam çalışan **tek** bir set",
            "Sonuç, doğrudan SMC3Utils'e girilecek biçimde — 'başlangıç değeridir, gerçek sistemde ince ayar gerekir' notuyla",
        ],
    },
    "report": {
        "title": "Rapor",
        "phase": 6,
        "blocked_by": "Faz 3–5",
        "why": "Rapor tüm fazların çıktısını bir araya getirir.",
        "will_do": [
            "Tek düğmeyle Markdown + PDF",
            "Atölye ölçü listesi: mafsal direği yüksekliği, delik konumları, krank boyu, çubuk boyu, motor montaj konumları — kaynakçıya verilecek biçimde",
            "Üstten ve yandan ölçülü 2D çizimler",
            "Tork, akım ve kuvvet özet tablosu, emniyet katsayıları",
            "Önerilen PID ve limit değerleri",
            "Varsayımlar listesi ve belirsizlikler",
        ],
    },
}


def render(key: str) -> None:
    info = PHASES[key]
    st.header(info["title"])
    st.info(
        f"**Faz {info['phase']} — henüz yapılmadı.** Ön koşul: {info['blocked_by']}.\n\n"
        f"{info['why']}"
    )

    st.subheader("Bu sekme ne yapacak")
    for item in info["will_do"]:
        st.markdown(f"- {item}")

    if "meanwhile" in info:
        st.divider()
        st.warning(info["meanwhile"])
