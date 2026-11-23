"""Screenshot Reader (faza 15, pasul 15.1): V-002…V-026, SPEC_05 §14.

Nucleul nu face capturi: le face sistemul de ferestre, printr-un `ScreenGrabber`
dat de interfata (faza_15_pasi.md, decizia 2). Aici sunt regulile: zona minima
10×10, intarzierea fixa de 5 secunde (V-006, decizia 3), ultima zona (V-026),
recunoasterea textului si a tabelului, si scrierea rezultatelor (V-010…V-019).

Capturile se scriu ca PNG in folderul de temporare, marite de 3 ori (un ecran are
~96 dpi, iar recunoasterea lucreaza bine la ~300 dpi). Zona e in coordonatele
desktopului virtual, deci poate traversa mai multe monitoare (V-025).
"""

from __future__ import annotations

import csv
import io
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from app.core.images.loader import LoadedImage
from app.core.model import AreaType, ColorMode, ExportFormat, LanguageCode, Rect

MIN_SIZE = 10
"""SPEC_05: zona capturata are minimum 10×10 pixeli."""

TIMED_DELAY_S = 5
"""V-006: intarziere fixa, nu configurabila."""

UPSCALE = 3
"""Captura de ecran se mareste inainte de OCR (~96 dpi → ~300 dpi)."""

CAPTURE_MODES = ("area", "window", "screen", "timed")
"""V-003…V-006: combo-ul `Capture`."""

SEND_TARGETS = ("text_clipboard", "table_clipboard", "image_clipboard", "text_word",
                "table_excel", "text_file", "table_file", "image_file", "image_ocr_editor",
                "image_email")
"""V-010…V-019: combo-ul `Send`, in ordinea din cerinte."""

TEXT_FILE_FORMATS = (ExportFormat.TXT, ExportFormat.DOCX, ExportFormat.RTF, ExportFormat.ODT,
                     ExportFormat.HTML, ExportFormat.PDF)
"""V-015: `Text to File`."""

TABLE_FILE_FORMATS = (ExportFormat.XLSX, ExportFormat.CSV)
"""V-016: `Table to File`."""

IMAGE_FILE_FORMATS = {".png": "PNG", ".bmp": "BMP", ".jpg": "JPEG", ".jpeg": "JPEG",
                      ".tif": "TIFF", ".tiff": "TIFF"}
"""V-017: `Image to File`."""


class ScreenGrabber(Protocol):
    """Capturarea ecranului (o da interfata)."""

    def screens(self) -> list[Rect]:
        """Monitoarele, in coordonatele desktopului virtual (V-025)."""
        ...

    def grab(self, rect: Rect) -> Image.Image:
        """Pixelii zonei; fereastra utilitarului nu apare in captura (SPEC_05)."""
        ...

    def window_rect(self, window_id: int) -> Rect:
        """V-004: cadrul ferestrei alese."""
        ...


def union(rects: Sequence[Rect]) -> Rect:
    x0 = min(r.x for r in rects)
    y0 = min(r.y for r in rects)
    x1 = max(r.x + r.w for r in rects)
    y1 = max(r.y + r.h for r in rects)
    return Rect(x0, y0, x1 - x0, y1 - y0)


# V-002…V-026 (SPEC_05: ScreenshotReader)
class ScreenshotReader:
    """V-002: mereu disponibil (fara inregistrare). Ruleaza independent de aplicatia
    principala (V-001)."""

    def __init__(self, context: Any, grabber: ScreenGrabber, *, engine: Any = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._ctx = context
        self._grabber = grabber
        self._engine = engine
        self._sleep = sleep
        self._last: Rect | None = None
        self._folder = Path(tempfile.mkdtemp(prefix="screenshot-",
                                             dir=context.health.temp_folder()))
        """In folderul temporar al sesiunii: se sterge la inchiderea aplicatiei."""
        self._count = 0

    # --- capturile (V-003…V-006, V-025, V-026) ---

    def capture_area(self, rect: Rect, display: int | None = None) -> LoadedImage:
        """V-003: zona trasa pe ecran; minimum 10×10. Poate traversa monitoare
        (V-025). `display` muta zona pe monitorul ales (coordonate locale)."""
        if rect.w < MIN_SIZE or rect.h < MIN_SIZE:
            raise ValueError(f"zona capturata are minimum {MIN_SIZE}x{MIN_SIZE} pixeli")
        if display is not None:
            screen = self._grabber.screens()[display]
            rect = Rect(screen.x + rect.x, screen.y + rect.y, rect.w, rect.h)
        image = self._grabber.grab(rect)
        self._last = rect
        return self._store(image)

    def capture_window(self, window_id: int) -> LoadedImage:
        """V-004: fereastra aleasa cu clic pe cadrul evidentiat."""
        return self.capture_area(self._grabber.window_rect(window_id))

    def capture_screen(self, display: int | None = None) -> LoadedImage:
        """V-005: tot ecranul (toate monitoarele, sau cel ales)."""
        screens = self._grabber.screens()
        return self.capture_area(screens[display] if display is not None else union(screens))

    def capture_timed(self, delay_s: int = TIMED_DELAY_S,
                      display: int | None = None) -> LoadedImage:
        """V-006: ecranul, dupa intarziere (interfata da intotdeauna 5 secunde)."""
        if not 1 <= delay_s <= 60:
            raise ValueError("intarzierea e intre 1 si 60 de secunde")
        self._sleep(delay_s)
        return self.capture_screen(display)

    def last_region(self) -> Rect | None:
        """V-026: None cand nu exista o captura anterioara (butonul e gri)."""
        return self._last

    def repeat_last(self) -> LoadedImage:
        """V-026 `Repeat last capture`: aceeasi zona."""
        if self._last is None:
            raise ValueError("nu exista o captura anterioara")
        return self.capture_area(self._last)

    def _store(self, image: Image.Image) -> LoadedImage:
        self._count += 1
        path = self._folder / f"captura_{self._count:03d}.png"
        rgb = image.convert("RGB")
        big = rgb.resize((rgb.width * UPSCALE, rgb.height * UPSCALE), Image.Resampling.LANCZOS)
        big.save(path, dpi=(96 * UPSCALE, 96 * UPSCALE))
        return LoadedImage(path, big.width, big.height, 96 * UPSCALE, 96 * UPSCALE,
                           ColorMode.COLOR)

    # --- recunoasterea (V-008…V-011, V-023) ---

    @contextmanager
    def _recognized(self, image: LoadedImage, languages: Sequence[LanguageCode],
                    kind: AreaType, cancel: Callable[[], bool] | None = None
                    ) -> Iterator[Any]:
        """Un proiect temporar cu o singura zona peste toata captura: text (V-023:
        o singura limba recomandata) sau tabel."""
        from app.core.layout.areas import AreaEditor
        from app.core.model import AutoProcessMode
        from app.core.ocr.service import RecognitionService
        from app.core.project import OcrProject

        if not languages:
            raise ValueError("trebuie aleasa o limba")
        project = OcrProject.create(context=self._ctx)
        try:
            project.languages = list(languages)
            project.add_images([Path(image.path)], auto_process=AutoProcessMode.NONE)
            page = project.page(1)
            w, h = page.width_px - 1, page.height_px - 1
            AreaEditor(project).create(page, [(0, 0), (w, 0), (w, h), (0, h)], kind)
            RecognitionService(project, engine=self._engine).recognize_pages(
                cancel=cancel)  # V-008: `Stop` / `Esc`
            yield project
        finally:
            project.close()

    def to_text(self, image: LoadedImage, languages: Sequence[LanguageCode], *,
                cancel: Callable[[], bool] | None = None) -> str:
        """V-010 (si V-013, V-015): textul capturii."""
        with self._recognized(image, languages, AreaType.TEXT, cancel) as project:
            return self._export_text(project, ExportFormat.TXT)

    def to_table(self, image: LoadedImage, languages: Sequence[LanguageCode], *,
                 cancel: Callable[[], bool] | None = None) -> list[list[str]]:
        """V-011 (si V-014, V-016): randurile tabelului."""
        with self._recognized(image, languages, AreaType.TABLE, cancel) as project:
            data = self._export_text(project, ExportFormat.CSV)
        return [row for row in csv.reader(io.StringIO(data)) if any(c.strip() for c in row)]

    def _export_text(self, project: Any, fmt: ExportFormat) -> str:
        from app.core.automation.tasks import export_document

        with tempfile.TemporaryDirectory() as tmp:
            [path] = export_document(project, Path(tmp) / "captura", fmt)
            raw = path.read_bytes()
        for encoding in ("utf-8-sig", "utf-16", "cp1250"):
            try:
                return raw.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace").strip()

    # --- trimiterea in fisiere (V-013…V-017, V-019) ---

    def text_to_file(self, image: LoadedImage, languages: Sequence[LanguageCode],
                     target: Path) -> Path:
        """V-015 (si V-013 cu DOCX): formatul dupa extensie."""
        return self._to_file(image, languages, target, AreaType.TEXT, TEXT_FILE_FORMATS)

    def table_to_file(self, image: LoadedImage, languages: Sequence[LanguageCode],
                      target: Path) -> Path:
        """V-016 (si V-014 cu XLSX)."""
        return self._to_file(image, languages, target, AreaType.TABLE, TABLE_FILE_FORMATS)

    def _to_file(self, image: LoadedImage, languages: Sequence[LanguageCode], target: Path,
                 kind: AreaType, allowed: Sequence[ExportFormat]) -> Path:
        from app.core.automation.tasks import export_document

        target = Path(target)
        fmt = format_for(target)
        if fmt not in allowed:
            raise ValueError(f"formatul {target.suffix} nu e potrivit aici")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._recognized(image, languages, kind) as project, \
                tempfile.TemporaryDirectory() as tmp:
            [written] = export_document(project, Path(tmp) / target.stem, fmt)
            target.write_bytes(written.read_bytes())
        return target

    @staticmethod
    def image_to_file(image: LoadedImage, target: Path) -> Path:
        """V-017: PNG, BMP, JPEG sau TIFF, la marimea de pe ecran."""
        target = Path(target)
        kind = IMAGE_FILE_FORMATS.get(target.suffix.lower())
        if kind is None:
            raise ValueError(f"formatul {target.suffix} nu e un format de imagine")
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(image.path) as src:
            small = src.convert("RGB").resize((max(src.width // UPSCALE, 1),
                                               max(src.height // UPSCALE, 1)),
                                              Image.Resampling.LANCZOS)
            small.save(target, kind)
        return target

    def image_for_email(self, image: LoadedImage) -> Path:
        """V-019: imaginea se ataseaza ca BMP."""
        return self.image_to_file(image, self._folder / f"captura_{self._count:03d}.bmp")

    def temp_path(self, suffix: str) -> Path:
        """Fisierul temporar pentru `Text to Microsoft Word` / `Table to Microsoft
        Excel` (decizia 4)."""
        return self._folder / f"captura_{self._count:03d}{suffix}"


def format_for(path: Path) -> ExportFormat:
    suffix = Path(path).suffix.lower().lstrip(".")
    aliases = {"htm": "html", "xls": "xlsx"}
    try:
        return ExportFormat(aliases.get(suffix, suffix))
    except ValueError:
        raise ValueError(f"extensie necunoscuta: {path}") from None


def rows_to_tsv(rows: Sequence[Sequence[str]]) -> str:
    """V-011: tabelul in clipboard, cu TAB intre celule (se lipeste in Excel)."""
    return "\n".join("\t".join(cell.replace("\t", " ") for cell in row) for row in rows)
