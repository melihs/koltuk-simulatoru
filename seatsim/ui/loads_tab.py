"""Yukler sekmesi: kuvvet/tork tablosu, isi haritalari, en kotu durum, ters sarkac.

Bkz. docs/components/LoadsTab.md
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import config, loads
from ..geometry import Mechanism
from ..units import cm_to_m, deg_to_rad
from . import common as C

VERDICT_STYLE = {
    "YETERLI": ("🟢", st.success),
    "SINIRDA": ("🟠", st.warning),
    "YETERSIZ": ("🔴", st.error),
}


@st.cache_data(show_spinner="Tork haritası hesaplanıyor…")
def _torque_map(
    cfg_yaml: str, n: int, span: float, sc_kw: dict
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Ulasilabilir calisma alaninda tork ve emniyet katsayisi haritasi."""
    import yaml

    cfg = config.from_dict(yaml.safe_load(cfg_yaml))
    mech = Mechanism.from_config(cfg, check_collision=True)
    sc = loads.MassScenario.from_config(cfg, **sc_kw)

    pitches = np.linspace(-span, span, n)
    rolls = np.linspace(-span, span, n)
    torque = np.full((n, n), np.nan)
    sf = np.full((n, n), np.nan)
    for i, r in enumerate(rolls):
        for j, p in enumerate(pitches):
            pose = mech.ik(float(deg_to_rad(p)), float(deg_to_rad(r)))
            if not pose.ok:
                continue
            res = loads.solve(mech, pose, sc, stiffness=False)
            if res.singular:
                continue
            torque[i, j] = res.worst_torque_nm
            sf[i, j] = res.min_safety_factor
    return pitches, rolls, torque, sf


@st.cache_data(show_spinner="Tüm senaryolar taranıyor… (~40 saniye)")
def _worst_case(cfg_yaml: str) -> loads.WorstCase:
    import yaml

    cfg = config.from_dict(yaml.safe_load(cfg_yaml))
    mech = Mechanism.from_config(cfg, check_collision=True)
    return loads.worst_case(mech)


def _scenario_controls(cfg: config.SeatConfig) -> dict:
    st.subheader("Yük senaryosu")
    st.caption(
        "Bu değerler yalnızca aşağıdaki tek nokta analizini ve ısı haritasını etkiler. "
        "En kötü durum taraması kendi aralıklarını kullanır."
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        mass = st.slider("Kullanıcı kütlesi (kg)", 50.0, 150.0,
                         float(cfg.mass.user_kg), 5.0, key="l_mass")
        carried = st.slider("Koltuğun taşıdığı oran", 0.5, 1.0,
                            float(cfg.mass.carried_fraction), 0.05, key="l_carried")
    with c2:
        mode = st.radio(
            "Sırtlık", ["fixed", "tilting"],
            index=0 if cfg.mass.backrest_mode == "fixed" else 1,
            format_func=lambda m: ("Sırtlık sabit, sadece oturak eğiliyor"
                                   if m == "fixed" else "Koltuğun tamamı eğiliyor"),
            key="l_mode",
        )
        follow = st.slider(
            "Plakayla dönen kullanıcı oranı", 0.0, 1.0,
            float(cfg.mass.backrest_follow_fraction), 0.05, key="l_follow",
            disabled=(mode != "fixed"),
            help="Sırtlık sabitse kullanıcının ne kadarı plakayla birlikte döner. "
                 "Ölçülmesi zor; en kötü durum taraması 0,4–1,0 aralığını kapsar.",
        )
    with c3:
        fore = st.slider("AM ileri-geri (cm, + ileri)", -5.0, 8.0,
                         float(cfg.mass.user_com_fore_aft_cm), 0.5, key="l_fore")
        lat = st.slider("AM yanal (cm, + sağ)", -5.0, 5.0,
                        float(cfg.mass.user_com_lateral_cm), 0.5, key="l_lat")
        height = st.slider("AM yüksekliği (cm, minder üstünden)", 15.0, 35.0,
                           float(cfg.mass.user_com_height_cm), 1.0, key="l_height")

    return dict(
        user_kg=float(mass),
        carried_fraction=float(carried),
        backrest_mode=mode,
        backrest_follow_fraction=float(follow),
        seat_kg=cfg.mass.seat_kg if mode == "tilting" else 0.0,
        com_fore_aft_m=float(cm_to_m(fore)),
        com_lateral_m=float(cm_to_m(lat)),
        com_height_m=float(cm_to_m(height)),
    )


def _single_point(mech: Mechanism, cfg: config.SeatConfig, sc_kw: dict) -> None:
    st.subheader("Tek nokta analizi")
    c1, c2 = st.columns(2)
    with c1:
        pitch = st.slider("Pitch (°)", -20.0, 20.0, 0.0, 0.1, key="l_pitch")
    with c2:
        roll = st.slider("Roll (°)", -20.0, 20.0, 0.0, 0.1, key="l_roll")

    pose = mech.ik(float(deg_to_rad(pitch)), float(deg_to_rad(roll)))
    if not pose.reachable:
        st.error(f"Bu açıya ulaşılamıyor — {pose.reason.label_tr}.")
        return
    if not pose.ok:
        st.warning(
            f"Bu açı ulaşılabilir ama bir limit aşılıyor: **{pose.reason.label_tr}**. "
            "Kuvvetler yine hesaplandı."
        )

    sc = loads.MassScenario.from_config(cfg, **sc_kw)
    res = loads.solve(mech, pose, sc)
    if res.singular:
        st.error(
            "Bu pozda kuvvet matrisi tekil — bir çubuğun moment katkısı yok olmuş. "
            "Motor plakayı bu konumda tutamaz."
        )
        return

    stall = cfg.motor.stall_torque_nm
    target = cfg.targets.torque_safety_factor

    def rod_text(f: float) -> str:
        kind = "basma" if f > 0 else "çekme"
        return f"{abs(f):.0f} N ({kind})"

    rows = [
        ("Çubuk kuvveti", rod_text(res.rod_force_n[0]), rod_text(res.rod_force_n[1]),
         "Rot başının taşıması gereken yük."),
        ("Motor torku", f"{abs(res.motor_torque_nm[0]):.2f} N·m",
         f"{abs(res.motor_torque_nm[1]):.2f} N·m",
         f"Tahmini kilitlenme torku {stall:.0f} N·m."),
        ("Emniyet katsayısı",
         C.chip(C.classify(res.safety_factor[0], target, 1.5), f"{res.safety_factor[0]:.2f}"),
         C.chip(C.classify(res.safety_factor[1], target, 1.5), f"{res.safety_factor[1]:.2f}"),
         f"Hedef ≥ {target:.1f}."),
    ]
    st.dataframe(
        pd.DataFrame(rows, columns=["Büyüklük", "Sağ", "Sol", "Ne demek"]),
        width="stretch", hide_index=True,
    )

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Mafsal bileşke kuvveti", f"{np.linalg.norm(res.gimbal_reaction_n):.0f} N",
              help="Kardan mafsalının ve direğin taşıdığı kuvvet. Ucuz bir U-joint'in "
                   "asıl sınavı budur.")
    g2.metric("Direk taban eğilmesi", f"{res.gimbal_post_bending_nm:.1f} N·m",
              help="Mafsal pitch/roll momenti taşımaz; devrilme momentini çubuklar alır. "
                   "Direğe yalnızca yatay kuvvet × yükseklik kalır.")
    g3.metric("Hareketli kütle", f"{res.total_moving_mass_kg:.0f} kg")
    g4.metric("Yerçekimi momenti",
              f"{abs(res.gravity_moment_nm[0]):.1f} / {abs(res.gravity_moment_nm[1]):.1f} N·m",
              help="Mafsal etrafında (pitch / roll).")

    if np.isfinite(res.cross_check_error):
        st.caption(
            f"İç tutarlılık: sanal iş yöntemi ile doğrudan moment yöntemi arasındaki fark "
            f"**{res.cross_check_error:.2e} N·m** — iki bağımsız hesap uyuşuyor."
        )


def _verification(mech: Mechanism) -> None:
    st.subheader("Doğrulama senaryosu")
    st.caption(
        "Tanımdaki §2.2 elle hesabını programa yaptırır: 90 kg taşınan kütle, ağırlık "
        "merkezi mafsalın 5 cm önünde, plaka yatay, krank yatay, çubuklar dikey. "
        "Programa güvenip güvenemeyeceğinizi kendi gözünüzle doğruladığınız yer."
    )
    if not st.button("Doğrulama senaryosunu çalıştır", key="l_verify"):
        return

    res = loads.solve(mech, mech.ik(0.0, 0.0), loads.manual_check_scenario())
    expected = [
        ("Mafsal momenti", 44.145, abs(res.gravity_moment_nm[0]), "N·m"),
        ("Toplam çubuk kuvveti", 215.32, float(res.rod_force_n.sum()), "N"),
        ("Çubuk başına kuvvet", 107.66, float(res.rod_force_n[0]), "N"),
        ("Motor başına tork", 4.3065, abs(res.motor_torque_nm[0]), "N·m"),
    ]
    st.dataframe(
        pd.DataFrame(
            [
                (name, f"{exp:.3f} {unit}", f"{got:.3f} {unit}",
                 f"%{abs(got - exp) / exp * 100:.3f}")
                for name, exp, got, unit in expected
            ],
            columns=["Büyüklük", "Elle hesap", "Program", "Fark"],
        ),
        width="stretch", hide_index=True,
    )
    worst = max(abs(g - e) / e for _, e, g, _ in expected)
    if worst < 0.02:
        st.success(f"Tüm değerler ±%2 içinde (en büyük fark %{worst * 100:.3f}).")
    else:
        st.error(f"En büyük fark %{worst * 100:.2f} — ±%2 hedefinin dışında.")


def _heatmaps(cfg: config.SeatConfig, sc_kw: dict) -> None:
    st.subheader("Tüm çalışma alanında tork")
    n = st.selectbox("Izgara çözünürlüğü", [15, 21, 31], index=1, key="l_n")

    result, requested = C.expensive_result(
        "torque_map", cfg, "Tork haritasını hesapla",
        f"{n}×{n} ızgarada, yukarıdaki yük senaryosuyla tork ve emniyet katsayısı "
        "hesaplanacak. Senaryoyu değiştirdikçe otomatik yenilenmez.",
    )
    if requested:
        try:
            data = _torque_map(config.to_yaml(cfg), int(n), 14.0, sc_kw)
        except ValueError as exc:
            st.error(f"Hesaplanamadı: {exc}")
            return
        C.store_expensive_result("torque_map", cfg, data)
        st.rerun()

    if result is None:
        return
    pitches, rolls, torque, sf = result

    if not np.isfinite(torque).any():
        st.warning("Bu senaryoda kullanılabilir hiçbir poz yok.")
        return

    c1, c2 = st.columns(2)
    with c1:
        C.explain(
            "Her açı kombinasyonunda iki motorun en çok zorlanan olanının torku. "
            "Boş (gri) bölgeler ulaşılamayan açılar.",
            f"Kilitlenme torku {cfg.motor.stall_torque_nm:.0f} N·m'nin yarısının altı.",
        )
        fig = go.Figure(
            go.Heatmap(x=pitches, y=rolls, z=torque, colorscale="YlOrRd",
                       colorbar=dict(title="N·m"),
                       hovertemplate="pitch %{x:.1f}° · roll %{y:.1f}°"
                                     "<br>%{z:.1f} N·m<extra></extra>")
        )
        fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title="Pitch (°)", yaxis_title="Roll (°)",
                          yaxis=dict(scaleanchor="x", scaleratio=1))
        st.plotly_chart(fig, width="stretch", key="l_torque")

    with c2:
        target = cfg.targets.torque_safety_factor
        C.explain(
            "Emniyet katsayısı: kilitlenme torku ÷ gereken tork. Kalın çizgi hedef "
            "değerdir; çizginin dış tarafı yetersiz.",
            f"Her yerde ≥ {target:.1f}.",
        )
        fig = go.Figure(
            go.Heatmap(x=pitches, y=rolls, z=sf, colorscale="RdYlGn", zmid=target,
                       colorbar=dict(title="kat"),
                       hovertemplate="pitch %{x:.1f}° · roll %{y:.1f}°"
                                     "<br>SF %{z:.2f}<extra></extra>")
        )
        fig.add_trace(
            go.Contour(x=pitches, y=rolls, z=sf, showscale=False,
                       contours=dict(start=target, end=target, size=1, coloring="none"),
                       line=dict(color="black", width=3))
        )
        fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title="Pitch (°)", yaxis_title="Roll (°)",
                          yaxis=dict(scaleanchor="x", scaleratio=1))
        st.plotly_chart(fig, width="stretch", key="l_sf")


def _worst_case_card(cfg: config.SeatConfig) -> None:
    st.subheader("En kötü durum")
    st.caption(
        "Tüm ulaşılabilir açıları, üç kullanıcı kütlesini, ağırlık merkezinin tüm kayma "
        "kombinasyonlarını ve iki sırtlık senaryosunu tarar. Sonuç önbelleğe alınır."
    )
    if not st.button("En kötü durumu tara", key="l_worst"):
        return

    try:
        wc = _worst_case(config.to_yaml(cfg))
    except ValueError as exc:
        st.error(f"Tarama başarısız: {exc}")
        return

    icon, box = VERDICT_STYLE[wc.verdict]
    box(f"{icon} **{wc.verdict}**\n\n{wc.explanation_tr}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("En kötü tork", f"{wc.max_motor_torque_nm:.1f} N·m")
    c2.metric("Emniyet katsayısı", f"{wc.min_safety_factor:.2f}",
              f"hedef {cfg.targets.torque_safety_factor:.1f}")
    c3.metric("Taranan poz", f"{wc.n_poses}")
    c4.metric("Taranan senaryo", f"{wc.n_scenarios}")

    st.dataframe(
        pd.DataFrame(
            [
                ("En yüksek çubuk basma kuvveti", f"{wc.max_rod_compression_n:.0f} N",
                 "Çubuk ve rot başının basma dayanımıyla karşılaştırın."),
                ("En yüksek çubuk çekme kuvveti", f"{wc.max_rod_tension_n:.0f} N",
                 "Rot başının çekme dayanımıyla karşılaştırın."),
                ("Mafsal bileşke kuvveti", f"{wc.max_gimbal_force_n:.0f} N",
                 "Kardan mafsalının yük kapasitesiyle karşılaştırın — en kritik parça."),
                ("Mafsal direği taban eğilmesi", f"{wc.max_gimbal_post_bending_nm:.1f} N·m",
                 "Direk kesiti ve taban cıvataları bunu taşımalı."),
            ],
            columns=["Büyüklük", "En kötü değer", "Ne ile karşılaştırmalı"],
        ),
        width="stretch", hide_index=True,
    )


def _inverted_pendulum(mech: Mechanism, cfg: config.SeatConfig, sc_kw: dict) -> None:
    st.subheader("Ters sarkaç etkisi")
    sc = loads.MassScenario.from_config(cfg, **sc_kw)
    res = loads.solve(mech, mech.ik(0.0, 0.0), sc)
    k = float(res.gravity_stiffness_nm_rad[0])

    C.explain(
        "Ağırlık merkezi mafsalın üstünde olduğu için plaka eğildikçe onu **daha da** "
        "eğmeye çalışan bir moment doğar. Aşağıdaki eğri bu momenti gösterir.",
        "Eğri ne kadar dikse PID o kadar sert ayarlanmalı ve titreşim riski o kadar artar.",
    )

    angles = np.linspace(-12.0, 12.0, 61)
    moments = []
    for a in angles:
        pose = mech.ik(float(deg_to_rad(a)), 0.0, check_collision=False)
        if not pose.reachable:
            moments.append(np.nan)
            continue
        moments.append(float(loads.solve(mech, pose, sc, stiffness=False).gravity_moment_nm[0]))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=angles, y=moments, mode="lines", name="Yerçekimi momenti",
                             line=dict(width=3)))
    fig.add_hline(y=0.0, line=dict(color="gray", width=1))
    fig.add_vline(x=0.0, line=dict(color="gray", width=1))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_title="Pitch (°)", yaxis_title="Mafsal etrafında moment (N·m)")
    st.plotly_chart(fig, width="stretch", key="l_pendulum")

    stable = k <= 0.0
    st.markdown(
        f"**Yerçekimi sertliği: {k:+.0f} N·m/rad** — "
        + (
            "Negatif, yani sistem statik olarak **kararlı** (sarkaç gibi). "
            "Ağırlık merkezi mafsalın altında kalmış."
            if stable else
            "Pozitif olması, plaka eğildikçe onu **daha da** eğmeye çalışan momentin "
            "büyüdüğü anlamına gelir — sistem ters sarkaç gibi davranır ve statik olarak "
            "**kararsızdır**. Motor durduğunda sonsuz vida redüktörü bunu tutar, ama "
            "PID'in kapalı çevrimde yenmesi gereken şey budur. Faz 3'te PID ayarının en "
            "kritik girdisi olacak."
        )
    )
    st.caption(
        f"Nötr pozda analitik değeri `W · h` = ağırlık × ağırlık merkezinin mafsal "
        f"üstündeki yüksekliği. Bu senaryoda hareketli kütle "
        f"{res.total_moving_mass_kg:.0f} kg."
    )


def render(cfg: config.SeatConfig) -> None:
    st.header("Yükler")
    st.caption(
        "Her motorun ne kadar tork vermesi gerektiğini, çubuk ve mafsal kuvvetlerini "
        "hesaplar; tüm senaryoları tarayıp en kötü durumu bulur."
    )

    st.warning(
        f"Emniyet katsayısı hesabı `motor.stall_torque_nm = "
        f"{cfg.motor.stall_torque_nm:.0f} N·m` değerine dayanıyor ve bu değer "
        f"**TAHMİNİDİR**. Ölçüm yöntemi: `docs/ASSUMPTIONS.md` §1. Ölçmeden buradaki "
        f"hiçbir emniyet kararı kesin değildir."
    )

    try:
        mech = Mechanism.from_config(cfg, check_collision=True)
    except ValueError as exc:
        st.error(f"Geometri kurulamadı: {exc}")
        return

    sc_kw = _scenario_controls(cfg)
    st.divider()
    _single_point(mech, cfg, sc_kw)
    st.divider()
    _verification(mech)
    st.divider()
    _heatmaps(cfg, sc_kw)
    st.divider()
    _worst_case_card(cfg)
    st.divider()
    _inverted_pendulum(mech, cfg, sc_kw)
