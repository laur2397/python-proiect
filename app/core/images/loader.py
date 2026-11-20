"""Incarcarea imaginilor pentru OCR Editor.

Implementeaza `LoadedImage` si `ImageLoader` din SPEC_05 sectiunea 5.
Formatele vin din SPEC_09 anexa B.1, coloana „Intrare OCR Editor” (Y-100,
Y-101): numai acelea, si numai cu extensiile listate acolo.

Pasul 1a: imaginile raster, prin Pillow. Pasul 1b: PDF, prin PDFium
(app/core/pdf/document.py), randat la OCR_DPI. XPS, DjVu si JBIG2 sunt amanate (docs/plan/faza_1_pasi.md, decizia 4): dau
`UnsupportedFormatError` cu `reason="not_implemented"`, ca sa nu para ca
fisierul e stricat.
"""

from __future__ import annotations

import io
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageOps, ImageStat, UnidentifiedImageError

from app.core.errors import (
    FileCorruptError,
    OperationCancelledError,
    UnsupportedFormatError,
)
from app.core.model import (
    CancelToken,
    ColorMode,
    PasswordCallback,
    Progress,
    ProgressCallback,
    Px,
)
from app.core.pdf.document import PDFIUM_LOCK, open_pdfium, pixel_size, render_pdf_page

# SPEC_09 B.1, coloana „Intrare OCR Editor”, randurile de imagini raster.
RASTER_EXTENSIONS: dict[str, frozenset[str]] = {
    ".jpg": frozenset({"JPEG", "MPO"}),
    ".jpeg": frozenset({"JPEG", "MPO"}),
    ".jp2": frozenset({"JPEG2000"}),
    ".j2k": frozenset({"JPEG2000"}),
    ".jpf": frozenset({"JPEG2000"}),
    ".jpx": frozenset({"JPEG2000"}),
    ".jpc": frozenset({"JPEG2000"}),
    ".png": frozenset({"PNG"}),
    ".tif": frozenset({"TIFF"}),
    ".tiff": frozenset({"TIFF"}),
    ".bmp": frozenset({"BMP", "DIB"}),
    ".dib": frozenset({"BMP", "DIB"}),
    ".rle": frozenset({"BMP", "DIB"}),
    ".gif": frozenset({"GIF"}),
    ".pcx": frozenset({"PCX"}),
    ".dcx": frozenset({"DCX"}),
}
"""Extensia -> formatele Pillow acceptate pentru ea. Formatul se verifica dupa
continut, nu doar dupa extensie: un `.png` care e de fapt JPEG se accepta,
unul care e de fapt alt format nu."""

_ANY_RASTER = frozenset().union(*RASTER_EXTENSIONS.values())

PDF_EXTENSIONS: frozenset[str] = frozenset({".pdf"})

PLANNED_EXTENSIONS: frozenset[str] = frozenset({".xps", ".djvu", ".djv", ".jbig2", ".jb2"})
"""In SPEC_09 B.1 pentru OCR Editor, dar inca neimplementate: amanate
(licente GPL/AGPL sau lipsa unei biblioteci; CLAUDE.md §5)."""

OCR_DPI = 300
"""[DECIZIE] Rezolutia la care se randeaza paginile PDF pentru recunoastere:
tinta din N-100."""

_COLOR_PROBE_DPI = 36
"""Rezolutie mica, doar pentru a afla modul de culoare si a valida pagina."""

MAX_PDF_VERSION = 20
"""Y-108: PDF 2.0 sau mai vechi."""

DEFAULT_DPI = 300
"""[DECIZIE] Rezolutia presupusa cand fisierul nu declara una. 300 dpi e tinta
din N-100; schema cere dpi > 0 (SPEC_04 page.dpi_x)."""

MAX_PIXELS = 600_000_000
"""[DECIZIE] Pillow refuza implicit imaginile peste ~89 milioane de pixeli, ca
protectie. Corpusul de test (SPEC_06) are o pagina A0 la 600 dpi, adica ~560
de milioane. Peste MAX_PIXELS fisierul e refuzat ca stricat sau periculos.
Se seteaza o data, la importul modulului: comutarea la fiecare apel nu ar fi
sigura cand se incarca din mai multe fire."""

if (Image.MAX_IMAGE_PIXELS or 0) < MAX_PIXELS:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS

_GRAY_TOLERANCE = 6
"""O imagine RGB ale carei canale difera cu cel mult atat e de fapt gri (N-104)."""


# SPEC_05 sect. 5. L-018 (is_photo)
@dataclass(slots=True)
class LoadedImage:
    """O imagine incarcata, cu metadatele necesare OCR-ului."""

    path: Path
    width_px: Px
    height_px: Px
    dpi_x: int
    dpi_y: int
    color_mode: ColorMode
    source_page: int | None = None
    """Numarul paginii in fisier, de la 1."""
    is_photo: bool = False
    """L-018: decide daca se aplica uneltele marcate photo_only."""


# K-001, A-012, J-050 (partea de incarcare); Y-100, Y-101
class ImageLoader:
    """Formatele acceptate: SPEC_09 B.1, coloana „Intrare OCR Editor”."""

    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(RASTER_EXTENSIONS) | PDF_EXTENSIONS
    """Ce se poate incarca acum. Y-112: lista declarata explicit."""

    def __init__(self) -> None:
        self._pdf_passwords: dict[Path, str] = {}
        """Parolele PDF date la `load`, ca `open_pixels` sa poata randa pagina
        mai tarziu. Doar in memorie; nu se scriu niciodata pe disc."""

    def can_load(self, path: Path) -> bool:
        """Dupa extensie. Continutul se verifica la `load`."""
        return Path(path).suffix.lower() in self.SUPPORTED_EXTENSIONS

    # K-001, J-050: o imagine per pagina; A-012: format nesuportat -> eroare
    def load(
        self,
        path: Path,
        *,
        password: PasswordCallback | None = None,
        pages: Sequence[int] | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[LoadedImage]:
        """Un fisier multipagina intoarce o imagine per pagina.

        `pages` sunt numere de pagina de la 1; None = toate. Fiecare pagina se
        decodeaza o data, ca un fisier trunchiat sa fie prins aici, nu la OCR.
        `password` se foloseste doar pentru PDF (J-052, A-011): se cere numai
        daca documentul e protejat. Paginile PDF se descriu la OCR_DPI.

        Erori: `UnsupportedFormatError`, `FileCorruptError`,
        `OperationCancelledError`, `ValueError` (pagini in afara fisierului).
        """
        path = Path(path)
        if path.suffix.lower() in PDF_EXTENSIONS:
            return self._load_pdf(path, password, pages, progress, cancel)
        with _open(path) as img:
            total = _frame_count(img)
            wanted = _validate_pages(pages, total)
            result: list[LoadedImage] = []
            for i, number in enumerate(wanted):
                if cancel is not None and cancel():
                    raise OperationCancelledError(path=str(path), done=i, total=len(wanted))
                if progress is not None:
                    progress(Progress(i, len(wanted), "stage.loading_images", path.name))
                frame = _seek(img, path, number)
                try:
                    frame.load()
                except (OSError, ValueError, SyntaxError) as exc:
                    raise FileCorruptError(
                        "pagina nu se poate decoda", path=str(path), page=number, detail=str(exc)
                    ) from exc
                result.append(_describe(path, frame, number))
            if progress is not None:
                progress(Progress(len(wanted), len(wanted), "stage.loading_images", path.name))
            return result

    def read_page_count(self, path: Path) -> int:
        """Numarul de pagini, fara sa decodeze imaginile."""
        path = Path(path)
        if path.suffix.lower() in PDF_EXTENSIONS:
            doc, _ = self._open_pdf(path, None)
            with PDFIUM_LOCK:
                try:
                    return len(doc)
                finally:
                    doc.close()
        with _open(path) as img:
            return _frame_count(img)

    # Miniaturi (B-022 in SPEC_05) si documentele recente
    def render_thumbnail(self, path: Path, page: int, max_size: Px) -> bytes:
        """PNG cu latura cea mai mare de cel mult `max_size` pixeli.

        Orientarea din EXIF se aplica, ca fotografia sa apara cum a fost facuta.
        """
        if max_size < 1:
            raise ValueError(f"max_size trebuie sa fie pozitiv: {max_size}")
        path = Path(path)
        if path.suffix.lower() in PDF_EXTENSIONS:
            return self._pdf_thumbnail(path, page, max_size)
        with _open(path) as img:
            _validate_pages([page], _frame_count(img))
            frame = _seek(img, path, page)
            try:
                thumb = ImageOps.exif_transpose(frame.copy())
                thumb.thumbnail((max_size, max_size))
                if thumb.mode not in ("1", "L", "RGB", "RGBA"):
                    thumb = thumb.convert("RGBA" if "A" in thumb.getbands() else "RGB")
                out = io.BytesIO()
                thumb.save(out, format="PNG")
            except (OSError, ValueError, SyntaxError) as exc:
                raise FileCorruptError(
                    "miniatura nu se poate face", path=str(path), page=page, detail=str(exc)
                ) from exc
            return out.getvalue()

    # Adaugare fata de SPEC_05: contractul nu spune cum ajung pixelii la
    # proiect (pasul 1c) si la preprocesare (faza 2). Marcat in raportul 1a.
    def open_pixels(self, image: LoadedImage) -> Image.Image:
        """Pixelii unei pagini incarcate, ca imagine Pillow independenta de fisier.
        Paginile PDF se randeaza la rezolutia din `image` (OCR_DPI la `load`)."""
        if image.path.suffix.lower() in PDF_EXTENSIONS:
            doc, _ = self._open_pdf(image.path, None)
            try:
                return render_pdf_page(doc, image.path, image.source_page or 1, image.dpi_x)
            finally:
                with PDFIUM_LOCK:
                    doc.close()
        with _open(image.path) as img:
            frame = _seek(img, image.path, image.source_page or 1)
            try:
                return frame.copy()
            except (OSError, ValueError, SyntaxError) as exc:
                raise FileCorruptError(
                    "pagina nu se poate decoda", path=str(image.path),
                    page=image.source_page, detail=str(exc),
                ) from exc


    # --- PDF (pasul 1b) -------------------------------------------------------

    def _open_pdf(
        self, path: Path, password: PasswordCallback | None
    ) -> tuple[pdfium.PdfDocument, str | None]:
        """Deschide PDF-ul; foloseste parola memorata, daca a mai fost data."""
        known = self._pdf_passwords.get(path.resolve())
        callback = password
        if known is not None:
            given = iter([known])

            def callback(_p: str) -> str | None:
                return next(given, None)

        doc, used = open_pdfium(path, callback)
        if used is not None:
            self._pdf_passwords[path.resolve()] = used
        with PDFIUM_LOCK:
            version = doc.get_version()
        if version is not None and version > MAX_PDF_VERSION:
            with PDFIUM_LOCK:
                doc.close()
            raise UnsupportedFormatError(
                "versiune PDF prea noua", path=str(path), extension=".pdf",
                version=f"{version // 10}.{version % 10}", reason="pdf_version",
            )
        return doc, used

    def _load_pdf(
        self,
        path: Path,
        password: PasswordCallback | None,
        pages: Sequence[int] | None,
        progress: ProgressCallback | None,
        cancel: CancelToken | None,
    ) -> list[LoadedImage]:
        doc, _ = self._open_pdf(path, password)
        try:
            with PDFIUM_LOCK:
                total = len(doc)
            wanted = _validate_pages(pages, total)
            result: list[LoadedImage] = []
            for i, number in enumerate(wanted):
                if cancel is not None and cancel():
                    raise OperationCancelledError(path=str(path), done=i, total=len(wanted))
                if progress is not None:
                    progress(Progress(i, len(wanted), "stage.loading_images", path.name))
                with PDFIUM_LOCK:
                    w_pt, h_pt = doc.get_page_size(number - 1)
                probe = render_pdf_page(doc, path, number, _COLOR_PROBE_DPI)
                width_px, height_px = pixel_size(w_pt, h_pt, OCR_DPI)
                result.append(
                    LoadedImage(
                        path=path,
                        width_px=width_px,
                        height_px=height_px,
                        dpi_x=OCR_DPI,
                        dpi_y=OCR_DPI,
                        color_mode=_color_mode(probe),
                        source_page=number,
                        is_photo=False,
                    )
                )
            if progress is not None:
                progress(Progress(len(wanted), len(wanted), "stage.loading_images", path.name))
            return result
        finally:
            with PDFIUM_LOCK:
                doc.close()

    def _pdf_thumbnail(self, path: Path, page: int, max_size: Px) -> bytes:
        doc, _ = self._open_pdf(path, None)
        try:
            with PDFIUM_LOCK:
                total = len(doc)
            _validate_pages([page], total)
            with PDFIUM_LOCK:
                w_pt, h_pt = doc.get_page_size(page - 1)
            dpi = max_size * 72 / max(w_pt, h_pt, 1)
            thumb = render_pdf_page(doc, path, page, dpi)
            thumb.thumbnail((max_size, max_size))
            out = io.BytesIO()
            thumb.save(out, format="PNG")
            return out.getvalue()
        finally:
            with PDFIUM_LOCK:
                doc.close()


# =============================================================================
# Detalii
# =============================================================================


@contextmanager
def _open(path: Path) -> Iterator[Image.Image]:
    ext = path.suffix.lower()
    if ext in PLANNED_EXTENSIONS:
        raise UnsupportedFormatError(
            "format inca neimplementat", path=str(path), extension=ext, reason="not_implemented"
        )
    if ext not in RASTER_EXTENSIONS:
        raise UnsupportedFormatError(
            "format nesuportat", path=str(path), extension=ext, reason="unsupported"
        )
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        img = Image.open(path)
    except UnidentifiedImageError as exc:
        raise FileCorruptError(
            "fisierul nu e o imagine citibila", path=str(path), detail=str(exc)
        ) from exc
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise FileCorruptError(
            "fisierul nu se poate deschide", path=str(path), detail=str(exc)
        ) from exc
    with img:
        # Continutul poate fi alt format raster decat spune extensia (de exemplu
        # un JPEG salvat ca .png): se accepta. Un format din afara listei, nu.
        if img.format not in _ANY_RASTER:
            raise UnsupportedFormatError(
                "continutul nu e intr-un format acceptat", path=str(path),
                extension=ext, detected=img.format, reason="unsupported",
            )
        yield img


def _frame_count(img: Image.Image) -> int:
    return max(1, int(getattr(img, "n_frames", 1)))


def _validate_pages(pages: Sequence[int] | None, total: int) -> list[int]:
    if pages is None:
        return list(range(1, total + 1))
    wanted = list(pages)
    bad = [p for p in wanted if not isinstance(p, int) or not 1 <= p <= total]
    if bad:
        raise ValueError(f"pagini in afara fisierului (1..{total}): {bad}")
    return wanted


def _seek(img: Image.Image, path: Path, number: int) -> Image.Image:
    try:
        img.seek(number - 1)
    except (EOFError, OSError, ValueError) as exc:
        raise FileCorruptError(
            "pagina lipseste din fisier", path=str(path), page=number, detail=str(exc)
        ) from exc
    return img


def _declared_dpi(img: Image.Image) -> tuple[int, int] | None:
    dpi = img.info.get("dpi")
    if not dpi:
        return None
    try:
        x, y = (round(float(v)) for v in dpi[:2])
    except (TypeError, ValueError):
        return None
    if x <= 1 or y <= 1:  # JFIF fara unitati (raport de aspect), nu rezolutie
        return None
    return x, y


def _color_mode(img: Image.Image) -> ColorMode:
    if img.mode == "1":
        return ColorMode.BW
    if img.mode in ("L", "LA", "I", "I;16", "I;16B", "I;16L", "F"):
        return ColorMode.GRAY
    # N-104: multe scanari gri sunt salvate ca RGB sau cu paleta.
    sample = img.copy()
    sample.thumbnail((256, 256))
    rgb = sample.convert("RGB")
    r, g, b = rgb.split()
    diff_rg = ImageStat.Stat(ImageChops.difference(r, g)).extrema[0][1]
    diff_gb = ImageStat.Stat(ImageChops.difference(g, b)).extrema[0][1]
    if max(diff_rg, diff_gb) <= _GRAY_TOLERANCE:
        return ColorMode.GRAY
    return ColorMode.COLOR


# L-018, partea din metadate. INCOMPLET, marcat: SPEC_05 cere si estimarea din
# zgomot si din neuniformitatea fundalului; aceea vine cu preprocesarea (faza 2).
def _looks_like_photo(img: Image.Image, dpi: tuple[int, int] | None) -> bool:
    exif = img.getexif()
    has_camera = bool(exif.get(0x010F) or exif.get(0x0110))  # Make, Model
    return has_camera or (dpi is None and img.format in ("JPEG", "MPO"))


def _describe(path: Path, frame: Image.Image, number: int) -> LoadedImage:
    dpi = _declared_dpi(frame)
    dpi_x, dpi_y = dpi if dpi else (DEFAULT_DPI, DEFAULT_DPI)
    width, height = frame.size
    # Orientarea din EXIF (fotografii de pe telefon): dimensiunile afisate.
    orientation = frame.getexif().get(0x0112)
    if orientation in (5, 6, 7, 8):
        width, height = height, width
    return LoadedImage(
        path=path,
        width_px=width,
        height_px=height,
        dpi_x=dpi_x,
        dpi_y=dpi_y,
        color_mode=_color_mode(frame),
        source_page=number,
        is_photo=_looks_like_photo(frame, dpi),
    )


__all__ = [
    "DEFAULT_DPI",
    "OCR_DPI",
    "PDF_EXTENSIONS",
    "PLANNED_EXTENSIONS",
    "RASTER_EXTENSIONS",
    "ImageLoader",
    "LoadedImage",
]
