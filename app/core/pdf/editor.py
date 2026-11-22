"""`PdfContentEditor` din SPEC_05 (faza 9): antetele, filigranele si stergerea
zonelor (pasul 9.2); editarea textului si a imaginilor vine in pasul 9.5.

ID-urile din docstring-urile SPEC_05 sunt decalate fata de SPEC_01; aici sunt
cele din SPEC_01, care decid. `remove_watermarks` sterge toate filigranele
(F-050, cerinta `D`), nu doar cele puse de aplicatie, cum scrie in SPEC_05.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.model import Rect

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument


# --- 9.5: editarea blocurilor si a imaginilor (F-001…F-023) ---------------------------------

FORMAT_KEYS = ("font_name", "font_size", "bold", "italic", "underline", "color", "alignment",
               "line_spacing", "paragraph_spacing", "direction")
"""F-015, F-016, F-108…F-110: ce se poate schimba la un bloc."""


class _Editing:
    """Metodele de editare a continutului, adaugate in `PdfContentEditor`."""

    document: PdfDocument
    _pages: dict[int, Any]

    # F-001…F-003
    def prepare_page(self, page: int, *, progress: Any = None, context: Any = None,
                     engine: Any = None) -> Any:
        """Modelul de blocuri al paginii (pe o scanare, cu OCR). Pe o pagina care
        nu se poate edita: `ContentNotEditableError` (F-002, F-003). `context` si
        `engine` (recunoasterea) sunt adaugate fata de SPEC_05."""
        from app.core.pdf import content

        prepared = content.prepare(self.document, page, context=context, engine=engine)
        self._pages[page] = prepared
        return prepared

    def _prepared(self, page: int) -> Any:
        if page not in self._pages:
            self.prepare_page(page)
        return self._pages[page]

    def blocks(self, page: int) -> list[Any]:
        """SPEC_05: blocurile paginii, ca `BlockData`."""
        return [b.as_block_data() for b in self._prepared(page).blocks]

    def text_blocks(self, page: int) -> list[Any]:
        """Blocurile cu formatarea lor (`TextBlock`), pentru interfata."""
        return list(self._prepared(page).blocks)

    def block(self, page: int, block_id: int) -> Any:
        for block in self._prepared(page).blocks:
            if block.id == block_id:
                return block
        raise KeyError(block_id)

    def _rewrite(self, page: int, old: Any, new: Any) -> Any:
        """Scoate blocul vechi si deseneaza noul bloc, ca o singura operatie: la
        o eroare, documentul revine la starea dinainte."""
        from app.core.pdf import content

        prepared = self._prepared(page)
        snapshot = self.document._snapshot()
        try:
            cover = None
            if old is not None:
                if old.source == "ocr":  # textul e in imagine: se acopera
                    cover = content.background_color(self.document, page, old.rect)
                    content.remove_area(self.document, page, old.rect, invisible_only=True)
                else:
                    content.remove_area(self.document, page, old.rect)
            area = None
            if new is not None and new.text.strip():
                area = content.draw_block(self.document, page, new, cover=cover,
                                          cover_rect=old.rect if old is not None else None)
            elif cover is not None:
                blank = content.TextBlock(0, old.rect, "", color=cover)
                content.draw_block(self.document, page, blank, cover=cover)
            if old is not None and old.source != "ocr":
                self.document._ocr_layer.pop(page, None)
            self.document._changed()
        except BaseException:
            self.document._restore(snapshot)
            raise
        blocks = [b for b in prepared.blocks if old is None or b.id != old.id]
        if new is not None and new.text.strip():
            from dataclasses import replace as _replace

            fresh = _replace(new, rect=area or new.rect, source="new")
            blocks.append(fresh)
            blocks.sort(key=lambda b: (b.rect.y, b.rect.x))
        prepared.blocks = blocks
        return blocks[-1] if new is not None and blocks else None

    # F-008
    def set_block_text(self, page: int, block_id: int, text: str) -> None:
        """Textul nou face reflow in latimea blocului."""
        from dataclasses import replace

        block = self.block(page, block_id)
        self._rewrite(page, block, replace(block, text=text))

    # F-011
    def add_text_block(self, page: int, rect: Rect, text: str = "") -> Any:
        """Un bloc nou; nu poate trece de marginile paginii (`ValueError`)."""
        from app.core.pdf import content

        width, height = self.document.page_size(page)
        if rect.x < 0 or rect.y < 0 or rect.x + rect.w > width or rect.y + rect.h > height:
            raise ValueError("blocul nou trece peste marginile paginii (F-011)")
        if rect.w < content.MIN_BLOCK_WIDTH:
            raise ValueError(f"latimea minima a unui bloc e {content.MIN_BLOCK_WIDTH} pt")
        prepared = self._prepared(page)
        new_id = max((b.id for b in prepared.blocks), default=0) + 1
        block = content.TextBlock(new_id, rect, text, source="new")
        if text.strip():
            self._rewrite(page, None, block)
        else:
            prepared.blocks.append(block)
        return self.block(page, new_id).as_block_data() if any(
            b.id == new_id for b in prepared.blocks) else block.as_block_data()

    # F-012
    def delete_block(self, page: int, block_id: int) -> None:
        """Blocul dispare; pe o scanare, fundalul se completeaza."""
        self._rewrite(page, self.block(page, block_id), None)

    # F-014
    def move_block(self, page: int, block_id: int, dx: float, dy: float) -> None:
        from dataclasses import replace

        block = self.block(page, block_id)
        moved = Rect(block.rect.x + dx, block.rect.y + dy, block.rect.w, block.rect.h)
        width, height = self.document.page_size(page)
        if moved.x < 0 or moved.y < 0 or moved.x + moved.w > width or \
                moved.y + moved.h > height:
            raise ValueError("blocul ar iesi din pagina (F-011)")
        self._rewrite(page, block, replace(block, rect=moved))

    # F-013
    def resize_block(self, page: int, block_id: int, rect: Rect) -> None:
        """Textul face reflow in noua latime (minimum 10 pt)."""
        from dataclasses import replace

        from app.core.pdf import content

        if rect.w < content.MIN_BLOCK_WIDTH:
            raise ValueError(f"latimea minima a unui bloc e {content.MIN_BLOCK_WIDTH} pt")
        block = self.block(page, block_id)
        self._rewrite(page, block, replace(block, rect=rect))

    # F-015, F-016
    def apply_text_format(self, page: int, block_id: int, **attrs: Any) -> None:
        """Fontul, marimea (1…1638 pt), aldin, cursiv, subliniat, culoarea,
        alinierea, spatierea randurilor si a paragrafelor, directia (F-108),
        pe tot blocul."""
        from dataclasses import replace

        from app.core.pdf import content

        unknown = set(attrs) - set(FORMAT_KEYS)
        if unknown:
            raise ValueError(f"formatare necunoscuta: {sorted(unknown)}")
        if "font_size" in attrs and not 1 <= float(attrs["font_size"]) <= 1638:
            raise ValueError("dimensiunea fontului e intre 1 si 1638 pt (F-015)")
        if "alignment" in attrs and attrs["alignment"] not in content.ALIGNMENTS:
            raise ValueError(f"aliniere necunoscuta: {attrs['alignment']}")
        if "direction" in attrs and attrs["direction"] not in ("ltr", "rtl"):
            raise ValueError("directia e `ltr` sau `rtl`")
        block = self.block(page, block_id)
        self._rewrite(page, block, replace(block, **attrs))

    # F-019
    def edit_table_cell(self, page: int, table: Rect, row: int, col: int, text: str) -> None:
        """Continutul unei celule se schimba, structura tabelului ramane (liniile
        nu se ating). SPEC_05 identifica tabelul printr-o zona OCR; in PDF Editor
        tabelul e zona lui pe pagina (`table`)."""
        from app.core.pdf import content, copying

        structure = copying.area_table(self.document, page, table)
        cell = structure.table.cell_at(row, col)
        if cell is None:
            raise KeyError((row, col))
        scale = table.w / structure.image.width  # celulele sunt in pixelii imaginii zonei
        box = cell.bbox
        rect = Rect(table.x + box.x * scale + 1, table.y + box.y * scale + 1,
                    max(box.w * scale - 2, content.MIN_BLOCK_WIDTH), max(box.h * scale - 2, 1))
        old = content.TextBlock(-1, rect, "")
        size = max(1.0, min(12.0, rect.h * 0.7))
        new = content.TextBlock(-1, rect, text, source="new", font_size=size)
        snapshot = self.document._snapshot()
        try:
            content.remove_area(self.document, page, old.rect)
            if text.strip():
                content.draw_block(self.document, page, new)
            self.document._changed()
        except BaseException:
            self.document._restore(snapshot)
            raise
        self._pages.pop(page, None)

    # --- imaginile (F-020…F-023) ---------------------------------------------------------

    def pictures(self, page: int) -> list[Any]:
        return list(self.prepare_page(page).pictures) if page not in self._pages \
            else list(self._pages[page].pictures)

    def _image_objects(self, page: int, handle: Any = None) -> list[Any]:
        from app.core.pdf import content

        raw = content._raw()
        handle = handle if handle is not None else self.document._require_open()[page - 1]
        return [o for o in handle.get_objects() if o.type == raw.FPDF_PAGEOBJ_IMAGE]

    def _commit_objects(self, page: int, handle: Any) -> None:
        """`handle` e pagina PDFium pe care s-au facut modificarile."""
        from app.core.pdf import content

        handle.gen_content()
        content.commit_pdfium(self.document)
        self.document._changed()
        self._pages.pop(page, None)

    def add_picture(self, page: int, image: Path, at: Any) -> int:
        """F-020: imaginea, cu coltul stanga-sus in `at` (x, y, puncte de sus),
        la marimea ei (96 dpi), micsorata daca nu incape. Intoarce id-ul ei."""
        import pypdfium2 as pdfium
        from PIL import Image

        from app.core.pdf.text import page_geometry

        x, y = (at.x, at.y) if hasattr(at, "x") else at
        width, height = self.document.page_size(page)
        with Image.open(image) as source:
            picture = source.convert("RGB")
        w, h = picture.width * 72 / 96, picture.height * 72 / 96
        fit = min(1.0, (width - x) / w if w else 1.0, (height - y) / h if h else 1.0)
        if fit <= 0:
            raise ValueError("imaginea nu incape pe pagina")
        w, h = w * fit, h * fit
        doc = self.document._require_open()
        obj = pdfium.PdfImage.new(doc)
        obj.set_bitmap(pdfium.PdfBitmap.from_pil(picture))
        left, bottom, page_h = page_geometry(self.document._pike().pages[page - 1])
        obj.set_matrix(pdfium.PdfMatrix().scale(w, h).translate(left + x,
                                                                bottom + page_h - y - h))
        handle = doc[page - 1]
        handle.insert_obj(obj)
        self._commit_objects(page, handle)
        return len(self._image_objects(page))

    def transform_picture(self, page: int, picture_id: int, *, rect: Rect | None = None,
                          rotation: float | None = None) -> None:
        """F-021: mutare si redimensionare (`rect`), rotire (grade, in jurul
        centrului)."""
        import pypdfium2 as pdfium

        from app.core.pdf.text import page_geometry, to_pdf_rect

        handle = self.document._require_open()[page - 1]
        objects = self._image_objects(page, handle)
        if not 1 <= picture_id <= len(objects):
            raise KeyError(picture_id)
        obj = objects[picture_id - 1]
        geo = page_geometry(self.document._pike().pages[page - 1])
        if rect is None:
            from app.core.pdf import content

            rect = content._to_rect(self.document, page, obj.get_bounds())
        x0, y0, x1, y1 = to_pdf_rect(geo, rect)
        matrix = pdfium.PdfMatrix().scale(x1 - x0, y1 - y0).translate(-(x1 - x0) / 2,
                                                                      -(y1 - y0) / 2)
        if rotation:
            matrix = matrix.rotate(rotation)
        obj.set_matrix(matrix.translate((x0 + x1) / 2, (y0 + y1) / 2))
        self._commit_objects(page, handle)

    def delete_picture(self, page: int, picture_id: int) -> None:
        """F-023: numai pe PDF-urile produse de alte aplicatii; imaginea unei
        pagini scanate nu se sterge (ar disparea pagina)."""
        if self._prepared(page).kind == "scan":
            raise ValueError("imaginea unei pagini scanate nu se sterge (F-023)")
        handle = self.document._require_open()[page - 1]
        objects = self._image_objects(page, handle)
        if not 1 <= picture_id <= len(objects):
            raise KeyError(picture_id)
        handle.remove_obj(objects[picture_id - 1])
        self._commit_objects(page, handle)

    def bring_to_front(self, page: int, object_id: int) -> None:
        """F-022: imaginea se deseneaza ultima, peste celelalte."""
        handle = self.document._require_open()[page - 1]
        objects = self._image_objects(page, handle)
        if not 1 <= object_id <= len(objects):
            raise KeyError(object_id)
        import pypdfium2 as pdfium

        obj = objects[object_id - 1]
        # PDFium nu reordoneaza un obiect scos si pus la loc: se pune o copie
        # (aceeasi imagine, aceeasi pozitie) la sfarsit si originalul se scoate.
        copy = pdfium.PdfImage.new(self.document._require_open())
        copy.set_bitmap(obj.get_bitmap(render=False))
        copy.set_matrix(obj.get_matrix())
        handle.insert_obj(copy)
        handle.remove_obj(obj)
        self._commit_objects(page, handle)

    # --- F-017, F-018 ---------------------------------------------------------------------

    def skew_angle(self, page: int) -> float:
        """F-017: inclinarea detectata (grade); butonul apare doar cand e mai
        mare decat `SKEW_VISIBLE`."""
        import numpy as np
        from PIL import Image

        from app.core.images.preprocess import detect_skew

        image = Image.open(io.BytesIO(self.document.render_page(page, 1.5, annotations=False)))
        return float(detect_skew(np.asarray(image.convert("L"))))

    def correct_skew(self, page: int | None = None, *, context: Any = None,
                     engine: Any = None) -> None:
        """F-017: indreptarea si orientarea paginii curente (sau a tuturor)."""
        from app.core.pdf.organize import PageOrganizer
        from app.core.settings import PreprocessSettings

        pages = [page] if page is not None else list(range(1, self.document.page_count + 1))
        settings = PreprocessSettings(
            correct_orientation=True, deskew=True, straighten_lines=False,
            correct_resolution=False, detect_page_edges=False, whiten_background=False,
            reduce_iso_noise=False, remove_motion_blur=False, fix_inverted_colors=False,
            convert_to_bw=False, remove_color_marks=False)
        PageOrganizer(self.document).enhance_images(pages, settings, context=context,
                                                    engine=engine)
        for n in pages:
            self._pages.pop(n, None)

    def replace_text_layer(self, page: int, settings: Any = None, *,
                           correct_orientation: bool = False, deskew: bool = False,
                           context: Any = None, engine: Any = None) -> None:
        """F-018: stratul de text vechi (invizibil) se pierde, pagina se
        recunoaste din nou si stratul nou se scrie. Apelantul confirma intai.
        Optiunile dialogului `Recognize Document` sunt adaugate fata de SPEC_05."""
        from app.core.pdf import content

        if correct_orientation or deskew:
            self.correct_skew(page, context=context, engine=engine)
        width, height = self.document.page_size(page)
        content.remove_area(self.document, page, Rect(0, 0, width, height),
                            invisible_only=True)
        self.document._ocr_layer.pop(page, None)
        self.document._changed()
        languages = getattr(settings, "languages", None)
        self.document.recognize_and_store(pages=[page], languages=languages, context=context,
                                          engine=engine)
        self._pages.pop(page, None)


SKEW_VISIBLE = 0.3
"""F-017: de la ce inclinare (grade) apare butonul `Correct Skew`."""


class PdfContentEditor(_Editing):
    """F-001…F-050. Editarea continutului unei pagini PDF."""

    def __init__(self, document: PdfDocument, font_matcher: Any = None) -> None:
        self.document = document
        self.font_matcher = font_matcher
        self._pages: dict[int, Any] = {}
        """Paginile pregatite (F-003): blocurile si imaginile lor."""

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
