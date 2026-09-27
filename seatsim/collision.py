"""Disbukey ilkeller (kutu, kapsul) arasinda minimum mesafe.

Kapsul-kapsul ve nokta-kutu TAMDIR. Kapsul-kutu ve kutu-kutu yaklasiktir; hata
siniri docs/files/collision.md'de belgelenmistir. Kapsul-kutu icin kaba ornekleme
sonrasi altin oran aramasi ile iyilestirme yapilir (hata < 0,1 mm).

Bkz. docs/files/collision.md
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .bodies import Body, Box, Capsule

_EPS = 1e-12
_GOLDEN = 0.6180339887498949


@dataclass
class Contact:
    """Iki govde arasindaki en yakin yaklasma."""

    body_a: str
    body_b: str
    label_tr: str
    distance: float
    static_pair: bool = False
    """Iki govde de alt plakaya sabit mi.

    Statik ciftlerin boslugu poza BAGLI DEGILDIR -- bu bir montaj/imalat sorunudur,
    calisma alanini kisitlamaz. Hareketli bir govde iceren ciftler ise calisma
    alanini gercekten sinirlar.
    """

    @property
    def colliding(self) -> bool:
        return self.distance < 0.0


# --- Temel mesafe fonksiyonlari --------------------------------------------------


def segment_segment(
    p0: np.ndarray, p1: np.ndarray, q0: np.ndarray, q1: np.ndarray
) -> tuple[float, float, float]:
    """Iki dogru parcasi arasindaki en kisa mesafe. TAM yontem.

    Returns:
        (mesafe, s, t) -- s ve t parcalar uzerindeki [0,1] parametreleri
    """
    d1 = p1 - p0
    d2 = q1 - q0
    r = p0 - q0
    a = float(np.dot(d1, d1))
    e = float(np.dot(d2, d2))
    f = float(np.dot(d2, r))

    if a <= _EPS and e <= _EPS:  # iki nokta
        return float(np.linalg.norm(r)), 0.0, 0.0
    if a <= _EPS:  # birinci parca nokta
        t = float(np.clip(f / e, 0.0, 1.0))
        return float(np.linalg.norm((q0 + t * d2) - p0)), 0.0, t

    c = float(np.dot(d1, r))
    if e <= _EPS:  # ikinci nokta
        s = float(np.clip(-c / a, 0.0, 1.0))
        return float(np.linalg.norm((p0 + s * d1) - q0)), s, 0.0

    b = float(np.dot(d1, d2))
    denom = a * e - b * b
    s = float(np.clip((b * f - c * e) / denom, 0.0, 1.0)) if denom > _EPS else 0.0
    t = (b * s + f) / e

    if t < 0.0:
        t = 0.0
        s = float(np.clip(-c / a, 0.0, 1.0))
    elif t > 1.0:
        t = 1.0
        s = float(np.clip((b - c) / a, 0.0, 1.0))

    closest = (p0 + s * d1) - (q0 + t * d2)
    return float(np.linalg.norm(closest)), s, t


def point_obb(p: np.ndarray, box: Box) -> float:
    """Noktadan yonlendirilmis kutuya mesafe. Nokta icerideyse 0. TAM yontem."""
    local = box.R.T @ (p - box.center)
    excess = np.abs(local) - box.half
    return float(np.linalg.norm(np.maximum(excess, 0.0)))


def _point_obb_signed(p: np.ndarray, box: Box) -> float:
    """Isaretli mesafe: iceride negatif (en yakin yuze uzaklik)."""
    return float(_point_obb_signed_many(p[None, :], box)[0])


def _point_obb_signed_many(pts: np.ndarray, box: Box) -> np.ndarray:
    """Cok nokta icin isaretli mesafe, tek numpy islemiyle. pts: (..., 3) -> (...,)

    box.R.T @ (p - c) ile (p - c) @ box.R aynidir; ikincisi toplu calisir.
    """
    local = (pts - box.center) @ box.R
    excess = np.abs(local) - box.half
    out = np.linalg.norm(np.maximum(excess, 0.0), axis=-1)
    inside = np.all(excess <= 0.0, axis=-1)
    if np.any(inside):
        out = np.where(inside, np.max(excess, axis=-1), out)
    return out


def capsule_capsule(a: Capsule, b: Capsule) -> float:
    """Kapsul-kapsul mesafesi. TAM yontem."""
    d, _, _ = segment_segment(a.p0, a.p1, b.p0, b.p1)
    return d - a.radius - b.radius


def _min_on_segments(
    P0: np.ndarray, P1: np.ndarray, box: Box, samples: int
) -> np.ndarray:
    """Her parca icin kutuya en kucuk isaretli mesafe. P0, P1: (k, 3) -> (k,)

    Kaba tarama yerel minimumun hangi aralikta oldugunu bulur, ardindan altin oran
    aramasi TUM parcalar icin ayni anda calisir. Hata < 0,1 mm.
    """
    P0 = np.atleast_2d(P0)
    P1 = np.atleast_2d(P1)
    k = len(P0)
    D = P1 - P0
    n = max(samples, 5)

    ts = np.linspace(0.0, 1.0, n)
    pts = P0[:, None, :] + ts[None, :, None] * D[:, None, :]  # (k, n, 3)
    vals = _point_obb_signed_many(pts, box)  # (k, n)
    idx = np.argmin(vals, axis=1)
    best = vals[np.arange(k), idx]

    lo = ts[np.maximum(idx - 1, 0)]
    hi = ts[np.minimum(idx + 1, n - 1)]

    def eval_at(x: np.ndarray) -> np.ndarray:
        return _point_obb_signed_many(P0 + x[:, None] * D, box)

    x1 = hi - _GOLDEN * (hi - lo)
    x2 = lo + _GOLDEN * (hi - lo)
    f1, f2 = eval_at(x1), eval_at(x2)
    for _ in range(34):
        if np.all(hi - lo < 1e-7):
            break
        left = f1 < f2
        new_hi = np.where(left, x2, hi)
        new_lo = np.where(left, lo, x1)
        hi, lo = new_hi, new_lo
        x1 = hi - _GOLDEN * (hi - lo)
        x2 = lo + _GOLDEN * (hi - lo)
        f1, f2 = eval_at(x1), eval_at(x2)

    return np.minimum(best, np.minimum(f1, f2))


def _min_on_segment(p0: np.ndarray, p1: np.ndarray, box: Box, samples: int) -> float:
    """Tek parca icin _min_on_segments sarmalayicisi."""
    return float(_min_on_segments(p0[None, :], p1[None, :], box, samples)[0])


def capsule_box(cap: Capsule, box: Box, samples: int = 16) -> float:
    """Kapsul-kutu mesafesi. Yaklasik; iyilestirme ile hata < 0,1 mm."""
    return _min_on_segment(cap.p0, cap.p1, box, samples) - cap.radius


def _sat(a: Box, b: Box) -> tuple[bool, float, float]:
    """Ayirici eksen teoremi.

    Returns:
        (cakisiyor_mu, en_kucuk_ortusme, mesafe_alt_siniri)

    Cakisma kararinda TAMDIR. Ayrik durumda, herhangi bir ayirici eksendeki izdusum
    bosluğu gercek mesafenin GECERLI BIR ALT SINIRIDIR; eksenler uzerindeki en buyuk
    bosluk en iyi alt sinirdir. Bu, pahali kenar ornekleme adimini atlamak icin
    kullanilir.
    """
    axes = [a.R[:, i] for i in range(3)] + [b.R[:, i] for i in range(3)]
    for i in range(3):
        for j in range(3):
            cross = np.cross(a.R[:, i], b.R[:, j])
            n = float(np.linalg.norm(cross))
            if n > 1e-9:
                axes.append(cross / n)

    min_overlap = np.inf
    max_gap = 0.0
    separated = False
    d = b.center - a.center
    for axis in axes:
        ra = float(np.sum(np.abs(a.half * (a.R.T @ axis))))
        rb = float(np.sum(np.abs(b.half * (b.R.T @ axis))))
        gap = abs(float(np.dot(d, axis))) - ra - rb
        if gap > 0.0:
            separated = True
            max_gap = max(max_gap, gap)
        else:
            min_overlap = min(min_overlap, -gap)
    if separated:
        return False, 0.0, max_gap
    return True, float(min_overlap), 0.0


def _sat_overlap(a: Box, b: Box) -> tuple[bool, float]:
    """Geriye donuk uyumluluk: (cakisiyor_mu, ortusme_derinligi)."""
    overlapping, depth, _ = _sat(a, b)
    return overlapping, depth


_EDGE_PAIRS = [
    (i, j) for i in range(8) for j in range(i + 1, 8) if (i ^ j).bit_count() == 1
]
"""Box.corners() sirasinda indis bitleri isaretlere karsilik gelir; i ^ j tek bitse
o iki kose bir kenardir. 12 kenar."""


def box_box(a: Box, b: Box, samples: int = 16, cutoff: float = np.inf) -> float:
    """Kutu-kutu mesafesi. Cakisma kararinda tam (SAT), ayrik mesafede yaklasik.

    Args:
        cutoff: SAT alt siniri bunu asiyorsa pahali kenar ornekleme atlanir ve alt
            sinir dondurulur. Gercek mesafe bundan buyuk oldugu icin "uzakta" karari
            degismez; yalnizca raporlanan sayi bir miktar kucuk kalir.
    """
    overlapping, depth, lower_bound = _sat(a, b)
    if overlapping:
        return -depth
    if lower_bound > cutoff:
        return float(lower_bound)

    # Ayrik: her kutunun kose ve kenarlarini digerine karsi olc
    best = np.inf
    for src, dst in ((a, b), (b, a)):
        corners = src.corners()
        best = min(best, float(np.min(_point_obb_signed_many(corners, dst))))
        e0 = corners[[i for i, _ in _EDGE_PAIRS]]
        e1 = corners[[j for _, j in _EDGE_PAIRS]]
        best = min(best, float(np.min(_min_on_segments(e0, e1, dst, samples))))
    return float(max(best, 0.0))


def min_distance(
    a: Box | Capsule, b: Box | Capsule, samples: int = 16, cutoff: float = np.inf
) -> float:
    """Iki ilkel arasinda minimum mesafe (m). Negatif = cakisma.

    cutoff, yalnizca kutu-kutu ciftinde pahali adimi atlamak icin kullanilir.
    """
    if isinstance(a, Capsule) and isinstance(b, Capsule):
        return capsule_capsule(a, b)
    if isinstance(a, Capsule) and isinstance(b, Box):
        return capsule_box(a, b, samples)
    if isinstance(a, Box) and isinstance(b, Capsule):
        return capsule_box(b, a, samples)
    return box_box(a, b, samples, cutoff)


# --- Cift tarama ----------------------------------------------------------------


def _aabb_gap(a: Body, b: Body) -> float:
    """Eksene hizali sinirlayici kutular arasindaki bosluk (alt sinir)."""
    lo_a, hi_a = a.aabb()
    lo_b, hi_b = b.aabb()
    gap = np.maximum(lo_a - hi_b, lo_b - hi_a)
    return float(np.linalg.norm(np.maximum(gap, 0.0)))


def pairwise(
    bodies: list[Body],
    exclude_pairs: set[frozenset[str]] | None = None,
    samples: int = 16,
    prefilter: float = 0.05,
    *,
    skip_static: bool = False,
    cutoff: float = np.inf,
) -> list[Contact]:
    """Tum govde ciftleri icin minimum mesafe, artan sirali.

    Args:
        bodies: govde listesi
        exclude_pairs: denetlenmeyecek cift kumeleri (yon bagimsiz)
        samples: kapsul-kutu ve kutu-kutu ornekleme sayisi
        prefilter: AABB bosluk esigi (m); bundan uzak ciftler atlanir.
            0 verilirse on eleme kapanir (dogruluk testi icin).
        skip_static: iki govdesi de alt plakaya sabit olan ciftleri hic hesaplama.
            Calisma alani taramasinda kullanilir -- statik ciftlerin boslugu poza
            bagli olmadigi icin her dugumde yeniden hesaplamak bosunadir.
        cutoff: kutu-kutu ciftinde bu mesafenin otesini kesin olarak hesaplamaz
            (bkz. box_box). "Uzakta" karari degismez, sadece hizlanir.
    """
    excluded = exclude_pairs or set()
    active = [b for b in bodies if b.collidable]
    out: list[Contact] = []

    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]
            static = a.group == "static" and b.group == "static"
            if skip_static and static:
                continue
            if frozenset((a.name, b.name)) in excluded:
                continue
            if prefilter > 0.0 and _aabb_gap(a, b) > prefilter:
                continue
            best = min(
                min_distance(pa, pb, samples, cutoff)
                for pa in a.primitives
                for pb in b.primitives
            )
            out.append(
                Contact(
                    a.name,
                    b.name,
                    f"{a.label_tr} ↔ {b.label_tr}",
                    float(best),
                    static_pair=static,
                )
            )

    out.sort(key=lambda c: c.distance)
    return out
