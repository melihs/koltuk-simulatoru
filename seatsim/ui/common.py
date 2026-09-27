"""Arayuz katmaninin ortak yardimcilari: mesh uretimi, parametre editoru, rozetler.

Bu katman SI bilmez -- ekrana cm ve derece yazar, cekirdege cm ve derece verir
(donusumu Mechanism.from_config yapar). Fizik hesabi BURADA YAPILMAZ.

Bkz. docs/ARCHITECTURE.md (katman kurali)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from .. import config
from ..bodies import Body, Box, Capsule

# --- Renkler ---------------------------------------------------------------------

COLOR_OK = "#6b8e9e"
COLOR_MOVING = "#c8a063"
COLOR_LINKAGE = "#8c8c94"
COLOR_WARN = "#e08a3c"
COLOR_BAD = "#c0392b"
COLOR_STATIC = "#5a5a62"
COLOR_STOP = "#7a6a8a"

GOOD, WARN, BAD = "İYİ", "DİKKAT", "SORUN"
_CHIP = {GOOD: "🟢", WARN: "🟠", BAD: "🔴"}

CONFIDENCE_LABEL = {
    config.OLCULDU: ("✅ ÖLÇÜLDÜ", "Kendi sisteminizde ölçtünüz."),
    config.TAHMINI: ("⚠️ TAHMİNİ", "Ölçülmemiş, makul bir tahmin. Sonuçlar buna bağlı."),
    config.TASARIM: ("✏️ TASARIM", "Sizin kararınız; ölçülecek bir şey değil."),
    config.TURETILDI: ("🧮 TÜRETİLDİ", "Başka parametrelerden hesaplanır."),
}


# --- Metin yardimcilari ----------------------------------------------------------


def explain(text: str, healthy: str | None = None) -> None:
    """Her grafigin ustune bir cumlelik "bu ne gosteriyor" aciklamasi."""
    body = text
    if healthy:
        body += f"  \n**Sağlıklı aralık:** {healthy}"
    st.caption(body)


def chip(status: str, text: str) -> str:
    return f"{_CHIP[status]} {text}"


def classify(value: float, good_above: float, warn_above: float) -> str:
    """Buyuk iyi olan bir olcut icin durum."""
    if value >= good_above:
        return GOOD
    if value >= warn_above:
        return WARN
    return BAD


def classify_inverse(value: float, good_below: float, warn_below: float) -> str:
    """Kucuk iyi olan bir olcut icin durum."""
    if value <= good_below:
        return GOOD
    if value <= warn_below:
        return WARN
    return BAD


# --- Parametre editoru -----------------------------------------------------------


@dataclass(frozen=True)
class Param:
    """Arayuzde duzenlenebilir tek bir parametre."""

    path: str
    label: str
    unit: str = ""
    step: float = 0.1
    help: str = ""
    lockable: bool = True
    components: tuple[str, ...] = ()
    """Liste parametrelerinde her bilesenin etiketi, orn. ("x sağ", "y yukarı").

    Bos birakilirsa bilesenler [0], [1], [2] diye numaralanir. Etiketi yalnizca ilk
    bilesene koymak yaniltir: "Mafsal yuksekligi (y)" yazan kutu aslinda x'i duzenler.
    """


@dataclass(frozen=True)
class Group:
    name: str
    intro: str
    params: tuple[Param, ...]


GROUPS: tuple[Group, ...] = (
    Group(
        "Mafsal ve plakalar",
        "Mekanizmanın iskeleti. Mafsal yüksekliği toplam yüksekliği ve ters sarkaç "
        "etkisini birlikte belirler.",
        (
            Param("geometry.gimbal.position_cm", "Mafsal dönme merkezi", "cm", 0.5,
                  help="Yükseklik (y) toplam yüksekliği ve ters sarkaç etkisini belirler. "
                       "x ve z normalde 0'dır: mafsal orta hatta ve orijinde.",
                  components=("x — sağ", "y — yukarı", "z — ileri")),
            Param("geometry.top_plate.underside_above_gimbal_cm",
                  "Üst plaka alt yüzeyi, mafsalın üstünde", "cm", 0.1),
            Param("geometry.top_plate.thickness_cm", "Üst plaka kalınlığı", "cm", 0.1),
            Param("geometry.top_plate.center_offset_z_cm",
                  "Üst plaka merkezi, mafsalın önünde", "cm", 0.5),
            Param("geometry.cushion.thickness_cm", "Minder kalınlığı", "cm", 0.5),
            Param("geometry.base_plate.thickness_cm", "Alt plaka kalınlığı", "cm", 0.1),
        ),
    ),
    Group(
        "Krank, çubuk ve motor mili",
        "Hareketin üretildiği yer. Çubuk/krank oranı 3'ün altına inince çalışma alanı "
        "hızla daralır.",
        (
            Param("geometry.crank.length_cm", "Krank boyu", "cm", 0.5,
                  help="Büyütmek çalışma alanını genişletir ama motor torku ihtiyacını "
                       "aynı oranda artırır."),
            Param("geometry.crank.neutral_offset_deg",
                  "Krankın nötrdeki açısı (0 = yatay, arkaya)", "°", 1.0,
                  help="Çalışma alanı yukarı/aşağı asimetrikse bunu kaydırmak dengeler."),
            Param("geometry.rod.length_cm", "İtme çubuğu boyu (rot başı merkezleri arası)",
                  "cm", 0.5),
            Param("geometry.rod.diameter_cm", "Çubuk çapı", "cm", 0.1),
            Param("geometry.crank.thickness_cm", "Krank kalınlığı", "cm", 0.1),
        ),
    ),
    Group(
        "Bağlantı noktaları",
        "Plakaya ve motora nereden bağlanıldığı. `x` işareti sağ/sol için otomatik "
        "çevrilir.",
        (
            Param("geometry.rod_attach_cm", "Plaka bağlantısı", "cm", 0.1,
                  help="Mafsala göre, plaka çerçevesinde. x işareti sağ/sol için çevrilir.",
                  components=("x — sağ", "y — yukarı", "z — ileri")),
            Param("geometry.motor_shaft_cm", "Motor mili merkezi", "cm", 0.1, components=("x — sağ", "y — yukarı", "z — ileri")),
        ),
    ),
    Group(
        "Donanım ölçüleri",
        "Motorlar elinizde olduğunda kumpasla ölçüp girin — çarpışma analizi doğrudan "
        "bunlara dayanıyor.",
        (
            Param("hardware.gearbox_box_cm", "Redüktör kutusu boyutları", "cm", 0.2,
                  components=("x — genişlik", "z — derinlik", "y — yükseklik")),
            Param("hardware.motor_cylinder_diameter_cm", "Motor silindiri çapı", "cm", 0.2),
            Param("hardware.motor_cylinder_length_cm", "Motor silindiri boyu", "cm", 0.5),
            Param("hardware.shaft_protrusion_cm",
                  "Mil çıkıntısı (kutu dış yüzü → krank düzlemi)", "cm", 0.1,
                  help="Çok küçükse krank motor gövdesine çarpar."),
            Param("hardware.pot_offset_cm", "Pot braketi, krank düzleminin dışında",
                  "cm", 0.1),
            Param("hardware.pot_bracket_cm", "Pot braketi boyutları", "cm", 0.2,
                  components=("x — genişlik", "z — derinlik", "y — yükseklik")),
            Param("hardware.gimbal_post_diameter_cm", "Mafsal direği çapı", "cm", 0.2),
        ),
    ),
    Group(
        "Kütle ve kullanıcı",
        "Tork hesabının girdisi. Ağırlık merkezinin ileri kayması en etkili terimdir.",
        (
            Param("mass.user_kg", "Tasarım yükü (kullanıcı kütlesi)", "kg", 5.0),
            Param("mass.carried_fraction", "Koltuğun taşıdığı oran", "", 0.05,
                  help="Ayaklar yerde/pedaldayken yükün bir kısmı koltuğa binmez."),
            Param("mass.plate_assembly_kg", "Üst plaka + minder + braketler", "kg", 0.5),
            Param("mass.user_com_height_cm", "AM yüksekliği (minder üstünden)", "cm", 1.0),
            Param("mass.user_com_fore_aft_cm", "AM ileri-geri (+ ileri)", "cm", 1.0),
            Param("mass.user_com_lateral_cm", "AM yanal (+ sağ)", "cm", 1.0),
            Param("mass.seat_kg", "Koltuk kütlesi (yalnız 'koltuk da eğiliyor' modunda)",
                  "kg", 1.0),
            Param("mass.backrest_follow_fraction",
                  "Plakayla dönen kullanıcı oranı (yalnız 'sırtlık sabit')", "", 0.05),
            Param("hardware.user_box_cm", "Kullanıcı atalet kutusu", "cm", 2.0,
                  components=("genişlik", "derinlik", "boy")),
        ),
    ),
    Group(
        "Limitler",
        "Parçaların izin verdiği sınırlar. Çalışma alanı haritasındaki renkler bunlardan "
        "doğar.",
        (
            Param("limits.rod_end_misalign_deg", "Rot başı maksimum sapma", "°", 1.0),
            Param("limits.gimbal_max_deg", "Kardan mafsalı maksimum açı", "°", 1.0),
            Param("limits.deadpoint_margin_deg", "Ölü noktaya asgari marj", "°", 1.0),
            Param("limits.clearance_min_cm", "Parçalar arası asgari boşluk", "cm", 0.2),
            Param("limits.total_height_max_cm", "Toplam yükseklik kısıtı", "cm", 0.5),
            Param("limits.pot.mechanical_range_deg", "Pot mekanik açı aralığı", "°", 5.0),
            Param("limits.pot.mount_offset_deg", "Pot montaj kayması", "°", 5.0),
        ),
    ),
    Group(
        "Takozlar (mekanik stop)",
        "Son koruma katmanı. Konum değiştirirseniz yüksekliği yeniden hesaplatın — "
        "sabit bir açı varsayılmaz.",
        (
            Param("stops.top_height_cm", "Takoz üst yüzey yükseklikleri", "cm", 0.2,
                  components=("Takoz 1", "Takoz 2", "Takoz 3", "Takoz 4")),
            Param("stops.size_cm", "Takoz yatay kesiti", "cm", 0.5,
                  components=("x", "z")),
        ),
    ),
    Group(
        "Motor (Faz 2'de emniyet katsayısı için)",
        "Kilitlenme torku, projenin yapılabilir olup olmadığını belirleyen tek sayıdır. "
        "Mutlaka ölçün.",
        (
            Param("motor.stall_torque_nm", "Kilitlenme (stall) torku", "N·m", 1.0),
            Param("motor.no_load_rpm", "Yüksüz hız", "rpm", 1.0),
            Param("motor.stall_current_a", "Kilitlenme akımı", "A", 1.0),
            Param("motor.no_load_current_a", "Yüksüz akım", "A", 0.5),
        ),
    ),
    Group(
        "Hedefler",
        "Programın 'KISIT İHLALİ' kararını verirken kullandığı eşikler.",
        (
            Param("targets.pitch_deg", "Hedef pitch", "°", 1.0, lockable=False),
            Param("targets.roll_deg", "Hedef roll", "°", 1.0, lockable=False),
            Param("targets.combined_deg", "Hedef eşzamanlı eğim", "°", 1.0, lockable=False,
                  components=("pitch", "roll")),
            Param("targets.torque_safety_factor", "Hedef emniyet katsayısı", "", 0.1,
                  lockable=False),
        ),
    ),
)


def _confidence_caption(cfg: config.SeatConfig, path: str) -> str:
    meta = cfg.get_meta(path)
    label, meaning = CONFIDENCE_LABEL.get(meta.confidence, ("", ""))
    parts = [f"{label} — {meaning}"]
    if meta.note:
        parts.append(f"**Not:** {meta.note}")
    if meta.how_to_measure:
        parts.append(f"**Nasıl ölçerim:** {meta.how_to_measure}")
    return "  \n".join(parts)


def render_param(cfg: config.SeatConfig, p: Param, key_prefix: str = "") -> None:
    """Tek bir parametreyi duzenlenebilir olarak cizer (rozet + kilit kutusu dahil)."""
    value = config.get_by_path(cfg, p.path)
    key = f"{key_prefix}{p.path}"
    meta = cfg.get_meta(p.path)
    suffix = f" [{p.unit}]" if p.unit else ""

    col_val, col_lock = st.columns([5, 2])
    with col_val:
        if isinstance(value, list):
            st.markdown(f"**{p.label}**{suffix}")
            new = []
            sub = st.columns(len(value))
            for i, v in enumerate(value):
                with sub[i]:
                    if isinstance(v, list):  # ic ice liste (takoz konumlari) -- salt okunur
                        st.text(str(v))
                        new.append(v)
                    else:
                        comp = p.components[i] if i < len(p.components) else f"[{i}]"
                        new.append(
                            st.number_input(
                                comp, value=float(v), step=p.step, key=f"{key}_{i}",
                                format="%.2f",
                            )
                        )
            config.set_by_path(cfg, p.path, new)
        else:
            new = st.number_input(
                f"{p.label}{suffix}", value=float(value), step=p.step, key=key,
                format="%.3f",
            )
            config.set_by_path(cfg, p.path, float(new))

    with col_lock:
        if p.lockable:
            locked = st.checkbox(
                "Sabitle", value=meta.locked, key=f"{key}__lock",
                help="'Elimde var' — Faz 4 optimizasyonunda bu ölçü değiştirilmez.",
            )
            if locked != meta.locked:
                cfg.meta[p.path] = config.ParamMeta(
                    confidence=config.OLCULDU if locked else meta.confidence,
                    locked=locked, note=meta.note, how_to_measure=meta.how_to_measure,
                )

    st.caption(_confidence_caption(cfg, p.path))


def render_groups(cfg: config.SeatConfig) -> None:
    """Tum parametre gruplarini acilir bolumler halinde cizer."""
    for g in GROUPS:
        n_unknown = sum(
            1 for p in g.params if cfg.get_meta(p.path).confidence == config.TAHMINI
        )
        title = g.name + (f"  ·  {n_unknown} tahmini değer" if n_unknown else "")
        with st.expander(title):
            st.caption(g.intro)
            for p in g.params:
                render_param(cfg, p)
                st.divider()


# --- 3D mesh uretimi -------------------------------------------------------------

_BOX_TRIS = np.array(
    [
        [0, 1, 3], [0, 3, 2],  # x-
        [4, 6, 7], [4, 7, 5],  # x+
        [0, 4, 5], [0, 5, 1],  # y-
        [2, 3, 7], [2, 7, 6],  # y+
        [0, 2, 6], [0, 6, 4],  # z-
        [1, 5, 7], [1, 7, 3],  # z+
    ]
)


def box_mesh(b: Box, color: str, name: str, opacity: float = 1.0) -> go.Mesh3d:
    v = b.corners() * 100.0  # m -> cm
    return go.Mesh3d(
        x=v[:, 0], y=v[:, 1], z=v[:, 2],
        i=_BOX_TRIS[:, 0], j=_BOX_TRIS[:, 1], k=_BOX_TRIS[:, 2],
        color=color, opacity=opacity, name=name, hoverinfo="name",
        flatshading=True, showlegend=False,
    )


def capsule_mesh(
    c: Capsule, color: str, name: str, opacity: float = 1.0, n_circ: int = 14,
    n_cap: int = 5,
) -> go.Mesh3d:
    """Kapsul yuzeyi: iki yarimkure + silindir, tek donel yuzey olarak."""
    axis = c.p1 - c.p0
    length = float(np.linalg.norm(axis))
    if length < 1e-12:
        axis = np.array([0.0, 0.0, 1.0])
        length = 1e-12
    w = axis / length
    # w'ye dik iki birim vektor. Bu bir CIZIM tabani -- kapsul yuzeyinin cevresel
    # noktalarini uretmek icin. Fizik hesabi degil: kuvvet, moment veya kinematik
    # cozumu arayuz katmaninda YAPILMAZ (bkz. docs/ARCHITECTURE.md katman kurali).
    helper = np.array([1.0, 0.0, 0.0]) if abs(w[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(w, helper)
    u /= np.linalg.norm(u)
    v = np.cross(w, u)

    # Profil acilari: -90..0 alt yarimkure (merkez p0), 0..+90 ust (merkez p1)
    lats = np.concatenate(
        [np.linspace(-np.pi / 2, 0.0, n_cap), np.linspace(0.0, np.pi / 2, n_cap)[1:]]
    )
    centers = np.where(lats[:, None] < 0.0, c.p0, c.p1)  # (n_lat, 3)
    circ = np.linspace(0.0, 2.0 * np.pi, n_circ, endpoint=False)

    radial = c.radius * np.cos(lats)[:, None]  # (n_lat, 1)
    axial = c.radius * np.sin(lats)[:, None] * w  # (n_lat, 3)
    ring = np.cos(circ)[:, None] * u + np.sin(circ)[:, None] * v  # (n_circ, 3)

    pts = centers[:, None, :] + axial[:, None, :] + radial[:, :, None] * ring[None, :, :]
    n_lat = len(lats)
    verts = pts.reshape(-1, 3) * 100.0  # m -> cm

    tri = []
    for a in range(n_lat - 1):
        for b in range(n_circ):
            b2 = (b + 1) % n_circ
            p00 = a * n_circ + b
            p01 = a * n_circ + b2
            p10 = (a + 1) * n_circ + b
            p11 = (a + 1) * n_circ + b2
            tri.append((p00, p10, p11))
            tri.append((p00, p11, p01))
    tri = np.asarray(tri)

    return go.Mesh3d(
        x=verts[:, 0], y=verts[:, 1], z=verts[:, 2],
        i=tri[:, 0], j=tri[:, 1], k=tri[:, 2],
        color=color, opacity=opacity, name=name, hoverinfo="name",
        flatshading=True, showlegend=False,
    )


def body_color(body: Body, status: str) -> str:
    """Govde rengi: once durum, sonra grup."""
    if status == BAD:
        return COLOR_BAD
    if status == WARN:
        return COLOR_WARN
    if body.name.startswith("stop_"):
        return COLOR_STOP
    return {
        "moving": COLOR_MOVING,
        "linkage": COLOR_LINKAGE,
        "static": COLOR_STATIC,
    }.get(body.group, COLOR_OK)


def mechanism_figure(
    bodies_list: list[Body], body_status: dict[str, str], *, height: int = 560
) -> go.Figure:
    """Mekanizmanin 3D gorunumu. Eksenler kullanici sisteminde etiketlenir."""
    fig = go.Figure()
    for b in bodies_list:
        status = body_status.get(b.name, GOOD)
        color = body_color(b, status)
        opacity = 0.35 if b.name == "user_body" else 0.95
        for prim in b.primitives:
            if isinstance(prim, Box):
                fig.add_trace(box_mesh(prim, color, b.label_tr, opacity))
            else:
                fig.add_trace(capsule_mesh(prim, color, b.label_tr, opacity))

    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        scene=dict(
            # Ic sistem (X=sag, Y=ileri, Z=yukari) -> kullanici etiketleri
            xaxis_title="x — sağ (cm)",
            yaxis_title="z — ileri (cm)",
            zaxis_title="y — yukarı (cm)",
            aspectmode="data",
            camera=dict(eye=dict(x=1.6, y=-1.7, z=1.0)),
        ),
        showlegend=False,
    )
    return fig


# --- Oturum durumu ---------------------------------------------------------------


def expensive_result(slot: str, cfg: config.SeatConfig, label: str, help_text: str):
    """Pahali bir hesabin sonucunu dugme arkasina alir ve bayatligini bildirir.

    NEDEN GEREKLI: Streamlit her etkilesimde TUM betigi (dolayisiyla tum sekmeleri)
    yeniden calistirir. Calisma alani haritasi gibi bir hesap her yeniden cizimde
    yapilirsa, kullanici Tasarim sekmesinde bir olcuyu degistirdiginde -- haritaya
    bakmiyor olsa bile -- dakikalar suren bir donma yasar. Olculdu: krank 4 -> 7,5
    degisiminde 41x41 harita 900 saniyeyi asti.

    Sonuc, uretildigi yapilandirmanin YAML metniyle birlikte oturum durumunda saklanir;
    tasarim degisince "bayat" olarak isaretlenir ama SILINMEZ -- eski sonucu gormeye
    devam edersiniz, yalnizca guncel olmadigini bilirsiniz.

    Returns:
        (sonuc veya None, yeniden_hesapla_istendi)
    """
    key = config.to_yaml(cfg)
    stored = st.session_state.get(slot)
    stale = stored is not None and stored["key"] != key

    if stored is None:
        st.info(f"{help_text}\n\nHesaplamak için **{label}** düğmesine basın.")
    elif stale:
        st.warning(
            "**Tasarım değişti, aşağıdaki sonuç bayat.** Gösterilen değerler "
            f"önceki ölçülere ait. Güncellemek için **{label}** düğmesine basın."
        )

    requested = st.button(label, key=f"{slot}__compute", width="stretch")
    return (None if stored is None else stored["value"]), requested


def store_expensive_result(slot: str, cfg: config.SeatConfig, value) -> None:
    """expensive_result ile okunacak sonucu, uretildigi yapilandirmayla saklar."""
    st.session_state[slot] = {"key": config.to_yaml(cfg), "value": value}


def param_widget_keys() -> list[str]:
    """GROUPS'taki her parametrenin urettigi tum Streamlit widget anahtarlari."""
    keys: list[str] = []
    for g in GROUPS:
        for prm in g.params:
            keys.append(prm.path)
            keys.append(f"{prm.path}__lock")
            # Liste parametreleri bilesen basina ayri anahtar uretir
            keys.extend(f"{prm.path}_{i}" for i in range(6))
    return keys


def replace_config(cfg: config.SeatConfig) -> None:
    """Aktif yapilandirmayi degistirir ve widget durumunu temizler.

    NEDEN GEREKLI: st.number_input'a `key` verildiginde Streamlit widget durumunu
    kalici tutar ve sonraki her yeniden cizimde `value=` argumanini YOK SAYAR. Bu
    yuzden yapilandirmayi yeniden yuklemek tek basina yeterli degildir -- eski widget
    degerleri yeni cfg'nin uzerine geri yazilir ve "Profili yukle", "Baslangic
    degerlerine don" gibi islemler sessizce hicbir sey yapmaz.

    Bayat anahtarlari silmek, widget'larin yeni cfg'den yeniden dogmasini saglar.
    """
    for key in param_widget_keys():
        st.session_state.pop(key, None)
    st.session_state.cfg = cfg


def active_config() -> config.SeatConfig:
    """Oturumdaki aktif yapilandirma; yoksa config.yaml'dan yuklenir."""
    if "cfg" not in st.session_state:
        st.session_state.cfg = config.load("config.yaml")
    return st.session_state.cfg


def issues_panel(cfg: config.SeatConfig) -> None:
    """config.validate() sonuclarini agirliga gore gosterir."""
    issues = config.validate(cfg)
    errors = [i for i in issues if i.severity == config.ERROR]
    warns = [i for i in issues if i.severity == config.WARN]
    infos = [i for i in issues if i.severity == config.INFO]

    if errors:
        st.error(
            "**Yapılandırma hatası** — düzeltilmeden sonuçlar anlamsız:\n\n"
            + "\n".join(f"- `{i.path}` — {i.message}" for i in errors)
        )
    if warns:
        st.warning(
            "**Uyarılar** (başlangıç tasarımında bunlar beklenir, bkz. `docs/FINDINGS.md`):\n\n"
            + "\n".join(f"- `{i.path}` — {i.message}" for i in warns)
        )
    for i in infos:
        st.info(i.message)
