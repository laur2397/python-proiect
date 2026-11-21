"""Motorul de recunoastere: interfata OcrEngine si implementarea Tesseract.

Implementeaza din SPEC_05 sectiunea 7 `RecognitionResult`, `OcrEngine` si
`TesseractEngine`, pasul 4.1 din docs/plan/faza_4_pasi.md. Orchestrarea
(paginile, paralelizarea, recunoasterea automata) vine in 4.3, in service.py.

Tesseract e un program separat (Apache-2.0), apelat prin pytesseract. Unde il
gasim, in ordine: variabila DOCULENS_TESSERACT; `tesseract` din PATH (Windows:
installer-ul UB Mannheim, SETUP.md 1.4; la impachetare, cel livrat cu
produsul, faza 16); copia de dezvoltare din .tools/ (conda-forge, pe Mac).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import pytesseract
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.core.errors import (
    LanguageModelMissingError,
    NoLanguageSelectedError,
    OperationCancelledError,
    RecognitionFailedError,
)
from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    CancelToken,
    LanguageCode,
    LineData,
    OcrQuality,
    PageData,
    PageWarning,
    PrintType,
    Rect,
    TableData,
    WordData,
)
from app.core.settings import OcrSettings

_DEV_TESSERACT = Path(__file__).resolve().parents[3] / ".tools" / "ocr" / "bin" / "tesseract"

# P-008: forma corecta a diacriticelor romanesti e cu virgula dedesubt
_CEDILLA_TO_COMMA = str.maketrans({"ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț"})


def normalize_romanian(text: str, *, keep_cedilla: bool = False) -> str:
    """ş ţ (sedila) -> ș ț (virgula), daca nu se cere pastrarea sedilei.
    Tesseract le amesteca: pe aceeasi pagina, aceeasi litera iese cand asa,
    cand asa (docs/plan/faza_4_pasi.md, decizia 4)."""
    return text if keep_cedilla else text.translate(_CEDILLA_TO_COMMA)


def find_tesseract() -> Path | None:
    """Programul tesseract, sau None daca nu e instalat."""
    env = os.environ.get("DOCULENS_TESSERACT")
    if env and Path(env).is_file():
        return Path(env)
    found = shutil.which("tesseract")
    if found:
        return Path(found)
    return _DEV_TESSERACT if _DEV_TESSERACT.is_file() else None


@lru_cache(maxsize=4)
def _languages(cmd: str) -> tuple[str, ...]:
    out = subprocess.run([cmd, "--list-langs"], capture_output=True, text=True, timeout=30,
                         check=False)
    lines = (out.stdout or out.stderr).splitlines()
    return tuple(sorted(x.strip() for x in lines[1:] if x.strip()))


# SPEC_05 sect. 7
@dataclass(slots=True)
class RecognitionResult:
    page_number: int
    blocks: list[BlockData] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    barcodes: list[tuple[AreaData, str, str]] = field(default_factory=list)
    """(zona, tip de cod, valoare) - M-057, pasul 4.5."""
    avg_confidence: float = 0.0
    uncertain_count: int = 0
    duration_ms: int = 0
    warnings: list[PageWarning] = field(default_factory=list)
    area_blocks: dict[int | None, list[BlockData]] = field(default_factory=dict)
    """Adaugare fata de SPEC_05: blocurile pe zona (id; None = pagina intreaga,
    fara zone), pentru salvare."""
    cell_blocks: dict[int, list[BlockData]] = field(default_factory=dict)
    """Adaugare fata de SPEC_05: blocurile pe celula de tabel (id-ul celulei),
    pentru salvare (M-003, pasul 4.5.2)."""


# SPEC_05 sect. 7
@runtime_checkable
class OcrEngine(Protocol):
    """Interfata catre motorul de recunoastere; nucleul nu depinde de niciunul."""

    name: str

    def available_languages(self) -> list[LanguageCode]: ...
    def supports_language(self, code: LanguageCode) -> bool: ...
    def recognize_area(self, page: PageData, area: AreaData, settings: OcrSettings,
                       cancel: CancelToken | None = None) -> RecognitionResult: ...
    def recognize_page(self, page: PageData, settings: OcrSettings,
                       cancel: CancelToken | None = None) -> RecognitionResult: ...
    def read_barcode(self, page: PageData, area: AreaData) -> tuple[str, str] | None: ...


PAD = 10
"""Margine alba (pixeli) adaugata in jurul zonei trimise la Tesseract."""
SMALL_AREA = 0.05
"""O zona sub 5% din inaltimea paginii e un rand (un numar de pagina, o
celula): daca modul pagina nu gaseste nimic, se reincearca un singur rand."""

_TEXT_AREAS = (AreaType.TEXT, AreaType.RECOGNITION)
"""Zonele recunoscute ca text. Tabelele (pe celule) le recunoaste serviciul
(4.5.2), codurile de bare vin in 4.5.4; imaginile nu se recunosc (M-004)."""


# N-005, N-013..N-017, N-024, P-008, Y-004
class TesseractEngine:
    name = "tesseract"

    def __init__(self, cmd: Path | None = None, *, keep_cedilla: bool = False) -> None:
        found = cmd or find_tesseract()
        if found is None:
            raise LanguageModelMissingError(
                "Tesseract nu e instalat", language_code="*", expected_path="tesseract")
        self.cmd = Path(found)
        self.keep_cedilla = keep_cedilla

    def available_languages(self) -> list[LanguageCode]:
        return list(_languages(str(self.cmd)))

    def supports_language(self, code: LanguageCode) -> bool:
        return code in _languages(str(self.cmd))

    def _check_languages(self, codes: tuple[LanguageCode, ...]) -> None:
        if not codes:
            raise NoLanguageSelectedError("nicio limba selectata")
        for code in codes:
            if not self.supports_language(code):
                raise LanguageModelMissingError(
                    "modelul limbii nu e instalat", language_code=code,
                    expected_path=f"tessdata/{code}.traineddata")

    # N-005
    def recognize_area(self, page: PageData, area: AreaData, settings: OcrSettings,
                       cancel: CancelToken | None = None) -> RecognitionResult:
        start = time.perf_counter()
        langs = tuple(area.language_codes or settings.languages)
        self._check_languages(langs)
        if cancel is not None and cancel():
            raise OperationCancelledError(page=page.page_number)
        with Image.open(page.image_path) as src:
            image = _area_image(ImageOps.exif_transpose(src), area)
        image = _prepare(image, area.print_type if area.print_type is not PrintType.AUTO
                         else settings.print_type, area.is_inverted)
        pytesseract.pytesseract.tesseract_cmd = str(self.cmd)  # programul gasit, nu PATH
        # Tesseract cere o margine alba in jurul textului: pe un decupaj strans
        # (un numar de pagina, o celula) nu gaseste nimic
        image = ImageOps.expand(image, border=PAD, fill=255 if image.mode == "L" else
                                (255,) * len(image.getbands()))
        origin = Rect(area.bbox.x - PAD, area.bbox.y - PAD, area.bbox.w, area.bbox.h)
        config = _config(settings)
        blocks = self._run(image, langs, config, origin, settings, page.page_number)
        if not blocks and area.bbox.h < SMALL_AREA * page.height_px:
            # o zona mica, goala in modul pagina: un singur rand (psm 7)
            blocks = self._run(image, langs, config.replace("--psm 3", "--psm 7"), origin,
                               settings, page.page_number)
        # id None = pagina intreaga, fara zone; store.py ii creeaza zona
        result = RecognitionResult(page.page_number, blocks=blocks, area_blocks={area.id: blocks})
        _summarize(result, start)
        return result

    # N-003, N-004
    def recognize_page(self, page: PageData, settings: OcrSettings,
                       cancel: CancelToken | None = None) -> RecognitionResult:
        """Recunoaste zonele de text ale paginii, in ordinea lor.

        O pagina fara zone se recunoaste intreaga, ca o singura zona. Tabelele
        (pe celule) le recunoaste RecognitionService, cu `recognize_area` pe
        fiecare celula, ca sa functioneze cu orice motor.
        INCOMPLET, marcat: codurile de bare vin in pasul 4.5.4."""
        start = time.perf_counter()
        areas = [a for a in page.areas if a.area_type in _TEXT_AREAS]
        if not page.areas:
            whole = Rect(0, 0, page.width_px, page.height_px)
            areas = [AreaData(None, AreaType.TEXT, [], 0, bbox=whole)]
        result = RecognitionResult(page.page_number)
        for area in areas:
            if cancel is not None and cancel():
                raise OperationCancelledError(page=page.page_number)
            part = self.recognize_area(page, area, settings, cancel)
            result.blocks += part.blocks
            result.area_blocks.update(part.area_blocks)
        _summarize(result, start)
        return result

    def read_barcode(self, page: PageData, area: AreaData) -> tuple[str, str] | None:
        """M-057: pasul 4.5 (zxing-cpp)."""
        raise NotImplementedError("citirea codurilor de bare vine in pasul 4.5")

    def _run(self, image: Image.Image, langs: tuple[LanguageCode, ...], config: str,
             origin: Rect, settings: OcrSettings, page_number: int) -> list[BlockData]:
        try:
            data = pytesseract.image_to_data(image, lang="+".join(langs), config=config,
                                             output_type=pytesseract.Output.DICT)
        except (pytesseract.TesseractError, OSError, RuntimeError) as exc:
            raise RecognitionFailedError("Tesseract a esuat", page_number=page_number,
                                         detail=str(exc)) from exc
        return self._blocks(data, origin, settings.confidence_threshold, langs[0])

    def _blocks(self, data: dict[str, list[Any]], origin: Rect, threshold: float,
                language: LanguageCode) -> list[BlockData]:
        blocks: dict[tuple[int, int], BlockData] = {}
        lines: dict[tuple[int, int, int], LineData] = {}
        for i, raw in enumerate(data["text"]):
            text = normalize_romanian(str(raw).strip(), keep_cedilla=self.keep_cedilla)
            conf = float(data["conf"][i])
            if not text or conf < 0:
                continue
            bkey = (data["block_num"][i], data["par_num"][i])
            lkey = (*bkey, data["line_num"][i])
            box = Rect(origin.x + data["left"][i], origin.y + data["top"][i],
                       data["width"][i], data["height"][i])
            block = blocks.setdefault(bkey, BlockData(None))
            if lkey not in lines:
                lines[lkey] = LineData(None)
                block.lines.append(lines[lkey])
            conf = max(0.0, min(100.0, conf))
            lines[lkey].words.append(WordData(
                None, text, conf, bbox=box, is_uncertain=conf < threshold,
                language_code=language))
        for block in blocks.values():
            for line in block.lines:
                line.bbox = _union(w.bbox for w in line.words)
                line.ends_with_hyphen = line.words[-1].text.endswith("-")
            block.bbox = _union(line.bbox for line in block.lines)
        return list(blocks.values())


def _config(settings: OcrSettings) -> str:
    """N-013, N-014: `thorough` analizeaza blocurile (psm 3), `fast` trateaza
    zona ca un singur bloc (psm 6). Ambele cu motorul LSTM (oem 1).
    INCOMPLET, marcat: modelele `tessdata_best` pentru `thorough` (decizia de
    impachetare, faza 16)."""
    psm = 3 if settings.quality is OcrQuality.THOROUGH else 6
    return f"--oem 1 --psm {psm} -c preserve_interword_spaces=1"


def _area_image(page_image: Image.Image, area: AreaData) -> Image.Image:
    box = area.bbox
    crop = page_image.crop((box.x, box.y, box.right, box.bottom))
    if area.polygon and area.is_polygon:  # in afara conturului: alb
        mask = Image.new("L", crop.size, 0)
        ImageDraw.Draw(mask).polygon([(x - box.x, y - box.y) for x, y in area.polygon], fill=255)
        white = Image.new(crop.mode, crop.size, 255 if crop.mode == "L" else (255,) * len(
            crop.getbands()))
        crop = Image.composite(crop, white, mask)
    return crop


def _prepare(image: Image.Image, print_type: PrintType, inverted: bool) -> Image.Image:
    """M-027 (inversare) si N-016, N-017 (tipul de document).
    INCOMPLET, marcat: Tesseract nu are moduri Typewriter / Fax; Fax se
    aproximeaza cu un filtru median contra zgomotului (decizia 5)."""
    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB" if "A" in image.getbands() or image.mode == "P" else "L")
    if inverted:
        image = ImageOps.invert(image.convert("L"))
    if print_type is PrintType.FAX:
        image = image.filter(ImageFilter.MedianFilter(3))
    return image


def _union(rects: Any) -> Rect:
    rects = list(rects)
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    return Rect(x0, y0, max(r.right for r in rects) - x0, max(r.bottom for r in rects) - y0)


def _summarize(result: RecognitionResult, start: float) -> None:
    words = [w for b in result.blocks for line in b.lines for w in line.words]
    result.avg_confidence = round(sum(w.confidence for w in words) / len(words), 2) if words else 0.0
    result.uncertain_count = sum(w.is_uncertain for w in words)
    result.duration_ms = int((time.perf_counter() - start) * 1000)
