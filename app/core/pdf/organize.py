"""Operatiile pe paginile unui PDF (faza 8): E-004…E-022, E-035, E-036.

Contractul e `PageOrganizer` din SPEC_05. ID-urile din docstring-urile SPEC_05
sunt decalate fata de SPEC_01; aici se folosesc cele din SPEC_01, care decid.

Modificarile se fac in vederea pikepdf a documentului, apoi `document._changed()`
reciteste PDFium din memorie. Pozitiile de inserare (`at`) sunt numarul paginii
inaintea careia se pune continutul nou: 1 = inainte de prima, `n + 1` = dupa
ultima (E-016). Coordonatele cadrului de decupare sunt in puncte, cu originea in
coltul stanga-sus al MediaBox-ului paginii nerotite, ca in restul PDF Editor-ului.
"""

from __future__ import annotations

import io
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.errors import LastPageError, PasswordRequiredError, WrongPasswordError
from app.core.model import PasswordCallback, Rect

if TYPE_CHECKING:
    from app.core.context import AppContext
    from app.core.export.base import ExportOptions
    from app.core.images.scanner import ScannerService, ScanSettings
    from app.core.pdf.document import PdfDocument

POSITIONS = ("first", "last", "after")
"""E-016: inainte de prima pagina, dupa ultima, dupa pagina selectata."""

BLANK_THRESHOLD = 0.98
"""E-021: ca in OCR Editor (`project.BLANK_THRESHOLD`): pagina e goala cand
`blank_score` >= prag."""

_INHERITED = ("/Resources", "/MediaBox", "/CropBox", "/Rotate")
"""Cheile pe care o pagina le poate mosteni din arborele de pagini."""

WARN_NOTES = "notes"
"""E-022: pagina are adnotari (note de mana, comentarii)."""
WARN_IMAGES = "images"
"""E-022: pagina are imagini puse peste pagina (nu doar imaginea scanarii)."""


@dataclass
class PageRange:
    """Rezultatul E-004: paginile alese si numerele ignorate (din afara
    documentului), pentru avertisment."""

    pages: tuple[int, ...]
    ignored: tuple[int, ...] = field(default_factory=tuple)


# E-016
def insertion_point(position: str, page_count: int, selected: int | None = None) -> int:
    """Pozitia de inserare `at` pentru cele trei variante din dialog."""
    if position == "first":
        return 1
    if position == "last":
        return page_count + 1
    if position == "after":
        if selected is None or not 1 <= selected <= page_count:
            raise ValueError(f"pagina dupa care se insereaza: 1..{page_count}")
        return selected + 1
    raise ValueError(f"pozitie necunoscuta: {position} ({POSITIONS})")


# E-004
def parse_range(text: str, page_count: int) -> PageRange:
    """`2, 3, 5-7`, sau `Even Pages`, `Odd Pages`, `All Pages` (si `even`,
    `odd`, `all`, fara deosebire de majuscule). Spatiile se accepta, intervalele
    inversate se normalizeaza, numerele din afara documentului se ignora si se
    raporteaza. Ordinea e crescatoare, fara dubluri. Un text care nu e nici
    numar, nici interval → `ValueError`."""
    words = " ".join(text.lower().split())
    named = {"all pages": "all", "all": "all", "even pages": "even", "even": "even",
             "odd pages": "odd", "odd": "odd"}
    if words in named:
        kind = named[words]
        everything = range(1, page_count + 1)
        if kind == "all":
            return PageRange(tuple(everything))
        parity = 0 if kind == "even" else 1
        return PageRange(tuple(n for n in everything if n % 2 == parity))
    chosen: set[int] = set()
    ignored: set[int] = set()
    for raw in words.replace(";", ",").split(","):
        part = raw.replace(" ", "")
        if not part:
            continue
        if "-" in part:
            first, _, last = part.partition("-")
            if not (first.isdigit() and last.isdigit()):
                raise ValueError(f"interval invalid: {part!r}")
            low, high = sorted((int(first), int(last)))
            numbers = range(low, high + 1)
        elif part.isdigit():
            numbers = range(int(part), int(part) + 1)
        else:
            raise ValueError(f"numar de pagina invalid: {part!r}")
        for n in numbers:
            (chosen if 1 <= n <= page_count else ignored).add(n)
    if not chosen and not ignored:
        raise ValueError("nu e scrisa nicio pagina")
    return PageRange(tuple(sorted(chosen)), tuple(sorted(ignored)))


def format_range(pages: Sequence[int]) -> str:
    """Pentru campul `Selected pages` (E-103): `2, 5, 7-9`. Doua pagini
    consecutive raman separate (`2, 3`), de la trei se scrie interval."""
    out: list[str] = []
    ordered = sorted(set(pages))
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        if j - i >= 2:
            out.append(f"{ordered[i]}-{ordered[j]}")
        else:
            out.extend(str(n) for n in ordered[i:j + 1])
        i = j + 1
    return ", ".join(out)


def open_source_pdf(source: Path, password: PasswordCallback | None) -> pikepdf.Pdf:
    """E-014: un PDF sursa; daca e protejat, se cere parola prin `password`
    pana cand e corecta sau se renunta (None)."""
    attempt = ""
    tried = False
    while True:
        try:
            return pikepdf.open(source, password=attempt)
        except pikepdf.PasswordError:
            pass
        if password is None:
            raise PasswordRequiredError("PDF-ul cere parola", path=str(source))
        answer = password(str(source))
        if answer is None:
            if tried:
                raise WrongPasswordError("parola nu e corecta", path=str(source))
            raise PasswordRequiredError("PDF-ul cere parola", path=str(source))
        attempt, tried = answer, True


class PageOrganizer:
    """E-001…E-040. Operatii pe pagini de PDF."""

    def __init__(self, document: PdfDocument) -> None:
        self.document = document

    # --- utilitare --------------------------------------------------------------------

    @property
    def page_count(self) -> int:
        return self.document.page_count

    def _pdf(self) -> pikepdf.Pdf:
        return self.document._pike()

    def _check(self, pages: Sequence[int]) -> list[int]:
        self.document._check_pages(pages)
        return sorted(set(pages))

    def _check_at(self, at: int) -> None:
        if not 1 <= at <= self.page_count + 1:
            raise ValueError(f"pozitie de inserare invalida: {at} (1..{self.page_count + 1})")

    def _done(self, *, structure: bool = True) -> None:
        """Dupa o modificare: semnele de carte catre pagini disparute se scot,
        stratul OCR temporar (B-028) se uita daca s-a schimbat ordinea."""
        if structure:
            _prune_outline(self._pdf())
            self.document._ocr_layer.clear()
        self.document._changed()

    # E-004
    def parse_page_range(self, text: str, page_count: int | None = None) -> tuple[int, ...]:
        """Contractul SPEC_05: numai paginile; avertismentul e in `parse_range`."""
        return parse_range(text, self.page_count if page_count is None else page_count).pages

    # E-005
    def delete(self, pages: Sequence[int]) -> None:
        """Paginile dispar, restul se renumeroteaza. Nu se pot sterge toate:
        `LastPageError`, iar documentul ramane neschimbat."""
        chosen = self._check(pages)
        if len(chosen) >= self.page_count:
            raise LastPageError("documentul trebuie sa pastreze cel putin o pagina",
                                pages=len(chosen))
        pdf = self._pdf()
        for n in reversed(chosen):
            del pdf.pages[n - 1]
        self._done()

    # E-006, E-007
    def rotate(self, pages: Sequence[int], degrees: int) -> None:
        """In sensul acelor de ceasornic (negativ = invers), multiplu de 90.
        Rotatia se scrie in pagina (/Rotate)."""
        if degrees % 90:
            raise ValueError("rotatia trebuie sa fie multiplu de 90 de grade")
        pdf = self._pdf()
        for n in self._check(pages):
            page = pdf.pages[n - 1].obj
            page.Rotate = (int(_inherited(page, "/Rotate") or 0) + degrees) % 360
        self._done(structure=False)

    # E-008
    def correct_orientation(self, pages: Sequence[int], *,
                            detect: Callable[[Path], int] | None = None) -> dict[int, int]:
        """Rotatia aplicata fiecarei pagini, detectata din text (OSD Tesseract,
        ca X-017 in OCR Editor). O pagina fara text (sau fara Tesseract) ramane
        neschimbata si nu apare in rezultat. `detect` e adaugat fata de SPEC_05,
        pentru teste: primeste imaginea paginii asa cum se vede si intoarce cu cat
        trebuie rotita, in sensul acelor de ceasornic."""
        chosen = self._check(pages)
        detect = detect or _detect_orientation
        applied: dict[int, int] = {}
        with tempfile.TemporaryDirectory(prefix="doculens-orient-") as tmp:
            for n in chosen:
                image = Path(tmp) / f"{n}.png"
                image.write_bytes(self.document.render_page(n, 2.0, annotations=False))
                angle = int(detect(image)) % 360
                if angle % 90:
                    continue
                if angle:
                    applied[n] = angle
        pdf = self._pdf()
        for n, angle in applied.items():
            page = pdf.pages[n - 1].obj
            page.Rotate = (int(_inherited(page, "/Rotate") or 0) + angle) % 360
        if applied:
            self._done(structure=False)
        return applied

    # E-010, E-011
    def crop(self, pages: Sequence[int], rect: Rect | Mapping[int, Rect], *,
             same_for_all: bool = True) -> None:
        """Decuparea (CropBox). `same_for_all`: un singur cadru pentru toate
        paginile alese; altfel `rect` e un dictionar pagina → cadru, cate unul
        per pagina (E-010, cele doua optiuni)."""
        from app.core.pdf.text import page_geometry, to_pdf_rect

        chosen = self._check(pages)
        if same_for_all:
            if not isinstance(rect, Rect):
                raise TypeError("un singur cadru: `rect` e un Rect")
            frames = {n: rect for n in chosen}
        else:
            if not isinstance(rect, Mapping):
                raise TypeError("cadre separate: `rect` e un dictionar pagina → Rect")
            missing = [n for n in chosen if n not in rect]
            if missing:
                raise ValueError(f"lipseste cadrul pentru paginile {missing}")
            frames = {n: rect[n] for n in chosen}
        pdf = self._pdf()
        boxes = {}
        for n, frame in frames.items():
            page = pdf.pages[n - 1]
            _materialize(page.obj)
            mx0, my0, mx1, my1 = (float(v) for v in page.mediabox)
            x0, y0, x1, y1 = to_pdf_rect(page_geometry(page), frame)
            x0, x1 = max(x0, min(mx0, mx1)), min(x1, max(mx0, mx1))
            y0, y1 = max(y0, min(my0, my1)), min(y1, max(my0, my1))
            if x1 - x0 < 1 or y1 - y0 < 1:
                raise ValueError(f"cadrul de decupare e in afara paginii {n}")
            boxes[n] = (x0, y0, x1, y1)
        for n, box in boxes.items():
            pdf.pages[n - 1].obj.CropBox = pikepdf.Array(box)
        self._done(structure=False)

    # E-013
    def add_blank(self, at: int, size: tuple[float, float] | None = None) -> None:
        """Pagina goala inaintea paginii `at`. Implicit, de marimea paginii de
        langa ea (cea dinainte, sau prima)."""
        self._check_at(at)
        pdf = self._pdf()
        if size is None:
            if self.page_count:
                near = pdf.pages[max(at - 2, 0)]
                x0, y0, x1, y1 = (float(v) for v in near.mediabox)
                size = (abs(x1 - x0), abs(y1 - y0))
            else:
                size = (595.0, 842.0)  # A4
        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError("dimensiunea paginii trebuie sa fie pozitiva")
        page = pikepdf.Page(pikepdf.Dictionary(
            Type=pikepdf.Name.Page, MediaBox=[0, 0, width, height],
            Contents=pdf.make_stream(b""), Resources=pikepdf.Dictionary()))
        pdf.pages.insert(at - 1, page)
        self._done()

    # E-014, E-016
    def insert_from_pdf(self, source: Path, *, source_pages: Sequence[int] | None = None,
                        at: int, password: PasswordCallback | None = None) -> int:
        """Paginile unui PDF, copiate fara procesare de imagine. Intoarce numarul
        de pagini inserate. PDF protejat → se cere parola (E-014)."""
        self._check_at(at)
        with open_source_pdf(Path(source), password) as src:
            numbers = _source_numbers(source_pages, len(src.pages))
            pdf = self._pdf()
            for i, n in enumerate(numbers):
                pdf.pages.insert(at - 1 + i, src.pages[n - 1])
            self._done()
        return len(numbers)

    # E-015
    def insert_from_file(self, source: Path, *, source_pages: Sequence[int] | None = None,
                         at: int, split_facing_pages: bool = False,
                         options: ExportOptions | None = None,
                         context: AppContext | None = None, engine: Any = None) -> int:
        """Orice fisier acceptat de OCR Editor (imagini, PDF, ...), trecut prin
        procesarea de imagine (mai lent decat E-014): preprocesarea recomandata,
        impartirea paginilor alaturate la cerere, apoi PDF dupa `options`
        (E-038: calitatea imaginii, MRC, textul recunoscut). `split_facing_pages`,
        `options`, `context` si `engine` sunt adaugate fata de SPEC_05."""
        self._check_at(at)
        data = files_to_pdf([Path(source)], source_pages=source_pages,
                            split_facing_pages=split_facing_pages, options=options,
                            context=context, engine=engine)
        return self._insert_bytes(data, at)

    # E-017
    def insert_from_scanner(self, settings: ScanSettings, at: int, *,
                            service: ScannerService, options: ExportOptions | None = None,
                            context: AppContext | None = None, engine: Any = None) -> int:
        """Paginile scanate, procesate ca la E-015, inaintea paginii `at`.
        `service` (driverul de scanare) e adaugat fata de SPEC_05."""
        from app.core.images.scanner import ScanSession

        self._check_at(at)
        images, _warnings = ScanSession(service).acquire(settings)
        if not images:
            return 0
        data = files_to_pdf([img.path for img in images], options=options,
                            context=context, engine=engine)
        return self._insert_bytes(data, at)

    def _insert_bytes(self, data: bytes, at: int) -> int:
        with pikepdf.open(io.BytesIO(data)) as src:
            pdf = self._pdf()
            for i, page in enumerate(src.pages):
                pdf.pages.insert(at - 1 + i, page)
            count = len(src.pages)
            self._done()
        return count

    # E-018, E-019
    def move(self, pages: Sequence[int], to: int) -> list[int]:
        """Paginile alese se muta, in ordinea lor, inaintea paginii `to` (din
        numerotarea de dinainte de mutare; `n + 1` = la sfarsit). Intoarce noile
        lor numere."""
        chosen = self._check(pages)
        self._check_at(to)
        total = self.page_count
        rest = [n for n in range(1, total + 1) if n not in chosen]
        cut = sum(1 for n in rest if n < to)
        order = rest[:cut] + chosen + rest[cut:]
        if order != list(range(1, total + 1)):
            _reorder(self._pdf(), order)
            self._done()
        return list(range(cut + 1, cut + 1 + len(chosen)))

    # E-020
    def replace(self, target_pages: Sequence[int], source: Path,
                source_pages: Sequence[int], *,
                password: PasswordCallback | None = None) -> None:
        """Paginile `target_pages` se inlocuiesc, in ordine, cu `source_pages`
        din `source`. Lungimi diferite → `ValueError` cu ambele lungimi."""
        targets = list(target_pages)
        self.document._check_pages(targets)
        if len(targets) != len(source_pages):
            raise ValueError(
                f"intervalele au lungimi diferite: {len(targets)} pagini de inlocuit, "
                f"{len(source_pages)} pagini sursa", len(targets), len(source_pages))
        with open_source_pdf(Path(source), password) as src:
            numbers = _source_numbers(source_pages, len(src.pages))
            pdf = self._pdf()
            for target, n in zip(targets, numbers, strict=True):
                pdf.pages.insert(target - 1, src.pages[n - 1])
                del pdf.pages[target]
            self._done()

    # E-021
    def blank_scores(self, pages: Sequence[int] | None = None) -> dict[int, float]:
        """`blank_score` pe pagina (0 = plina, 1 = goala), din randare, fara
        adnotari (acestea se semnaleaza separat, E-022)."""
        from app.core.project import _blank_score

        numbers = range(1, self.page_count + 1) if pages is None else self._check(pages)
        return {n: _blank_score(io.BytesIO(  # type: ignore[arg-type]
            self.document.render_page(n, 0.5, annotations=False))) for n in numbers}

    def find_blank(self, threshold: float | None = None) -> list[int]:
        """Paginile goale. `threshold` intre 0 si 1 (implicit
        `BLANK_THRESHOLD`); mai mic = mai permisiv."""
        limit = BLANK_THRESHOLD if threshold is None else float(threshold)
        if not 0 <= limit <= 1:
            raise ValueError("pragul e intre 0 si 1")
        return [n for n, score in self.blank_scores().items() if score >= limit]

    # E-022
    def content_warnings(self, pages: Sequence[int]) -> dict[int, list[str]]:
        """Inainte de stergerea paginilor goale: ce pagini au note de mana
        (adnotari) sau imagini puse peste pagina."""
        pdf = self._pdf()
        out: dict[int, list[str]] = {}
        for n in self._check(pages):
            page = pdf.pages[n - 1]
            found: list[str] = []
            annots = page.obj.get("/Annots")
            if annots is not None and any(
                    a.get("/Subtype") not in ("/Link", "/Widget", "/Popup") for a in annots):
                found.append(WARN_NOTES)
            if _placed_images(page):
                found.append(WARN_IMAGES)
            if found:
                out[n] = found
        return out

    # E-036, E-037
    def extract_to_new_document(self, pages: Sequence[int]) -> PdfDocument:
        """Un document nou, nesalvat (`path` None), cu paginile alese."""
        from app.core.pdf.document import PdfDocument

        chosen = list(pages)
        self.document._check_pages(chosen)
        pdf = self._pdf()
        part = pikepdf.new()
        for n in chosen:
            part.pages.append(pdf.pages[n - 1])
        out = io.BytesIO()
        part.save(out)
        document = PdfDocument._from_bytes(out.getvalue(), None)
        document.is_modified = True
        document._revision = 1
        return document

    # E-035
    def enhance_images(self, pages: Sequence[int], settings: Any = None, *,
                       options: ExportOptions | None = None,
                       context: AppContext | None = None, engine: Any = None) -> None:
        """Paginile alese se refac din imaginea lor, trecuta prin preprocesare
        (orientarea, indreptarea si rezolutia, dupa `settings`, un
        `PreprocessSettings`), cu stratul de text recunoscut daca `options`
        o cer. Paginile se inlocuiesc pe loc."""
        chosen = self._check(pages)
        with tempfile.TemporaryDirectory(prefix="doculens-enhance-") as tmp:
            images = []
            for n in chosen:
                image = Path(tmp) / f"{n:05d}.png"
                image.write_bytes(self.document.render_page(n, 300 / 72, annotations=False))
                images.append(image)
            data = files_to_pdf(images, preprocess=settings, options=options,
                                context=context, engine=engine)
        with pikepdf.open(io.BytesIO(data)) as src:
            if len(src.pages) != len(chosen):
                raise ValueError("preprocesarea a schimbat numarul de pagini")
            pdf = self._pdf()
            for n, page in zip(chosen, src.pages, strict=True):
                pdf.pages.insert(n - 1, page)
                del pdf.pages[n]
            self._done()


# --- functii ajutatoare ------------------------------------------------------------------


def files_to_pdf(files: Sequence[Path], *, source_pages: Sequence[int] | None = None,
                 split_facing_pages: bool = False, preprocess: Any = None,
                 options: ExportOptions | None = None, context: AppContext | None = None,
                 engine: Any = None) -> bytes:
    """E-015, E-017, E-035: fisierele trec prin proiectul OCR (preprocesarea
    recomandata, dupa `preprocess` daca e dat), apoi PDF dupa `options`.
    `options` lipsa = PDF doar-imagine, calitatea implicita."""
    from app.core.export.base import ExportOptions, default_service
    from app.core.model import AutoProcessMode, ExportFormat
    from app.core.ocr.service import RecognitionService
    from app.core.project import OcrProject
    from app.core.settings import _PREPROCESS_KEYS

    options = options or ExportOptions(searchable=False)
    project = OcrProject.create(context=context)
    try:
        if preprocess is not None:
            for name, key in _PREPROCESS_KEYS.items():
                project.settings().set(key, bool(getattr(preprocess, name)))
        project.settings().set("image.split_facing_pages", bool(
            split_facing_pages or getattr(preprocess, "split_facing_pages", False)))
        _, errors = project.add_images(list(files), auto_process=AutoProcessMode.NONE)
        if errors:
            raise errors[0][1]
        if source_pages is not None:
            numbers = _source_numbers(source_pages, len(project.pages))
            drop = [n for n in range(1, len(project.pages) + 1) if n not in numbers]
            if drop:
                project.delete_pages(drop)
        project.preprocess_pages(list(range(1, len(project.pages) + 1)))
        if options.searchable:
            RecognitionService(project, engine=engine).recognize_pages()
        fmt = ExportFormat.PDFA if options.pdfa_version is not None else ExportFormat.PDF
        with tempfile.TemporaryDirectory(prefix="doculens-insert-") as tmp:
            target = Path(tmp) / "pagini.pdf"
            default_service().export(project.pages, target, fmt, options)
            return target.read_bytes()
    finally:
        project.close()


def _source_numbers(source_pages: Sequence[int] | None, total: int) -> list[int]:
    if source_pages is None:
        return list(range(1, total + 1))
    numbers = list(source_pages)
    if not numbers:
        raise ValueError("nu e aleasa nicio pagina din sursa")
    bad = [n for n in numbers if not 1 <= n <= total]
    if bad:
        raise ValueError(f"paginile {bad} nu exista in sursa (1..{total})")
    return numbers


def _inherited(node: Any, key: str) -> Any:
    """O cheie a paginii, cautata si in parintii ei (atributele mostenite)."""
    for _ in range(64):
        if node is None:
            return None
        if key in node:
            return node[key]
        node = node.get("/Parent")
    return None


def _materialize(page: Any) -> None:
    """Atributele mostenite se copiaza in pagina, ca ea sa poata fi mutata."""
    for key in _INHERITED:
        if key not in page:
            value = _inherited(page, key)
            if value is not None:
                page[key] = value


def _reorder(pdf: pikepdf.Pdf, order: Sequence[int]) -> None:
    """Paginile in ordinea `order` (de la 1), prin lista de pagini pikepdf, ca
    evidenta ei interna sa ramana corecta. Atributele mostenite se copiaza
    intai in pagini."""
    pages = [pdf.pages[n - 1] for n in order]
    for page in pages:
        _materialize(page.obj)
    while len(pdf.pages):
        del pdf.pages[-1]
    for page in pages:
        pdf.pages.append(page)


def _prune_outline(pdf: pikepdf.Pdf) -> None:
    """Semnele de carte catre pagini care nu mai sunt in document se scot;
    copiii lor urca un nivel."""
    if "/Outlines" not in pdf.Root:
        return
    present = {page.objgen for page in pdf.pages}

    def target(item: pikepdf.OutlineItem) -> Any:
        dest = item.destination
        if dest is None and item.action is not None and item.action.get("/S") == "/GoTo":
            dest = item.action.get("/D")
        if isinstance(dest, pikepdf.Array) and len(dest) and \
                isinstance(dest[0], pikepdf.Dictionary):
            return dest[0].objgen
        return None

    def clean(items: list[pikepdf.OutlineItem]) -> list[pikepdf.OutlineItem]:
        out: list[pikepdf.OutlineItem] = []
        for item in items:
            item.children[:] = clean(list(item.children))
            page = target(item)
            if page is not None and page not in present:
                out.extend(item.children)
            else:
                out.append(item)
        return out

    with pdf.open_outline() as outline:
        outline.root[:] = clean(list(outline.root))


def _placed_images(page: pikepdf.Page) -> bool:
    """E-022: imagini puse peste pagina. O singura imagine e scanarea paginii
    si nu se numara; doua sau mai multe inseamna continut adaugat."""
    resources = page.obj.get("/Resources")
    xobjects = resources.get("/XObject") if resources is not None else None
    if xobjects is None:
        return False
    images = [k for k, v in xobjects.items() if v.get("/Subtype") == "/Image"]
    return len(images) >= 2


def _detect_orientation(image: Path) -> int:
    from app.core.layout.analyzer import LayoutAnalyzer

    return LayoutAnalyzer().detect_orientation(
        SimpleNamespace(image_path=image, rotation=0))  # type: ignore[arg-type]
