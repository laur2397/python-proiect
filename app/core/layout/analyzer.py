"""Analiza automata a paginii: zonele si orientarea.

Implementeaza `LayoutAnalyzer` din SPEC_05 sectiunea 6, pasul 4.2 din
docs/plan/faza_4_pasi.md (N-006, N-007, X-017). Structura documentului
(antete, note, cuprins, liste: N-018..N-021) vine in pasul 4.5.

Zonele se gasesc cu cod propriu, fara OCR, pe o imagine micsorata:
- imaginile: pete mari si dense (sau colorate);
- tabelele: grile de linii lungi (aceeasi detectie ca in tables.py);
- textul: literele unite in randuri si paragrafe prin „mazgalire”
  (dilatare pe orizontala, apoi pe verticala).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytesseract
from PIL import Image, ImageOps
from scipy import ndimage as ndi

from app.core.images.preprocess import detect_skew, otsu_threshold, to_array, to_gray
from app.core.layout.areas import column_order, rect_polygon
from app.core.layout.geometry import polygons_overlap
from app.core.layout.tables import _line_positions
from app.core.model import AreaData, AreaType, CancelToken, PageData, Rect
from app.core.ocr.engine import find_tesseract
from app.core.settings import OcrSettings

_SAMPLE = 1000
"""Latura mare a imaginii pe care se face analiza."""

PICTURE_MIN_SHARE = 0.01
"""[DECIZIE] O imagine ocupa cel putin 1% din pagina..."""
PICTURE_MIN_FILL = 0.35
"""...si cel putin 35% din dreptunghiul ei e „cerneala” (textul e mult mai rar)."""
TABLE_MAX_FILL = 0.3
"""[DECIZIE] Un tabel e mai ales spatiu gol intre linii: cel mult 30% cerneala.
O fotografie cu dungi inchise are mult mai mult."""
_MARGIN = 6
"""Pixeli (in pagina) adaugati in jurul unei zone gasite."""


def _small_gray(page: PageData) -> tuple[np.ndarray, float, np.ndarray]:
    with Image.open(page.image_path) as src:
        img = ImageOps.exif_transpose(src)
        rgb = to_array(img)
    gray = to_gray(rgb)
    h, w = gray.shape
    scale = min(1.0, _SAMPLE / max(h, w))
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    small = np.asarray(Image.fromarray(gray).resize(size, Image.Resampling.BOX))
    color = np.zeros(small.shape, dtype=bool)
    if rgb.ndim == 3:
        sat = (rgb.max(axis=2).astype(int) - rgb.min(axis=2)).astype(np.uint8)
        color = np.asarray(Image.fromarray(sat).resize(size, Image.Resampling.BOX)) > 40
    return small, scale, color


def _boxes(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    """(x0, y0, x1, y1) ale componentelor conexe, capatul exclusiv."""
    labels, _ = ndi.label(mask)
    out = []
    for sl in ndi.find_objects(labels):
        if sl is not None:
            out.append((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop))
    return out


def _to_page(box: tuple[int, int, int, int], scale: float, page: PageData) -> Rect:
    x0, y0, x1, y1 = (round(v / scale) for v in box)
    x0, y0 = max(0, x0 - _MARGIN), max(0, y0 - _MARGIN)
    x1, y1 = min(page.width_px, x1 + _MARGIN), min(page.height_px, y1 + _MARGIN)
    return Rect(x0, y0, x1 - x0, y1 - y0)


# SPEC_05 sect. 6. N-006, N-007, M-022, X-017
class LayoutAnalyzer:

    def analyze(self, page: PageData, settings: OcrSettings, *,
                template: Sequence[AreaData] | None = None,
                cancel: CancelToken | None = None) -> list[AreaData]:
        """Zonele noi ale paginii, numerotate pe coloane (M-022), fara cele
        care s-ar suprapune peste zonele existente: zonele facute de utilizator
        se pastreaza, iar analiza completeaza doar spatiul liber (SPEC_05).
        `template`: zonele unui sablon (M-032) se folosesc in locul analizei."""
        if template is not None:
            found = [AreaData(None, a.area_type, list(a.polygon), 0, bbox=a.bbox)
                     for a in template]
        else:
            found = self._detect(page)
        kept = [a for a in found if not any(
            polygons_overlap(list(a.polygon), list(e.polygon)) for e in page.areas
            if e.area_type is not AreaType.BACKGROUND_PICTURE)]
        return column_order(kept)

    def _detect(self, page: PageData) -> list[AreaData]:
        small, scale, color = _small_gray(page)
        if int(small.max()) - int(small.min()) < 40:
            return []  # pagina fara continut
        ink = small < otsu_threshold(small)
        h, w = ink.shape
        areas: list[AreaData] = []
        taken = np.zeros_like(ink)

        def add(kind: AreaType, box: tuple[int, int, int, int]) -> None:
            x0, y0, x1, y1 = box
            taken[y0:y1, x0:x1] = True
            rect = _to_page(box, scale, page)
            if rect.w >= 8 and rect.h >= 8:
                areas.append(AreaData(None, kind, rect_polygon(rect), 0, bbox=rect))

        # tabelele: cel putin doua linii orizontale si doua verticale lungi
        for box in self._tables(ink):
            add(AreaType.TABLE, box)
        # imaginile: pete mari, dense sau colorate
        blobs = ndi.binary_closing(ink | color, iterations=2) & ~taken
        for x0, y0, x1, y1 in _boxes(blobs):
            area = (x1 - x0) * (y1 - y0)
            fill = blobs[y0:y1, x0:x1].mean()
            colored = color[y0:y1, x0:x1].mean() > 0.3
            if area >= PICTURE_MIN_SHARE * h * w and (fill >= PICTURE_MIN_FILL or colored):
                add(AreaType.PICTURE, (x0, y0, x1, y1))
        # textul: ce a ramas, unit in randuri, apoi in paragrafe
        text = ink & ~taken
        heights = [b[3] - b[1] for b in _boxes(text) if b[3] - b[1] > 1]
        if heights:
            ch = max(2, int(np.median(heights)))
            lines = ndi.binary_dilation(text, structure=np.ones((1, ch * 2 + 1), bool))
            paras = ndi.binary_dilation(lines, structure=np.ones((ch + 1, 1), bool))
            for box in _boxes(paras & ~taken):
                x0, y0, x1, y1 = box
                if text[y0:y1, x0:x1].sum() >= 3 * ch:  # nu praf
                    add(AreaType.TEXT, box)
        return _merge_overlapping_text(areas)

    @staticmethod
    def _tables(ink: np.ndarray) -> list[tuple[int, int, int, int]]:
        h, w = ink.shape
        hl = ndi.binary_opening(ink, structure=np.ones((1, max(3, w // 8)), bool))
        vl = ndi.binary_opening(ink, structure=np.ones((max(3, h // 12), 1), bool))
        grid = ndi.binary_dilation(hl | vl, iterations=2)
        out = []
        for x0, y0, x1, y1 in _boxes(grid):
            sub = ink[y0:y1, x0:x1]
            if sub.mean() > TABLE_MAX_FILL:
                continue  # plin: o fotografie, nu un tabel
            if (len(_line_positions(sub, 1, x1 - x0)) >= 2
                    and len(_line_positions(sub, 0, y1 - y0)) >= 2):
                out.append((x0, y0, x1, y1))
        return out

    # X-017 (SPEC_05 il numeste L-020, E-012)
    def detect_orientation(self, page: PageData) -> int:
        """0, 90, 180 sau 270: cu cat trebuie rotita pagina (in sensul acelor de
        ceasornic) ca textul sa stea drept. Pe o pagina fara text (sau fara
        Tesseract) intoarce rotatia actuala a paginii, nu ghiceste."""
        cmd = find_tesseract()
        if cmd is None:
            return page.rotation
        pytesseract.pytesseract.tesseract_cmd = str(cmd)
        with Image.open(page.image_path) as src:
            img = ImageOps.exif_transpose(src).convert("L")
        img.thumbnail((2000, 2000))
        try:
            osd = pytesseract.image_to_osd(img, config="--psm 0",
                                           output_type=pytesseract.Output.DICT)
        except (pytesseract.TesseractError, OSError):
            return page.rotation  # prea putin text
        if float(osd.get("orientation_conf", 0)) < ORIENTATION_MIN_CONFIDENCE:
            return page.rotation
        return int(osd.get("rotate", 0)) % 360

    # SPEC_05 il numeste L-002; cerinta reala L-011
    def estimate_skew(self, page: PageData) -> float:
        with Image.open(page.image_path) as src:
            return detect_skew(to_array(ImageOps.exif_transpose(src)))

    # J-056, J-057 (SPEC_05 il numeste E-026)
    def blank_score(self, page: PageData) -> float:
        from app.core.project import (
            _blank_score,  # project importa layout: import tarziu
        )

        return _blank_score(page.image_path)


ORIENTATION_MIN_CONFIDENCE = 1.5
"""[DECIZIE] Sub aceasta incredere a modulului OSD, orientarea nu se schimba."""


def _merge_overlapping_text(areas: list[AreaData]) -> list[AreaData]:
    """Blocurile de text care se suprapun devin unul; restul raman."""
    others = [a for a in areas if a.area_type is not AreaType.TEXT]
    texts = [a.bbox for a in areas if a.area_type is AreaType.TEXT]
    changed = True
    while changed:
        changed = False
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                if texts[i].intersects(texts[j]):
                    a, b = texts[i], texts[j]
                    x0, y0 = min(a.x, b.x), min(a.y, b.y)
                    texts[i] = Rect(x0, y0, max(a.right, b.right) - x0,
                                    max(a.bottom, b.bottom) - y0)
                    del texts[j]
                    changed = True
                    break
            if changed:
                break
    merged = [AreaData(None, AreaType.TEXT, rect_polygon(r), 0, bbox=r) for r in texts]
    # textul nu are voie sa intre peste o imagine sau un tabel
    merged = [t for t in merged if not any(t.bbox.intersects(o.bbox) for o in others)]
    return others + merged
