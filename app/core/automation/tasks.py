"""Sarcinile automate (faza 13, pasul 13.1): T-001…T-021, SPEC_05 §13.

O sarcina e o lista de pasi (`TaskStep`), tinuta in `automated_task` si
`automated_task_step` (app.db). Primul pas e intotdeauna `get_images`: de unde
vin imaginile (fisiere sau scaner) si in ce proiect OCR intra (nou, existent sau
cel deschis, T-006, T-007). Urmeaza, in ordine, preprocesarea, analiza, recunoasterea
si pasii de salvare sau de trimitere.

Parametrii pasilor (JSON in `parameters`):

- `get_images`: `project` (`new` / `existing` / `current`), `project_path`,
  `source` (`files` / `scan`).
- `preprocess`: fara parametri (lantul recomandat, L-010).
- `analyze`: `mode` (`auto` / `manual` / `template`), `template` (numele din
  biblioteca), `ask_template` (T-107: sablonul se cere la fiecare pornire).
- `recognize`: `languages` (lista; lipsa = limbile proiectului).
- `save`: `kind` (`document` / `images` / `project`); pentru document `format`,
  `image_only` (PDF doar-imagine), `folder`, `timestamped_subfolder` (T-011); pentru
  imagini `format`, `folder`, `multipage` (T-014); pentru proiect `path` (T-016).
- `send_to`: `kind` (`app` / `email_document` / `email_images`), `app` (T-012,
  T-013, T-015). Nucleul nu porneste programe: fisierele de trimis se intorc in
  `last_run.sent`, iar interfata le da mai departe (faza_13_pasi.md, decizia 7).

Sarcinile livrate (T-003, T-004) au ca nume chei de traducere (decizia 8); nu se
modifica si nu se sterg, se duplica.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.errors import (
    BuiltinNotEditableError,
    CoreError,
    OperationCancelledError,
    ProjectVersionError,
    ShortcutConflictError,
    TaskValidationError,
)
from app.core.model import (
    AutoProcessMode,
    CancelToken,
    ExportFormat,
    LayoutMode,
    PageStatus,
    Progress,
    ProgressCallback,
)

# SPEC_05 §13
STEP_TYPES = ("get_images", "preprocess", "analyze", "recognize", "save", "send_to")

PROJECT_MODES = ("new", "existing", "current")
"""T-006: `Create new OCR project`, `Select existing OCR project`, `Use current OCR project`."""

IMAGE_SOURCES = ("files", "scan")
"""T-007: `Open image or PDF`, `Scan`."""

ANALYZE_MODES = ("auto", "manual", "template")
"""T-009: `Analyze the layout automatically`, `Draw areas manually`, `Use an area template`."""

SAVE_KINDS = ("document", "images", "project")
"""T-011, T-014, T-016."""

SEND_KINDS = ("app", "email_document", "email_images")
"""T-012, T-013, T-015."""

DOCUMENT_FORMATS = (ExportFormat.PDF, ExportFormat.PDFA, ExportFormat.DOCX, ExportFormat.RTF,
                    ExportFormat.ODT, ExportFormat.XLSX, ExportFormat.CSV, ExportFormat.PPTX,
                    ExportFormat.TXT, ExportFormat.HTML, ExportFormat.EPUB, ExportFormat.FB2,
                    ExportFormat.DJVU)

IMAGE_FORMATS = (ExportFormat.TIFF, ExportFormat.JPEG, ExportFormat.PNG, ExportFormat.PDF)
"""T-014: formatele in care DocuLens scrie imaginile paginilor (PDF = doar-imagine)."""

MULTIPAGE_FORMATS = ("tiff", "pdf", "jb2", "jbig2", "dcx")
"""T-014: un singur fisier multipagina e posibil numai pentru acestea."""

TASK_FILE_SUFFIX = ".dltask"
TASK_FILE_FORMAT = "doculens-task"
TASK_FILE_VERSION = 1
"""T-021, faza_13_pasi.md decizia 9."""


@dataclass(slots=True)
class TaskStep:
    step_type: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AutomatedTask:
    name: str
    steps: list[TaskStep] = field(default_factory=list)
    is_builtin: bool = False
    shortcut: str | None = None
    description: str | None = None


@dataclass
class RunReport:
    """Ce a produs ultima rulare, pe langa lista intoarsa de `run`."""

    outputs: list[Path] = field(default_factory=list)
    sent: list[tuple[str, str | None, list[Path]]] = field(default_factory=list)
    """(kind, aplicatia, fisierele) pentru pasii `send_to` (decizia 7)."""
    project_path: Path | None = None


def _step(step_type: str, **params: Any) -> TaskStep:
    return TaskStep(step_type, dict(params))


def _ocr(fmt: str, *, scan: bool = False, photo: bool = False,
         image_only: bool = False) -> list[TaskStep]:
    steps = [_step("get_images", project="new", source="scan" if scan else "files")]
    if photo:
        steps.append(_step("preprocess"))
    if not image_only:
        steps += [_step("analyze", mode="auto"), _step("recognize")]
    steps.append(_step("save", kind="document", format=fmt, image_only=image_only,
                       folder="", timestamped_subfolder=False))
    return steps


# T-003, T-004: cheie (sufixul cheii de traducere) → pasii
BUILTIN_TASKS: dict[str, Callable[[], list[TaskStep]]] = {
    "convert_pdf": lambda: _ocr("pdf", image_only=True),
    "convert_searchable_pdf": lambda: _ocr("pdf"),
    "convert_word": lambda: _ocr("docx"),
    "convert_excel": lambda: _ocr("xlsx"),
    "convert_photo_word": lambda: _ocr("docx", photo=True),
    "scan_pdf": lambda: _ocr("pdf", scan=True),
    "scan_word": lambda: _ocr("docx", scan=True),
    "scan_excel": lambda: _ocr("xlsx", scan=True),
    "scan_images": lambda: [
        _step("get_images", project="new", source="scan"),
        _step("save", kind="images", format="tiff", folder="", multipage=True)],
}

BUILTIN_PREFIX = "task.builtin."


def builtin_name(key: str) -> str:
    return f"{BUILTIN_PREFIX}{key}"


# --- editarea pasilor (T-010, T-017) ----------------------------------------------

def add_step(task: AutomatedTask, step: TaskStep, index: int | None = None) -> None:
    """Adauga un pas. T-010: un pas de recunoastere fara analiza inainte aduce si
    pasul de analiza (automat), imediat inaintea lui."""
    steps = task.steps
    at = len(steps) if index is None else max(1, min(index, len(steps)))
    if step.step_type == "recognize" and not any(s.step_type == "analyze" for s in steps[:at]):
        steps.insert(at, _step("analyze", mode="auto"))
        at += 1
    steps.insert(at, step)


def remove_step(task: AutomatedTask, index: int) -> None:
    """T-017: primul pas nu se sterge. T-010: stergerea analizei sterge si
    recunoasterea."""
    if index == 0:
        raise TaskValidationError("primul pas nu se poate sterge", step_index=0,
                                  reason="first_step")
    removed = task.steps.pop(index)
    if removed.step_type == "analyze":
        task.steps[:] = [s for s in task.steps if s.step_type != "recognize"]


# --- validarea (T-018) --------------------------------------------------------------

def _fail(index: int, reason: str, message: str) -> TaskValidationError:
    return TaskValidationError(message, step_index=index, reason=reason)


def validate_steps(steps: Sequence[TaskStep]) -> None:
    """T-018: pasii trebuie sa fie coerenti; eroarea spune care pas si de ce
    (`reason` e cheia mesajului din interfata)."""
    if not steps:
        raise _fail(0, "no_steps", "sarcina nu are pasi")
    if steps[0].step_type != "get_images":
        raise _fail(0, "first_step", "primul pas trebuie sa fie obtinerea imaginilor")
    seen: set[str] = set()
    saved = False
    for i, step in enumerate(steps):
        kind, p = step.step_type, step.parameters
        if kind not in STEP_TYPES:
            raise _fail(i, "unknown_step", f"pas necunoscut: {kind}")
        if kind == "get_images":
            if i:
                raise _fail(i, "get_images_twice", "imaginile se obtin numai in primul pas")
            if p.get("project", "new") not in PROJECT_MODES:
                raise _fail(i, "project_mode", "mod de proiect necunoscut")
            if p.get("project") == "existing" and not p.get("project_path"):
                raise _fail(i, "project_path", "lipseste proiectul OCR existent")
            if p.get("source", "files") not in IMAGE_SOURCES:
                raise _fail(i, "image_source", "sursa de imagini necunoscuta")
        elif kind == "analyze":
            mode = p.get("mode", "auto")
            if mode not in ANALYZE_MODES:
                raise _fail(i, "analyze_mode", "mod de analiza necunoscut")
            if mode == "template" and not (p.get("template") or p.get("ask_template")):
                raise _fail(i, "template", "lipseste sablonul de zone")
        elif kind == "recognize":
            if "analyze" not in seen:  # T-010
                raise _fail(i, "recognize_needs_analyze", "recunoasterea cere analiza inainte")
        elif kind == "save":
            _validate_save(i, p, seen)
            saved = True
        elif kind == "send_to":
            if p.get("kind") not in SEND_KINDS:
                raise _fail(i, "send_kind", "destinatie necunoscuta")
            if p.get("kind") == "app" and not p.get("app"):
                raise _fail(i, "send_app", "lipseste aplicatia tinta")
            if not saved:
                raise _fail(i, "send_needs_save", "se trimite numai ce s-a salvat inainte")
        seen.add(kind)
    if not saved:
        raise _fail(len(steps), "no_output", "sarcina nu salveaza nimic")


def _validate_save(i: int, p: dict[str, Any], seen: set[str]) -> None:
    kind = p.get("kind")
    if kind not in SAVE_KINDS:
        raise _fail(i, "save_kind", "tip de salvare necunoscut")
    if kind == "project":
        if not p.get("path"):
            raise _fail(i, "project_path", "lipseste calea proiectului")
        return
    try:
        fmt = ExportFormat(p.get("format"))
    except ValueError:
        raise _fail(i, "format", "format necunoscut") from None
    if kind == "document":
        if fmt not in DOCUMENT_FORMATS:
            raise _fail(i, "format", "format de document necunoscut")
        image_only = bool(p.get("image_only")) and fmt in (ExportFormat.PDF, ExportFormat.PDFA)
        if not image_only and "recognize" not in seen:  # SPEC_05: textul cere recunoastere
            raise _fail(i, "save_needs_recognize", "salvarea textului cere recunoastere")
    else:
        if fmt not in IMAGE_FORMATS:
            raise _fail(i, "format", "format de imagine necunoscut")
        if p.get("multipage") and fmt.value not in MULTIPAGE_FORMATS:  # T-014
            raise _fail(i, "multipage", "fisier multipagina numai pentru TIFF, PDF, JB2,"
                        " JBIG2 si DCX")


# --- managerul (T-001…T-021) ----------------------------------------------------------

# T-001…T-021 (SPEC_05: AutomatedTaskRunner)
class AutomatedTaskRunner:
    """Sarcinile din app.db si rularea lor."""

    def __init__(self, context: Any, *, engine: Any = None) -> None:
        self._ctx = context
        self._con: sqlite3.Connection = context.app_db
        self._engine = engine
        self.last_run = RunReport()
        self._ensure_builtins()

    # --- citirea ---

    def _ensure_builtins(self) -> None:
        """T-004: sarcinile livrate exista intotdeauna (se refac daca lipsesc)."""
        with self._con:
            for key, make in BUILTIN_TASKS.items():
                name = builtin_name(key)
                if self._task_id(name) is not None:
                    continue
                cur = self._con.execute(
                    "INSERT INTO automated_task (name, is_builtin) VALUES (?, 1)", (name,))
                self._write_steps(int(cur.lastrowid or 0), make())

    def _task_id(self, name: str) -> int | None:
        row = self._con.execute("SELECT id FROM automated_task WHERE name = ?",
                                (name,)).fetchone()
        return row[0] if row else None

    def _load(self, row: tuple[Any, ...]) -> AutomatedTask:
        tid, name, description, builtin, shortcut = row
        steps = [TaskStep(kind, json.loads(params or "{}")) for kind, params in self._con.execute(
            "SELECT step_type, parameters FROM automated_task_step WHERE task_id = ?"
            " ORDER BY order_index", (tid,))]
        return AutomatedTask(name, steps, bool(builtin), shortcut, description)

    def all_tasks(self) -> list[AutomatedTask]:
        """T-001: cele livrate, in ordinea din T-004, apoi cele proprii, alfabetic."""
        rows = self._con.execute(
            "SELECT id, name, description, is_builtin, shortcut FROM automated_task").fetchall()
        order = {builtin_name(k): i for i, k in enumerate(BUILTIN_TASKS)}
        rows.sort(key=lambda r: (not r[3], order.get(r[1], 0), r[1].lower()))
        return [self._load(r) for r in rows]

    def builtin_tasks(self) -> list[AutomatedTask]:
        return [t for t in self.all_tasks() if t.is_builtin]

    def task(self, name: str) -> AutomatedTask:
        row = self._con.execute(
            "SELECT id, name, description, is_builtin, shortcut FROM automated_task"
            " WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        return self._load(row)

    # --- scrierea ---

    def validate(self, task: AutomatedTask) -> None:
        """T-005 (nume nevid) si T-018 (pasi coerenti)."""
        if not task.name.strip():
            raise TaskValidationError("numele sarcinii e gol", step_index=-1, reason="name")
        validate_steps(task.steps)

    def save(self, task: AutomatedTask, *, previous_name: str | None = None) -> None:
        """T-005, T-018: sarcina noua sau modificata (`previous_name` la redenumire).
        T-003: sarcinile livrate nu se modifica (`BuiltinNotEditableError`). T-005:
        numele e unic."""
        self.validate(task)
        old = previous_name or task.name
        tid = self._task_id(old)
        if (tid is not None and self.task(old).is_builtin) or \
                task.name.startswith(BUILTIN_PREFIX):
            raise BuiltinNotEditableError("sarcinile livrate nu se modifica, se duplica",
                                          name=old)
        other = self._task_id(task.name)
        if other is not None and other != tid:
            raise TaskValidationError("exista deja o sarcina cu acest nume", step_index=-1,
                                      reason="name_taken")
        if task.shortcut:
            self._check_shortcut(task.shortcut, tid)
        with self._con:
            if tid is None:
                tid = int(self._con.execute(
                    "INSERT INTO automated_task (name, description, shortcut) VALUES (?, ?, ?)",
                    (task.name, task.description, task.shortcut)).lastrowid or 0)
            else:
                self._con.execute(
                    "UPDATE automated_task SET name = ?, description = ?, shortcut = ?,"
                    " updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?",
                    (task.name, task.description, task.shortcut, tid))
                self._con.execute("DELETE FROM automated_task_step WHERE task_id = ?", (tid,))
            self._write_steps(tid, task.steps)

    def _write_steps(self, tid: int, steps: Sequence[TaskStep]) -> None:
        self._con.executemany(
            "INSERT INTO automated_task_step (task_id, order_index, step_type, parameters)"
            " VALUES (?, ?, ?, ?)",
            [(tid, i, s.step_type, json.dumps(s.parameters, ensure_ascii=False))
             for i, s in enumerate(steps)])

    def _free_name(self, base: str) -> str:
        name, n = base, 1
        while self._task_id(name) is not None:
            n += 1
            name = f"{base} ({n})"
        return name

    def duplicate(self, name: str, new_name: str | None = None) -> AutomatedTask:
        """T-003: orice sarcina, si cele livrate, se poate duplica; copia e a
        utilizatorului. `new_name` lipsa: numele cu un numar (`Nume (2)`)."""
        source = self.task(name)
        base = new_name or name
        if base.startswith(BUILTIN_PREFIX):
            raise TaskValidationError("copia unei sarcini livrate are nevoie de nume",
                                      step_index=-1, reason="name")
        copy = AutomatedTask(self._free_name(base), [
            TaskStep(s.step_type, dict(s.parameters)) for s in source.steps],
            description=source.description)
        with self._con:
            tid = int(self._con.execute(
                "INSERT INTO automated_task (name, description) VALUES (?, ?)",
                (copy.name, copy.description)).lastrowid or 0)
            self._write_steps(tid, copy.steps)
        return copy

    def delete(self, name: str) -> None:
        """T-003: sarcinile livrate nu se sterg."""
        task = self.task(name)
        if task.is_builtin:
            raise BuiltinNotEditableError("sarcinile livrate nu se sterg", name=name)
        with self._con:
            self._con.execute("DELETE FROM automated_task WHERE name = ?", (name,))

    def _check_shortcut(self, shortcut: str, own_id: int | None) -> None:
        row = self._con.execute("SELECT id, name FROM automated_task WHERE shortcut = ?",
                                (shortcut,)).fetchone()
        if row is not None and row[0] != own_id:
            raise ShortcutConflictError("combinatia e deja folosita", shortcut=shortcut,
                                        existing_command=row[1])
        row = self._con.execute("SELECT command_id FROM keyboard_shortcut WHERE shortcut = ?",
                                (shortcut,)).fetchone()
        if row is not None:
            raise ShortcutConflictError("combinatia e deja folosita", shortcut=shortcut,
                                        existing_command=row[0])

    def set_shortcut(self, name: str, shortcut: str | None) -> None:
        """T-020: o combinatie folosita (de alta sarcina sau de o comanda) da
        `ShortcutConflictError`. Merge si pentru sarcinile livrate."""
        tid = self._task_id(name)
        if tid is None:
            raise KeyError(name)
        shortcut = shortcut or None
        if shortcut:
            self._check_shortcut(shortcut, tid)
        with self._con:
            self._con.execute("UPDATE automated_task SET shortcut = ? WHERE id = ?",
                              (shortcut, tid))

    # --- exportul si importul (T-021) ---

    def export_task(self, name: str, path: Path) -> None:
        task = self.task(name)
        payload = {"format": TASK_FILE_FORMAT, "format_version": TASK_FILE_VERSION,
                   "name": task.name, "description": task.description,
                   "steps": [{"type": s.step_type, "parameters": s.parameters}
                             for s in task.steps]}
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    def import_task(self, path: Path, *, name: str | None = None) -> AutomatedTask:
        """T-021: o versiune mai noua da `ProjectVersionError`; un nume existent
        primeste un numar. Sarcina importata e a utilizatorului (si cand vine
        dintr-o sarcina livrata: atunci `name` da numele copiei)."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CoreError(f"fisier de sarcina ilizibil: {exc}", path=str(path)) from exc
        if not isinstance(payload, dict) or payload.get("format") != TASK_FILE_FORMAT:
            raise CoreError("nu e un fisier de sarcina DocuLens", path=str(path))
        version = int(payload.get("format_version", 0))
        if version > TASK_FILE_VERSION:
            raise ProjectVersionError("sarcina e dintr-o versiune mai noua",
                                      found=version, supported=TASK_FILE_VERSION)
        steps = [TaskStep(str(s["type"]), dict(s.get("parameters") or {}))
                 for s in payload.get("steps", [])]
        base = name or str(payload.get("name") or Path(path).stem)
        if base.startswith(BUILTIN_PREFIX):
            base = Path(path).stem
        task = AutomatedTask(self._free_name(base), steps,
                             description=payload.get("description"))
        self.save(task)
        return task

    # --- rularea (T-008, T-019) ---

    def run(self, task: AutomatedTask, inputs: Sequence[Path], *,
            progress: ProgressCallback | None = None, cancel: CancelToken | None = None,
            project: Any = None, wait_for_areas: Callable[[Any], None] | None = None,
            ask_template: Callable[[], str | None] | None = None,
            output_name: str | None = None
            ) -> list[tuple[Path, Path | None, CoreError | None]]:
        """T-019: ruleaza sarcina pe fisiere (pentru `Scan`, interfata scaneaza
        intai si da fisierele). Toate imaginile intra intr-un singur proiect OCR
        (T-006) si dau un document per pas de salvare. Intoarce, pe fiecare intrare,
        (intrare, primul fisier scris, eroare). Un fisier care nu se incarca nu
        opreste lotul (A-028). `project`: proiectul deschis, pentru `current`.
        T-106: `Draw areas manually` cheama `wait_for_areas(project)` si asteapta."""
        from app.core.project import OcrProject

        self.validate(task)
        self.last_run = report = RunReport()
        get = task.steps[0].parameters
        mode = get.get("project", "new")
        own = True
        if mode == "current":
            if project is None:
                raise _fail(0, "no_current_project", "nu e deschis niciun proiect OCR")
            proj, own = project, False
        elif mode == "existing":
            proj = OcrProject.open(Path(get["project_path"]), context=self._ctx)
        else:
            proj = OcrProject.create(context=self._ctx)
        inputs = [Path(p) for p in inputs]
        total = len(task.steps)
        failed: dict[Path, CoreError] = {}
        try:
            recognize = next((s for s in task.steps if s.step_type == "recognize"), None)
            if recognize is not None and recognize.parameters.get("languages"):
                proj.languages = list(recognize.parameters["languages"])
            self._report(progress, 0, total, "get_images")
            known = {p.id for p in proj.pages}
            if inputs:
                _, errors = proj.add_images(inputs, auto_process=AutoProcessMode.NONE,
                                            cancel=cancel)
                failed = {Path(p): e for p, e in errors}
            new_pages = [p.page_number for p in proj.pages if p.id not in known]
            for i, step in enumerate(task.steps[1:], start=1):
                if cancel is not None and cancel():
                    raise OperationCancelledError(done=i, total=total)
                self._report(progress, i, total, step.step_type)
                new_pages = self._run_step(proj, step, i, new_pages, known, inputs,
                                           output_name, report, cancel, wait_for_areas,
                                           ask_template)
            self._report(progress, total, total, "done")
        except OperationCancelledError:
            raise
        except CoreError as exc:
            return [(p, None, failed.get(p, exc)) for p in inputs]
        except (ValueError, OSError) as exc:
            err = CoreError(str(exc))
            return [(p, None, failed.get(p, err)) for p in inputs]
        finally:
            if own:
                proj.close()
        first = report.outputs[0] if report.outputs else None
        return [(p, None, failed[p]) if p in failed else (p, first, None) for p in inputs]

    @staticmethod
    def _report(progress: ProgressCallback | None, done: int, total: int, step: str) -> None:
        if progress is not None:
            progress(Progress(done, total, f"stage.task.{step}", ""))

    def _run_step(self, proj: Any, step: TaskStep, index: int, new_pages: list[int],
                  known: set[int | None], inputs: list[Path], output_name: str | None,
                  report: RunReport, cancel: CancelToken | None,
                  wait_for_areas: Callable[[Any], None] | None,
                  ask_template: Callable[[], str | None] | None) -> list[int]:
        p = step.parameters
        kind = step.step_type
        if kind == "preprocess":
            if new_pages:
                proj.preprocess_pages(new_pages, cancel=cancel)
            # SPLIT (L-016) poate adauga pagini noi
            return [pg.page_number for pg in proj.pages if pg.id not in known]
        if kind == "analyze":
            # T-008: numai paginile fara zone (cele noi); cele analizate deja raman
            todo = [pg.page_number for pg in proj.pages
                    if pg.status in (PageStatus.IMPORTED, PageStatus.PREPROCESSED)]
            self._analyze(proj, p, index, todo, cancel, wait_for_areas, ask_template)
            return new_pages
        if kind == "recognize":
            from app.core.ocr.service import RecognitionService

            # T-008: paginile recunoscute nu se reproceseaza; cele analizate se recunosc
            RecognitionService(proj, engine=self._engine).recognize_pages(
                skip_recognized=True, cancel=cancel)
            return new_pages
        if kind == "save":
            report.outputs += self._save(proj, p, inputs, output_name, report)
            return new_pages
        if kind == "send_to":
            files = list(report.outputs)
            if p.get("kind") == "email_images":
                images = [f for f in files if f.suffix.lower() in (".tif", ".jpg", ".png")]
                files = images or files
            report.sent.append((str(p.get("kind")), p.get("app"), files))
        return new_pages

    def _analyze(self, proj: Any, p: dict[str, Any], index: int, todo: list[int],
                 cancel: CancelToken | None, wait_for_areas: Callable[[Any], None] | None,
                 ask_template: Callable[[], str | None] | None) -> None:
        mode = p.get("mode", "auto")
        if mode == "manual":  # T-106
            if wait_for_areas is None:
                raise _fail(index, "manual_needs_user",
                            "desenarea manuala a zonelor cere utilizatorul")
            wait_for_areas(proj)
            return
        if not todo:
            return
        if mode == "template":
            from app.core.layout.areas import AreaEditor

            name = p.get("template")
            if p.get("ask_template") and ask_template is not None:  # T-107
                name = ask_template() or name
            if not name:
                raise _fail(index, "template", "lipseste sablonul de zone")
            AreaEditor(proj).load_library_template([proj.page(n) for n in todo], name,
                                                   scale=True)
            return
        proj.analyze_pages(todo, cancel=cancel)

    def _save(self, proj: Any, p: dict[str, Any], inputs: list[Path],
              output_name: str | None, report: RunReport) -> list[Path]:
        kind = p.get("kind")
        if kind == "project":  # T-016
            target = Path(p["path"])
            proj.save(target)
            report.project_path = target
            return []
        if not proj.pages:
            raise CoreError("nicio pagina de salvat")
        folder = Path(p.get("folder") or (inputs[0].parent if inputs else Path.cwd()))
        if p.get("timestamped_subfolder"):  # T-011
            folder = folder / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        folder.mkdir(parents=True, exist_ok=True)
        stem = output_name or (inputs[0].stem if inputs else proj.name)
        fmt = ExportFormat(p["format"])
        if kind == "images":  # T-014
            from app.core.export.base import export_page_images

            if fmt is ExportFormat.PDF:
                return self._export(proj, folder, stem, fmt, image_only=True)
            suffix = {ExportFormat.TIFF: ".tif", ExportFormat.JPEG: ".jpg",
                      ExportFormat.PNG: ".png"}[fmt]
            target = free_path(folder / f"{stem}{suffix}")
            return export_page_images(proj.pages, target, fmt,
                                      multipage=bool(p.get("multipage")))
        return self._export(proj, folder, stem, fmt, image_only=bool(p.get("image_only")))

    @staticmethod
    def _export(proj: Any, folder: Path, stem: str, fmt: ExportFormat, *,
                image_only: bool) -> list[Path]:
        return export_document(proj, folder / stem, fmt, image_only=image_only)


def layout_for(fmt: ExportFormat) -> LayoutMode:
    """Modul de layout potrivit formatului (Q-001…Q-006), ca la conversia din Lansator."""
    if fmt in (ExportFormat.PDF, ExportFormat.PDFA, ExportFormat.DJVU):
        return LayoutMode.EXACT
    if fmt in (ExportFormat.DOCX, ExportFormat.RTF, ExportFormat.ODT):
        return LayoutMode.EDITABLE
    return LayoutMode.FORMATTED


def export_document(proj: Any, base: Path, fmt: ExportFormat, *,
                    image_only: bool = False) -> list[Path]:
    """Documentul proiectului in `base` + extensia formatului, fara suprascriere.
    PDF-ul e cautabil, afara de `image_only` (S-046, T-011)."""
    from app.core.export.base import default_service, options_from_settings

    fmt = ExportFormat(fmt)
    suffix = "pdf" if fmt in (ExportFormat.PDF, ExportFormat.PDFA) else fmt.value
    target = free_path(base.with_name(f"{base.name}.{suffix}"))
    options = options_from_settings(proj.settings(), fmt, layout_mode=layout_for(fmt))
    if fmt in (ExportFormat.PDF, ExportFormat.PDFA):
        options.searchable = not image_only
    return default_service().export(proj.pages, target, fmt, options)


def free_path(target: Path) -> Path:
    """Un fisier existent nu se suprascrie: `nume (2).pdf`."""
    candidate, n = target, 1
    while candidate.exists():
        n += 1
        candidate = target.with_name(f"{target.stem} ({n}){target.suffix}")
    return candidate
