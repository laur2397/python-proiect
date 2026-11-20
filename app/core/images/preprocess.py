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
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any, ClassVar, Protocol, runtime_checkable

import numpy as np
from PIL import Image, ImageDraw

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


# L-018: text deschis pe fundal inchis
class InvertTool(BaseTool):
    op = PreprocessOp.INVERT
    PARAMS: ClassVar[ParamSpec] = {}

    def _apply(self, image: np.ndarray, p: dict[str, Any]) -> tuple[np.ndarray, Meta]:
        return (255 - image).astype(np.uint8), {}


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
    ])
