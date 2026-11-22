"""`PdfContentEditor` din SPEC_05 (faza 9): antetele, filigranele si stergerea
zonelor (pasul 9.2); editarea textului si a imaginilor vine in pasul 9.5.

ID-urile din docstring-urile SPEC_05 sunt decalate fata de SPEC_01; aici sunt
cele din SPEC_01, care decid. `remove_watermarks` sterge toate filigranele
(F-050, cerinta `D`), nu doar cele puse de aplicatie, cum scrie in SPEC_05.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.model import Rect

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument


class PdfContentEditor:
    """F-001…F-050. Editarea continutului unei pagini PDF."""

    def __init__(self, document: PdfDocument, font_matcher: Any = None) -> None:
        self.document = document
        self.font_matcher = font_matcher

    # F-024, F-025
    def erase_region(self, page: int, rect: Rect) -> None:
        """`Erase`: continutul zonei dispare din pagina si din stratul de text;
        fundalul se completeaza cu culoarea detectata in jurul zonei. Adnotarile
        raman. Dupa stergere textul se cauta din nou in zona: daca mai apare,
        pagina revine la starea dinainte (`RedactionVerificationError`)."""
        from app.core.pdf.redact import PageEdit, rebuild_page, verify_removed

        self.document._check_pages([page])
        if rect.w <= 0 or rect.h <= 0:
            raise ValueError("zona de sters e goala")
        snapshot = self.document._snapshot()
        try:
            rebuild_page(self.document, page, [PageEdit(rect, fill=None)],
                         remove_annotations=False)
            self.document._changed()
            verify_removed(self.document, page, [rect], ())
        except BaseException:
            self.document._restore(snapshot)
            raise

    # F-039…F-042
    def add_header_footer(self, *, position: str, content: str,
                          pages: Sequence[int] | None = None, margin: float = 1.0,
                          margin_unit: str = "cm", font_name: str | None = None,
                          font_size: float | None = None, text_color: str | None = None,
                          bates_start: int | None = None, bates_digits: int = 6,
                          bold: bool = False, italic: bool = False, underline: bool = False,
                          moment: datetime | None = None) -> int | None:
        """Contractul SPEC_05; efectele de text si `moment` sunt adaugate (F-041,
        teste). Intoarce urmatorul numar Bates (`Continue from`)."""
        from app.core.pdf.decorate import HeaderFooter, add_header_footer

        hf = HeaderFooter(position=position, content=content, margin=margin,
                          margin_unit=margin_unit, font_name=font_name,
                          font_size=font_size or 10.0, text_color=text_color or "#000000",
                          bold=bold, italic=italic, underline=underline,
                          bates_start=bates_start, bates_digits=bates_digits)
        return add_header_footer(self.document, hf, pages=pages, moment=moment)

    # F-045…F-049
    def add_watermark(self, *, text: str | None = None, image: Path | None = None,
                      position: str = "center", offset: tuple[float, float] = (0.0, 0.0),
                      rotation: float = 0.0, opacity: float = 0.3,
                      behind_content: bool = False, pages: Sequence[int] | None = None,
                      font_name: str | None = None, font_size: float = 60.0,
                      text_color: str = "#808080", image_scale: float = 0.5) -> None:
        from app.core.pdf.decorate import Watermark, add_watermark

        wm = Watermark(text=text, image=Path(image) if image is not None else None,
                       position=position, offset=offset, rotation=rotation,
                       opacity=opacity, behind_content=behind_content, font_name=font_name,
                       font_size=font_size, text_color=text_color, image_scale=image_scale)
        add_watermark(self.document, wm, pages=pages)

    # F-050
    def remove_watermarks(self) -> int:
        """Sterge TOATE filigranele (F-050)."""
        from app.core.pdf.decorate import remove_watermarks

        return remove_watermarks(self.document)
