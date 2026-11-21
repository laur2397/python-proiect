"""Citirea codurilor de bare (faza 4, pasul 4.5.4): M-056..M-060.

Autodetectarea (M-057) acopera exact 11 tipuri. Zece le citeste zxing-cpp
(Apache-2.0); Postnet (codul postal american, bare inalte si scurte) nu e in
zxing-cpp si are aici un decodor propriu. Celelalte tipuri citite de zxing-cpp
se aleg manual din proprietatile zonei (M-058).

UCC-128 e Code 128 cu marcajul GS1 (FNC1, identificatorul `]C1`); UPC-A e
raportat de zxing-cpp ca EAN-13 cu un 0 in fata. Amandoua se deosebesc dupa
rezultat.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage as ndi

from app.core.images.preprocess import otsu_threshold
from app.core.model import AreaData, PageData

AUTODETECT = "autodetect"

AUTODETECT_TYPES = ("code39", "code93", "code128", "ean8", "ean13", "postnet", "ucc128",
                    "upce", "pdf417", "upca", "qrcode")
"""M-057: Code 3 of 9, Code 93, Code 128, EAN 8, EAN 13, Postnet, UCC-128,
UPC-E, PDF417, UPC-A, QR code. Numai acestea se autodetecteaza."""

MANUAL_TYPES = ("codabar", "itf", "datamatrix", "aztec", "databar", "maxicode", "microqr",
                "micropdf417")
"""M-058: tipuri care se citesc numai daca sunt alese manual."""

BARCODE_TYPES = (AUTODETECT, *AUTODETECT_TYPES, *MANUAL_TYPES)

_ZXING = {
    "code39": "Code39", "code93": "Code93", "code128": "Code128", "ucc128": "Code128",
    "ean8": "EAN8", "ean13": "EAN13", "upca": "EAN13", "upce": "UPCE", "pdf417": "PDF417",
    "qrcode": "QRCode", "codabar": "Codabar", "itf": "ITF", "datamatrix": "DataMatrix",
    "aztec": "Aztec", "databar": "DataBar", "maxicode": "MaxiCode", "microqr": "MicroQRCode",
    "micropdf417": "MicroPDF417",
}

_PAD = 20
"""Zona linistita (alb) adaugata in jurul codului: cititoarele o cer."""


# N-021 in SPEC_05 (cerinta reala M-057..M-060)
def read(page: PageData, area: AreaData) -> tuple[str, str] | None:
    """(tip, valoare) pentru codul din zona, sau None daca nu se poate citi:
    zona ramane imagine (M-060). Tipul ales in zona limiteaza cautarea;
    `autodetect` incearca numai cele 11 tipuri din M-057."""
    chosen = area.barcode_type or AUTODETECT
    if chosen not in BARCODE_TYPES:
        raise ValueError(f"tip de cod de bare necunoscut: {chosen!r}")
    with Image.open(page.image_path) as src:
        img = ImageOps.exif_transpose(src)
        b = area.bbox
        crop = img.crop((b.x, b.y, b.right, b.bottom)).convert("L")
    crop = ImageOps.expand(crop, border=_PAD, fill=255)
    wanted = AUTODETECT_TYPES if chosen == AUTODETECT else (chosen,)
    found = _zxing(crop, [t for t in wanted if t != "postnet"])
    if found is not None and found[0] in wanted:
        return found
    if "postnet" in wanted:
        value = read_postnet(np.asarray(crop))
        if value is not None:
            return "postnet", value
    return None


def _zxing(image: Image.Image, types: list[str]) -> tuple[str, str] | None:
    if not types:
        return None
    import zxingcpp

    names = sorted({_ZXING[t] for t in types})
    formats = zxingcpp.barcode_formats_from_str(",".join(names))
    for code in zxingcpp.read_barcodes(image, formats=formats):
        if code.valid:
            return _classify(code), code.text
    return None


def _classify(code: Any) -> str:
    """Tipul nostru pentru un rezultat zxing-cpp."""
    fmt = code.format
    name = getattr(fmt, "name", None) or str(fmt).rsplit(".", 1)[-1]
    text = code.text
    if name == "Code128":
        return "ucc128" if code.symbology_identifier == "]C1" else "code128"
    if name == "EAN13":
        return "upca" if len(text) == 13 and text.startswith("0") else "ean13"
    reverse = {v: k for k, v in _ZXING.items() if k not in ("ucc128", "upca")}
    return reverse.get(name, name.lower())


# --- Postnet --------------------------------------------------------------------------

_POSTNET_WEIGHTS = (7, 4, 2, 1, 0)
_POSTNET_LENGTHS = (6, 10, 12)
"""Cifre, cu cifra de control: ZIP (5), ZIP+4 (9), punct de livrare (11)."""


def read_postnet(gray: np.ndarray) -> str | None:
    """Cifrele unui cod Postnet (fara cifra de control), sau None. Codul poate
    fi rotit cu 90, 180 sau 270 de grade."""
    if gray.size == 0 or int(gray.max()) - int(gray.min()) < 40:
        return None
    ink = gray < otsu_threshold(gray)
    for view in (ink, np.rot90(ink)):
        for oriented in (view, view[::-1, ::-1]):
            value = _decode(_bars(oriented))
            if value is not None:
                return value
    return None


def _bars(ink: np.ndarray) -> list[tuple[int, int]]:
    """(sus, jos) pentru fiecare bara verticala, de la stanga la dreapta."""
    labels, _ = ndi.label(ink)
    out = []
    for sl in ndi.find_objects(labels):
        if sl is None:
            continue
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if h >= 2 * w:  # o bara: mult mai inalta decat lata
            out.append((sl[1].start, sl[0].start, sl[0].stop))
    out.sort()
    return [(top, bottom) for _, top, bottom in out]


def _decode(bars: list[tuple[int, int]]) -> str | None:
    if len(bars) < 32:
        return None
    heights = np.array([b - t for t, b in bars], dtype=float)
    bottoms = np.array([b for _, b in bars], dtype=float)
    if np.ptp(bottoms) > 0.25 * heights.max():
        return None  # barele Postnet stau pe aceeasi linie de baza
    if heights.max() < 1.5 * heights.min():
        return None
    tall = heights > (heights.min() + heights.max()) / 2
    if not (tall[0] and tall[-1]):
        return None
    inner = tall[1:-1]
    if len(inner) % 5 or len(inner) // 5 not in _POSTNET_LENGTHS:
        return None
    digits = []
    for i in range(0, len(inner), 5):
        group = inner[i:i + 5]
        if int(group.sum()) != 2:
            return None
        value = sum(w for w, t in zip(_POSTNET_WEIGHTS, group, strict=True) if t)
        digits.append(0 if value == 11 else value)
    if sum(digits) % 10:
        return None  # cifra de control
    return "".join(map(str, digits[:-1]))


def postnet_pattern(digits: str) -> list[bool]:
    """Barele (True = inalta) pentru `digits` plus cifra de control. Folosit
    de teste; exportul (faza 6) il poate folosi la redesenare."""
    values = [int(d) for d in digits]
    values.append((10 - sum(values) % 10) % 10)
    table = {}
    for a in range(5):
        for b in range(a + 1, 5):
            value = _POSTNET_WEIGHTS[a] + _POSTNET_WEIGHTS[b]
            table[0 if value == 11 else value] = [i in (a, b) for i in range(5)]
    return [True, *[bar for v in values for bar in table[v]], True]
