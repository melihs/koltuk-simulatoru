"""config.yaml semasi: yukleme, dogrulama, kaydetme, profil karsilastirma.

Deger agaci duz float/list tutar (cm ve derece cinsinden) -- boylece cekirdek kod
`cfg.geometry.crank.length_cm` yazabilir, `.value` zincirine girmez. Kilitleme ve
guven rozeti gibi ust veri, noktali yol ile anahtarlanan ayri bir sozlukte durur.

Bkz. docs/files/config.md, docs/ASSUMPTIONS.md
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .units import deg_to_rad

# --- Guven rozetleri -------------------------------------------------------------

OLCULDU = "OLCULDU"  # kullanici olctu, sorgulanmaz
TAHMINI = "TAHMINI"  # makul tahmin, OLCULMELI
TASARIM = "TASARIM"  # kullanicinin karari, olculecek bir sey degil
TURETILDI = "TURETILDI"  # baska parametrelerden hesaplanir


@dataclass
class ParamMeta:
    """Bir parametrenin deger disindaki ust verisi."""

    confidence: str = TASARIM
    locked: bool = False
    note: str = ""
    how_to_measure: str = ""


# docs/ASSUMPTIONS.md'nin kod karsiligi. Burada olmayan her parametre TASARIM sayilir.
PARAM_META_DEFAULTS: dict[str, ParamMeta] = {
    "motor.no_load_rpm": ParamMeta(
        TAHMINI,
        how_to_measure=(
            "Motoru 24 V'a yuksuz bagla, mile bir isaret koy, telefonla 30 sn video cek, "
            "tur say, x2 = rpm."
        ),
    ),
    "motor.stall_torque_nm": ParamMeta(
        TAHMINI,
        note="Projenin yapilabilir olup olmadigi bu sayiya bagli -- bkz. docs/FINDINGS.md A3",
        how_to_measure=(
            "Mile 10 cm'lik saglam bir kol civatala. Kolun ucuna el tipi bagaj kantari "
            "bagla. Motoru 24 V'a ver, kantari motor DURUNCAYA kadar cek, en yuksek "
            "okumayi kaydet. Tork = kg x 9,81 x 0,10. Kol tam yatay, cekme tam dikey "
            "olmali. 2-3 sn'den uzun tutma, motor yanar."
        ),
    ),
    "motor.stall_current_a": ParamMeta(
        TAHMINI,
        note="LRS-350-24 bu akimi veremez; olcum icin aku veya guclu kaynak gerekir",
        how_to_measure="Stall tork olcumu sirasinda besleme hattina pens ampermetre tak.",
    ),
    "motor.no_load_current_a": ParamMeta(
        TAHMINI, how_to_measure="Yuksuz donerken pens ampermetre."
    ),
    "motor.forward_efficiency": ParamMeta(
        TAHMINI,
        note=(
            "Yalnizca motor tarafi verisinden cikis torku turetilirken kullanilir. "
            "Olculmus cikis stall torku girildiginde UYGULANMAZ (verim cift sayimi)."
        ),
    ),
    "motor.reverse_efficiency": ParamMeta(
        TAHMINI,
        how_to_measure=(
            "Motoru surmeden plakaya agirlik koy, kayiyor mu bak. Kaymiyorsa 0 dogru."
        ),
    ),
    "mass.carried_fraction": ParamMeta(
        TAHMINI,
        how_to_measure=(
            "Banyo terazisine oturma pozisyonunda otur, ayaklarin yerde. Okunan deger / "
            "toplam kutlen = bu oran."
        ),
    ),
    "mass.plate_assembly_kg": ParamMeta(
        TAHMINI, how_to_measure="Ust plaka + minder + braketleri tartip topla. Kolay olculur."
    ),
    "mass.plate_com_cm": ParamMeta(
        TAHMINI,
        how_to_measure=(
            "Ust plaka + minder + braketleri birlestirip tek parca olarak bir kalemin "
            "uzerinde dengeleyin; dengede kaldigi nokta agirlik merkezidir. Mafsal "
            "merkezine gore (yukari, ileri) olcup girin."
        ),
    ),
    "mass.seat_kg": ParamMeta(TAHMINI, how_to_measure="Koltugu tart."),
    "mass.seat_com_cm": ParamMeta(
        TAHMINI,
        note="Yalnizca 'koltugun tamami egiliyor' senaryosunda kullanilir.",
        how_to_measure=(
            "Koltugun agirlik merkezi yaklasik olarak oturma yuzeyinin 20-30 cm ustunde "
            "ve sirtligin one dogru 5-10 cm onundedir. Kesin olcum icin koltugu yan "
            "yatirip iki noktadan tartin."
        ),
    ),
    "mass.backrest_follow_fraction": ParamMeta(
        TAHMINI,
        note="Olculmesi zor. En kotu durum taramasi 0,4-1,0 araligini kapsar.",
    ),
    "mass.user_com_height_cm": ParamMeta(
        TAHMINI, note="Oturan yetiskin icin 20-30 cm tipik. Tarama bu araligi kapsar."
    ),
    "limits.rod_end_misalign_deg": ParamMeta(
        TAHMINI,
        how_to_measure="Rot basinin katalogunda 'misalignment angle' olarak gecer.",
    ),
    "limits.gimbal_max_deg": ParamMeta(
        TAHMINI, how_to_measure="Mafsali elinle yat, takildigi aciyi aciolcerle olc."
    ),
    "limits.pot.mechanical_range_deg": ParamMeta(
        TAHMINI, how_to_measure="Potu uctan uca cevirip aciolcerle olc. Tipik 270 veya 300."
    ),
    "stops.top_height_cm": ParamMeta(
        TURETILDI,
        note=(
            "+-12 derece hedefine gore hesaplandi. Takoz konumu degisirse yeniden "
            "hesaplanmali -- program devreye girme acisini raporlar."
        ),
    ),
    "hardware.gearbox_box_cm": ParamMeta(
        TAHMINI, how_to_measure="Motorlar elde oldugunda kumpasla olc. Carpisma analizi buna dayanir."
    ),
    "hardware.motor_cylinder_diameter_cm": ParamMeta(TAHMINI, how_to_measure="Kumpasla olc."),
    "hardware.motor_cylinder_length_cm": ParamMeta(TAHMINI, how_to_measure="Kumpasla olc."),
    "hardware.pot_bracket_cm": ParamMeta(TAHMINI, how_to_measure="Kumpasla olc."),
    "hardware.gimbal_post_diameter_cm": ParamMeta(TAHMINI, how_to_measure="Kumpasla olc."),
}


# --- Deger agaci -----------------------------------------------------------------


@dataclass
class BasePlateCfg:
    size_cm: list[float] = field(default_factory=lambda: [46.0, 50.0])
    thickness_cm: float = 1.8
    center_z_cm: float = 4.0


@dataclass
class TopPlateCfg:
    size_cm: list[float] = field(default_factory=lambda: [42.0, 42.0])
    thickness_cm: float = 1.8
    center_offset_z_cm: float = 3.0
    underside_above_gimbal_cm: float = 2.0


@dataclass
class CushionCfg:
    size_cm: list[float] = field(default_factory=lambda: [40.0, 40.0])
    thickness_cm: float = 4.0


@dataclass
class GimbalCfg:
    position_cm: list[float] = field(default_factory=lambda: [0.0, 13.0, 0.0])
    outer_axis: str = "pitch"


@dataclass
class CrankCfg:
    length_cm: float = 4.0
    neutral_offset_deg: float = 0.0
    thickness_cm: float = 1.2


@dataclass
class RodCfg:
    length_cm: float = 5.5
    diameter_cm: float = 1.2


@dataclass
class GeometryCfg:
    base_plate: BasePlateCfg = field(default_factory=BasePlateCfg)
    top_plate: TopPlateCfg = field(default_factory=TopPlateCfg)
    cushion: CushionCfg = field(default_factory=CushionCfg)
    gimbal: GimbalCfg = field(default_factory=GimbalCfg)
    rod_attach_cm: list[float] = field(default_factory=lambda: [18.2, -0.5, 20.5])
    motor_shaft_cm: list[float] = field(default_factory=lambda: [18.2, 7.0, 24.5])
    crank: CrankCfg = field(default_factory=CrankCfg)
    rod: RodCfg = field(default_factory=RodCfg)


@dataclass
class HardwareCfg:
    gearbox_box_cm: list[float] = field(default_factory=lambda: [6.0, 8.0, 7.0])
    motor_cylinder_diameter_cm: float = 6.4
    motor_cylinder_length_cm: float = 13.0
    pot_bracket_cm: list[float] = field(default_factory=lambda: [4.0, 4.0, 2.0])
    gimbal_post_diameter_cm: float = 5.0
    # Mil ekseni boyunca (x) yerlesim: krank, reduktor kutusunun DISINDA doner.
    shaft_protrusion_cm: float = 2.5  # kutunun dis yuzu ile krank duzlemi arasi
    pot_offset_cm: float = 2.0  # pot braketi krank duzleminden ne kadar disda
    user_box_cm: list[float] = field(default_factory=lambda: [40.0, 30.0, 50.0])


@dataclass
class MassCfg:
    user_kg: float = 120.0
    user_sweep_kg: list[float] = field(default_factory=lambda: [60.0, 90.0, 120.0])
    carried_fraction: float = 0.85
    plate_assembly_kg: float = 8.0
    plate_com_cm: list[float] = field(default_factory=lambda: [0.0, 3.0, 4.0])
    backrest_mode: str = "fixed"
    backrest_follow_fraction: float = 0.60
    seat_kg: float = 12.0
    seat_com_cm: list[float] = field(default_factory=lambda: [0.0, 25.0, -5.0])
    user_com_height_cm: float = 25.0
    user_com_fore_aft_cm: float = 0.0
    user_com_lateral_cm: float = 0.0


@dataclass
class PotCfg:
    mechanical_range_deg: float = 270.0
    mount_offset_deg: float = 0.0


@dataclass
class LimitsCfg:
    rod_end_misalign_deg: float = 12.0
    gimbal_max_deg: float = 20.0
    deadpoint_margin_deg: float = 20.0
    clearance_min_cm: float = 1.0
    total_height_max_cm: float = 18.0
    pot: PotCfg = field(default_factory=PotCfg)


@dataclass
class StopsCfg:
    # (x, z) konumlar. On takozlar motor govdelerinden kacinmak icin ice alinmistir;
    # arka takozlar motorlarin tamamen arkasinda.
    positions_cm: list[list[float]] = field(
        default_factory=lambda: [[5.5, 18.0], [-5.5, 18.0], [18.0, -16.0], [-18.0, -16.0]]
    )
    # Takoz basina ust yuzey yuksekligi. Tek sayi verilirse hepsine uygulanir.
    top_height_cm: list[float] | float = field(
        default_factory=lambda: [10.07, 10.07, 7.78, 7.78]
    )
    size_cm: list[float] = field(default_factory=lambda: [4.0, 4.0])

    def heights(self) -> list[float]:
        """Takoz basina ust yuzey yuksekligi listesi."""
        n = len(self.positions_cm)
        if isinstance(self.top_height_cm, (int, float)):
            return [float(self.top_height_cm)] * n
        h = list(self.top_height_cm)
        if len(h) == 1:
            return h * n
        if len(h) != n:
            raise ValueError(
                f"stops.top_height_cm {len(h)} deger icerir ama {n} takoz tanimli"
            )
        return [float(v) for v in h]


@dataclass
class TargetsCfg:
    pitch_deg: float = 10.0
    roll_deg: float = 10.0
    combined_deg: list[float] = field(default_factory=lambda: [7.0, 7.0])
    torque_safety_factor: float = 2.0


@dataclass
class MotorCfg:
    no_load_rpm: float = 55.0
    stall_torque_nm: float = 30.0
    stall_current_a: float = 20.0
    no_load_current_a: float = 2.0
    forward_efficiency: float = 0.50
    reverse_efficiency: float = 0.0


@dataclass
class PowerCfg:
    supply_voltage_v: float = 24.0
    supply_current_a: float = 14.6
    supply_peak_current_a: float = 17.5
    fuse_a: float = 20.0


# Birbirine BAGLI parcalar: temas etmeleri normaldir, carpisma sayilmaz.
# Bu liste config.yaml ile AYNI olmak zorunda -- ayrisirsa config.yaml silindiginde
# program hicbir cifti haric tutmaz ve calisma alani sifira duser.
# tests/test_config.py::test_load_defaults_match_dataclass bunu korur.
_DEFAULT_EXCLUDE_PAIRS: list[list[str]] = [
    ["rod_right", "crank_right"],
    ["rod_left", "crank_left"],
    ["rod_right", "top_plate"],
    ["rod_left", "top_plate"],
    ["rod_right", "cushion"],
    ["rod_left", "cushion"],
    ["top_plate", "cushion"],
    ["top_plate", "gimbal_post"],
    ["cushion", "user_body"],
    ["top_plate", "user_body"],
    ["base_plate", "gimbal_post"],
    ["base_plate", "gearbox_right"],
    ["base_plate", "gearbox_left"],
    ["base_plate", "motor_right"],
    ["base_plate", "motor_left"],
    ["base_plate", "pot_right"],
    ["base_plate", "pot_left"],
    ["base_plate", "stop_0"],
    ["base_plate", "stop_1"],
    ["base_plate", "stop_2"],
    ["base_plate", "stop_3"],
    ["gearbox_right", "motor_right"],
    ["gearbox_left", "motor_left"],
    ["gearbox_right", "pot_right"],
    ["gearbox_left", "pot_left"],
    ["motor_right", "pot_right"],
    ["motor_left", "pot_left"],
]


@dataclass
class CollisionCfg:
    samples: int = 16
    exclude_pairs: list[list[str]] = field(
        default_factory=lambda: [list(pair) for pair in _DEFAULT_EXCLUDE_PAIRS]
    )

    def excluded(self) -> set[frozenset[str]]:
        """Yon bagimsiz karsilastirma icin kume kumesi."""
        return {frozenset(p) for p in self.exclude_pairs}


@dataclass
class SeatConfig:
    geometry: GeometryCfg = field(default_factory=GeometryCfg)
    hardware: HardwareCfg = field(default_factory=HardwareCfg)
    mass: MassCfg = field(default_factory=MassCfg)
    limits: LimitsCfg = field(default_factory=LimitsCfg)
    stops: StopsCfg = field(default_factory=StopsCfg)
    targets: TargetsCfg = field(default_factory=TargetsCfg)
    motor: MotorCfg = field(default_factory=MotorCfg)
    power: PowerCfg = field(default_factory=PowerCfg)
    collision: CollisionCfg = field(default_factory=CollisionCfg)
    controller: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, ParamMeta] = field(default_factory=dict)

    def get_meta(self, path: str) -> ParamMeta:
        """Bir parametrenin ust verisi; tanimlanmamissa TASARIM varsayilir."""
        if path in self.meta:
            return self.meta[path]
        return PARAM_META_DEFAULTS.get(path, ParamMeta())

    def uncertain_parameters(self) -> list[tuple[str, Any, ParamMeta]]:
        """Rozeti TAHMINI olan parametreler: (yol, deger, ust veri)."""
        out = []
        for path, value in _walk(self):
            m = self.get_meta(path)
            if m.confidence == TAHMINI:
                out.append((path, value, m))
        return out

    def free_parameters(self) -> list[str]:
        """Kilitli olmayan sayisal parametre yollari (Faz 4 tasarim degiskenleri)."""
        return [
            path
            for path, value in _walk(self)
            if isinstance(value, (int, float)) and not self.get_meta(path).locked
        ]

    def copy(self) -> SeatConfig:
        return copy.deepcopy(self)


# --- Agac gezinme ----------------------------------------------------------------

_SKIP_SECTIONS = {"meta", "controller", "collision"}
"""_walk'un atladigi bolumler.

`collision` ve `controller` sayisal tasarim degiskeni degildir; optimizasyona ve
"tahmini deger" listesine girmemeleri gerekir. Ancak PROFIL KARSILASTIRMASINA
girmeleri gerekir -- `collision.exclude_pairs` calisma alani sonucunu degistirir.
Bu yuzden diff() ayri bir gezinme kullanir (bkz. _walk_all).
"""


def _walk(node: Any, prefix: str = "", skip: set[str] | None = None
          ) -> list[tuple[str, Any]]:
    """Dataclass agacinda yapraklari (noktali yol, deger) olarak dolasir."""
    skip = _SKIP_SECTIONS if skip is None else skip
    out: list[tuple[str, Any]] = []
    for f in fields(node):
        if not prefix and f.name in skip:
            continue
        value = getattr(node, f.name)
        path = f"{prefix}.{f.name}" if prefix else f.name
        if is_dataclass(value):
            out.extend(_walk(value, path, skip))
        else:
            out.append((path, value))
    return out


def _walk_all(cfg: SeatConfig) -> list[tuple[str, Any]]:
    """diff() icin: yalnizca `meta` atlanir, `collision` ve `controller` dahil edilir."""
    out = _walk(cfg, "", {"meta"})
    out.append(("controller", cfg.controller))
    return out


def get_by_path(cfg: SeatConfig, path: str) -> Any:
    """Noktali yol ile deger oku. Ornek: "geometry.crank.length_cm"."""
    node: Any = cfg
    for part in path.split("."):
        node = getattr(node, part)
    return node


def set_by_path(cfg: SeatConfig, path: str, value: Any) -> None:
    """Noktali yol ile deger yaz."""
    parts = path.split(".")
    node: Any = cfg
    for part in parts[:-1]:
        node = getattr(node, part)
    setattr(node, parts[-1], value)


# --- Yukleme / kaydetme ----------------------------------------------------------

_LONG_FORM_KEYS = {"value", "locked", "confidence", "note", "how_to_measure"}


def _is_long_form(raw: Any) -> bool:
    """Uzun bicim: icinde `value` olan sozluk.

    Bilinmeyen alt anahtar varsa bu YINE uzun bicimdir ve _fill acik bir hata verir --
    sozlugu oldugu gibi deger olarak yazmak, validate()'in sonradan TypeError ile
    cokmesine yol acardi.
    """
    return isinstance(raw, dict) and "value" in raw


def _fill(node: Any, raw: dict[str, Any], prefix: str, meta: dict[str, ParamMeta],
          strict: bool) -> None:
    """YAML sozlugunu dataclass agacina yazar, uzun bicim ust verisini toplar."""
    known = {f.name for f in fields(node)}
    if strict:
        unknown = set(raw) - known
        if unknown:
            where = prefix or "(kok)"
            raise ValueError(f"{where}: bilinmeyen anahtar(lar): {sorted(unknown)}")

    for f in fields(node):
        if f.name not in raw:
            continue
        value = raw[f.name]
        path = f"{prefix}.{f.name}" if prefix else f.name
        current = getattr(node, f.name)

        if is_dataclass(current):
            if not isinstance(value, dict):
                raise ValueError(f"{path}: sozluk bekleniyordu, {type(value).__name__} geldi")
            _fill(current, value, path, meta, strict)
            continue

        if _is_long_form(value):
            unknown = set(value) - _LONG_FORM_KEYS
            if unknown:
                raise ValueError(
                    f"{path}: uzun bicimde bilinmeyen anahtar(lar) {sorted(unknown)}. "
                    f"Izin verilenler: {sorted(_LONG_FORM_KEYS)}"
                )
            base = PARAM_META_DEFAULTS.get(path, ParamMeta())
            meta[path] = ParamMeta(
                confidence=value.get("confidence", base.confidence),
                locked=bool(value.get("locked", base.locked)),
                note=value.get("note", base.note),
                how_to_measure=value.get("how_to_measure", base.how_to_measure),
            )
            value = value["value"]
        elif isinstance(value, dict):
            raise ValueError(
                f"{path}: sozluk verildi ama uzun bicim degil -- `value` anahtari yok. "
                f"Ya sayiyi dogrudan yazin ya da {{value: ..., locked: ...}} bicimini "
                f"kullanin."
            )

        setattr(node, f.name, value)


def from_dict(raw: dict[str, Any], strict: bool = True) -> SeatConfig:
    """Duz sozlukten SeatConfig kurar (YAML'dan okunmus veya to_dict cikisi).

    Raises:
        ValueError: sema uyusmazliginda (strict=True ise bilinmeyen anahtar dahil)
    """
    if not isinstance(raw, dict):
        raise TypeError(f"kokte sozluk bekleniyordu, {type(raw).__name__} geldi")
    raw = dict(raw)  # cagiranin sozlugunu bozmayalim
    cfg = SeatConfig()
    meta: dict[str, ParamMeta] = {}
    controller = raw.pop("controller", {})
    _fill(cfg, raw, "", meta, strict)
    cfg.controller = controller or {}
    cfg.meta = meta
    return cfg


def to_dict(cfg: SeatConfig) -> dict[str, Any]:
    """SeatConfig'i duz sozluge cevirir. Kilitli parametreler uzun bicimde yazilir.

    from_dict(to_dict(cfg)) gidis-donusu degeri korur.
    """
    return _to_dict(cfg, "", cfg.meta)


def load(path: str | Path = "config.yaml", strict: bool = True) -> SeatConfig:
    """config.yaml'i yukler.

    Raises:
        FileNotFoundError: dosya yoksa
        ValueError: sema uyusmazliginda (strict=True ise bilinmeyen anahtar dahil)
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"yapilandirma dosyasi bulunamadi: {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    try:
        return from_dict(raw, strict)
    except ValueError as exc:
        raise ValueError(f"{p}: {exc}") from exc


def _to_dict(node: Any, prefix: str, meta: dict[str, ParamMeta]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in fields(node):
        if not prefix and f.name == "meta":
            continue
        value = getattr(node, f.name)
        path = f"{prefix}.{f.name}" if prefix else f.name
        if is_dataclass(value):
            out[f.name] = _to_dict(value, path, meta)
        elif path in meta:
            m = meta[path]
            entry: dict[str, Any] = {"value": value, "locked": m.locked,
                                     "confidence": m.confidence}
            if m.note:
                entry["note"] = m.note
            out[f.name] = entry
        else:
            out[f.name] = value
    return out


def to_yaml(cfg: SeatConfig) -> str:
    """Yapilandirmanin YAML metni. Onbellek anahtari olarak da kullanilir."""
    return yaml.safe_dump(
        to_dict(cfg), allow_unicode=True, sort_keys=True, default_flow_style=False
    )


def save(cfg: SeatConfig, path: str | Path) -> None:
    """Yapilandirmayi YAML olarak kaydeder. Kilitli parametreler uzun bicimde yazilir."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = to_dict(cfg)
    header = (
        "# 2DoF Hareketli Koltuk -- Tasarim Parametreleri\n"
        "# BIRIMLER: uzunluk cm, aci derece, kutle kg, kuvvet N, tork N.m\n"
        "# Koordinat sistemi: x = sag, y = yukari, z = ileri\n"
        "# Sema: docs/files/config.md\n\n"
    )
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    p.write_text(header + body, encoding="utf-8")


# --- Dogrulama -------------------------------------------------------------------

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"


@dataclass
class Issue:
    severity: str
    path: str
    message: str


def validate(cfg: SeatConfig) -> list[Issue]:
    """Yapilandirmayi denetler. Hata FIRLATMAZ, sorun listesi dondurur.

    Baslangic config.yaml dosyasi 3 WARN uretir -- bu beklenen davranistir,
    bkz. docs/FINDINGS.md.
    """
    issues: list[Issue] = []
    g = cfg.geometry

    # --- ERROR: fiziksel olarak anlamsiz degerler
    positive = {
        "geometry.crank.length_cm": g.crank.length_cm,
        "geometry.rod.length_cm": g.rod.length_cm,
        "geometry.top_plate.thickness_cm": g.top_plate.thickness_cm,
        "geometry.base_plate.thickness_cm": g.base_plate.thickness_cm,
        "geometry.cushion.thickness_cm": g.cushion.thickness_cm,
        "hardware.gimbal_post_diameter_cm": cfg.hardware.gimbal_post_diameter_cm,
        "motor.stall_torque_nm": cfg.motor.stall_torque_nm,
    }
    for path, value in positive.items():
        if value <= 0:
            issues.append(Issue(ERROR, path, f"pozitif olmali, {value} verildi"))

    if not 0.0 <= cfg.mass.carried_fraction <= 1.0:
        issues.append(Issue(ERROR, "mass.carried_fraction", "0 ile 1 arasinda olmali"))
    if not 0.0 <= cfg.mass.backrest_follow_fraction <= 1.0:
        issues.append(
            Issue(ERROR, "mass.backrest_follow_fraction", "0 ile 1 arasinda olmali")
        )
    if cfg.mass.backrest_mode not in ("fixed", "tilting"):
        issues.append(
            Issue(ERROR, "mass.backrest_mode", "'fixed' veya 'tilting' olmali")
        )
    if g.gimbal.outer_axis not in ("pitch", "roll"):
        issues.append(Issue(ERROR, "geometry.gimbal.outer_axis", "'pitch' veya 'roll' olmali"))

    n_stops = len(cfg.stops.positions_cm)
    heights = cfg.stops.top_height_cm
    if isinstance(heights, list) and len(heights) not in (1, n_stops):
        issues.append(
            Issue(
                ERROR,
                "stops.top_height_cm",
                f"{len(heights)} yukseklik verildi ama {n_stops} takoz tanimli. "
                f"Tek sayi yazin (hepsine uygulanir) veya takoz basina bir deger verin.",
            )
        )

    # --- ERROR: notr pozda geometri kendi icinde tutarli mi
    #     Cubuk boyu, notrdeki pim-plaka mesafesine esit olmali.
    if g.crank.length_cm <= 0.0 or g.rod.length_cm <= 0.0:
        return issues  # olcu anlamsiz; yukaridaki ERROR'lar yeterli

    # Notrde pim ile plaka baglantisi arasindaki mesafe, 3 BOYUTLU olarak.
    # Yalnizca (y, z) bakmak, mafsalin x/z kaymasini ve baglanti ile milin yanal (x)
    # farkini gozden kacirir -- tam da bu kontrolun uyardigi durumu.
    gx, gy, gz = g.gimbal.position_cm
    ax, ay, az = g.rod_attach_cm
    sx, sy, sz = g.motor_shaft_cm
    attach = (gx + ax, gy + ay, gz + az)

    phi0 = deg_to_rad(g.crank.neutral_offset_deg)
    pin = (
        sx,
        sy + g.crank.length_cm * float(np.sin(phi0)),
        sz - g.crank.length_cm * float(np.cos(phi0)),
    )
    neutral_span = float(
        np.linalg.norm(np.asarray(attach, dtype=float) - np.asarray(pin, dtype=float))
    )
    if abs(neutral_span - g.rod.length_cm) > 0.02:
        issues.append(
            Issue(
                ERROR,
                "geometry.rod.length_cm",
                f"notr pozda pim-plaka mesafesi {neutral_span:.3f} cm, "
                f"cubuk boyu {g.rod.length_cm:.3f} cm -- plaka notrde yatay olmaz. "
                f"Cubuk boyunu {neutral_span:.2f} cm yap veya motor mili konumunu degistir.",
            )
        )

    # --- WARN: bilinen tasarim cakismalari (docs/FINDINGS.md)
    total_h = (
        g.gimbal.position_cm[1]
        + g.top_plate.underside_above_gimbal_cm
        + g.top_plate.thickness_cm
        + g.cushion.thickness_cm
    )
    if total_h > cfg.limits.total_height_max_cm:
        issues.append(
            Issue(
                WARN,
                "geometry.gimbal.position_cm",
                f"toplam yukseklik {total_h:.1f} cm, kisit "
                f"{cfg.limits.total_height_max_cm:.1f} cm -- "
                f"{total_h - cfg.limits.total_height_max_cm:.1f} cm fazla "
                f"(docs/FINDINGS.md A2)",
            )
        )

    # validate() asla istisna firlatmamali; sifir krank yukarida ERROR olarak zaten
    # bildirildi, burada bolmeye girmeyiz.
    ratio = g.rod.length_cm / g.crank.length_cm if g.crank.length_cm > 0.0 else None
    if ratio is not None and ratio < 2.0:
        issues.append(
            Issue(
                WARN,
                "geometry.rod.length_cm",
                f"cubuk/krank orani {ratio:.2f} -- 2'nin altinda. Krank dondukce hareketin "
                f"buyuk kismi cubugun yatmasina gider, calisma alani daralir "
                f"(docs/FINDINGS.md A1)",
            )
        )

    plate_front = g.top_plate.center_offset_z_cm + g.top_plate.size_cm[1] / 2.0
    if g.motor_shaft_cm[2] > plate_front:
        issues.append(
            Issue(
                WARN,
                "geometry.motor_shaft_cm",
                f"motor mili z={g.motor_shaft_cm[2]:.1f} cm, ust plakanin on kenari "
                f"z={plate_front:.1f} cm -- mil izdusumun "
                f"{g.motor_shaft_cm[2] - plate_front:.1f} cm disinda (docs/FINDINGS.md B1)",
            )
        )

    plate_half_w = g.top_plate.size_cm[0] / 2.0
    shaft_outer = abs(g.motor_shaft_cm[0]) + cfg.hardware.gearbox_box_cm[0] / 2.0
    if shaft_outer > plate_half_w:
        issues.append(
            Issue(
                WARN,
                "geometry.motor_shaft_cm",
                f"reduktor kutusu yan yonde izdusumun {shaft_outer - plate_half_w:.1f} cm "
                f"disinda",
            )
        )

    # --- INFO
    n_unknown = len(cfg.uncertain_parameters())
    if n_unknown:
        issues.append(
            Issue(
                INFO,
                "(genel)",
                f"{n_unknown} parametre TAHMINI rozetli -- olculmeden sonuclar kesinlesmez "
                f"(docs/ASSUMPTIONS.md)",
            )
        )

    return issues


# --- Profil karsilastirma --------------------------------------------------------


@dataclass
class Change:
    path: str
    old: Any
    new: Any


def diff(cfg_a: SeatConfig, cfg_b: SeatConfig) -> list[Change]:
    """Iki profil arasindaki farklar.

    `collision` ve `controller` bolumleri de karsilastirilir: tasarim degiskeni
    olmasalar da sonucu etkilerler (orn. collision.exclude_pairs).
    """
    a = dict(_walk_all(cfg_a))
    b = dict(_walk_all(cfg_b))
    out: list[Change] = []
    for path in sorted(set(a) | set(b)):
        old, new = a.get(path, "(yok)"), b.get(path, "(yok)")
        if isinstance(old, float) and isinstance(new, float):
            if abs(old - new) > 1e-12:
                out.append(Change(path, old, new))
        elif old != new:
            out.append(Change(path, old, new))
    return out
