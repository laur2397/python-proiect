"""Documentul PDF: deschidere, randare, salvare, text, metadate.

Din `PdfDocument` (SPEC_05 sectiunea 10): citirea si randarea (faza 1),
salvarea, textul, metadatele, permisiunile si salvarea automata de siguranta
(faza 7, pasul 7.1: I-001…I-007, I-024). Cautarea, adnotarile si
recunoasterea in fundal vin in pasii urmatori ai fazei 7 si nu sunt declarate
aici.

[DECIZIE AUTONOMA] (faza_7_pasi.md, decizia 1) PDFium randeaza si citeste
textul; pikepdf modifica si salveaza. Dupa fiecare modificare PDFium reciteste
documentul din memorie, ca imaginea sa arate exact ce se va salva.

Randarea foloseste PDFium prin pypdfium2. PDFium nu e sigur pentru apeluri
din mai multe fire simultan, deci toate apelurile trec prin `PDFIUM_LOCK`.
"""

from __future__ import annotations

import errno
import io
import math
import os
import tempfile
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import pikepdf
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image

from app.core.errors import (
    CoreError,
    DiskFullError,
    FileCorruptError,
    FileLockedError,
    NoWritePermissionError,
    PasswordRequiredError,
    WrongPasswordError,
)
from app.core.model import AnnotationData, PasswordCallback, Rect, ReviewStatus

if TYPE_CHECKING:
    from app.core.context import AppContext
    from app.core.export.base import ExportOptions
    from app.core.model import AnnotationType
    from app.core.pdf.text import SearchHit

PDFIUM_LOCK = threading.RLock()
"""Un singur fir foloseste PDFium la un moment dat."""

SCREEN_DPI = 96
"""[DECIZIE] `zoom=1.0` in `render_page` inseamna 100% pe ecran: 96 pixeli pe
inch. Un punct PDF e 1/72 inch."""

AUTOSAVE_INTERVAL_S = 300
"""I-024: salvarea automata de siguranta, la 5 minute. Ceasul il tine interfata."""

METADATA_KEYS = {
    "title": "/Title", "author": "/Author", "subject": "/Subject",
    "keywords": "/Keywords", "creator": "/Creator", "producer": "/Producer",
    "created": "/CreationDate", "modified": "/ModDate",
}
"""Campurile din dictionarul Info, cu numele folosite de `metadata()`."""

PERMISSIONS = ("print_lowres", "print_highres", "extract", "accessibility",
               "modify_annotation", "modify_form", "modify_assembly", "modify_other")
"""Cheile din `permissions`, ca in pikepdf (bitii /P din standardul PDF)."""

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


# SPEC_05 sect. 10. B-001, A-010, A-011, I-001…I-007, I-024
class PdfDocument:
    """Documentul PDF deschis in editor.

    Doua vederi ale aceluiasi document: `_doc` (PDFium, pentru randare si text)
    si `_pdf` (pikepdf, pentru modificari si salvare). `_pdf` se deschide doar
    la prima modificare sau salvare.
    """

    def __init__(self, path: Path | None, doc: pdfium.PdfDocument, *, is_encrypted: bool,
                 password: str | None = None, pdf: pikepdf.Pdf | None = None) -> None:
        self.path: Path | None = None if path is None else Path(path)
        self._doc: pdfium.PdfDocument | None = doc
        self._pdf: pikepdf.Pdf | None = pdf
        self._password = password
        self.is_encrypted = is_encrypted
        self.is_modified = False
        self._recovery_path: Path | None = None
        self._autosaved_revision: int | None = None
        self._registry_context: AppContext | None = None
        self._revision = 0

    @classmethod
    def open(cls, path: Path, *, password: PasswordCallback | None = None) -> PdfDocument:
        """A-010, A-011. Erori: vezi `open_pdfium`."""
        doc, used = open_pdfium(Path(path), password)
        return cls(Path(path), doc, is_encrypted=used is not None, password=used)

    @classmethod
    def create_empty(cls) -> PdfDocument:
        """Un document nou, fara pagini si fara fisier (`path` e None)."""
        pdf = pikepdf.new()
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument.new()
        return cls(None, doc, is_encrypted=False, pdf=pdf)

    # A-013
    @classmethod
    def from_images(cls, images: Sequence[Path], *, options: ExportOptions,
                    context: AppContext | None = None, engine: Any = None) -> PdfDocument:
        """Un PDF nou din imagini (sau alte fisiere acceptate de OCR Editor),
        nesalvat: `path` e None si `is_modified` e True. Cu `options.searchable`
        paginile se recunosc (strat de text, I-003); altfel PDF doar-imagine
        (I-004). `context` si `engine` sunt adaugate fata de SPEC_05, pentru
        aplicatie si pentru teste (motorul OCR)."""
        if not images:
            raise ValueError("lista de imagini e goala (A-013)")
        with tempfile.TemporaryDirectory(prefix="doculens-pdf-") as tmp:
            target = Path(tmp) / "document.pdf"
            _export_via_project([Path(i) for i in images], target, options,
                                context=context, engine=engine)
            data = target.read_bytes()
        document = cls._from_bytes(data, None)
        document.is_modified = True
        document._revision = 1
        return document

    @classmethod
    def _from_bytes(cls, data: bytes, path: Path | None) -> PdfDocument:
        pdf = pikepdf.open(io.BytesIO(data))
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(data) if len(pdf.pages) else pdfium.PdfDocument.new()
        return cls(path, doc, is_encrypted=False, pdf=pdf)

    # --- stare ------------------------------------------------------------------------

    def _require_open(self) -> pdfium.PdfDocument:
        if self._doc is None:
            raise ValueError("documentul e inchis")
        return self._doc

    def _pike(self) -> pikepdf.Pdf:
        """Vederea pikepdf, deschisa la prima nevoie."""
        self._require_open()
        if self._pdf is None:
            assert self.path is not None
            try:
                self._pdf = pikepdf.open(self.path, password=self._password or "")
            except pikepdf.PdfError as exc:
                raise _corrupt(self.path, exc) from exc
        return self._pdf

    def _changed(self) -> None:
        """Dupa o modificare prin pikepdf: PDFium reciteste documentul din memorie."""
        pdf = self._pike()
        out = io.BytesIO()
        pdf.save(out, **self._save_kwargs(pdf, keep_encryption=False))
        with PDFIUM_LOCK:
            old = self._doc
            self._doc = pdfium.PdfDocument(out.getvalue()) if len(pdf.pages) \
                else pdfium.PdfDocument.new()
            if old is not None:
                old.close()
        self.is_modified = True
        self._revision += 1

    @property
    def page_count(self) -> int:
        with PDFIUM_LOCK:
            return len(self._require_open())

    @property
    def pdf_version(self) -> str:
        """'1.7', '2.0'. Y-108: se accepta pana la 2.0 inclusiv."""
        if self._pdf is not None:
            return str(self._pdf.pdf_version)
        with PDFIUM_LOCK:
            v = self._require_open().get_version()
        return "" if v is None else f"{v // 10}.{v % 10}"

    @property
    def permissions(self) -> Mapping[str, bool]:
        """Ce permite autorul unui fisier protejat (cheile din `PERMISSIONS`).
        Un fisier neprotejat permite tot."""
        allow = self._pike().allow
        return {key: bool(getattr(allow, key)) for key in PERMISSIONS}

    @property
    def is_tagged(self) -> bool:
        """PDF etichetat (accesibil): `/MarkInfo /Marked true` sau arbore de structura."""
        root = self._pike().Root
        mark = root.get("/MarkInfo")
        if mark is not None and bool(mark.get("/Marked", False)):
            return True
        return "/StructTreeRoot" in root

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
        img = render_pdf_page(
            self._require_open(), self.path or Path("document.pdf"), number,
            SCREEN_DPI * zoom, annotations=annotations,
        )
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    # --- textul -----------------------------------------------------------------------

    def extract_text(self, number: int) -> str:
        """Textul paginii `number` (de la 1), din stratul de text al fisierului."""
        doc = self._require_open()
        with PDFIUM_LOCK:
            if not 1 <= number <= len(doc):
                raise ValueError(f"pagina {number} nu exista (1..{len(doc)})")
            page = doc[number - 1]
            try:
                textpage = page.get_textpage()
                try:
                    return textpage.get_text_range().replace("\r\n", "\n")
                finally:
                    textpage.close()
            finally:
                page.close()

    # B-029, N-008
    def has_text_layer(self, number: int) -> bool:
        """Pagina are text in fisier (nu doar imagine): cel putin un caracter
        care nu e spatiu."""
        return any(not ch.isspace() for ch in self.extract_text(number))

    # --- cautarea (C-002…C-010) -------------------------------------------------------

    def search(self, query: str, *, match_case: bool = False, whole_word: bool = False,
               in_comments: bool = True, in_bookmarks: bool = True,
               in_metadata: bool = True) -> list[SearchHit]:
        """C-002…C-006: (pagina, dreptunghi, context), ca in SPEC_05; fiecare
        rezultat e un `SearchHit`, care spune si sursa (text, comentarii, semne
        de carte, metadate), dupa care il grupeaza apelantul. Dreptunghiurile
        sunt in puncte, cu originea sus-stanga (vezi `app/core/pdf/text.py`)."""
        from app.core.pdf.text import search_document

        return search_document(self, query, match_case=match_case, whole_word=whole_word,
                               in_comments=in_comments, in_bookmarks=in_bookmarks,
                               in_metadata=in_metadata)

    def mark_hits(self, hits: Sequence[SearchHit], kind: AnnotationType, color: str, *,
                  author: str | None = None) -> int:
        """C-007…C-010: marcheaza rezultatele din text cu adnotari (evidentiere,
        subliniere, taiere); textul PDF-ului nu se schimba. Intoarce cate
        adnotari s-au creat."""
        from app.core.pdf.markup import mark_hits

        return mark_hits(self, hits, kind, color, author=author)

    # C-015…C-018
    def replace_text(self, hits: Sequence[tuple[int, Rect]], new_text: str) -> int:
        """Inlocuieste rezultatele date (pagina, dreptunghi; un `SearchHit` aduce
        si dreptunghiurile pe randuri): textul vechi se acopera cu fondul
        detectat si dispare din stratul de text, iar textul nou (poate fi gol)
        se deseneaza si intra in strat. Pagina ramane PDF imagine cu strat de
        text (C-018); verificarea fondului e `redact.background_is_uniform`,
        apelata de interfata inainte (C-018). Modificarile se salveaza explicit
        (C-017). Intoarce numarul de inlocuiri."""
        from app.core.pdf.redact import PageEdit, rebuild_page

        pages: dict[int, list[PageEdit]] = {}
        total = self.page_count
        for hit in hits:
            number, rect = hit[0], hit[1]
            if not 1 <= number <= total:
                raise ValueError(f"pagina {number} nu exista (1..{total})")
            rects = list(getattr(hit, "rects", ()) or (rect,))
            edits = pages.setdefault(number, [])
            edits.append(PageEdit(rects[0], None, new_text))
            edits += [PageEdit(r, None) for r in rects[1:]]
        if not pages:
            return 0
        snapshot = self._snapshot()
        try:
            for number, edits in pages.items():
                rebuild_page(self, number, edits, remove_annotations=False)
            self._changed()
        except BaseException:
            self._restore(snapshot)
            raise
        return len(hits)

    def _snapshot(self) -> tuple[bytes, bool, int]:
        """Starea documentului, pentru anularea unei operatii esuate."""
        pdf = self._pike()
        out = io.BytesIO()
        pdf.save(out, **self._save_kwargs(pdf, keep_encryption=False))
        return out.getvalue(), self.is_modified, self._revision

    def _restore(self, snapshot: tuple[bytes, bool, int]) -> None:
        data, modified, revision = snapshot
        pdf = pikepdf.open(io.BytesIO(data))
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(data) if len(pdf.pages) else pdfium.PdfDocument.new()
        self.close_views()
        self._pdf, self._doc = pdf, doc
        self.is_modified, self._revision = modified, revision

    # --- adnotari (D-001…D-044), detaliile in app/core/pdf/annotations.py ---------------

    def annotations(self, page: int | None = None) -> list[AnnotationData]:
        """D-024: comentariile, marcajele, casetele, stampilele (fara linkuri si
        campuri de formular); raspunsurile sunt in `replies`."""
        from app.core.pdf import annotations

        return annotations.list_annotations(self, page)

    def add_annotation(self, annot: AnnotationData) -> AnnotationData:
        """D-001…D-017. Marcajele pe text cer strat de text: altfel
        `NoTextFoundError` (D-003), iar interfata porneste recunoasterea."""
        from app.core.pdf import annotations

        return annotations.add_annotation(self, annot)

    def update_annotation(self, annot: AnnotationData) -> AnnotationData:
        from app.core.pdf import annotations

        return annotations.update_annotation(self, annot)

    def delete_annotations(self, ids: Sequence[int]) -> None:
        """D-028: se sterg si raspunsurile si statusurile."""
        from app.core.pdf import annotations

        annotations.delete_annotations(self, ids)

    def delete_all_annotations(self) -> int:
        """D-029: intoarce cate au fost sterse (apelantul confirma intai)."""
        from app.core.pdf import annotations

        return annotations.delete_all_annotations(self)

    def add_reply(self, parent_id: int, content: str, author: str) -> AnnotationData:
        """D-026."""
        from app.core.pdf import annotations

        return annotations.add_reply(self, parent_id, content, author)

    def set_review_status(self, annot_id: int, status: ReviewStatus, author: str) -> None:
        """D-031: istoricul schimbarilor se pastreaza."""
        from app.core.pdf import annotations

        annotations.set_review_status(self, annot_id, status, author)

    # --- metadate ---------------------------------------------------------------------

    def metadata(self) -> Mapping[str, str]:
        """Campurile completate din dictionarul Info, cu cheile din `METADATA_KEYS`."""
        info = self._pike().docinfo
        out: dict[str, str] = {}
        for key, name in METADATA_KEYS.items():
            value = info.get(name)
            if value is not None and str(value):
                out[key] = str(value)
        return out

    def set_metadata(self, **fields: str) -> None:
        """Schimba campurile date; un sir gol sterge campul. Pe un fisier protejat
        care nu permite modificari: `NoWritePermissionError`.

        [DECIZIE AUTONOMA] SPEC_05 spune ca la fisierele protejate campurile sunt
        blocate, fara sa numeasca o exceptie; se foloseste `NoWritePermissionError`."""
        unknown = set(fields) - set(METADATA_KEYS)
        if unknown:
            raise ValueError(f"campuri necunoscute: {sorted(unknown)}")
        if not self.permissions["modify_other"]:
            raise NoWritePermissionError("documentul protejat nu permite modificari",
                                         path=str(self.path or ""))
        info = self._pike().docinfo
        for key, value in fields.items():
            name = pikepdf.Name(METADATA_KEYS[key])
            if value:
                info[name] = pikepdf.String(value)
            elif name in info:
                del info[name]
        self._changed()

    # --- salvarea ---------------------------------------------------------------------

    def _save_kwargs(self, pdf: pikepdf.Pdf, *, keep_encryption: bool) -> dict[str, Any]:
        """I-001, I-007: versiunea nu scade; fluxurile se copiaza octet cu octet
        (nu se decodeaza si nu se recomprima); XMP-ul nu se rescrie.

        Un fisier care ramane criptat se recripteaza la scriere, deci copierea
        octet cu octet nu e posibila acolo; continutul ramane acelasi."""
        encrypt = keep_encryption and pdf.is_encrypted
        kwargs: dict[str, Any] = {
            "min_version": pdf.pdf_version,
            "recompress_flate": False,
            "fix_metadata_version": False,
            "object_stream_mode": pikepdf.ObjectStreamMode.preserve,
            "encryption": encrypt,
        }
        if not encrypt:
            kwargs["stream_decode_level"] = pikepdf.StreamDecodeLevel.none
        return kwargs

    # I-001, I-007
    def save(self) -> None:
        """Scrie modificarile in fisierul documentului. Fara modificari nu se
        atinge fisierul. Scrierea e atomica: intai un fisier temporar langa
        original, apoi inlocuirea. Erori: `FileLockedError` (fisierul e deschis
        in alta aplicatie), `NoWritePermissionError`, `DiskFullError`."""
        if self.path is None:
            raise ValueError("documentul nu are inca fisier: folositi save_as")
        if not self.is_modified:
            return
        self._write(self.path, pages=None, keep_encryption=True)
        self.is_modified = False
        self._forget_autosave()

    # I-002, I-003, I-004, I-006
    def save_as(self, path: Path, *, options: ExportOptions | None = None,
                pages: Sequence[int] | None = None, context: AppContext | None = None,
                engine: Any = None) -> None:
        """I-002: fara `options`, o copie a documentului la `path` (redenumire sau
        mutare); documentul deschis trece pe noul fisier.

        Cu `options`: PDF cautabil (`options.searchable`, paginile trec prin OCR,
        I-003) sau doar-imagine (I-004), tot la `path`, iar documentul deschis
        trece pe rezultat.

        `pages` (I-006, de la 1): doar paginile alese, intr-un fisier separat;
        documentul deschis ramane cel de acum.

        [DECIZIE AUTONOMA] `pages`, `context` si `engine` sunt adaugate fata de
        SPEC_05: semnatura din contract nu are unde primi selectia de pagini
        (I-006), contextul aplicatiei si motorul OCR (pentru teste)."""
        path = Path(path)
        if pages is not None:
            self._check_pages(pages)
        if options is None:
            same = self.path is not None and path.resolve() == self.path.resolve()
            self._write(path, pages=pages, keep_encryption=pages is None and same)
            if pages is None:
                self._switch_to(path, keep_encryption=same)
            return
        with tempfile.TemporaryDirectory(prefix="doculens-pdf-") as tmp:
            source = Path(tmp) / "sursa.pdf"
            self._write(source, pages=pages, keep_encryption=False, atomic=False)
            produced = Path(tmp) / "rezultat.pdf"
            _export_via_project([source], produced, options, context=context, engine=engine)
            self._replace_file(produced.read_bytes(), path)
        if pages is None:
            self._switch_to(path, keep_encryption=False)

    def _check_pages(self, pages: Sequence[int]) -> None:
        if not pages:
            raise ValueError("nu e aleasa nicio pagina (I-006)")
        total = self.page_count
        bad = [n for n in pages if not 1 <= n <= total]
        if bad:
            raise ValueError(f"paginile {bad} nu exista (1..{total})")

    def _write(self, path: Path, *, pages: Sequence[int] | None, keep_encryption: bool,
               atomic: bool = True) -> None:
        pdf = self._pike()
        out = io.BytesIO()
        if pages is None:
            pdf.save(out, **self._save_kwargs(pdf, keep_encryption=keep_encryption))
        else:
            part = pikepdf.new()
            for n in pages:
                part.pages.append(pdf.pages[n - 1])
            info = pdf.docinfo
            for name in METADATA_KEYS.values():
                if name in info:
                    part.docinfo[pikepdf.Name(name)] = pikepdf.String(str(info[name]))
            kwargs = self._save_kwargs(pdf, keep_encryption=False)
            part.save(out, **kwargs)
        if atomic:
            self._replace_file(out.getvalue(), path)
        else:
            Path(path).write_bytes(out.getvalue())

    def _replace_file(self, data: bytes, path: Path) -> None:
        """Scriere atomica: fisier temporar in acelasi folder, apoi `os.replace`.
        Pe Windows fisierul propriu trebuie eliberat inainte (PDFium si pikepdf
        il tin deschis), deci la inlocuirea lui documentul se reincarca."""
        path = Path(path)
        own = self.path is not None and path.exists() and path.resolve() == self.path.resolve()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=".doculens-", suffix=".pdf", dir=path.parent)
        except OSError as exc:
            raise _write_error(exc, path) from exc
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise _write_error(exc, path) from exc
        if own:
            self._release_file()
        try:
            os.replace(tmp, path)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            # documentul ramane cel din memorie, cu modificarile nesalvate
            if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (32, 33):
                raise FileLockedError("fisierul e deschis in alta aplicatie",
                                      path=str(path)) from exc
            raise _write_error(exc, path) from exc
        if own:
            self._reload_from(path)

    def _release_file(self) -> None:
        """Pastreaza documentul in memorie si inchide fisierul de pe disc."""
        pdf = self._pike()
        out = io.BytesIO()
        pdf.save(out, **self._save_kwargs(pdf, keep_encryption=False))
        data = out.getvalue()
        pdf.close()
        self._pdf = pikepdf.open(io.BytesIO(data))
        with PDFIUM_LOCK:
            old = self._doc
            self._doc = pdfium.PdfDocument(data) if len(self._pdf.pages) \
                else pdfium.PdfDocument.new()
            if old is not None:
                old.close()

    def _reload_from(self, path: Path | None) -> None:
        """Dupa inlocuirea fisierului: ambele vederi citesc din nou de pe disc,
        daca acolo e documentul; altfel raman cele din memorie."""
        if path is None or not Path(path).exists():
            return
        password = self._password if self.is_encrypted else None
        try:
            pdf = pikepdf.open(path, password=password or "")
            with PDFIUM_LOCK:
                doc = pdfium.PdfDocument(path, password=password) if len(pdf.pages) \
                    else pdfium.PdfDocument.new()
        except (pikepdf.PdfError, pdfium.PdfiumError):
            return
        modified = self.is_modified
        self.close_views()
        self._pdf, self._doc = pdf, doc
        self.is_modified = modified

    def _switch_to(self, path: Path, *, keep_encryption: bool) -> None:
        """Documentul deschis trece pe fisierul abia scris (Save As)."""
        if not keep_encryption:
            self.is_encrypted = False
            self._password = None
        self.path = path
        self._reload_from(path)
        self.is_modified = False
        self._forget_autosave()

    # --- salvarea automata de siguranta (I-024) ---------------------------------------

    def autosave(self, context: AppContext | None = None) -> Path | None:
        """Copie de siguranta in folderul de recuperare, doar daca exista
        modificari nesalvate si s-a schimbat ceva de la ultima copie. Intoarce
        calea copiei, ori None daca documentul n-are nimic de salvat.
        Intervalul (`AUTOSAVE_INTERVAL_S`) il tine interfata."""
        if not self.is_modified:
            return None
        if self._autosaved_revision == self._revision and self._recovery_path is not None:
            return self._recovery_path
        registry = _context(context).recovery
        dest = registry.new_recovery_path("pdf", "pdf")
        pdf = self._pike()
        try:
            pdf.save(dest, **self._save_kwargs(pdf, keep_encryption=False))
        except OSError as exc:
            dest.unlink(missing_ok=True)
            raise _write_error(exc, dest) from exc
        registry.register(dest, self.path, "pdf")
        self._forget_autosave(context)
        self._recovery_path = dest
        self._autosaved_revision = self._revision
        self._registry_context = context
        return dest

    @classmethod
    def find_recovery(cls, *, context: AppContext | None = None
                      ) -> list[tuple[Path, Path | None]]:
        """(copia de siguranta, calea originala) pentru PDF-urile ramase de la o
        sesiune cazuta. None = document care nu fusese salvat niciodata."""
        return [(e.recovery_path, e.original_path)
                for e in _context(context).recovery.find_pending() if e.doc_kind == "pdf"]

    @classmethod
    def recover(cls, recovery_path: Path, *, context: AppContext | None = None) -> PdfDocument:
        """Deschide o copie de siguranta ca document nesalvat, cu calea originala.
        Copia iese din evidenta: de acum o protejeaza salvarea automata."""
        registry = _context(context).recovery
        recovery_path = Path(recovery_path)
        entry = next((e for e in registry.find_pending()
                      if e.recovery_path == recovery_path and e.doc_kind == "pdf"), None)
        if entry is None:
            raise FileNotFoundError(recovery_path)
        document = cls._from_bytes(recovery_path.read_bytes(), entry.original_path)
        document.is_modified = True
        document._revision = 1
        registry.discard(entry)
        return document

    def _forget_autosave(self, context: AppContext | None = None) -> None:
        if self._recovery_path is not None:
            ctx = context or self._registry_context
            _context(ctx).recovery.forget(self._recovery_path)
            self._recovery_path = None
        self._autosaved_revision = None

    # --- inchiderea -------------------------------------------------------------------

    def close_views(self) -> None:
        if self._pdf is not None:
            self._pdf.close()
            self._pdf = None
        if self._doc is not None:
            with PDFIUM_LOCK:
                self._doc.close()
            self._doc = None

    def close(self) -> None:
        """Nu intreaba nimic: apelantul verifica `is_modified` inainte (I-023)."""
        if self._doc is None:
            return
        self._forget_autosave()
        self.close_views()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _context(context: AppContext | None) -> AppContext:
    if context is not None:
        return context
    from app.core.context import current

    return current()


def _write_error(exc: OSError, path: Path) -> CoreError:
    if exc.errno == errno.ENOSPC:
        return DiskFullError(str(exc), path=str(path))
    return NoWritePermissionError(str(exc), path=str(path))


# I-003, I-004, A-013
def _export_via_project(files: Sequence[Path], target: Path, options: ExportOptions, *,
                        context: AppContext | None, engine: Any) -> None:
    """PDF cautabil sau doar-imagine prin OCR Editor: un proiect temporar cu
    fisierele, recunoasterea (numai pentru cautabil) si exportul PDF."""
    from app.core.export.base import default_service
    from app.core.model import AutoProcessMode, ExportFormat
    from app.core.ocr.service import RecognitionService
    from app.core.project import OcrProject

    project = OcrProject.create(context=context)
    try:
        _, errors = project.add_images(list(files), auto_process=AutoProcessMode.NONE)
        if errors:
            raise errors[0][1]
        if options.searchable:
            RecognitionService(project, engine=engine).recognize_pages()
        fmt = ExportFormat.PDFA if options.pdfa_version is not None else ExportFormat.PDF
        default_service().export(project.pages, target, fmt, options)
    finally:
        project.close()
