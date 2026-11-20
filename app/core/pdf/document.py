"""Documentul PDF: deschidere cu parola si randarea paginilor.

Implementeaza din `PdfDocument` (SPEC_05 sectiunea 10) doar partea de citire,
de care are nevoie faza 1: `open`, `close`, `page_count`, `pdf_version`,
`is_encrypted`, `render_page`, `page_size`. Restul clasei (salvare, text,
adnotari) vine cu PDF Editor, in faza 7, si nu e declarat aici.

Randarea foloseste PDFium prin pypdfium2. PDFium nu e sigur pentru apeluri
din mai multe fire simultan, deci toate apelurile trec prin `PDFIUM_LOCK`.
"""

from __future__ import annotations

import io
import math
import threading
from pathlib import Path
from typing import Self

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image

from app.core.errors import FileCorruptError, PasswordRequiredError, WrongPasswordError
from app.core.model import PasswordCallback

PDFIUM_LOCK = threading.RLock()
"""Un singur fir foloseste PDFium la un moment dat."""

SCREEN_DPI = 96
"""[DECIZIE] `zoom=1.0` in `render_page` inseamna 100% pe ecran: 96 pixeli pe
inch. Un punct PDF e 1/72 inch."""

MAX_RENDER_PIXELS = 400_000_000
"""[DECIZIE] Limita unei randari, ca un zoom extrem sa nu ceara gigaocteti."""


def pixel_size(width_pt: float, height_pt: float, dpi: float) -> tuple[int, int]:
    """Dimensiunea in pixeli a unei pagini randate la `dpi`, calculata exact ca
    PDFium (rotunjire in sus). Zonele (faza 3) au coordonate in acesti pixeli,
    deci imaginea descrisa si cea randata trebuie sa coincida."""
    scale = dpi / 72
    return max(1, math.ceil(width_pt * scale)), max(1, math.ceil(height_pt * scale))


def _corrupt(path: Path, exc: Exception, page: int | None = None) -> FileCorruptError:
    params: dict[str, object] = {"path": str(path), "detail": str(exc)}
    if page is not None:
        params["page"] = page
    return FileCorruptError("PDF-ul nu se poate citi", **params)


# A-010, A-011, J-052
def open_pdfium(
    path: Path, password: PasswordCallback | None
) -> tuple[pdfium.PdfDocument, str | None]:
    """Deschide fisierul cu PDFium. Intoarce documentul si parola folosita.

    Parola: daca documentul o cere, `password(cale)` se apeleaza pana cand da
    parola corecta sau intoarce None. Limita de incercari (A-011: 3) o tine
    apelantul, in callback.

    Erori: `PasswordRequiredError` (cere parola si nu s-a dat niciuna),
    `WrongPasswordError` (s-au dat parole, dar niciuna corecta),
    `FileCorruptError`, `FileNotFoundError`.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    attempt: str | None = None
    tried = False
    while True:
        try:
            with PDFIUM_LOCK:
                return pdfium.PdfDocument(path, password=attempt), attempt
        except pdfium.PdfiumError as exc:
            if getattr(exc, "err_code", None) != pdfium_raw.FPDF_ERR_PASSWORD:
                raise _corrupt(path, exc) from exc
        if password is None:
            raise PasswordRequiredError("PDF-ul cere parola", path=str(path))
        attempt = password(str(path))
        if attempt is None:
            if tried:
                raise WrongPasswordError("parola nu e corecta", path=str(path))
            raise PasswordRequiredError("PDF-ul cere parola", path=str(path))
        tried = True


def render_pdf_page(
    doc: pdfium.PdfDocument,
    path: Path,
    number: int,
    dpi: float,
    *,
    annotations: bool = True,
    grayscale: bool = False,
) -> Image.Image:
    """Randeaza pagina `number` (de la 1) la `dpi`. FileCorruptError doar pentru
    pagina stricata, ca restul documentului sa ramana folosibil (B-001)."""
    if dpi <= 0:
        raise ValueError(f"rezolutia trebuie sa fie pozitiva: {dpi}")
    with PDFIUM_LOCK:
        total = len(doc)
        if not 1 <= number <= total:
            raise ValueError(f"pagina {number} nu exista (1..{total})")
        try:
            page = doc[number - 1]
            try:
                w_pt, h_pt = page.get_size()
                scale = dpi / 72
                if w_pt * scale * h_pt * scale > MAX_RENDER_PIXELS:
                    raise ValueError(
                        f"randarea ar avea peste {MAX_RENDER_PIXELS} de pixeli; micsorati zoom-ul"
                    )
                bitmap = page.render(
                    scale=scale, draw_annots=annotations, grayscale=grayscale,
                    may_draw_forms=annotations,
                )
                return bitmap.to_pil().copy()
            finally:
                page.close()
        except pdfium.PdfiumError as exc:
            raise _corrupt(path, exc, number) from exc


# SPEC_05 sect. 10 — partea de citire. B-001, A-010, A-011
class PdfDocument:
    """Documentul PDF deschis. Faza 1: citire si randare."""

    def __init__(self, path: Path, doc: pdfium.PdfDocument, *, is_encrypted: bool) -> None:
        self.path: Path | None = path
        self._doc: pdfium.PdfDocument | None = doc
        self.is_encrypted = is_encrypted
        self.is_modified = False

    @classmethod
    def open(cls, path: Path, *, password: PasswordCallback | None = None) -> PdfDocument:
        """A-010, A-011. Erori: vezi `open_pdfium`."""
        doc, used = open_pdfium(Path(path), password)
        return cls(Path(path), doc, is_encrypted=used is not None)

    def _require_open(self) -> pdfium.PdfDocument:
        if self._doc is None:
            raise ValueError("documentul e inchis")
        return self._doc

    @property
    def page_count(self) -> int:
        with PDFIUM_LOCK:
            return len(self._require_open())

    @property
    def pdf_version(self) -> str:
        """'1.7', '2.0'. Y-108: se accepta pana la 2.0 inclusiv."""
        with PDFIUM_LOCK:
            v = self._require_open().get_version()
        return "" if v is None else f"{v // 10}.{v % 10}"

    def page_size(self, number: int) -> tuple[float, float]:
        """In puncte (1/72 inch)."""
        doc = self._require_open()
        with PDFIUM_LOCK:
            if not 1 <= number <= len(doc):
                raise ValueError(f"pagina {number} nu exista (1..{len(doc)})")
            w, h = doc.get_page_size(number - 1)
        return float(w), float(h)

    # B-001: GUI-ul cere doar paginile vizibile, plus una inainte si una dupa.
    def render_page(self, number: int, zoom: float, *, annotations: bool = True) -> bytes:
        """PNG al paginii `number` (de la 1). `zoom=1.0` = 100% (SCREEN_DPI).

        O pagina stricata da FileCorruptError doar pentru ea; GUI-ul desenaza
        chenarul gri cu mesaj (B-001)."""
        if zoom <= 0:
            raise ValueError(f"zoom-ul trebuie sa fie pozitiv: {zoom}")
        assert self.path is not None
        img = render_pdf_page(
            self._require_open(), self.path, number, SCREEN_DPI * zoom, annotations=annotations
        )
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    def close(self) -> None:
        if self._doc is not None:
            with PDFIUM_LOCK:
                self._doc.close()
            self._doc = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
