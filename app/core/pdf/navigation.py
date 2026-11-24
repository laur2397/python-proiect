"""Navigarea si siguranta in PDF Editor (faza 7, pasul 7.5): B-021, B-023,
B-034…B-042.

- semnele de carte ca arbore (B-021);
- atasamentele: lista, cu marcajul celor executabile, si extragerea lor
  (B-023; confirmarea `Allow`/`Cancel` inainte de deschidere, B-034, o cere
  interfata);
- linkurile din pagina si detectia automata a adreselor web si de e-mail din
  text (B-035, B-042);
- JavaScript-ul: unde apare in document (banda de notificare, B-037), regula
  de activare (B-038…B-040) si limita de timp (B-041).

Motorul JavaScript e QuickJS (faza 11): `javascript.py` ruleaza scripturile, cu
limita de 2 secunde a motorului, iar `form_actions.py` le leaga de formular si de
document. `run_script` de aici ramane limita generica, pe fir separat, pentru un
`runner` oarecare.

Coordonatele: puncte, originea sus-stanga a MediaBox-ului (ca in `text.py`).
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.model import BookmarkData, Rect
from app.core.pdf.text import (
    _dest_page,
    _named_dest,
    from_pdf_rect,
    page_geometry,
    to_pdf_rect,
)

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

# --- semnele de carte (B-021) ---------------------------------------------------------


def _target_y(item: Any, pdf: pikepdf.Pdf, page: int) -> float | None:
    """Pozitia verticala a destinatiei (puncte de sus), pentru /XYZ si /FitH."""
    dest = item.destination
    if dest is None and item.action is not None and item.action.get("/S") == "/GoTo":
        dest = item.action.get("/D")
    if isinstance(dest, (pikepdf.String, pikepdf.Name, str)):
        dest = _named_dest(pdf, str(dest).lstrip("/"))
    if isinstance(dest, pikepdf.Dictionary):
        dest = dest.get("/D")
    if not isinstance(dest, pikepdf.Array) or len(dest) < 3:
        return None
    mode = str(dest[1])
    index = 3 if mode == "/XYZ" else 2 if mode in ("/FitH", "/FitBH") else None
    if index is None or len(dest) <= index:
        return None
    try:
        value = float(dest[index])
    except (TypeError, ValueError):
        return None  # /XYZ cu null: pozitia ramane cea curenta
    _left, bottom, height = page_geometry(pdf.pages[page - 1])
    return max(0.0, bottom + height - value)


def bookmarks(document: PdfDocument) -> list[BookmarkData]:
    """B-021: arborele semnelor de carte. `id` = pozitia in parcurgerea in
    adancime (de la 1), valabila cat documentul nu se schimba; `target_page`
    None = fara destinatie in document."""
    pdf = document._pike()
    pages = {page.objgen: i for i, page in enumerate(pdf.pages, start=1)}
    counter = iter(range(1, 10_000_000))

    def walk(items: Any, level: int) -> list[BookmarkData]:
        out = []
        for item in items:
            page = _dest_page(item, pages, pdf)
            node = BookmarkData(next(counter), str(item.title or ""), level, page or None,
                                _target_y(item, pdf, page) if page else None)
            node.children = walk(item.children, level + 1)
            out.append(node)
        return out

    try:
        with pdf.open_outline() as outline:
            return walk(outline.root, 1)
    except (pikepdf.PdfError, pikepdf.OutlineStructureError):
        return []


# --- atasamentele (B-023, B-034) ------------------------------------------------------

EXECUTABLE_EXTENSIONS = frozenset({
    ".exe", ".com", ".bat", ".cmd", ".msi", ".msp", ".scr", ".pif", ".cpl", ".dll",
    ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta", ".jar",
    ".lnk", ".reg", ".sh", ".command", ".app", ".py", ".pl", ".rb",
})
"""F-048: fisierele care pot rula cod la deschidere; interfata avertizeaza."""


def is_executable(name: str) -> bool:
    return Path(name).suffix.lower() in EXECUTABLE_EXTENSIONS


def attachments(document: PdfDocument) -> list[tuple[str, int, bool]]:
    """B-023: (nume, dimensiune in octeti, e executabil), dupa nume."""
    out = []
    for name, spec in document._pike().attachments.items():
        try:
            size = len(spec.get_file().read_bytes())
        except (pikepdf.PdfError, KeyError, AttributeError):
            size = 0
        out.append((str(name), size, is_executable(str(spec.filename or name))))
    return sorted(out, key=lambda item: item[0].casefold())


def extract_attachment(document: PdfDocument, name: str, to: Path) -> Path:
    """Scrie atasamentul `name` la `to` (fisier; un folder primeste numele
    atasamentului). Interfata confirma inainte de deschidere (B-034)."""
    files = document._pike().attachments
    if name not in files:
        raise KeyError(name)
    target = Path(to)
    if target.is_dir():
        target = target / Path(name).name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(files[name].get_file().read_bytes())
    return target


# --- linkurile (B-035, B-042) ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PageLink:
    rects: tuple[Rect, ...]
    uri: str | None = None
    """Adresa externa (http, https, mailto, file); interfata confirma inainte (B-035)."""
    target_page: int | None = None
    """Destinatia in document."""
    detected: bool = False
    """B-042: gasit in text, nu link al documentului."""


@dataclass
class _Holder:
    """Un obiect cu `destination` si `action`, ca un semn de carte, pentru
    `_dest_page`."""

    destination: Any
    action: Any


def page_links(document: PdfDocument, number: int) -> list[PageLink]:
    """Linkurile documentului de pe pagina (adnotarile /Link)."""
    pdf = document._pike()
    page = pdf.pages[number - 1]
    geo = page_geometry(page)
    pages = {p.objgen: i for i, p in enumerate(pdf.pages, start=1)}
    out = []
    for annot in page.obj.get("/Annots", None) or []:
        if annot.get("/Subtype") != pikepdf.Name.Link or "/Rect" not in annot:
            continue
        rect = from_pdf_rect(geo, annot.Rect)
        action = annot.get("/A")
        kind = action.get("/S") if isinstance(action, pikepdf.Dictionary) else None
        uri, target = None, None
        if kind == "/URI":
            uri = str(action.get("/URI", "")) or None
        elif kind == "/Launch":
            spec = action.get("/F")
            path = str(spec.get("/F", "")) if isinstance(spec, pikepdf.Dictionary) \
                else str(spec or "")
            uri = file_uri(path) if path else None
        else:
            target = _dest_page(_Holder(annot.get("/Dest"), action), pages, pdf) or None
        out.append(PageLink((rect,), uri, target))
    return out


_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"]+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TRAILING = ".,;:!?)]}'\""


# B-042
def detect_links(document: PdfDocument, number: int) -> list[PageLink]:
    """Adresele web si de e-mail din textul paginii, cu dreptunghiurile lor.
    `www.` primeste `http://`, e-mailul `mailto:` (F-027)."""
    page = document.page_text(number)  # cu stratul temporar (B-028)
    text = page.text
    found: list[tuple[int, int, str]] = []
    for match in _URL.finditer(text):
        value = match.group(0).rstrip(_TRAILING)
        found.append((match.start(), len(value),
                      value if "://" in value else "http://" + value))
    taken = [range(start, start + length) for start, length, _uri in found]
    for match in _EMAIL.finditer(text):
        if any(match.start() in r for r in taken):
            continue
        value = match.group(0).rstrip(_TRAILING)
        found.append((match.start(), len(value), "mailto:" + value))
    found.sort()
    return [PageLink(tuple(page.span_rects(start, length)), uri, detected=True)
            for start, length, uri in found]


# --- JavaScript (B-037…B-041) ---------------------------------------------------------

SCRIPT_TIMEOUT_S = 2.0
"""B-041: un script care depaseste 2 secunde se opreste si se noteaza."""


def _is_js(action: Any) -> bool:
    return isinstance(action, pikepdf.Dictionary) and action.get("/S") == "/JavaScript"


def _aa_has_js(aa: Any) -> bool:
    return isinstance(aa, pikepdf.Dictionary) and any(_is_js(aa[k]) for k in aa)


def javascript_locations(document: PdfDocument) -> list[str]:
    """B-037: unde apare JavaScript in document (gol = fara JavaScript). Valorile
    sunt descrieri tehnice pentru jurnal, nu text de interfata."""
    pdf = document._pike()
    root = pdf.Root
    found: list[str] = []
    names = root.get("/Names")
    if isinstance(names, pikepdf.Dictionary) and "/JavaScript" in names:
        found.append("/Names/JavaScript")
    if _is_js(root.get("/OpenAction")):
        found.append("/OpenAction")
    if _aa_has_js(root.get("/AA")):
        found.append("/AA")
    for number, page in enumerate(pdf.pages, start=1):
        if _aa_has_js(page.obj.get("/AA")):
            found.append(f"page {number} /AA")
        for annot in page.obj.get("/Annots", None) or []:
            if _is_js(annot.get("/A")) or _aa_has_js(annot.get("/AA")):
                found.append(f"page {number} annotation")
                break
    form = root.get("/AcroForm")
    if isinstance(form, pikepdf.Dictionary):
        stack = list(form.get("/Fields", []))
        while stack:
            fld = stack.pop()
            if _aa_has_js(fld.get("/AA")) or _is_js(fld.get("/A")):
                found.append("/AcroForm field")
                break
            stack.extend(fld.get("/Kids", []))
    return found


def has_javascript(document: PdfDocument) -> bool:
    return bool(javascript_locations(document))


@dataclass
class ScriptPolicy:
    """B-038…B-040: cand au voie scripturile sa ruleze. Implicit nu (B-040,
    setarea `pdf.enable_javascript`). `Enable JavaScript for This Document
    Only` (B-038) activeaza numai documentul dat, cat e deschis; `... for All
    Documents` (B-039) e setarea, din dialogul Options."""

    enabled_globally: bool = False
    _documents: set[int] = field(default_factory=set)

    @classmethod
    def from_settings(cls, settings: Any) -> ScriptPolicy:
        return cls(bool(settings.get("pdf.enable_javascript")))

    def enable_for(self, document: PdfDocument) -> None:
        self._documents.add(id(document))

    def forget(self, document: PdfDocument) -> None:
        self._documents.discard(id(document))

    def allows(self, document: PdfDocument) -> bool:
        return self.enabled_globally or id(document) in self._documents


@dataclass(frozen=True, slots=True)
class ScriptOutcome:
    ran: bool
    timed_out: bool = False
    result: Any = None
    error: str | None = None


ScriptRunner = Callable[[str, threading.Event], Any]
"""Motorul: primeste codul si un eveniment de oprire, pe care il verifica."""


def run_script(code: str, runner: ScriptRunner | None, *,
               timeout: float = SCRIPT_TIMEOUT_S,
               on_timeout: Callable[[float], None] | None = None) -> ScriptOutcome:
    """B-041: ruleaza scriptul cu limita de timp. La depasire, motorul primeste
    semnalul de oprire si `on_timeout(secunde)` noteaza evenimentul. Fara
    motor (`runner` None), scriptul nu ruleaza (INCOMPLET, vezi docstringul)."""
    if runner is None:
        return ScriptOutcome(False)
    stop = threading.Event()
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box["result"] = runner(code, stop)
        except Exception as exc:  # noqa: BLE001 - eroarea scriptului se raporteaza
            box["error"] = str(exc)

    started = time.monotonic()
    thread = threading.Thread(target=work, name="pdf-script", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        stop.set()
        if on_timeout is not None:
            on_timeout(time.monotonic() - started)
        return ScriptOutcome(True, timed_out=True)
    return ScriptOutcome(True, result=box.get("result"), error=box.get("error"))


# --- editarea linkurilor (F-026…F-030) -------------------------------------------------

LINK_KINDS = ("page", "url", "email", "file")
"""F-026: o pagina din document (cu destinatie precisa) sau alta resursa."""


def validate_link_target(target: Mapping[str, Any]) -> dict[str, Any]:
    """F-026, F-027: tinta unui link. `kind` = page (cu `page` si, optional,
    `y`), url (`http://`, `https://`), email (cu prefixul `mailto:`), file (cu
    prefixul `file://`). Fara prefix → `ValueError`."""
    kind = target.get("kind")
    if kind == "destination":  # numele din SPEC_05
        kind = "page"
    if kind not in LINK_KINDS:
        raise ValueError(f"tip de link necunoscut: {kind} ({LINK_KINDS})")
    if kind == "page":
        page = int(target.get("page") or 0)
        y = target.get("y")
        return {"kind": "page", "page": page, "y": None if y is None else float(y)}
    uri = str(target.get("uri") or "").strip()
    prefix = {"url": ("http://", "https://"), "email": ("mailto:",),
              "file": ("file://",)}[kind]
    if not uri.lower().startswith(prefix) or len(uri) <= len(prefix[0]):
        raise ValueError(f"adresa trebuie sa inceapa cu {prefix[0]} (F-027)")
    return {"kind": kind, "uri": uri}


def _link_action(pdf: pikepdf.Pdf, target: dict[str, Any]) -> dict[str, Any]:
    if target["kind"] == "page":
        page = target["page"]
        if not 1 <= page <= len(pdf.pages):
            raise ValueError(f"pagina {page} nu exista (1..{len(pdf.pages)})")
        dest_page = pdf.pages[page - 1]
        if target["y"] is None:
            return {"Dest": pikepdf.Array([dest_page.obj, pikepdf.Name.Fit])}
        _left, bottom, height = page_geometry(dest_page)
        return {"Dest": pikepdf.Array([dest_page.obj, pikepdf.Name.XYZ, None,
                                       bottom + height - target["y"], None])}
    if target["kind"] == "file":
        path = target["uri"][len("file://"):]
        return {"A": pikepdf.Dictionary(S=pikepdf.Name.Launch, F=pikepdf.Dictionary(
            Type=pikepdf.Name.Filespec, F=pikepdf.String(path)))}
    return {"A": pikepdf.Dictionary(S=pikepdf.Name.URI, URI=pikepdf.String(target["uri"]))}


def _link_annots(page: pikepdf.Page) -> list[Any]:
    return [a for a in page.obj.get("/Annots", None) or []
            if a.get("/Subtype") == pikepdf.Name.Link and "/Rect" in a]


def add_link(document: PdfDocument, number: int, rect: Rect, target: Mapping[str, Any]
             ) -> None:
    """F-026: linkul (adnotare /Link fara chenar) peste zona `rect`."""
    clean = validate_link_target(target)
    if rect.w <= 0 or rect.h <= 0:
        raise ValueError("zona linkului e goala")
    pdf = document._pike()
    page = pdf.pages[number - 1]
    annot = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Link,
        Rect=pikepdf.Array(to_pdf_rect(page_geometry(page), rect)),
        Border=pikepdf.Array([0, 0, 0]), **_link_action(pdf, clean)))
    if "/Annots" not in page.obj:
        page.obj.Annots = pdf.make_indirect(pikepdf.Array())
    page.obj.Annots.append(annot)
    document._changed()


def _find_link(document: PdfDocument, number: int, rect: Rect) -> Any:
    """Linkul de pe pagina al carui dreptunghi se potriveste (cu toleranta de
    un punct) sau care contine centrul lui `rect`."""
    page = document._pike().pages[number - 1]
    geo = page_geometry(page)
    cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
    best = None
    for annot in _link_annots(page):
        r = from_pdf_rect(geo, annot.Rect)
        if max(abs(r.x - rect.x), abs(r.y - rect.y), abs(r.w - rect.w),
               abs(r.h - rect.h)) <= 1:
            return annot
        if best is None and r.x <= cx <= r.x + r.w and r.y <= cy <= r.y + r.h:
            best = annot
    if best is None:
        raise KeyError("niciun link in zona data")
    return best


def update_link(document: PdfDocument, number: int, rect: Rect,
                target: Mapping[str, Any]) -> None:
    """F-028: `Edit Link...`: tinta noua pentru linkul din zona."""
    clean = validate_link_target(target)
    annot = _find_link(document, number, rect)
    pdf = document._pike()
    for key in ("/A", "/Dest"):
        if key in annot:
            del annot[key]
    for key, value in _link_action(pdf, clean).items():
        annot[pikepdf.Name("/" + key)] = value
    document._changed()


def delete_link(document: PdfDocument, number: int, rect: Rect) -> None:
    """F-030: `Remove Link`."""
    annot = _find_link(document, number, rect)
    page = document._pike().pages[number - 1]
    page.obj.Annots = pikepdf.Array([a for a in page.obj.Annots
                                     if not _same(a, annot)])
    document._changed()


def _same(a: Any, b: Any) -> bool:
    if a.is_indirect and b.is_indirect:
        return bool(a.objgen == b.objgen)
    return bool(a.unparse() == b.unparse())


def link_target(document: PdfDocument, number: int, rect: Rect) -> dict[str, Any]:
    """Tinta linkului din zona, in forma lui `validate_link_target` (F-028,
    F-029: `Copy Link` copiaza `uri`)."""
    for link in page_links(document, number):
        r = link.rects[0]
        cx, cy = rect.x + rect.w / 2, rect.y + rect.h / 2
        if r.x <= cx <= r.x + r.w and r.y <= cy <= r.y + r.h:
            if link.uri is not None:
                low = link.uri.lower()
                kind = "email" if low.startswith("mailto:") else \
                    "file" if low.startswith("file://") else "url"
                return {"kind": kind, "uri": link.uri}
            return {"kind": "page", "page": link.target_page, "y": None}
    raise KeyError("niciun link in zona data")


# --- editarea atasamentelor (F-052) ----------------------------------------------------


def add_attachment(document: PdfDocument, path: Path, description: str = "") -> str:
    """Atasamentul nou, cu numele fisierului (unic: `nume (2).ext`)."""
    import mimetypes

    path = Path(path)
    pdf = document._pike()
    name = path.name
    stem, ext = path.stem, path.suffix
    n = 2
    while name in pdf.attachments:
        name = f"{stem} ({n}){ext}"
        n += 1
    pdf.attachments[name] = pikepdf.AttachedFileSpec(
        pdf, path.read_bytes(), filename=name, description=description,
        mime_type=mimetypes.guess_type(name)[0] or "application/octet-stream")
    document._changed()
    return name


def rename_attachment(document: PdfDocument, name: str, new_name: str) -> None:
    """F-052: continutul ramane neschimbat."""
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("numele atasamentului nu poate fi gol")
    files = document._pike().attachments
    if name not in files:
        raise KeyError(name)
    if new_name != name and new_name in files:
        raise ValueError(f"exista deja un atasament {new_name}")
    spec = files[name]
    data = spec.get_file().read_bytes()
    description = str(spec.description or "")
    del files[name]
    files[new_name] = pikepdf.AttachedFileSpec(document._pike(), data, filename=new_name,
                                               description=description)
    document._changed()


def delete_attachment(document: PdfDocument, name: str) -> None:
    files = document._pike().attachments
    if name not in files:
        raise KeyError(name)
    del files[name]
    document._changed()


def file_uri(path: str) -> str:
    """F-027: adresa `file://` a unei cai din PDF (Windows `C:\\...`, POSIX sau
    relativa), cu spatiile si diacriticele codate."""
    import re
    from pathlib import PurePosixPath, PureWindowsPath
    from urllib.parse import quote

    if re.match(r"^[A-Za-z]:[\\/]", path) or path.startswith("\\\\"):
        return PureWindowsPath(path).as_uri()
    if path.startswith("/"):
        return PurePosixPath(path).as_uri()
    return "file:" + quote(path.replace("\\", "/"))
