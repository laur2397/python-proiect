"""Actiunile campurilor de formular si scripturile lor (faza 11, pasul 11.3):
H-006, H-034, H-040…H-058, B-036…B-041.

Actiunile se scriu ca actiuni PDF standard, ca alte cititoare sa le inteleaga:
`Click` = `/A` (activarea), restul in `/AA` (`Drop` = `/D`, apasarea; `Mouse
Over` = `/E`; `Mouse Out` = `/X`; `Focus` = `/Fo`; `Focus Out` = `/Bl`). Mai
multe actiuni pe acelasi eveniment se leaga prin `/Next`. Navigarea, vizualizarea,
panourile si comenzile de fereastra sunt actiuni `/Named`, cu numele din Acrobat
unde exista (`FirstPage`, `FitWidth`, `Print`...).

Executia: `FormScripts.run_event` intoarce comenzile pentru fereastra (nucleul
nu stie de interfata), iar `FormScripts.commit` aplica o valoare noua cu
scripturile de format, validare si calcul ale formularului (H-006), numai daca
JavaScript-ul e activat (B-038…B-040).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.model import FormFieldType

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument
    from app.core.pdf.forms import FormEditor, _Field
    from app.core.pdf.javascript import ScriptResult

TRIGGER_EVENTS = ("click", "drop", "mouse_enter", "mouse_exit", "on_focus", "on_blur")
"""H-040: exact cele sase evenimente (`Click`, `Drop`, `Mouse Over`, `Mouse Out`,
`Focus`, `Focus Out`), cu valorile din SPEC_04 (`form_field_action`)."""
_EVENT_KEYS = {"drop": "/D", "mouse_enter": "/E", "mouse_exit": "/X", "on_focus": "/Fo",
               "on_blur": "/Bl"}

NAMED_ACTIONS = {
    # H-043: navigare
    "first_page": "FirstPage", "last_page": "LastPage", "next_page": "NextPage",
    "prev_page": "PrevPage", "go_back": "GoBack", "go_forward": "GoForward",
    # H-045: vizualizare
    "single_page": "SinglePage", "two_pages": "TwoPages",
    "single_page_scroll": "OneColumn", "two_pages_scroll": "TwoColumns",
    "zoom_100": "ActualSize", "fit_width": "FitWidth", "fit_page": "FitPage",
    "full_screen": "FullScreen",
    # H-046: panouri
    "toggle_attachments": "ShowHideFileAttachment", "toggle_bookmarks": "ShowHideBookmarks",
    "toggle_pages": "ShowHideThumbnails", "toggle_signatures": "ShowHideSignatures",
    # H-051…H-057: comenzi de fereastra
    "save_form_as": "SaveAs", "print_form": "Print", "close_document": "Close",
    "exit_application": "Quit", "search_document": "Find",
    "document_properties": "GeneralInfo", "scan_pages": "AddPagesFromScanner",
}
ACTION_GROUPS = {
    "navigation": ("first_page", "last_page", "next_page", "prev_page", "go_back",
                   "go_forward", "go_to_page"),
    "view": ("single_page", "two_pages", "single_page_scroll", "two_pages_scroll",
             "zoom_100", "fit_width", "fit_page", "full_screen"),
    "panels": ("toggle_attachments", "toggle_bookmarks", "toggle_pages", "toggle_signatures"),
    "other": ("open_file", "follow_link", "send_form", "reset_form", "save_form_as",
              "print_form", "close_document", "exit_application", "search_document",
              "document_properties", "scan_pages", "run_javascript"),
}
"""H-043…H-058: actiunile, in grupele din dialogul `Action`."""
ACTION_TYPES = tuple(a for group in ACTION_GROUPS.values() for a in group)

SEND_FORMATS = {"pdf": 1 << 8, "fdf": 0, "xfdf": 1 << 5, "html": 1 << 2}
"""H-049, H-108: formatul trimis si indicatorii `/SubmitForm` (SubmitPDF,
FDF implicit, XFDF, ExportFormat)."""
_EMAIL = re.compile(r"^(mailto:)?[^@\s:/]+@[^@\s/]+\.[^@\s/]+$", re.IGNORECASE)
_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:\S+$", re.IGNORECASE)
_SCRIPT_COMMANDS = {"print_form", "save_form_as", "close_document", "reset_form",
                    "go_to_page", "send_form", "focus"}


# --- validarea (H-041, H-044, H-047…H-049, H-058) ---------------------------------------


def validate_action(document: PdfDocument, event: str, action_type: str,
                    params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Parametrii actiunii, verificati. `ValueError` pentru eveniment sau actiune
    necunoscuta, pagina in afara documentului (H-044), fisier sau link gol,
    adresa de trimitere invalida (H-049)."""
    params = dict(params or {})
    if event not in TRIGGER_EVENTS:
        raise ValueError(f"eveniment necunoscut: {event}")
    if action_type == "unsupported":
        return params
    if action_type not in ACTION_TYPES:
        raise ValueError(f"actiune necunoscuta: {action_type}")
    if action_type == "go_to_page":
        page = int(params.get("page", 0))
        if not 1 <= page <= document.page_count:
            raise ValueError(f"pagina {page} nu exista (1..{document.page_count})")
        return {"page": page}
    if action_type == "open_file":
        name = str(params.get("file", "")).strip()
        if not name:
            raise ValueError("lipseste fisierul")
        return {"file": name}
    if action_type == "follow_link":
        url = str(params.get("url", "")).strip()
        if not _SCHEME.match(url):
            raise ValueError("linkul cere prefix (http://, https://, mailto:, file://)")
        return {"url": url}
    if action_type == "send_form":
        to = str(params.get("to", "")).strip()
        fmt = str(params.get("format", "pdf")).lower()
        if fmt not in SEND_FORMATS:
            raise ValueError(f"format necunoscut: {fmt}")
        if not (_EMAIL.match(to) or _URL.match(to)):
            raise ValueError("adresa de trimitere nu e valida")
        return {"to": to, "format": fmt}
    if action_type == "run_javascript":
        return {"script": str(params.get("script", ""))}
    return {}


def submit_target(to: str) -> tuple[str, str]:
    """H-049: (`email`, adresa) sau (`url`, adresa). Trimiterea la un URL ar fi o
    cerere de retea, pe care DocuLens nu o face (CLAUDE.md §6.1)."""
    to = to.strip()
    if _EMAIL.match(to):
        return "email", re.sub(r"^mailto:", "", to, flags=re.IGNORECASE)
    return "url", to


# --- scrierea si citirea actiunilor PDF ---------------------------------------------------


def _action_object(pdf: pikepdf.Pdf, action_type: str, params: Mapping[str, Any]
                   ) -> pikepdf.Dictionary:
    if action_type == "unsupported" and isinstance(params.get("object"), pikepdf.Dictionary):
        return pikepdf.Dictionary({k: v for k, v in params["object"].items()})
    action = pikepdf.Dictionary(Type=pikepdf.Name.Action)
    if action_type in NAMED_ACTIONS:
        action.S = pikepdf.Name.Named
        action.N = pikepdf.Name("/" + NAMED_ACTIONS[action_type])
    elif action_type == "go_to_page":
        action.S = pikepdf.Name.GoTo
        action.D = pikepdf.Array([pdf.pages[int(params["page"]) - 1].obj,
                                  pikepdf.Name.Fit])
    elif action_type == "open_file":
        action.S = pikepdf.Name.Launch
        action.F = pikepdf.String(str(params["file"]))
    elif action_type == "follow_link":
        action.S = pikepdf.Name.URI
        action.URI = pikepdf.String(str(params["url"]))
    elif action_type == "send_form":
        to = str(params["to"])
        if _EMAIL.match(to) and not to.lower().startswith("mailto:"):
            to = "mailto:" + to
        action.S = pikepdf.Name.SubmitForm
        action.F = pikepdf.Dictionary(FS=pikepdf.Name.URL, F=pikepdf.String(to))
        action.Flags = SEND_FORMATS[str(params.get("format", "pdf"))]
    elif action_type == "reset_form":
        action.S = pikepdf.Name.ResetForm
    elif action_type == "run_javascript":
        action.S = pikepdf.Name.JavaScript
        action.JS = pikepdf.String(str(params.get("script", "")))
    else:
        raise ValueError(f"actiune necunoscuta: {action_type}")
    return action


def _script_text(value: Any) -> str:
    if isinstance(value, pikepdf.Stream):
        return value.read_bytes().decode("utf-8", errors="replace")
    return str(value) if value is not None else ""


def _target(value: Any) -> str:
    if isinstance(value, pikepdf.Dictionary):
        return str(value.get("/F", value.get("/UF", "")))
    return str(value) if value is not None else ""


def _parse_action(pdf: pikepdf.Pdf, action: pikepdf.Dictionary) -> tuple[str, dict[str, Any]]:
    kind = action.get("/S")
    if kind == "/Named":
        name = str(action.get("/N", ""))[1:]
        for key, value in NAMED_ACTIONS.items():
            if value == name:
                return key, {}
    elif kind == "/GoTo":
        dest = action.get("/D")
        if isinstance(dest, pikepdf.Array) and len(dest) and isinstance(
                dest[0], pikepdf.Dictionary):
            for number, page in enumerate(pdf.pages, start=1):
                if page.obj.objgen == dest[0].objgen:
                    return "go_to_page", {"page": number}
    elif kind == "/Launch":
        return "open_file", {"file": _target(action.get("/F"))}
    elif kind == "/URI":
        return "follow_link", {"url": str(action.get("/URI", ""))}
    elif kind == "/SubmitForm":
        to = re.sub(r"^mailto:", "", _target(action.get("/F")), flags=re.IGNORECASE)
        flags = int(action.get("/Flags", 0))
        fmt = "pdf" if flags & SEND_FORMATS["pdf"] else "xfdf" if flags & SEND_FORMATS[
            "xfdf"] else "html" if flags & SEND_FORMATS["html"] else "fdf"
        return "send_form", {"to": to, "format": fmt}
    elif kind == "/ResetForm":
        return "reset_form", {}
    elif kind == "/JavaScript":
        return "run_javascript", {"script": _script_text(action.get("/JS"))}
    plain = pikepdf.Dictionary({k: v for k, v in action.items() if k != "/Next"})
    return "unsupported", {"subtype": str(kind or ""), "object": plain}


def _chain(pdf: pikepdf.Pdf, action: Any) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    stack = [action]
    seen: set[tuple[int, int]] = set()
    while stack:
        current = stack.pop(0)
        if isinstance(current, pikepdf.Array):
            stack[:0] = list(current)
            continue
        if not isinstance(current, pikepdf.Dictionary):
            continue
        if current.is_indirect:
            if current.objgen in seen:
                continue
            seen.add(current.objgen)
        out.append(_parse_action(pdf, current))
        if "/Next" in current:
            stack.insert(0, current.Next)
    return out


def read_actions(pdf: pikepdf.Pdf, widget: pikepdf.Object
                 ) -> list[tuple[str, str, Mapping[str, Any]]]:
    """H-034, H-040: actiunile widgetului, in ordinea evenimentelor."""
    out: list[tuple[str, str, Mapping[str, Any]]] = []
    aa = widget.get("/AA")
    aa = aa if isinstance(aa, pikepdf.Dictionary) else pikepdf.Dictionary()
    for event in TRIGGER_EVENTS:
        sources = [widget.get("/A"), aa.get("/U")] if event == "click" else \
            [aa.get(_EVENT_KEYS[event])]
        for source in sources:
            for kind, params in _chain(pdf, source):
                out.append((event, kind, params))
    return out


def write_actions(pdf: pikepdf.Pdf, widget: pikepdf.Object,
                  actions: Sequence[tuple[str, str, Mapping[str, Any]]]) -> None:
    """H-041, H-042: inlocuieste actiunile widgetului (declansatorii de camp din
    /AA — format, validare, calcul — raman)."""
    aa = widget.get("/AA")
    aa = aa if isinstance(aa, pikepdf.Dictionary) else pikepdf.Dictionary()
    for key in ("/U", *_EVENT_KEYS.values()):
        if key in aa:
            del aa[key]
    if "/A" in widget:
        del widget["/A"]
    for event in TRIGGER_EVENTS:
        chosen = [_action_object(pdf, kind, params) for e, kind, params in actions
                  if e == event]
        if not chosen:
            continue
        for i in range(len(chosen) - 2, -1, -1):  # de la coada: atribuirea copiaza
            chosen[i].Next = chosen[i + 1]
        head = pdf.make_indirect(chosen[0])
        if event == "click":
            widget.A = head
        else:
            aa[_EVENT_KEYS[event]] = head
    if len(aa):
        widget.AA = aa
    elif "/AA" in widget:
        del widget["/AA"]


# --- scripturile documentului (B-038) ------------------------------------------------------


def document_scripts(document: PdfDocument) -> list[str]:
    """Scripturile la nivel de document (`/Names/JavaScript` si `/OpenAction`),
    in ordine; definesc functiile folosite de campuri si ruleaza la deschidere."""
    pdf = document._pike()
    scripts: list[str] = []
    names = pdf.Root.get("/Names")
    tree = names.get("/JavaScript") if isinstance(names, pikepdf.Dictionary) else None
    stack = [tree]
    while stack:
        node = stack.pop(0)
        if not isinstance(node, pikepdf.Dictionary):
            continue
        entries = list(node.get("/Names", []))
        for value in entries[1::2]:
            if isinstance(value, pikepdf.Dictionary):
                scripts.append(_script_text(value.get("/JS")))
        stack.extend(node.get("/Kids", []))
    opening = pdf.Root.get("/OpenAction")
    if isinstance(opening, pikepdf.Dictionary):
        scripts.extend(p["script"] for kind, p in _chain(pdf, opening)
                       if kind == "run_javascript")
    return scripts


# --- executia (H-006, H-043…H-058) ---------------------------------------------------------


@dataclass
class ActionOutcome:
    """Ce trebuie sa faca fereastra dupa actiunile unui eveniment."""

    commands: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    """(actiune, parametri), in ordine: navigarea, vizualizarea, trimiterea..."""
    alerts: list[tuple[str, str]] = field(default_factory=list)
    """Mesajele scripturilor: (`text`, mesaj) sau (`format`/`range`, camp)."""
    accepted: bool = True
    """La `commit`: False = valoarea a fost refuzata de verificarile de format."""
    timed_out: bool = False
    """B-041: un script a depasit limita si a fost oprit."""
    errors: list[str] = field(default_factory=list)


class FormScripts:
    """Actiunile si scripturile unui formular. `enabled`: JavaScript-ul e activat
    pentru document (B-038…B-040); altfel scripturile nu ruleaza (H-006, H-058)."""

    def __init__(self, editor: FormEditor, *, enabled: bool) -> None:
        self.editor = editor
        self.enabled = enabled

    @property
    def document(self) -> PdfDocument:
        return self.editor.document

    def set_actions(self, widget_id: int,
                    actions: Sequence[tuple[str, str, Mapping[str, Any]]]) -> None:
        """H-041, H-042: actiunile noi ale widgetului, verificate."""
        from app.core.pdf.forms import _find_widget

        checked = [(e, k, validate_action(self.document, e, k, p)) for e, k, p in actions]
        pdf = self.document._pike()
        _item, _page, widget, _index = _find_widget(pdf, widget_id)
        write_actions(pdf, widget, checked)
        self.document._changed()

    def _field_values(self) -> dict[str, dict[str, Any]]:
        from app.core.pdf.forms import _text

        out: dict[str, dict[str, Any]] = {}
        for item in self.editor._fields():
            kind = item.kind
            out[item.name] = {"value": _text(item.get("/V")),
                              "type": kind.value if kind else "",
                              "readonly": bool(item.flags & 1),
                              "required": bool(item.flags & 2)}
        return out

    def _run(self, code: str, outcome: ActionOutcome, *,
             event: Mapping[str, Any] | None = None, page: int = 1) -> ScriptResult:
        from app.core.pdf.javascript import run_script

        result = run_script(code, fields=self._field_values(), event=event,
                            prelude=document_scripts(self.document),
                            num_pages=self.document.page_count, page_num=page - 1)
        if result.timed_out:
            outcome.timed_out = True
        if result.error:
            outcome.errors.append(result.error)
        outcome.alerts.extend((str(a[0]), str(a[1]) if len(a) > 1 else "")
                              for a in result.alerts)
        for command in result.commands:
            name = str(command[0])
            if name not in _SCRIPT_COMMANDS:
                continue
            params: dict[str, Any] = {}
            if name == "go_to_page":
                params = {"page": int(command[1])}
            elif name == "send_form":
                params = {"to": str(command[1]), "format": "pdf"}
            elif name == "focus":
                params = {"field": str(command[1])}
            outcome.commands.append((name, params))
        for name, value in result.changes.items():
            self._apply(name, value)
        return result

    def _apply(self, name: str, value: str) -> None:
        """O valoare data de script; scripturile pot scrie si campuri doar-citire."""
        from app.core.pdf.forms import _to_data

        try:
            item, _button = self.editor._find(name)
        except KeyError:
            return
        if item.kind in (FormFieldType.BUTTON, FormFieldType.SIGNATURE):
            return
        data = _to_data(self.document._pike(), item, *item.widgets[0], 0)
        try:
            stored = self.editor._value_for(item, data, value, None)
        except ValueError:
            return
        self.editor._store(item, stored)

    def run_event(self, widget_id: int, event: str) -> ActionOutcome:
        """H-040…H-058: actiunile widgetului pentru `event`. Scripturile ruleaza
        numai cu JavaScript-ul activat (H-058); restul devin comenzi."""
        from app.core.pdf.forms import _find_widget

        pdf = self.document._pike()
        item, page, widget, _index = _find_widget(pdf, widget_id)
        outcome = ActionOutcome()
        changed = False
        for e, kind, params in read_actions(pdf, widget):
            if e != event:
                continue
            if kind == "run_javascript":
                if self.enabled:
                    self._run(str(params.get("script", "")), outcome, page=page,
                              event={"name": event, "target_name": item.name})
                    changed = True
            elif kind != "unsupported":
                outcome.commands.append((kind, dict(params)))
        if changed:
            self._recalculate(outcome)
            self.document._changed()
        return outcome

    def run_document_open(self) -> ActionOutcome:
        """B-038: scripturile documentului, cand JavaScript-ul se activeaza."""
        outcome = ActionOutcome()
        if self.enabled and document_scripts(self.document):
            self._run("", outcome)
            self.document._changed()
        return outcome

    # --- completarea cu verificari (H-006) ---

    def _field_script(self, item: _Field, key: str) -> str | None:
        from app.core.pdf.forms import _inherited

        aa = _inherited(item.obj, "/AA")
        action = aa.get(key) if isinstance(aa, pikepdf.Dictionary) else None
        if isinstance(action, pikepdf.Dictionary) and action.get("/S") == "/JavaScript":
            return _script_text(action.get("/JS"))
        return None

    def commit(self, name: str, value: str) -> ActionOutcome:
        """H-006: valoarea noua a campului, cu scripturile lui de tastare
        (`/K`, la confirmare) si validare (`/V`), apoi calculele (`/C`, in ordinea
        din `/CO`) si formatul afisat (`/F`). Un script care refuza valoarea
        (`event.rc = false`) o lasa neschimbata. Cu JavaScript-ul dezactivat,
        verificarile nu ruleaza (H-006) si valoarea se scrie direct."""
        from app.core.pdf.forms import _text, _to_data

        item, button = self.editor._find(name)
        data = _to_data(self.document._pike(), item, *item.widgets[0], 0)
        if data.is_readonly:
            raise ValueError(f"campul {item.name!r} e doar pentru citire")
        outcome = ActionOutcome()
        stored = self.editor._value_for(item, data, value, button)
        text_value = _text(stored) if stored is not None else ""
        if self.enabled and item.kind in (FormFieldType.TEXT, FormFieldType.DROPDOWN,
                                          FormFieldType.LISTBOX):
            for key, event_name in (("/K", "Keystroke"), ("/V", "Validate")):
                script = self._field_script(item, key)
                if script is None:
                    continue
                result = self._run(script, outcome, page=item.widgets[0][0], event={
                    "name": event_name, "value": text_value, "willCommit": True,
                    "change": "", "target_name": item.name})
                if not result.rc:
                    outcome.accepted = False
                    self.document._changed()
                    return outcome
                if result.value is not None:
                    text_value = result.value
            stored = self.editor._value_for(item, data, text_value, button)
        self.editor._store(item, stored)
        if self.enabled:
            self._recalculate(outcome)
        self.document._changed()
        return outcome

    def _recalculate(self, outcome: ActionOutcome) -> None:
        """Calculele (`/C`) in ordinea din `/AcroForm /CO`, apoi formatul afisat
        (`/F`) al campurilor care il au."""
        from app.core.pdf.forms import _text

        pdf = self.document._pike()
        form = pdf.Root.get("/AcroForm")
        order = list(form.get("/CO", [])) if isinstance(form, pikepdf.Dictionary) else []
        by_obj = {i.obj.objgen: i for i in self.editor._fields() if i.obj.is_indirect}
        for node in order:
            if not isinstance(node, pikepdf.Dictionary) or not node.is_indirect:
                continue
            item = by_obj.get(node.objgen)
            script = self._field_script(item, "/C") if item is not None else None
            if item is None or script is None or not item.widgets:
                continue
            result = self._run(script, outcome, page=item.widgets[0][0], event={
                "name": "Calculate", "value": _text(item.get("/V")),
                "target_name": item.name})
            if result.rc and result.value is not None:
                self._apply(item.name, result.value)
        for item in self.editor._fields():
            script = self._field_script(item, "/F")
            value = _text(item.get("/V"))
            if script is None or not item.widgets or not value:
                continue
            result = self._run(script, outcome, page=item.widgets[0][0], event={
                "name": "Format", "value": value, "target_name": item.name})
            if result.value is not None and result.value != value:
                self.editor._refresh(item, display=result.value)


def submission(editor: FormEditor, fmt: str, folder: Path) -> Path:
    """H-049: fisierul trimis (PDF-ul completat sau datele lui in FDF, XFDF,
    HTML), scris in `folder`."""
    fmt = fmt.lower()
    if fmt not in SEND_FORMATS:
        raise ValueError(f"format necunoscut: {fmt}")
    stem = editor.document.path.stem if editor.document.path else "formular"
    target = Path(folder) / f"{stem}.{fmt}"
    if fmt == "pdf":
        editor.document.export_copy(target)
    else:
        editor.save_data(target, fmt)
    return target
