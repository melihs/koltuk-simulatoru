"""Tasarim sekmesi: parametreler + canli 3D gorunum + montaj bosluklari + profiller.

Bkz. docs/components/DesignTab.md
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from .. import bodies, collision, config
from ..collision import Contact
from ..geometry import Mechanism, Pose
from ..units import deg_to_rad
from . import common as C

PROFILE_DIR = Path("profiles")
_VALID_NAME = re.compile(r"[\w-]{1,64}")
"""Profil adi: yalnizca harf, rakam, alt tire ve tire; en fazla 64 karakter.

Yol ayraci (`/`, `..`) kabul edilmez -- aksi halde `../config` gibi bir ad proje
kokundeki config.yaml'i ezebilirdi. Uzunluk siniri, dosya sistemi sinirini asan bir
adin yakalanmamis OSError uretmesini onler.
"""


def _body_status(
    pose: Pose, cfg: config.SeatConfig, contacts: list[Contact]
) -> dict[str, str]:
    """Her govde icin renk durumu: carpisan kirmizi, limite yakin turuncu."""
    status: dict[str, str] = {}
    clearance = cfg.limits.clearance_min_cm / 100.0
    for c in contacts:
        for name in (c.body_a, c.body_b):
            if c.distance < clearance:
                status[name] = C.BAD
            elif c.distance < 2.0 * clearance:
                status[name] = status.get(name, C.WARN)

    # Olu noktaya yaklasan krank/cubuk
    margin = cfg.limits.deadpoint_margin_deg
    for side, tag in ((0, "right"), (1, "left")):
        m = pose.deadpoint_margin_deg[side]
        if m < margin:
            status[f"crank_{tag}"] = C.BAD
        elif m < 1.5 * margin and status.get(f"crank_{tag}") != C.BAD:
            status[f"crank_{tag}"] = C.WARN
        # Rot basi limiti cubuga yazilir
        worst = float(np.max(pose.rod_end_misalign_deg[side]))
        if worst > cfg.limits.rod_end_misalign_deg:
            status[f"rod_{tag}"] = C.BAD
        elif worst > 0.75 * cfg.limits.rod_end_misalign_deg:
            status[f"rod_{tag}"] = status.get(f"rod_{tag}", C.WARN)

    for idx, touching in enumerate(pose.stop_contact):
        if touching:
            status[f"stop_{idx}"] = C.BAD

    if pose.gimbal_tilt_deg > cfg.limits.gimbal_max_deg:
        status["gimbal_post"] = C.BAD
    return status


def _status_table(
    pose: Pose, cfg: config.SeatConfig, contacts: list[Contact]
) -> pd.DataFrame:
    lim = cfg.limits
    moving = [c for c in contacts if not c.static_pair]
    nearest = moving[0] if moving else None

    rows = [
        (
            "Krank açıları",
            f"{np.degrees(pose.theta[0]):+.1f}° / {np.degrees(pose.theta[1]):+.1f}°",
            C.GOOD,
            "Motor millerinin nötrden sapması.",
        ),
        (
            "Transmisyon açısı",
            f"{pose.transmission_deg[0]:.0f}° / {pose.transmission_deg[1]:.0f}°",
            C.classify(float(np.min(pose.deadpoint_margin_deg)), 60.0, 30.0),
            "90° ideal. 60°–120° iyi.",
        ),
        (
            "Ölü nokta marjı",
            f"{np.min(pose.deadpoint_margin_deg):.0f}°",
            C.classify(float(np.min(pose.deadpoint_margin_deg)),
                       lim.deadpoint_margin_deg, lim.deadpoint_margin_deg * 0.6),
            f"Hedef ≥ {lim.deadpoint_margin_deg:.0f}°.",
        ),
        (
            "Rot başı sapması",
            f"{np.max(pose.rod_end_misalign_deg):.1f}°",
            C.classify_inverse(float(np.max(pose.rod_end_misalign_deg)),
                               lim.rod_end_misalign_deg * 0.75, lim.rod_end_misalign_deg),
            f"Limit {lim.rod_end_misalign_deg:.0f}°.",
        ),
        (
            "Kardan mafsalı açısı",
            f"{pose.gimbal_tilt_deg:.1f}°",
            C.classify_inverse(pose.gimbal_tilt_deg, lim.gimbal_max_deg * 0.8,
                               lim.gimbal_max_deg),
            f"Limit {lim.gimbal_max_deg:.0f}°.",
        ),
        (
            "Pot açısı",
            f"{np.max(np.abs(pose.pot_angle_deg)):.0f}°",
            C.classify_inverse(float(np.max(np.abs(pose.pot_angle_deg))),
                               lim.pot.mechanical_range_deg / 2 * 0.8,
                               lim.pot.mechanical_range_deg / 2),
            f"Aralık ±{lim.pot.mechanical_range_deg / 2:.0f}°. Aşılırsa pot kırılır.",
        ),
        (
            "En dar hareket boşluğu",
            (f"{nearest.distance * 100:.1f} cm — {nearest.label_tr}"
             if nearest else "hesaplanmadı"),
            C.classify(nearest.distance * 100 if nearest else 99.0,
                       lim.clearance_min_cm * 2, lim.clearance_min_cm),
            f"Asgari {lim.clearance_min_cm:.1f} cm.",
        ),
        (
            "Takoz teması",
            "var" if bool(np.any(pose.stop_contact)) else "yok",
            C.BAD if bool(np.any(pose.stop_contact)) else C.GOOD,
            "Takoz değdiyse mekanizma sınırına gelmiş.",
        ),
    ]
    return pd.DataFrame(
        [(C.chip(s, n), v, note) for n, v, s, note in rows],
        columns=["Ölçüt", "Değer", "Sağlıklı aralık"],
    )


def _profiles_panel(cfg: config.SeatConfig) -> None:
    st.subheader("Profiller")
    st.caption(
        "Tasarımı adlandırıp kaydedin; iki profili yan yana karşılaştırın. "
        "Kilitli parametreler uzun biçimde yazılır."
    )
    PROFILE_DIR.mkdir(exist_ok=True)
    existing = sorted(p.name for p in PROFILE_DIR.glob("*.yaml"))

    col_a, col_b = st.columns(2)
    with col_a:
        name = st.text_input("Profil adı", value="tasarim-1", key="profile_name")
        if st.button("Profili kaydet", width="stretch"):
            if not _VALID_NAME.fullmatch(name or ""):
                st.error(
                    "Profil adı yalnızca harf, rakam, `-` ve `_` içerebilir ve en "
                    "fazla 64 karakter olabilir. Yol ayracı (`/`, `..`) kabul "
                    "edilmez — aksi halde proje dosyalarının üzerine yazılabilirdi."
                )
            else:
                path = PROFILE_DIR / f"{name}.yaml"
                config.save(cfg, path)
                st.success(f"Kaydedildi: `{path}`")
        if st.button("config.yaml'a yaz", width="stretch",
                     help="Proje kökündeki ana yapılandırmayı günceller."):
            config.save(cfg, "config.yaml")
            st.success("`config.yaml` güncellendi.")

    with col_b:
        if existing:
            pick = st.selectbox("Yüklenecek profil", existing, key="profile_load")
            if st.button("Profili yükle", width="stretch"):
                C.replace_config(config.load(PROFILE_DIR / pick))
                st.rerun()
            other = st.selectbox("Karşılaştırılacak profil", existing, key="profile_diff")
            if st.button("Karşılaştır", width="stretch"):
                changes = config.diff(cfg, config.load(PROFILE_DIR / other))
                if not changes:
                    st.info("İki tasarım aynı.")
                else:
                    st.dataframe(
                        pd.DataFrame(
                            [(c.path, c.old, c.new) for c in changes],
                            columns=["Parametre", "Şu anki", other],
                        ),
                        width="stretch", hide_index=True,
                    )
        else:
            st.caption("Henüz kayıtlı profil yok.")

    if st.button("Başlangıç değerlerine dön", width="stretch"):
        C.replace_config(config.load("config.yaml"))
        st.rerun()


def render(cfg: config.SeatConfig) -> None:
    st.header("Tasarım")
    st.caption(
        "Soldaki ölçüleri değiştirin, sağdaki 3D görünümde sonucu anında görün. "
        "Çarpışan parçalar kırmızı, limite yaklaşanlar turuncu olur."
    )
    C.issues_panel(cfg)

    left, right = st.columns([1, 1.25], gap="large")

    with left:
        C.render_groups(cfg)
        st.divider()
        _profiles_panel(cfg)

    with right:
        try:
            mech = Mechanism.from_config(cfg, check_collision=False)
        except ValueError as exc:
            st.error(f"Geometri kurulamadı: {exc}")
            return

        c1, c2 = st.columns(2)
        with c1:
            pitch = st.slider("Pitch (+ ön yukarı)", -20.0, 20.0, 0.0, 0.1, key="d_pitch")
        with c2:
            roll = st.slider("Roll (+ sağ yukarı)", -20.0, 20.0, 0.0, 0.1, key="d_roll")

        pose = mech.ik(float(deg_to_rad(pitch)), float(deg_to_rad(roll)),
                       check_collision=False)

        if not pose.reachable:
            st.error(
                f"**Bu açıya ulaşılamıyor** — {pose.reason.label_tr}. "
                "Mekanizma bu konuma geometrik olarak giremez; 3D görünüm son geçerli "
                "konumda kalır."
            )
            pose = mech.ik(0.0, 0.0, check_collision=False)

        body_list = bodies.build(cfg, pose)
        contacts = collision.pairwise(
            body_list, exclude_pairs=cfg.collision.excluded(),
            samples=cfg.collision.samples, prefilter=0.0,
        )
        status = _body_status(pose, cfg, contacts)

        C.explain(
            "Mekanizmanın bu açıdaki hâli. Kaydırıcıları oynatarak hareketi izleyin.",
            "Hiçbir parça kırmızı olmamalı.",
        )
        st.plotly_chart(
            C.mechanism_figure(body_list, status), width="stretch",
            key="design_3d",
        )

        st.subheader("Bu konumun durumu")
        st.dataframe(_status_table(pose, cfg, contacts),
                     width="stretch", hide_index=True)

        with st.expander("Montaj boşlukları (poza bağlı değil)"):
            st.caption(
                "Alt plakaya sabit iki parça arasındaki boşluk, plaka nasıl eğilirse "
                "eğilsin değişmez. Bu bir **montaj/imalat** konusudur, çalışma alanını "
                "kısıtlamaz — ama 1 cm'in altına inen bir çift atölyede sorun çıkarır."
            )
            static = [c for c in contacts if c.static_pair][:12]
            if static:
                st.dataframe(
                    pd.DataFrame(
                        [
                            (
                                C.chip(
                                    C.classify(c.distance * 100,
                                               cfg.limits.clearance_min_cm * 2,
                                               cfg.limits.clearance_min_cm),
                                    c.label_tr,
                                ),
                                f"{c.distance * 100:.2f} cm",
                            )
                            for c in static
                        ],
                        columns=["Çift", "Boşluk"],
                    ),
                    width="stretch", hide_index=True,
                )
            else:
                st.caption("Yakın statik çift yok.")

        with st.expander("Takozlar — hangi açıda devreye giriyor?"):
            st.caption(
                "Takozun devreye girme açısı konumuna ve yüksekliğine bağlıdır; "
                "sabit bir ±12° varsayılmaz. Konumu değiştirirseniz yüksekliği "
                "aşağıdaki düğmeyle yeniden hesaplatın."
            )
            rows = []
            for s in mech.stop_engagement_deg():
                ang = s["engages_at_deg"]
                rows.append((
                    s["label_tr"],
                    f"({s['x_cm']:+.1f}, {s['z_cm']:+.1f}) cm",
                    f"{s['top_height_cm']:.2f} cm",
                    f"{ang:.1f}°" if ang is not None else "hiç devreye girmiyor",
                ))
            st.dataframe(
                pd.DataFrame(rows, columns=["Takoz", "Konum (x, z)", "Üst yüzey",
                                           "Devreye giriyor"]),
                width="stretch", hide_index=True,
            )
            target = st.number_input("Hedef devreye girme açısı", value=12.0, step=0.5,
                                     key="stop_target")
            if st.button("Yükseklikleri bu açıya göre hesapla"):
                updated = cfg.copy()
                updated.stops.top_height_cm = mech.suggest_stop_heights_cm(float(target))
                # Widget durumunu temizlemeden rerun edilirse bayat degerler geri
                # yazilir ve hesaplanan yukseklikler kaybolur -- bkz. C.replace_config
                C.replace_config(updated)
                st.rerun()
