"""Calisma alani sekmesi: sinirlayan sebep haritasi, transmisyon, hedef kisitlari.

Bkz. docs/components/WorkspaceTab.md
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import config
from ..geometry import (
    LimitReason,
    Mechanism,
    WorkspaceMap,
    reason_code,
    reason_order,
)
from . import common as C

# Sebep -> renk. Sira geometry._REASON_ORDER ile ayni (kod 0 = OK).
REASON_COLORS: dict[str, str] = {
    "OK": "#4e7a5e",
    "UNREACHABLE_ROD": "#c9c9cf",
    "UNREACHABLE_CIRCLE": "#55555c",
    "DEAD_POINT": "#c0392b",
    "POT_RANGE": "#d9659b",
    "GIMBAL_ANGLE": "#d8c14a",
    "ROD_END_ANGLE": "#e08a3c",
    "MECH_STOP": "#4a7ab5",
    "COLLISION": "#8e5fa8",
}


@st.cache_data(show_spinner="Çalışma alanı taranıyor…")
def _compute_map(cfg_yaml: str, n: int, span: float) -> tuple[WorkspaceMap, list[dict]]:
    """Yapilandirmanin YAML metni uzerinden onbellege alinir.

    Streamlit'in onbellegi hashlenebilir anahtar ister; SeatConfig bir dataclass
    agaci oldugu icin YAML metni anahtar olarak kullanilir.
    """
    import yaml

    cfg = config.from_dict(yaml.safe_load(cfg_yaml))
    mech = Mechanism.from_config(cfg, check_collision=True)
    wm = mech.workspace_map((-span, span), (-span, span), n=n)
    return wm, mech.stop_engagement_deg()


def _reason_figure(wm: WorkspaceMap) -> go.Figure:
    """Sinirlayan sebep haritasi: her sebep ayri renk, ayrik renk skalasi."""
    order = reason_order()
    present = sorted(set(wm.reason_code.ravel().tolist()))
    remap = {code: i for i, code in enumerate(present)}
    z = np.vectorize(remap.get)(wm.reason_code)

    n = len(present)
    colorscale = []
    for i, code in enumerate(present):
        color = REASON_COLORS[order[code].code]
        colorscale.append([i / n, color])
        colorscale.append([(i + 1) / n, color])

    return go.Figure(
        go.Heatmap(
            x=wm.pitch_deg, y=wm.roll_deg, z=z,
            colorscale=colorscale, zmin=-0.5, zmax=n - 0.5,
            showscale=False,
            customdata=np.array(
                [[order[c].label_tr for c in row] for row in wm.reason_code]
            ),
            hovertemplate="pitch %{x:.1f}° · roll %{y:.1f}°<br>%{customdata}<extra></extra>",
        )
    )


def _add_target_contours(fig: go.Figure, cfg: config.SeatConfig) -> None:
    t = cfg.targets
    cp, cr = t.combined_deg
    # Hedef dikdortgenler: eksen hedefleri ve eszamanli hedef
    fig.add_shape(
        type="rect", x0=-t.pitch_deg, x1=t.pitch_deg, y0=-t.roll_deg, y1=t.roll_deg,
        line=dict(color="white", width=2, dash="dash"), fillcolor="rgba(0,0,0,0)",
    )
    fig.add_shape(
        type="rect", x0=-cp, x1=cp, y0=-cr, y1=cr,
        line=dict(color="white", width=1.5, dash="dot"), fillcolor="rgba(0,0,0,0)",
    )
    fig.add_annotation(
        x=t.pitch_deg, y=t.roll_deg, text=f"hedef ±{t.pitch_deg:g}°/±{t.roll_deg:g}°",
        showarrow=False, font=dict(color="white", size=10), xanchor="right", yanchor="bottom",
    )
    fig.add_annotation(
        x=cp, y=cr, text=f"eşzamanlı {cp:g}°+{cr:g}°", showarrow=False,
        font=dict(color="white", size=10), xanchor="left", yanchor="top",
    )


def _scalar_figure(
    wm: WorkspaceMap, z: np.ndarray, title: str, colorscale: str,
    zmid: float | None = None,
) -> go.Figure:
    return go.Figure(
        go.Heatmap(
            x=wm.pitch_deg, y=wm.roll_deg, z=z, colorscale=colorscale, zmid=zmid,
            colorbar=dict(title=title),
            hovertemplate="pitch %{x:.1f}° · roll %{y:.1f}°<br>%{z:.1f}<extra></extra>",
        )
    )


def _layout(fig: go.Figure, height: int = 520) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Pitch (°) — + ön yukarı",
        yaxis_title="Roll (°) — + sağ yukarı",
        yaxis=dict(scaleanchor="x", scaleratio=1),
    )
    return fig


def _render_targets(met: dict[str, bool], detail: dict[str, str]) -> None:
    """Hedef kisit tablosu ve KISIT IHLALI uyarisi."""
    if not all(met.values()):
        st.error(
            "**Bu tasarım hedeflerin bir kısmını sağlamıyor.** Bu beklenen bir durumdur — "
            "başlangıç ölçüleri bilinçli olarak değiştirilmemiştir. Sebebi ve çıkış yolları: "
            "`docs/FINDINGS.md`. Düzeltilmiş geometri Faz 4 (Optimizasyon) sekmesinde "
            "üretilecektir."
        )
    else:
        st.success("Tüm hedef kısıtlar sağlanıyor.")

    st.dataframe(
        pd.DataFrame(
            [
                ("✅ SAĞLANIYOR" if v else "❌ KISIT İHLALİ", k.replace("_", " "),
                 detail.get(k, ""))
                for k, v in met.items()
            ],
            columns=["Durum", "Hedef", "Ulaşılan"],
        ),
        width="stretch", hide_index=True,
    )


def render(cfg: config.SeatConfig) -> None:
    st.header("Çalışma alanı")
    st.caption(
        "Koltuğun hangi eğim kombinasyonlarına ulaşabildiğini ve ulaşamadığı yerlerde "
        "**sebebini** gösterir."
    )

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        n = st.selectbox("Izgara çözünürlüğü", [21, 31, 41, 61], index=2, key="w_n",
                         help="41×41 ≈ 20 saniye. Sonuç önbelleğe alınır.")
    with c2:
        span = st.number_input("Tarama aralığı (±°)", value=20.0, step=5.0, key="w_span")
    with c3:
        layer = st.radio(
            "Katman",
            ["Sınırlayan sebep", "Transmisyon açısı", "Ölü nokta marjı"],
            horizontal=True, key="w_layer",
        )

    # --- Hedef kisit tablosu: UCUZ, her zaman gosterilir
    try:
        mech = Mechanism.from_config(cfg, check_collision=True)
    except ValueError as exc:
        st.error(f"Geometri kurulamadı: {exc}")
        return

    targets_met, targets_detail = mech.target_report(with_limits=False)
    _render_targets(targets_met, targets_detail)

    st.divider()

    # --- Harita: PAHALI, dugme arkasinda
    result, requested = C.expensive_result(
        "wmap", cfg, "Haritayı hesapla",
        f"{n}×{n} ızgara taranacak. Ölçülen süre: 41×41 için ~20 saniye. "
        "Tasarımı değiştirdikçe otomatik yenilenmez — böylece Tasarım sekmesinde "
        "ölçü değiştirirken beklemek zorunda kalmazsınız.",
    )
    if requested:
        try:
            wm, stops = _compute_map(config.to_yaml(cfg), int(n), float(span))
        except ValueError as exc:
            st.error(f"Geometri kurulamadı: {exc}")
            return
        C.store_expensive_result("wmap", cfg, (wm, stops, int(n), float(span)))
        st.rerun()

    if result is None:
        return
    wm, stops, used_n, used_span = result
    if used_n != int(n) or used_span != float(span):
        st.caption(
            f"Gösterilen harita {used_n}×{used_n} ızgara ve ±{used_span:.0f}° aralıkla "
            f"hesaplandı. Yeni ayarlarla yeniden hesaplamak için düğmeye basın."
        )

    m1, m2, m3 = st.columns(3)
    m1.metric("Kullanılabilir açı kombinasyonu",
              f"{int(wm.ok.sum())} / {wm.ok.size}",
              f"%{100 * wm.ok.sum() / wm.ok.size:.1f}")
    m2.metric("Maksimum pitch",
              f"{wm.max_pitch_deg[0]:+.1f}° / {wm.max_pitch_deg[1]:+.1f}°")
    m3.metric("Maksimum roll",
              f"{wm.max_roll_deg[0]:+.1f}° / {wm.max_roll_deg[1]:+.1f}°")

    st.divider()

    # --- Harita
    if layer == "Sınırlayan sebep":
        C.explain(
            "Yeşil bölge çalışabilir alan. Renkli bölgelerde mekanizma o açıya ulaşamıyor "
            "veya bir parça limitine takılıyor; rengin anlamı aşağıdaki listede. "
            "Kesikli çizgiler hedeflerinizi gösterir.",
            "Hedef dikdörtgenlerinin tamamı yeşil bölgenin içinde kalmalı.",
        )
        fig = _reason_figure(wm)
        _add_target_contours(fig, cfg)
        st.plotly_chart(_layout(fig), width="stretch", key="w_reason")

        legend = wm.reason_legend
        st.dataframe(
            pd.DataFrame(
                [
                    (
                        r.label_tr,
                        int((wm.reason_code == reason_code(r)).sum()),
                        _reason_hint(r),
                    )
                    for r in legend
                ],
                columns=["Sebep", "Düğüm sayısı", "Ne yapmalı"],
            ),
            width="stretch", hide_index=True,
        )

    elif layer == "Transmisyon açısı":
        C.explain(
            "Motorun plakayı ne kadar verimli ittiğini gösterir. 90°'ye yakın renkler iyi; "
            "uzaklaştıkça motor aynı iş için daha fazla zorlanır.",
            "Çalışma bölgesinin tamamında 60°–120°.",
        )
        st.plotly_chart(
            _layout(_scalar_figure(wm, wm.transmission_deg, "°", "RdYlGn_r", zmid=90.0)),
            width="stretch", key="w_trans",
        )

    else:
        C.explain(
            "Krankın ölü noktaya ne kadar uzak olduğunu gösterir. Ölü noktada motor "
            "plakayı hiç hareket ettiremez.",
            f"Her yerde > {cfg.limits.deadpoint_margin_deg:.0f}°.",
        )
        st.plotly_chart(
            _layout(_scalar_figure(wm, wm.deadpoint_margin_deg, "°", "Greens")),
            width="stretch", key="w_margin",
        )

    with st.expander("Takozlar hangi açıda devreye giriyor?"):
        st.dataframe(
            pd.DataFrame(
                [
                    (
                        s["label_tr"],
                        f"({s['x_cm']:+.1f}, {s['z_cm']:+.1f}) cm",
                        f"{s['engages_at_deg']:.1f}°" if s["engages_at_deg"] else "—",
                    )
                    for s in stops
                ],
                columns=["Takoz", "Konum (x, z)", "Devreye giriyor"],
            ),
            width="stretch", hide_index=True,
        )


def _reason_hint(reason: LimitReason) -> str:
    return {
        LimitReason.OK: "—",
        LimitReason.UNREACHABLE_CIRCLE:
            "Krank boyunu artırın veya çubuğu uzatın; plaka bağlantısını mafsala yaklaştırın.",
        LimitReason.UNREACHABLE_ROD:
            "Çubuk yanal açıklığı kapatamıyor. Çubuğu uzatın veya bağlantı noktalarını "
            "aynı x'e getirin.",
        LimitReason.DEAD_POINT:
            "Krank nötr açısını kaydırın veya çubuk/krank oranını büyütün.",
        LimitReason.POT_RANGE:
            "Pot aralığı aşılıyor — **pot kırılır**. Krank boyunu artırıp açı ihtiyacını "
            "düşürün veya potu dişli/kayışla yavaşlatın.",
        LimitReason.GIMBAL_ANGLE:
            "Daha geniş açılı bir kardan mafsalı gerekiyor.",
        LimitReason.ROD_END_ANGLE:
            "Daha geniş sapma açılı rot başı seçin veya bağlantı noktalarını aynı x'e getirin.",
        LimitReason.MECH_STOP:
            "Takozlar burada devreye giriyor. İstenmiyorsa takozları alçaltın veya "
            "konumlarını değiştirin.",
        LimitReason.COLLISION:
            "Parçalar çarpışıyor. Tasarım sekmesinde hangi çiftin darda olduğuna bakın.",
    }.get(reason, "")
