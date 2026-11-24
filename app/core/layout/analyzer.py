"""Analiza automata a paginii: zonele si orientarea.

Implementeaza `LayoutAnalyzer` din SPEC_05 sectiunea 6, pasul 4.2 din
docs/plan/faza_4_pasi.md (N-006, N-007, X-017). Structura documentului
(antete, note, cuprins, liste: N-018..N-021) e in structure.py (4.5.3).

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
LINE_CONTRAST = 50
"""[DECIZIE] O linie de tabel e cu cel putin 50 de niveluri mai inchisa decat
hartia. Pragul Otsu (intre textul negru si hartie) pierdea liniile gri."""
LINE_SPAN = 0.6
"""O linie de tabel acopera cel putin 60% din latimea (inaltimea) tabelului."""
GRAPHIC_HEIGHT = 5
"""[DECIZIE] O componenta de peste 5 ori mai inalta decat literele (o stampila,
un desen) e grafica, nu text..."""
GRAPHIC_WIDTH = 20
"""...la fel una de peste 20 de ori mai lunga (o linie de pix, o semnatura)."""


def _small_gray(page: PageData) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Imaginea micsorata (gri, medie pe bloc), scara, masca de culoare si
    masca liniilor: un bloc e „linie” daca are macar un pixel mult mai inchis
    decat hartia, ca liniile subtiri sau gri sa nu dispara la micsorare."""
    with Image.open(page.image_path) as src:
        img = ImageOps.exif_transpose(src)
        rgb = to_array(img)
    gray = to_gray(rgb)
    h, w = gray.shape
    scale = min(1.0, _SAMPLE / max(h, w))
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    small = np.asarray(Image.fromarray(gray).resize(size, Image.Resampling.BOX))
    paper = int(np.percentile(gray, 90))
    dark = ((gray < paper - LINE_CONTRAST).astype(np.uint8)) * 255
    lines = np.asarray(Image.fromarray(dark).resize(size, Image.Resampling.BOX)) > 0
    color = np.zeros(small.shape, dtype=bool)
    if rgb.ndim == 3:
        sat = (rgb.max(axis=2).astype(int) - rgb.min(axis=2)).astype(np.uint8)
        color = np.asarray(Image.fromarray(sat).resize(size, Image.Resampling.BOX)) > 40
    return small, scale, color, lines


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
def osd_rotation(image: Image.Image) -> int | None:
    """X-017, N-105, N-107: rotatia (0, 90, 180, 270) care indreapta textul, dupa
    modelul `osd` al Tesseract; None fara Tesseract, fara text sau cu incredere
    prea mica (pagina ramane neschimbata)."""
    cmd = find_tesseract()
    if cmd is None:
        return None
    pytesseract.pytesseract.tesseract_cmd = str(cmd)
    img = image.convert("L")
    img.thumbnail((2000, 2000))
    try:
        osd = pytesseract.image_to_osd(img, config="--psm 0",
                                       output_type=pytesseract.Output.DICT)
    except (pytesseract.TesseractError, OSError):
        return None  # prea putin text
    if float(osd.get("orientation_conf", 0)) < ORIENTATION_MIN_CONFIDENCE:
        return None
    return int(osd.get("rotate", 0)) % 360


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
        small, scale, color, dark = _small_gray(page)
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
        for box in self._tables(dark, ink, small):
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
            # stampile, desene, linii de pix: componente mult mai mari decat
            # literele; devin imagini, nu text (testul manual din 21.11.2026)
            labels, _ = ndi.label(text)
            graphic = np.zeros_like(text)
            for i, sl in enumerate(ndi.find_objects(labels), start=1):
                if sl is None:
                    continue
                bh, bw = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
                if bh > GRAPHIC_HEIGHT * ch or bw > GRAPHIC_WIDTH * ch:
                    graphic[sl] |= labels[sl] == i
            if graphic.any():
                # interiorul unei stampile (cercul mic, textul) face parte din ea
                grouped = ndi.binary_fill_holes(ndi.binary_dilation(graphic, iterations=ch))
                for box in _boxes(grouped):
                    add(AreaType.PICTURE, box)
                text = ink & ~taken
            lines = ndi.binary_dilation(text, structure=np.ones((1, ch * 2 + 1), bool))
            # randurile cu spatiere 1,5 (golul de ~2 inaltimi de litera) raman un
            # paragraf; un rand liber intre paragrafe (~3 inaltimi) le desparte
            # (auditul din 24.11.2026: o pagina cu spatiere 1,5 dadea o zona pe rand)
            paras = ndi.binary_dilation(lines, structure=np.ones((2 * ch + 1, 1), bool))
            for box in _boxes(paras & ~taken):
                x0, y0, x1, y1 = box
                part = text[y0:y1, x0:x1]
                rows = np.nonzero(part.any(axis=1))[0]
                tall = rows.size and rows[-1] - rows[0] + 1 >= 0.7 * ch
                # nu praf: destula cerneala, sau macar un caracter intreg (un
                # numar de pagina „1” are putina cerneala, dar inaltimea unei litere)
                if part.sum() >= 3 * ch or tall:
                    add(AreaType.TEXT, box)
        return _merge_overlapping_text(areas)

    @staticmethod
    def _tables(dark: np.ndarray, ink: np.ndarray,
                small: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Grilele de linii lungi. O scanare usor inclinata (sub cateva grade)
        se indreapta intai: o linie inclinata devine o „scara” pe care nicio
        linie orizontala nu o mai acopera (testul manual din 21.11.2026)."""
        h, w = dark.shape
        angle = detect_skew(small)
        if abs(angle) >= 0.1:
            dark = ndi.rotate(dark, -angle, reshape=False, order=0)
            ink = ndi.rotate(ink, -angle, reshape=False, order=0)
        hl = ndi.binary_opening(ndi.binary_dilation(dark, np.ones((3, 1), bool)),
                                structure=np.ones((1, max(3, w // 8)), bool))
        vl = ndi.binary_opening(ndi.binary_dilation(dark, np.ones((1, 3), bool)),
                                structure=np.ones((max(3, h // 12), 1), bool))
        grid = ndi.binary_dilation(hl | vl, iterations=2)
        out = []
        for x0, y0, x1, y1 in _boxes(grid):
            if ink[y0:y1, x0:x1].mean() > TABLE_MAX_FILL:
                continue  # plin: o fotografie, nu un tabel
            rows = [b for b in _boxes(hl[y0:y1, x0:x1]) if b[2] - b[0] >= LINE_SPAN * (x1 - x0)]
            cols = [b for b in _boxes(vl[y0:y1, x0:x1]) if b[3] - b[1] >= LINE_SPAN * (y1 - y0)]
            if len(rows) >= 2 and len(cols) >= 2:
                out.append(_unrotate((x0, y0, x1, y1), angle, w, h)
                           if abs(angle) >= 0.1 else (x0, y0, x1, y1))
        return out

    # X-017 (SPEC_05 il numeste L-020, E-012)
    def detect_orientation(self, page: PageData) -> int:
        """0, 90, 180 sau 270: cu cat trebuie rotita pagina (in sensul acelor de
        ceasornic) ca textul sa stea drept. Pe o pagina fara text (sau fara
        Tesseract) intoarce rotatia actuala a paginii, nu ghiceste."""
        with Image.open(page.image_path) as src:
            img = ImageOps.exif_transpose(src).convert("L")
        turn = osd_rotation(img)
        return page.rotation if turn is None else turn

    # N-018..N-021 (SPEC_05 le numeste N-016..N-019)
    def detect_structural_elements(self, pages: Sequence[PageData],
                                   settings: OcrSettings) -> None:
        """Antete si subsoluri, note de subsol, cuprins, liste, pe tot
        documentul (structure.py). Marcheaza blocurile si zonele."""
        from app.core.layout import structure

        structure.detect(pages, headers=settings.detect_headers_footers,
                         footnotes=settings.detect_footnotes,
                         toc=settings.detect_table_of_contents,
                         lists=settings.detect_numbered_lists,
                         repeat_ratio=settings.header_repeat_ratio)

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


def _unrotate(box: tuple[int, int, int, int], angle: float, w: int,
              h: int) -> tuple[int, int, int, int]:
    """Dreptunghiul care cuprinde `box` (gasit pe imaginea indreptata cu
    -angle grade) adus inapoi pe imaginea inclinata."""
    import math

    rad = math.radians(angle)
    cx, cy = (w - 1) / 2, (h - 1) / 2
    xs, ys = [], []
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])):
        dx, dy = x - cx, y - cy
        # ndi.rotate(-angle) a rotit imaginea; aici se roteste punctul invers
        xs.append(cx + dx * math.cos(rad) + dy * math.sin(rad))
        ys.append(cy - dx * math.sin(rad) + dy * math.cos(rad))
    return (max(0, math.floor(min(xs))), max(0, math.floor(min(ys))),
            min(w, math.ceil(max(xs))), min(h, math.ceil(max(ys))))


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
