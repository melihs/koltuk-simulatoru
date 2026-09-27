"""2DoF Hareketli Koltuk — Simulasyon ve Optimizasyon Programi.

Calistirma:  streamlit run app.py

Bkz. README.md, docs/ARCHITECTURE.md
"""

from __future__ import annotations

import streamlit as st

from seatsim import __version__, config
from seatsim.ui import common as C
from seatsim.ui import design_tab, loads_tab, pending_tab, workspace_tab

st.set_page_config(
    page_title="Koltuk Simülatörü",
    page_icon="🪑",
    layout="wide",
)


def sidebar(cfg: config.SeatConfig) -> None:
    with st.sidebar:
        st.title("🪑 Koltuk Simülatörü")
        st.caption(f"sürüm {__version__} · 2 serbestlik dereceli hareketli koltuk")

        st.divider()
        st.markdown("**Faz durumu**")
        for phase, name, state in [
            (1, "Kinematik + 3D + çalışma alanı", "✅"),
            (2, "Statik yük ve tork", "✅"),
            (3, "Motor, SMC3, dinamik", "⏸"),
            (4, "Optimizasyon", "⏳"),
            (5, "Motion cueing", "⏳"),
            (6, "PID ayarı + rapor", "⏳"),
        ]:
            st.caption(f"{state} Faz {phase} — {name}")
        st.caption("⏸ = `SMC3.ino` bekleniyor")

        st.divider()
        st.markdown("**Birimler ve işaretler**")
        st.caption(
            "Ekranda **cm** ve **derece**; kodun içinde SI.\n\n"
            "Koordinat: `x` = sağ, `y` = yukarı, `z` = ileri.\n\n"
            "**Pitch +** = ön yukarı  \n**Roll +** = sağ taraf yukarı"
        )

        st.divider()
        n_unknown = len(cfg.uncertain_parameters())
        if n_unknown:
            st.warning(
                f"**{n_unknown} parametre ölçülmedi.** Sonuçlar bunlara bağlı — "
                "aşağıdaki listeye bakın."
            )
            with st.expander("Ölçülmesi gereken değerler"):
                for path, value, meta in cfg.uncertain_parameters():
                    st.markdown(f"**`{path}`** = {value}")
                    if meta.how_to_measure:
                        st.caption(meta.how_to_measure)
                    elif meta.note:
                        st.caption(meta.note)

        st.divider()
        st.caption(
            "Dokümantasyon: `docs/ARCHITECTURE.md`, `docs/FINDINGS.md` "
            "(bilinen tasarım çelişkileri), `docs/ASSUMPTIONS.md` (varsayımlar)."
        )


def main() -> None:
    try:
        cfg = C.active_config()
    except (FileNotFoundError, ValueError) as exc:
        st.error(
            f"`config.yaml` yüklenemedi:\n\n```\n{exc}\n```\n\n"
            "Dosyayı düzeltip sayfayı yenileyin."
        )
        return

    sidebar(cfg)

    tabs = st.tabs(
        [
            "Tasarım",
            "Çalışma alanı",
            "Yükler",
            "Dinamik test",
            "Optimizasyon",
            "Hareket",
            "PID ayarı",
            "Rapor",
        ]
    )
    with tabs[0]:
        design_tab.render(cfg)
    with tabs[1]:
        workspace_tab.render(cfg)
    with tabs[2]:
        loads_tab.render(cfg)
    with tabs[3]:
        pending_tab.render("dynamics")
    with tabs[4]:
        pending_tab.render("optimize")
    with tabs[5]:
        pending_tab.render("cueing")
    with tabs[6]:
        pending_tab.render("pid")
    with tabs[7]:
        pending_tab.render("report")


main()
