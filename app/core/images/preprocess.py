"""Uneltele de preprocesare si registrul lor.

Implementeaza din SPEC_05 sectiunea 5 `PreprocessTool` si, din
`PreprocessPipeline`, registrul (`register`, `tool_for`). Rularea pe paginile
proiectului (`run`, `recommended_chain`, `revert_to_original`) vine in pasul 2d.

Fiecare unealta e pura (SPEC_02 L): primeste un ndarray si parametri, intoarce
un ndarray nou si metadatele produse. Nu scrie pe disc, nu are stare.

Formatul imaginii (docs/plan/faza_2_pasi.md, decizia 3): ndarray `uint8`,
`(inaltime, latime)` pentru gri si alb-negru (0/255), `(inaltime, latime, 3)`
pentru culoare.

Pasul 2a: rotire si oglindire (L-015), decupare (L-017), inversare (L-018),
rezolutie (L-019), luminozitate si contrast (L-020), niveluri (L-021),
radiera (L-022), alb-negru (L-033).

Pasul 2b: indreptarea paginii (L-011, X-020), culori inversate (X-028),
marcaje colorate (L-023, X-030), albirea fundalului (X-024), zgomot ISO
(X-025). Cu numpy si scipy (BSD); nu OpenCV (decizia din 2026-11-20).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar, Protocol, runtime_checkable

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

from app.core.model import PreprocessOp

Params = Mapping[str, Any]
Meta = Mapping[str, Any]
ParamSpec = dict[str, tuple[Any, Callable[[Any], str | None]]]
"""{nume: (valoare implicita, verificare)}."""


# =============================================================================
# Conversia Pillow <-> ndarray
# =============================================================================


def to_array(img: Image.Image) -> np.ndarray:
    """Imaginea Pillow ca ndarray uint8: 2D pentru gri si alb-negru, 3D RGB pentru
    culoare. Transparenta se compune pe alb; 16 biti se reduc la 8."""
    mode = img.mode
    if mode == "1":
        return np.where(np.asarray(img, dtype=bool), 255, 0).astype(np.uint8)
    if mode == "L":
        return np.asarray(img, dtype=np.uint8).copy()
    if mode in ("I;16", "I;16B", "I;16L", "I"):
        data = np.asarray(img, dtype=np.float64)
        top = 65535.0 if mode.startswith("I;16") else max(float(data.max()), 1.0)
        return np.clip(data / top * 255.0 + 0.5, 0, 255).astype(np.uint8)
    if mode == "F":
        return np.clip(np.asarray(img) + 0.5, 0, 255).astype(np.uint8)
    if mode in ("LA", "RGBA", "PA") or (mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(white, rgba).convert("RGB")
        if mode == "LA":
            img = img.convert("L")
            return np.asarray(img, dtype=np.uint8).copy()
    elif mode != "RGB":
        img = img.convert("RGB")
    return np.asarray(img, dtype=np.uint8).copy()


def from_array(array: np.ndarray) -> Image.Image:
    """ndarray uint8 2D (L) sau 3D (RGB) ca imagine Pillow."""
    check_image(array)
    return Image.fromarray(array, mode="L" if array.ndim == 2 else "RGB")


def check_image(array: Any) -> None:
    """ValueError daca `array` nu respecta formatul uneltelor."""
    if not isinstance(array, np.ndarray) or array.dtype != np.uint8:
        raise ValueError("imaginea trebuie sa fie un ndarray uint8")
    if array.ndim == 3 and array.shape[2] == 3:
        pass
    elif array.ndim != 2:
        raise ValueError(f"forma imaginii nu e (h, w) sau (h, w, 3): {array.shape}")
    if array.shape[0] < 1 or array.shape[1] < 1:
        raise ValueError("imaginea e goala")


def is_bilevel(array: np.ndarray) -> bool:
    """Alb-negru: 2D si doar valorile 0 si 255."""
    return array.ndim == 2 and bool(np.isin(array, (0, 255)).all())


# =============================================================================
# Contractul
# =============================================================================


# SPEC_05 sect. 5. L-032 (photo_only; SPEC_05 il numeste L-018)
@runtime_checkable
class PreprocessTool(Protocol):
    """O unealta de preprocesare. Pura: nu scrie pe disc, nu are stare."""

    op: PreprocessOp
    photo_only: bool
    """L-032: se aplica automat doar fotografiilor."""

    def default_params(self) -> Mapping[str, Any]: ...
    def validate_params(self, params: Mapping[str, Any]) -> None: ...
    def apply(self, image: Any, params: Mapping[str, Any]) -> tuple[Any, Mapping[str, Any]]: ...


class BaseTool:
    """Validarea comuna: parametri necunoscuti, tipuri, intervale. Subclasele
    declara `PARAMS` = {nume: (implicit, verificare)} si `_apply`."""

    op: PreprocessOp
    photo_only = False
    PARAMS: ClassVar[ParamSpec] = {}

    def default_params(self) -> Mapping[str, Any]:
        return {k: _copy(v[0]) for k, v in self.PARAMS.items()}

    def validate_params(self, params: Params) -> None:
        """ValueError cu numele parametrului gresit."""
        unknown = set(params) - set(self.PARAMS)
        if unknown:
            raise ValueError(f"{self.op.value}: parametri necunoscuti {sorted(unknown)}")
        for name, value in params.items():
            reason = self.PARAMS[name][1](value)
            if reason:
                raise ValueError(f"{self.op.value}.{name}: {reason}")

    def apply(self, image: Any, params: Params) -> tuple[np.ndarray, Meta]:
        check_image(image)
        self.validate_params(params)
        full = {**self.default_params(), **params}
        return self._apply(image, full)

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        raise NotImplementedError  # pragma: no cover


def _copy(value: Any) -> Any:
    return list(value) if isinstance(value, list) else value


def _int_in(lo: int, hi: int) -> Callable[[Any], str | None]:
    def check(v: Any) -> str | None:
        if isinstance(v, bool) or not isinstance(v, int):
            return f"se asteapta un numar intreg, nu {v!r}"
        if not lo <= v <= hi:
            return f"{v} e in afara intervalului {lo}..{hi}"
        return None
    return check


def _num_in(lo: float, hi: float) -> Callable[[Any], str | None]:
    def check(v: Any) -> str | None:
        if isinstance(v, bool) or not isinstance(v, int | float) or math.isnan(v):
            return f"se asteapta un numar, nu {v!r}"
        if not lo <= v <= hi:
            return f"{v} e in afara intervalului {lo}..{hi}"
        return None
    return check


def _one_of(*allowed: Any) -> Callable[[Any], str | None]:
    """Valoare din lista, cu acelasi tip: 90.0 sau True nu trec drept 90 sau 1."""
    def check(v: Any) -> str | None:
        ok = any(type(v) is type(a) and v == a for a in allowed)
        return None if ok else f"{v!r} nu e in {list(allowed)}"
    return check


def _optional(inner: Callable[[Any], str | None]) -> Callable[[Any], str | None]:
    return lambda v: None if v is None else inner(v)


# =============================================================================
# Uneltele pasului 2a
# =============================================================================


# L-015: fara pierdere de calitate
class RotateTool(BaseTool):
    """Rotire cu multipli de 90, in sensul acelor de ceasornic (negativ = invers)."""

    op = PreprocessOp.ROTATE
    PARAMS: ClassVar[ParamSpec] = {"angle": (90, _one_of(90, 180, 270, -90, -180, -270))}

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        turn = p["angle"] % 360
        out = np.ascontiguousarray(np.rot90(image, k=-(turn // 90), axes=(0, 1)))
        return out, {"angle": turn, "swap_dpi": turn in (90, 270)}


# L-015
class FlipTool(BaseTool):
    """Oglindire: `horizontal` = stanga-dreapta, `vertical` = sus-jos."""

    op = PreprocessOp.FLIP
    PARAMS: ClassVar[ParamSpec] = {"axis": ("horizontal", _one_of("horizontal", "vertical"))}

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        out = image[:, ::-1] if p["axis"] == "horizontal" else image[::-1, :]
        return np.ascontiguousarray(out), {"axis": p["axis"]}


# L-017: valorile nu pot depasi imaginea
class CropTool(BaseTool):
    """Decupare in pixeli. Unitatile si formatele de hartie din L-017 (inci,
    milimetri, A4...) se transforma in pixeli cu `crop_params`."""

    op = PreprocessOp.CROP
    PARAMS: ClassVar[ParamSpec] = {
        "x": (0, _int_in(0, 10**7)),
        "y": (0, _int_in(0, 10**7)),
        "width": (None, _optional(_int_in(1, 10**7))),
        "height": (None, _optional(_int_in(1, 10**7))),
    }

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        h, w = image.shape[:2]
        x, y = p["x"], p["y"]
        cw = w - x if p["width"] is None else p["width"]
        ch = h - y if p["height"] is None else p["height"]
        if x + cw > w or y + ch > h or cw < 1 or ch < 1:
            raise ValueError(
                f"crop: zona ({x}, {y}, {cw}x{ch}) depaseste imaginea {w}x{h}"
            )
        return np.ascontiguousarray(image[y:y + ch, x:x + cw]), {
            "x": x, "y": y, "width": cw, "height": ch}


PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "a3": (297, 420), "a4": (210, 297), "a5": (148, 210), "b5": (176, 250),
    "letter": (215.9, 279.4), "legal": (215.9, 355.6), "executive": (184.15, 266.7),
}
"""L-017: dimensiunile de hartie pentru `Crop`, in milimetri, in picioare."""

_MM_PER_INCH = 25.4


# L-017, L-103: campurile dialogului (inci sau milimetri) -> pixeli
def crop_params(
    *,
    dpi: tuple[int, int],
    unit: str = "mm",
    paper: str | None = None,
    width: float | None = None,
    height: float | None = None,
    x: float = 0,
    y: float = 0,
) -> dict[str, int]:
    """Parametrii pentru CropTool din dimensiuni in `mm` sau `in`, sau dintr-un
    format de hartie (`paper`, care inlocuieste latimea si inaltimea)."""
    if unit not in ("mm", "in"):
        raise ValueError(f"unitate necunoscuta: {unit!r}; permise: mm, in")
    if paper is not None:
        if paper not in PAPER_SIZES_MM:
            raise ValueError(f"format de hartie necunoscut: {paper!r}")
        width, height = PAPER_SIZES_MM[paper]
        unit_mm = True
    else:
        unit_mm = unit == "mm"
    dx, dy = dpi

    def px(value: float, d: int, mm: bool) -> int:
        inches = value / _MM_PER_INCH if mm else value
        return round(inches * d)

    out = {"x": px(x, dx, unit == "mm"), "y": px(y, dy, unit == "mm")}
    if width is not None:
        out["width"] = px(width, dx, unit_mm)
    if height is not None:
        out["height"] = px(height, dy, unit_mm)
    return out


# L-018 (manual), X-028 (automat: `auto=True`)
class InvertTool(BaseTool):
    """Inverseaza culorile. Cu `auto=True` (X-028 „Fix inverted colors”)
    inverseaza doar o pagina cu fundal inchis si text deschis."""

    op = PreprocessOp.INVERT
    PARAMS: ClassVar[ParamSpec] = {"auto": (False, _one_of(True, False))}

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        if p["auto"] and not looks_inverted(image):
            return image.copy(), {"inverted": False}
        return (255 - image).astype(np.uint8), {"inverted": True}


INVERTED_DARK_SHARE = 0.6
"""[DECIZIE] O pagina e inversata cand peste 60% din pixeli sunt inchisi
(sub 128). Un titlu alb pe negru, oricat de mare, nu inverseaza pagina."""


def looks_inverted(image: np.ndarray) -> bool:
    """X-028: fundal inchis, text deschis."""
    gray = to_gray(image)
    return float((gray < 128).mean()) > INVERTED_DARK_SHARE


RESOLUTION_MIN, RESOLUTION_MAX = 72, 1200
"""L-019: rezolutia tinta intre 72 si 1200 dpi."""


# L-019
class ResolutionTool(BaseTool):
    """Reesantionare de la `from_dpi` la `dpi`. Dimensiunea fizica a paginii
    ramane aceeasi; numarul de pixeli se schimba."""

    op = PreprocessOp.RESOLUTION
    PARAMS: ClassVar[ParamSpec] = {
        "dpi": (300, _int_in(RESOLUTION_MIN, RESOLUTION_MAX)),
        "from_dpi": (300, _int_in(1, 10_000)),
    }

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        if p["dpi"] == p["from_dpi"]:
            return image.copy(), {"dpi": p["dpi"]}
        scale = p["dpi"] / p["from_dpi"]
        h, w = image.shape[:2]
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        bilevel = is_bilevel(image)
        resized = to_array(from_array(image).resize(size, Image.Resampling.LANCZOS))
        if bilevel:  # alb-negrul ramane alb-negru
            resized = np.where(resized >= 128, 255, 0).astype(np.uint8)
        return resized, {"dpi": p["dpi"]}


def _lookup(image: np.ndarray, table: np.ndarray) -> np.ndarray:
    return table[image]


# L-020
class BrightnessContrastTool(BaseTool):
    """Doua slidere, -100..100; 0 = neschimbat."""

    op = PreprocessOp.BRIGHTNESS_CONTRAST
    PARAMS: ClassVar[ParamSpec] = {"brightness": (0, _num_in(-100, 100)), "contrast": (0, _num_in(-100, 100))}

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        c = float(p["contrast"]) * 2.55
        factor = (259 * (c + 255)) / (255 * (259 - c))
        x = np.arange(256, dtype=np.float64)
        y = factor * (x - 128) + 128 + float(p["brightness"]) * 2.55
        table = np.clip(np.round(y), 0, 255).astype(np.uint8)
        return _lookup(image, table), {}


# L-021: punctul negru nu poate depasi punctul alb
class LevelsTool(BaseTool):
    """Intrare: punct negru, gama (sliderul din mijloc), punct alb. Iesire:
    negru si alb."""

    op = PreprocessOp.LEVELS
    PARAMS: ClassVar[ParamSpec] = {
        "black": (0, _int_in(0, 255)),
        "white": (255, _int_in(0, 255)),
        "gamma": (1.0, _num_in(0.1, 10.0)),
        "out_black": (0, _int_in(0, 255)),
        "out_white": (255, _int_in(0, 255)),
    }

    def validate_params(self, params: Params) -> None:
        super().validate_params(params)
        full = {**self.default_params(), **params}
        if full["black"] >= full["white"]:
            raise ValueError(
                f"levels.black: punctul negru ({full['black']}) trebuie sa fie sub "
                f"punctul alb ({full['white']})"
            )

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        x = np.arange(256, dtype=np.float64)
        norm = np.clip((x - p["black"]) / (p["white"] - p["black"]), 0, 1)
        norm = norm ** (1.0 / float(p["gamma"]))
        y = p["out_black"] + norm * (p["out_white"] - p["out_black"])
        table = np.clip(np.round(y), 0, 255).astype(np.uint8)
        return _lookup(image, table), {}


def _points(v: Any) -> str | None:
    if not isinstance(v, list | tuple) or not v:
        return "se asteapta cel putin un punct [x, y]"
    for pt in v:
        if (not isinstance(pt, list | tuple) or len(pt) != 2
                or not all(isinstance(c, int) and not isinstance(c, bool) for c in pt)):
            return f"punct invalid: {pt!r}"
    return None


def background_color(image: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Culoarea fundalului: mediana pixelilor (in afara mastii). Pentru o pagina
    scanata, hartia ocupa cea mai mare parte, deci mediana e hartia."""
    pixels = image if mask is None else image[~mask]
    if pixels.size == 0:
        pixels = image
    if image.ndim == 2:
        return np.array(int(np.median(pixels)), dtype=np.uint8)
    return np.median(pixels.reshape(-1, 3), axis=0).round().astype(np.uint8)


# L-022: zona se umple cu fundalul detectat
class EraseTool(BaseTool):
    """Radiera: un traseu (lista de puncte) cu pensula de `brush` pixeli."""

    op = PreprocessOp.ERASE
    PARAMS: ClassVar[ParamSpec] = {"path": ([], _points), "brush": (20, _int_in(1, 2000))}

    def validate_params(self, params: Params) -> None:
        super().validate_params(params)
        if "path" not in params:
            raise ValueError("erase.path: traseul lipseste")

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        h, w = image.shape[:2]
        mask_img = Image.new("1", (w, h), 0)
        draw = ImageDraw.Draw(mask_img)
        pts = [tuple(pt) for pt in p["path"]]
        r = p["brush"] / 2
        if len(pts) > 1:
            draw.line(pts, fill=1, width=p["brush"])
        for x, y in pts:  # capete rotunde si puncte izolate
            draw.ellipse((x - r, y - r, x + r, y + r), fill=1)
        mask = np.asarray(mask_img, dtype=bool)
        out = image.copy()
        out[mask] = background_color(image, mask)
        return out, {"erased_pixels": int(mask.sum())}


def otsu_threshold(gray: np.ndarray) -> int:
    """Pragul Otsu pe o imagine gri uint8."""
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    weights = np.cumsum(hist)
    means = np.cumsum(hist * np.arange(256))
    w0, w1 = weights, total - weights
    with np.errstate(divide="ignore", invalid="ignore"):
        between = (means[-1] * w0 / total - means) ** 2 / (w0 * w1 / total)
    between[~np.isfinite(between)] = 0
    return int(np.argmax(between))


def to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    weights = np.array([0.299, 0.587, 0.114])
    return np.clip(image @ weights + 0.5, 0, 255).astype(np.uint8)


# L-033, X-029: conversia e ireversibila
class ToBwTool(BaseTool):
    """Alb-negru (0/255). Pragul: dat, sau ales automat (Otsu)."""

    op = PreprocessOp.TO_BW
    PARAMS: ClassVar[ParamSpec] = {"threshold": (None, _optional(_int_in(1, 254)))}

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        gray = to_gray(image)
        t = otsu_threshold(gray) if p["threshold"] is None else p["threshold"]
        return np.where(gray > t, 255, 0).astype(np.uint8), {
            "threshold": t, "irreversible": True}


# =============================================================================
# Uneltele pasului 2b
# =============================================================================

DESKEW_MAX_ANGLE = 15.0
"""[DECIZIE] Cautarea unghiului se face intre -15 si +15 grade. O scanare mai
inclinata e de fapt rotita; aceea se corecteaza cu orientarea (faza 4)."""

DESKEW_MIN_ANGLE = 0.05
"""Sub acest unghi (grade) pagina se considera dreapta si nu se roteste."""

_DESKEW_SAMPLE = 1600
"""Latura mare a imaginii pe care se cauta unghiul."""

_DESKEW_MAX_POINTS = 250_000


def _ink_points(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Coordonatele (x, y) ale pixelilor de cerneala, pe o imagine micsorata, si
    factorul de micsorare."""
    gray = to_gray(image)
    h, w = gray.shape
    scale = min(1.0, _DESKEW_SAMPLE / max(h, w))
    if scale < 1.0:
        small = np.asarray(Image.fromarray(gray).resize(
            (max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.BOX))
    else:
        small = gray
    ink = small < otsu_threshold(small)
    if is_bilevel(gray):
        ink = small < 128
    ys, xs = np.nonzero(ink)
    if len(xs) > _DESKEW_MAX_POINTS:
        pick = np.random.default_rng(0).choice(len(xs), _DESKEW_MAX_POINTS, replace=False)
        xs, ys = xs[pick], ys[pick]
    return xs.astype(np.float64), ys.astype(np.float64), scale


def _profile_score(xs: np.ndarray, ys: np.ndarray, angle: float) -> float:
    """Cat de „ascutit” e profilul orizontal dupa indreptarea cu `angle`.
    Randurile drepte dau varfuri inalte si goluri adanci: suma patratelor mare."""
    t = np.deg2rad(angle)
    rows = np.round(xs * np.sin(t) + ys * np.cos(t)).astype(np.int64)
    rows -= rows.min()
    hist = np.bincount(rows).astype(np.float64)
    return float((hist * hist).sum())


# L-011, X-020
def detect_skew(image: np.ndarray, max_angle: float = DESKEW_MAX_ANGLE) -> float:
    """Unghiul de inclinare in grade; pozitiv = textul urca spre dreapta
    (rotit in sens invers acelor de ceasornic). 0 daca pagina n-are text."""
    xs, ys, _ = _ink_points(image)
    if len(xs) < 50:
        return 0.0
    best, step = 0.0, 0.5
    candidates = np.arange(-max_angle, max_angle + step / 2, step)
    for _ in range(3):  # grosier, apoi tot mai fin in jurul celui mai bun
        scores = [_profile_score(xs, ys, a) for a in candidates]
        best = float(candidates[int(np.argmax(scores))])
        lo, hi = max(-max_angle, best - step), min(max_angle, best + step)
        step /= 10
        candidates = np.arange(lo, hi + step / 2, step)
    return round(best, 2)


def rotate_fill(image: np.ndarray, angle: float) -> np.ndarray:
    """Roteste cu `angle` grade (pozitiv = invers acelor de ceasornic), cu
    aceeasi dimensiune; colturile descoperite se umplu cu fundalul."""
    bg = background_color(image)
    bilevel = is_bilevel(image)
    if image.ndim == 2:
        out = ndi.rotate(image.astype(np.float32), angle, reshape=False, order=1,
                         mode="constant", cval=float(bg))
    else:
        out = np.stack([
            ndi.rotate(image[..., c].astype(np.float32), angle, reshape=False, order=1,
                       mode="constant", cval=float(bg[c]))
            for c in range(3)
        ], axis=-1)
    out = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    if bilevel:
        out = np.where(out >= 128, 255, 0).astype(np.uint8)
    return out


# L-011, X-020
class DeskewTool(BaseTool):
    """Indreapta pagina. `angle=None`: unghiul se detecteaza; altfel se
    foloseste cel dat. Metadate: unghiul corectat."""

    op = PreprocessOp.DESKEW
    PARAMS: ClassVar[ParamSpec] = {
        "angle": (None, _optional(_num_in(-45.0, 45.0))),
        "max_angle": (DESKEW_MAX_ANGLE, _num_in(0.5, 45.0)),
    }

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        angle = detect_skew(image, p["max_angle"]) if p["angle"] is None else float(p["angle"])
        if abs(angle) < DESKEW_MIN_ANGLE:
            return image.copy(), {"angle": 0.0}
        return rotate_fill(image, -angle), {"angle": angle}


COLOR_MARK_SATURATION = 60
"""[DECIZIE] Un pixel e marcaj colorat cand canalele lui difera cu peste 60
(din 255): pix albastru, stampila rosie, marker. Textul negru si gri, nu."""

WHITE_BACKGROUND_MIN = 200
"""L-023: fundalul trebuie sa fie deschis (luminanta mediana peste 200)..."""

WHITE_BACKGROUND_MAX_SATURATION = 30
"""...si necolorat (diferenta intre canale sub 30)."""


def _saturation(image: np.ndarray) -> np.ndarray:
    return (image.max(axis=2).astype(np.int16) - image.min(axis=2)).astype(np.int16)


def has_white_background(image: np.ndarray) -> bool:
    """L-023: scanare cu fundal alb (nu fotografie, nu hartie colorata)."""
    bg = background_color(image)
    if image.ndim == 2:
        return int(bg) >= WHITE_BACKGROUND_MIN
    return int(bg.min()) >= WHITE_BACKGROUND_MIN and int(
        bg.max()) - int(bg.min()) <= WHITE_BACKGROUND_MAX_SATURATION


# L-023, X-030: numai pentru scanari cu fundal alb
class RemoveColorMarksTool(BaseTool):
    """Inlocuieste marcajele colorate (pix, stampile, marker) cu culoarea
    hartiei. Pe o imagine fara fundal alb nu face nimic si spune de ce
    (L-023: nu pentru fotografii sau fundaluri colorate)."""

    op = PreprocessOp.REMOVE_COLOR_MARKS
    PARAMS: ClassVar[ParamSpec] = {"saturation": (COLOR_MARK_SATURATION, _int_in(10, 255))}

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        if image.ndim == 2:
            return image.copy(), {"removed_pixels": 0, "skipped": "grayscale"}
        if not has_white_background(image):
            return image.copy(), {"removed_pixels": 0, "skipped": "background_not_white"}
        mask = _saturation(image) > p["saturation"]
        out = image.copy()
        out[mask] = background_color(image, mask)
        return out, {"removed_pixels": int(mask.sum())}


_WHITEN_SAMPLE = 400
"""Latura mare a hartii de iluminare (fundalul variaza lent)."""


# X-024 („Whiten background”, doar fotografii, L-032)
class WhitenBackgroundTool(BaseTool):
    """Egalizeaza iluminarea hartiei: fundalul estimat (fara text, netezit)
    devine alb, iar textul isi pastreaza contrastul fata de el."""

    op = PreprocessOp.WHITEN_BACKGROUND
    photo_only = True
    PARAMS: ClassVar[ParamSpec] = {"strength": (1.0, _num_in(0.0, 1.0))}

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        channels = [image] if image.ndim == 2 else [image[..., c] for c in range(3)]
        out = np.stack([self._whiten(ch, float(p["strength"])) for ch in channels], axis=-1)
        return (out[..., 0] if image.ndim == 2 else out), {}

    @staticmethod
    def _whiten(channel: np.ndarray, strength: float) -> np.ndarray:
        h, w = channel.shape
        scale = min(1.0, _WHITEN_SAMPLE / max(h, w))
        small = np.asarray(Image.fromarray(channel).resize(
            (max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.BOX),
            dtype=np.float32)
        # textul e inchis: o inchidere morfologica (maxim local) il acopera cu hartia
        size = max(3, round(min(small.shape) / 25) | 1)
        bg_small = ndi.gaussian_filter(ndi.grey_closing(small, size=(size, size)), size / 2)
        bg = np.asarray(Image.fromarray(bg_small).resize((w, h), Image.Resampling.BILINEAR),
                        dtype=np.float32)
        flat = channel.astype(np.float32) / np.maximum(bg, 1.0) * 255.0
        mixed = strength * flat + (1.0 - strength) * channel
        return np.clip(mixed + 0.5, 0, 255).astype(np.uint8)


# X-025 („Reduce ISO noise”, doar fotografii, L-032)
class DenoiseTool(BaseTool):
    """Median selectiv: un pixel se inlocuieste cu mediana vecinilor doar daca
    e izolat (cel mult `max_similar` vecini din 8 care difera cu mai putin de
    `difference`).

    Un median simplu ar manca liniile subtiri ale literelor (1-2 pixeli); un
    pixel dintr-o linie are vecini asemanatori de-a lungul ei, deci ramane.
    """

    op = PreprocessOp.DENOISE
    photo_only = True
    PARAMS: ClassVar[ParamSpec] = {
        "size": (3, _one_of(3, 5, 7)),
        "difference": (80, _int_in(5, 255)),
        "max_similar": (0, _int_in(0, 4)),
    }
    """[DECIZIE] Implicit: niciun vecin asemanator (diferenta sub 80). Pe o
    pagina de test: 85% din zgomot reparat, 100% din text pastrat. Cu criterii
    mai largi se repara ceva mai mult zgomot, dar se ating marginile literelor."""

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        gray = to_gray(image).astype(np.int16)
        padded = np.pad(gray, 1, mode="edge")
        h, w = gray.shape
        similar = np.zeros((h, w), dtype=np.int8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    neighbour = padded[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
                    similar += np.abs(neighbour - gray) < p["difference"]
        isolated = similar <= p["max_similar"]
        k = p["size"]
        footprint = (k, k) if image.ndim == 2 else (k, k, 1)
        smoothed = ndi.median_filter(image, size=footprint, mode="nearest")
        out = image.copy()
        out[isolated] = smoothed[isolated]
        return out, {"replaced_pixels": int(isolated.sum())}


# =============================================================================
# Registrul
# =============================================================================


# SPEC_05: PreprocessPipeline, partea de registru (pasul 2a). Rularea: pasul 2d.
class PreprocessPipeline:
    """L-001, L-015..L-034. Fiecare valoare din PreprocessOp are o unealta
    inregistrata (pana la sfarsitul fazei 2)."""

    def __init__(self, tools: Sequence[PreprocessTool] = ()) -> None:
        self._tools: dict[PreprocessOp, PreprocessTool] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: PreprocessTool) -> None:
        if not isinstance(tool, PreprocessTool):
            raise TypeError(f"{tool!r} nu respecta PreprocessTool")
        self._tools[PreprocessOp(tool.op)] = tool

    def tool_for(self, op: PreprocessOp) -> PreprocessTool:
        try:
            return self._tools[PreprocessOp(op)]
        except KeyError:
            raise ValueError(f"nicio unealta inregistrata pentru {op!r}") from None

    @property
    def ops(self) -> frozenset[PreprocessOp]:
        return frozenset(self._tools)


def default_pipeline() -> PreprocessPipeline:
    """Registrul cu toate uneltele implementate pana acum."""
    return PreprocessPipeline([
        RotateTool(), FlipTool(), CropTool(), InvertTool(), ResolutionTool(),
        BrightnessContrastTool(), LevelsTool(), EraseTool(), ToBwTool(),
        DeskewTool(), RemoveColorMarksTool(), WhitenBackgroundTool(), DenoiseTool(),
    ])
