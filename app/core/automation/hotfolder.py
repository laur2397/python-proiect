"""Hot Folder (faza 13, pasul 13.2): S-005…S-073, SPEC_05 §13.

O sarcina Hot Folder verifica o sursa (un folder local sau de retea, ori un
proiect OCR, S-033, S-036) la ora planificata (S-031, S-032) si proceseaza
fisierele noi: preprocesare, analiza si recunoastere dupa modul ales (S-040),
apoi unul sau mai multe pasi de salvare (S-046…S-052).

Reguli (faza_13_pasi.md):

- S-005: nu exista serviciu de sistem; sarcinile ruleaza cat aplicatia e
  deschisa. `install_service` refuza (decizia 2).
- S-032: singurele planificari repetate sunt la fiecare minut, zi, saptamana,
  luna; nu exista declansare pe aparitia unui fisier. Ceasul il da interfata,
  care cheama `tick(now)` (decizia 1).
- S-009: un fisier procesat cu succes nu se mai proceseaza (dupa `processing_log`;
  unul modificat de atunci, da). S-072: dupa 3 incercari esuate fisierul trece in
  subfolderul `Errors` al sursei. S-073: un fisier se preia numai dupa ce nu s-a
  mai schimbat 3 secunde.
- S-006: contorul de pagini pe 30 de zile (decizia 4).
- S-068, S-069: jurnalul TXT in folderul rezultatelor, cu statisticile.

Statusurile din SPEC_04 sunt `stopped`, `running`, `error`, `completed`; cele afisate
(S-015…S-020) se deduc: `running` + `once` = `Scheduled`, `running` + repetat =
`Watching...`, iar `Running...` cat se proceseaza (`display_status`).

Textele jurnalului vin din interfata, prin `tr` (CLAUDE.md §6.5).
"""

from __future__ import annotations

import calendar
import fnmatch
import json
import shutil
import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.automation.tasks import export_document, free_path
from app.core.errors import (
    CoreError,
    NoWritePermissionError,
    OperationCancelledError,
    ProjectVersionError,
    TaskValidationError,
)
from app.core.model import (
    CancelToken,
    ExportFormat,
    PageStatus,
    Progress,
    ProgressCallback,
)

SOURCE_KINDS = ("folder", "ftp", "outlook", "network")
"""SPEC_04. `ftp` si `outlook` nu sunt facute (decizia 5, INCOMPLET)."""

UNAVAILABLE_SOURCES = ("ftp", "outlook")

SCHEDULE_KINDS = ("once", "interval", "daily", "weekly", "monthly")
"""S-031, S-032: `Run once`; `Every minute` (interval de 1 minut), `Every day`,
`Every week`, `Every month`. `on_new_file` din SPEC_05 nu exista (decizia 2)."""

PROCESS_MODES = ("recognize", "analyze", "preprocess")
"""S-040: `Document processing settings`."""

OUTPUT_MODES = ("per_file", "per_folder", "single")
"""S-048, S-049, S-050."""

NAME_CLASH = ("overwrite", "number", "skip")

SAVE_KINDS = ("document", "images", "project")
"""S-206: `Save document`, `Save images`, `Save OCR project` (`Save to SharePoint`
e un serviciu online, decizia 5)."""

IMAGE_FORMATS = (ExportFormat.TIFF, ExportFormat.JPEG, ExportFormat.PNG)

PROJECT_FORMAT = "ocr_project"
"""`output_format` pentru `Save OCR project` (SPEC_04 cere o valoare la salvare)."""

ORIGINAL_ACTIONS = ("keep", "delete", "move")
"""S-038."""

FILE_TYPES: dict[str, tuple[str, ...]] = {
    "all": ("*",),
    "images_pdf": ("*.bmp", "*.dib", "*.dcx", "*.djvu", "*.djv", "*.gif", "*.jb2",
                   "*.jbig2", "*.jp2", "*.j2k", "*.jpf", "*.jpx", "*.jpg", "*.jpeg", "*.jfif",
                   "*.pcx", "*.pdf", "*.png", "*.tif", "*.tiff", "*.wdp", "*.jxr", "*.xps"),
    "bmp": ("*.bmp", "*.dib"),
    "dcx": ("*.dcx",),
    "djvu": ("*.djvu", "*.djv"),
    "gif": ("*.gif",),
    "jbig2": ("*.jb2", "*.jbig2"),
    "jpeg2000": ("*.jp2", "*.j2k", "*.jpf", "*.jpx"),
    "jpeg": ("*.jpg", "*.jpeg", "*.jfif"),
    "pcx": ("*.pcx",),
    "pdf": ("*.pdf",),
    "png": ("*.png",),
    "tiff": ("*.tif", "*.tiff"),
    "wdp": ("*.wdp", "*.jxr"),
    "xps": ("*.xps",),
}
"""S-211: combo-ul `File type`, in ordinea din cerinta. `file_pattern` din SPEC_04
tine cheia de aici sau un tipar propriu (`*.png;*.tif`)."""

ERRORS_FOLDER = "Errors"
"""S-072."""

PERIOD_DAYS = 30
"""S-006: contorul se reinnoieste la 30 de zile."""

HFT_SUFFIX = ".hft"
HFT_FORMAT = "doculens-hotfolder"
HFT_VERSION = 1
"""S-065, faza_13_pasi.md decizia 3."""

NAME_MACROS = ("[F]", "[X]", "[D]", "[T]", "[#]")
"""S-216: numele originalului, extensia lui, data, ora, contorul de fisiere."""

_BAD_CHARS = '<>:"/\\|?*'


@dataclass(slots=True)
class HotFolderStep:
    """Un pas al sarcinii (`hot_folder_step`). Pentru `save`: formatul, folderul,
    sablonul de nume (S-051, S-216), ce se face la un nume existent, si in
    `parameters`: `image_only` (S-046) si `output` (S-048…S-050)."""

    step_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    output_format: str | None = None
    output_folder: str | None = None
    name_template: str = "[F]"
    on_name_clash: str = "number"


@dataclass(slots=True)
class HotFolderTask:
    """S-030…S-053 (SPEC_05: HotFolderTask). Pasul de procesare (S-039…S-045) e
    in `process`: `mode`, `languages`, `template`, `delete_blank`, `blank_folder`."""

    name: str
    source_kind: str
    source_path: str
    include_subfolders: bool = False
    file_pattern: str = "images_pdf"
    credential_ref: str | None = None
    original_action: str = "keep"
    original_move_to: str | None = None
    schedule_kind: str = "interval"
    schedule_at: str | None = None
    schedule_interval_minutes: int | None = 1
    schedule_time: str | None = None
    schedule_days: tuple[int, ...] = ()
    steps: list[HotFolderStep] = field(default_factory=list)
    max_parallel: int = 2
    notify_on_error: bool = False
    notify_email: str | None = None
    is_enabled: bool = False
    process: dict[str, Any] = field(default_factory=lambda: {
        "mode": "recognize", "languages": ["ron"]})
    status: str = "stopped"
    last_run_at: str | None = None
    next_run_at: str | None = None
    last_error: str | None = None


@dataclass
class RunSummary:
    """Statisticile unei rulari (S-069) si ce s-a scris."""

    task: str
    files: int = 0
    pages: int = 0
    errors: int = 0
    warnings: int = 0
    uncertain: int = 0
    outputs: list[Path] = field(default_factory=list)
    messages: list[tuple[str, str]] = field(default_factory=list)
    """(nivel, text) pentru jurnal: `error` sau `warning`."""
    stopped: bool = False
    limit_reached: bool = False


# --- planificarea (S-031, S-032) ---------------------------------------------------

def _hhmm(value: str | None) -> tuple[int, int]:
    if not value:
        return 0, 0
    h, m = value.split(":", 1)
    return int(h), int(m)


def next_start(task: HotFolderTask, now: datetime,
               last_run: datetime | None = None) -> datetime | None:
    """Ora urmatoarei verificari (`Next Start Time`, S-003), sau None cand nu mai
    urmeaza nimic (`Run once` deja rulat). Functie pura."""
    kind = task.schedule_kind
    if kind == "once":
        if not task.schedule_at or last_run is not None:
            return None
        return datetime.fromisoformat(task.schedule_at)
    if kind == "interval":  # `Every minute`
        return now if last_run is None else last_run + timedelta(minutes=1)
    hour, minute = _hhmm(task.schedule_time)
    if kind == "daily":
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return candidate if candidate > now else candidate + timedelta(days=1)
    if kind == "weekly":
        days = task.schedule_days or (0,)
        for offset in range(8):
            day = now + timedelta(days=offset)
            if day.weekday() in days:
                candidate = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate > now:
                    return candidate
        return None
    if kind == "monthly":
        days = task.schedule_days or (1,)
        year, month = now.year, now.month
        for _ in range(13):
            last = calendar.monthrange(year, month)[1]
            for d in sorted({min(int(x), last) for x in days}):
                candidate = datetime(year, month, d, hour, minute)
                if candidate > now:
                    return candidate
            month += 1
            if month > 12:
                year, month = year + 1, 1
        return None
    return None


def display_status(task: HotFolderTask, *, processing: bool = False) -> str:
    """S-015…S-020: `running` (`Running...`), `scheduled`, `watching`, `stopped`,
    `completed`, `error`."""
    if processing:
        return "running"
    if task.status == "running":
        return "scheduled" if task.schedule_kind == "once" else "watching"
    return task.status


# --- numele fisierelor (S-051, S-216) -----------------------------------------------

def safe_name(name: str) -> str:
    for bad in _BAD_CHARS:
        name = name.replace(bad, "_")
    return name.strip()


def expand_name(template: str, source: Path, when: datetime, counter: int) -> str:
    """S-216: `[F]` numele originalului, `[X]` extensia (fara punct), `[D]` data
    (AAAA-LL-ZZ), `[T]` ora (HH-MM-SS), `[#]` contorul de fisiere."""
    name = template or "[F]"
    for macro, value in (("[F]", source.stem), ("[X]", source.suffix.lstrip(".")),
                         ("[D]", when.strftime("%Y-%m-%d")), ("[T]", when.strftime("%H-%M-%S")),
                         ("[#]", str(counter))):
        name = name.replace(macro, value)
    return safe_name(name) or source.stem


def matches(path: Path, pattern: str) -> bool:
    """S-211: cheia din `FILE_TYPES` sau tipare separate prin `;`."""
    patterns = FILE_TYPES.get(pattern) or tuple(
        p.strip() for p in pattern.split(";") if p.strip())
    name = path.name.lower()
    return any(fnmatch.fnmatch(name, p.lower()) for p in patterns or ("*",))


def is_ocr_project(path: Path) -> bool:
    """S-036: sursa e un proiect OCR (folderul lui), nu un folder cu imagini."""
    from app.core.project import DB_NAME

    path = Path(path)
    return (path / DB_NAME).is_file() or (path.name == DB_NAME and path.is_file())


def _now_iso(when: datetime) -> str:
    return when.replace(microsecond=0).isoformat()


# --- serviciul (S-005…S-073) -------------------------------------------------------------

# S-005…S-073 (SPEC_05: HotFolderService)
class HotFolderService:
    """Sarcinile Hot Folder din app.db, planificarea si procesarea lor."""

    FILE_STABLE_SECONDS: int = 3
    """S-073 (SPEC_05 il numeste S-015)."""

    MAX_RETRIES: int = 3
    """S-072 (SPEC_05 il numeste S-033)."""

    def __init__(self, context: Any, *, engine: Any = None,
                 clock: Callable[[], datetime] = datetime.now,
                 tr: Callable[..., str] | None = None) -> None:
        self._ctx = context
        self._con: sqlite3.Connection = context.app_db
        self._engine = engine
        self._clock = clock
        self._tr = tr or (lambda key, **kw: f"{key} {json.dumps(kw, ensure_ascii=False)}"
                          if kw else key)
        self._seen: dict[Path, tuple[int, float]] = {}
        self._stop: set[str] = set()
        self.processing: str | None = None
        """Sarcina care se proceseaza acum (`Running...`)."""

    # --- citirea ---

    def tasks(self) -> list[HotFolderTask]:
        rows = self._con.execute("SELECT name FROM hot_folder_task ORDER BY name").fetchall()
        return [self.task(r[0]) for r in rows]

    def task(self, name: str) -> HotFolderTask:
        row = self._con.execute(
            "SELECT id, name, is_enabled, source_kind, source_path, include_subfolders,"
            " file_pattern, credential_ref, original_action, original_move_to, schedule_kind,"
            " schedule_at, schedule_interval_minutes, schedule_time, schedule_days, status,"
            " last_run_at, next_run_at, last_error, max_parallel, notify_on_error,"
            " notify_email FROM hot_folder_task WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        (tid, name, enabled, kind, path, subfolders, pattern, cred, action, move_to, skind,
         at, interval, stime, days, status, last_run, next_run, last_error, parallel,
         notify, email) = row
        steps: list[HotFolderStep] = []
        process: dict[str, Any] = {}
        for stype, params, fmt, folder, template, clash in self._con.execute(
                "SELECT step_type, parameters, output_format, output_folder, name_template,"
                " on_name_clash FROM hot_folder_step WHERE hot_folder_id = ?"
                " ORDER BY order_index", (tid,)):
            parameters = json.loads(params or "{}")
            if stype == "save":
                steps.append(HotFolderStep(stype, parameters, fmt, folder, template or "[F]",
                                           clash or "number"))
            else:
                process.update(parameters)
        return HotFolderTask(
            name, kind, path, bool(subfolders), pattern, cred, action, move_to, skind, at,
            interval, stime, tuple(json.loads(days or "[]")), steps, parallel, bool(notify),
            email, bool(enabled), process or {"mode": "recognize", "languages": ["ron"]},
            status, last_run, next_run, last_error)

    def _task_id(self, name: str) -> int | None:
        row = self._con.execute("SELECT id FROM hot_folder_task WHERE name = ?",
                                (name,)).fetchone()
        return row[0] if row else None

    # --- validarea (S-030…S-053) ---

    @staticmethod
    def _fail(reason: str, message: str, index: int = -1) -> TaskValidationError:
        return TaskValidationError(message, step_index=index, reason=reason)

    def validate(self, task: HotFolderTask) -> None:
        """S-053: `Create Task` cere o sarcina completa; `reason` spune ce lipseste."""
        if not task.name.strip():
            raise self._fail("name", "numele sarcinii e gol")  # S-030
        if task.source_kind not in SOURCE_KINDS:
            raise self._fail("source_kind", "sursa necunoscuta")
        if task.source_kind in UNAVAILABLE_SOURCES:
            raise self._fail("source_unavailable", "sursa nu e disponibila in DocuLens")
        if not task.source_path:
            raise self._fail("source_path", "lipseste folderul sursa")
        if task.schedule_kind not in SCHEDULE_KINDS:  # S-032
            raise self._fail("schedule_kind", "planificare necunoscuta (fara declansare pe"
                             " fisier nou)")
        if task.schedule_kind == "once":
            if not task.schedule_at:
                raise self._fail("schedule_at", "lipseste data si ora")
            try:
                datetime.fromisoformat(task.schedule_at)
            except ValueError:
                raise self._fail("schedule_at", "data si ora invalide") from None
        if task.schedule_kind == "interval" and task.schedule_interval_minutes != 1:
            raise self._fail("schedule_interval", "repetarea e numai la fiecare minut")
        if task.schedule_kind in ("daily", "weekly", "monthly"):
            try:
                hour, minute = _hhmm(task.schedule_time)
            except ValueError:
                raise self._fail("schedule_time", "ora invalida") from None
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise self._fail("schedule_time", "ora invalida")
        if task.original_action not in ORIGINAL_ACTIONS:
            raise self._fail("original_action", "actiune necunoscuta")
        if task.original_action == "move" and not task.original_move_to:  # S-038
            raise self._fail("original_move_to", "lipseste folderul pentru originale")
        mode = task.process.get("mode", "recognize")
        if mode not in PROCESS_MODES:
            raise self._fail("process_mode", "mod de procesare necunoscut")
        if not task.process.get("languages"):  # S-039
            raise self._fail("languages", "trebuie aleasa cel putin o limba")
        if task.process.get("blank_folder") and not task.process.get("delete_blank"):  # S-045
            raise self._fail("blank_folder", "folderul paginilor goale cere stergerea lor")
        if not any(s.step_type == "save" for s in task.steps):
            raise self._fail("no_output", "sarcina nu salveaza nimic")
        for i, step in enumerate(task.steps):
            if step.step_type != "save":
                continue
            if not step.output_format or not step.output_folder:  # S-046, S-047
                raise self._fail("save_target", "lipseste formatul sau folderul", i)
            kind = step.parameters.get("kind", "document")
            if kind not in SAVE_KINDS:
                raise self._fail("save_kind", "tip de salvare necunoscut", i)
            if kind == "project":
                if step.output_format != PROJECT_FORMAT:
                    raise self._fail("format", "proiectul OCR se salveaza ca proiect", i)
            else:
                try:
                    fmt = ExportFormat(step.output_format)
                except ValueError:
                    raise self._fail("format", "format necunoscut", i) from None
                if kind == "images" and fmt not in IMAGE_FORMATS:
                    raise self._fail("format", "format de imagine necunoscut", i)
                image_only = kind == "images" or (bool(step.parameters.get("image_only"))
                                                  and fmt in (ExportFormat.PDF,
                                                              ExportFormat.PDFA))
                if mode != "recognize" and not image_only:
                    raise self._fail("save_needs_recognize",
                                     "salvarea textului cere recunoastere", i)
            if step.parameters.get("output", "per_file") not in OUTPUT_MODES:
                raise self._fail("output", "mod de iesire necunoscut", i)
            if step.on_name_clash not in NAME_CLASH:
                raise self._fail("name_clash", "regula de nume necunoscuta", i)

    def test_source(self, task: HotFolderTask) -> None:
        """S-033: folderul sursa trebuie sa existe si sa fie citibil; S-047:
        folderele de iesire trebuie sa fie scriibile."""
        if task.source_kind in UNAVAILABLE_SOURCES:
            raise CoreError("sursa nu e disponibila", source=task.source_kind)
        source = Path(task.source_path)
        if not source.exists():
            raise CoreError("folderul sursa nu exista", path=str(source))
        if source.is_dir():
            try:
                next(source.iterdir(), None)
            except OSError as exc:
                raise CoreError("folderul sursa nu se poate citi", path=str(source)) from exc
        for step in task.steps:
            if step.step_type == "save" and step.output_folder:
                self._check_writable(Path(step.output_folder))

    @staticmethod
    def _check_writable(folder: Path) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".doculens-probe"
            probe.write_bytes(b"")
            probe.unlink()
        except OSError as exc:
            raise NoWritePermissionError("folderul nu se poate scrie", path=str(folder)) from exc

    # --- scrierea ---

    _COLUMNS = ("name", "is_enabled", "source_kind", "source_path", "include_subfolders",
                "file_pattern", "credential_ref", "original_action", "original_move_to",
                "schedule_kind", "schedule_at", "schedule_interval_minutes", "schedule_time",
                "schedule_days", "max_parallel", "notify_on_error", "notify_email")

    def save(self, task: HotFolderTask, *, previous_name: str | None = None) -> None:
        """S-053; S-062: o sarcina care ruleaza se opreste intai."""
        self.validate(task)
        old = previous_name or task.name
        tid = self._task_id(old)
        if tid is not None and self.task(old).status == "running":
            raise self._fail("running", "sarcina ruleaza; se opreste intai")
        other = self._task_id(task.name)
        if other is not None and other != tid:
            raise self._fail("name_taken", "exista deja o sarcina cu acest nume")
        values = (task.name, int(task.is_enabled), task.source_kind, task.source_path,
                  int(task.include_subfolders), task.file_pattern, task.credential_ref,
                  task.original_action, task.original_move_to, task.schedule_kind,
                  task.schedule_at, task.schedule_interval_minutes, task.schedule_time,
                  json.dumps(list(task.schedule_days)), task.max_parallel,
                  int(task.notify_on_error), task.notify_email)
        with self._con:
            if tid is None:
                tid = int(self._con.execute(
                    f"INSERT INTO hot_folder_task ({', '.join(self._COLUMNS)}) VALUES"
                    f" ({', '.join('?' * len(values))})", values).lastrowid or 0)
            else:
                sets = ", ".join(f"{c} = ?" for c in self._COLUMNS)
                self._con.execute(f"UPDATE hot_folder_task SET {sets} WHERE id = ?",
                                  (*values, tid))
                self._con.execute("DELETE FROM hot_folder_step WHERE hot_folder_id = ?", (tid,))
            self._write_steps(tid, task)

    def _write_steps(self, tid: int, task: HotFolderTask) -> None:
        """Pasul de procesare devine `preprocess` / `analyze` / `recognize`
        (S-040), cu parametrii lui pe ultimul; urmeaza pasii de salvare."""
        mode = task.process.get("mode", "recognize")
        kinds = {"preprocess": ["preprocess"], "analyze": ["preprocess", "analyze"],
                 "recognize": ["preprocess", "analyze", "recognize"]}[mode]
        rows: list[tuple[Any, ...]] = []
        for kind in kinds:
            params = dict(task.process) if kind == kinds[-1] else {}
            rows.append((tid, len(rows), kind, json.dumps(params, ensure_ascii=False),
                         None, None, None, None))
        for step in task.steps:
            if step.step_type == "save":
                rows.append((tid, len(rows), "save",
                             json.dumps(step.parameters, ensure_ascii=False),
                             step.output_format, step.output_folder, step.name_template,
                             step.on_name_clash))
        self._con.executemany(
            "INSERT INTO hot_folder_step (hot_folder_id, order_index, step_type, parameters,"
            " output_format, output_folder, name_template, on_name_clash)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)

    def _free_name(self, base: str) -> str:
        name, n = base, 1
        while self._task_id(name) is not None:
            n += 1
            name = f"{base} ({n})"
        return name

    def duplicate(self, name: str) -> HotFolderTask:
        """S-063: `Copy`; copia e oprita."""
        task = self.task(name)
        task.name = self._free_name(task.name)
        task.status, task.is_enabled = "stopped", False
        self.save(task)
        return self.task(task.name)

    def delete(self, name: str) -> None:
        """S-064: o sarcina care ruleaza se opreste intai (confirmarea e in interfata)."""
        if self._task_id(name) is None:
            raise KeyError(name)
        self.stop(name)
        with self._con:
            self._con.execute("DELETE FROM hot_folder_task WHERE name = ?", (name,))

    # --- pornirea si oprirea (S-060, S-061) ---

    def _set(self, name: str, **fields: Any) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self._con:
            self._con.execute(f"UPDATE hot_folder_task SET {sets} WHERE name = ?",
                              (*fields.values(), name))

    def start(self, name: str) -> None:
        """S-060 (`Start on Schedule`): sarcina asteapta ora planificata. O repornire
        planifica de la zero (si `Run once`)."""
        task = self.task(name)
        when = next_start(task, self._clock())
        self._stop.discard(name)
        self._set(name, status="running", is_enabled=1,
                  next_run_at=_now_iso(when) if when else None, last_error=None)

    def stop(self, name: str) -> None:
        """S-061: se termina fisierul curent, apoi `Stopped`."""
        if self.processing == name:
            self._stop.add(name)
        self._set(name, status="stopped", is_enabled=0, next_run_at=None)

    def run_now(self, name: str, *, progress: ProgressCallback | None = None,
                cancel: CancelToken | None = None) -> RunSummary:
        """S-060 (`Start Now`): proceseaza acum; o sarcina pornita revine la
        planificare, una oprita ramane `Completed`."""
        return self._run(self.task(name), progress=progress, cancel=cancel)

    def tick(self, now: datetime | None = None, *, progress: ProgressCallback | None = None,
             cancel: CancelToken | None = None) -> list[RunSummary]:
        """Ruleaza sarcinile pornite a caror ora a venit (o cheama interfata periodic)."""
        now = now or self._clock()
        done = []
        for task in self.tasks():
            if task.status != "running" or not task.next_run_at:
                continue
            if datetime.fromisoformat(task.next_run_at) <= now:
                done.append(self._run(task, progress=progress, cancel=cancel))
        return done

    def install_service(self) -> None:
        """S-005 (`D`): Hot Folder nu ruleaza ca serviciu de sistem, fara utilizator
        conectat. Semnatura e din SPEC_05; raspunsul e intotdeauna refuzul."""
        raise CoreError("Hot Folder ruleaza numai cat utilizatorul e conectat (S-005)",
                        requirement="S-005")

    # --- fisierele (S-009, S-037, S-072, S-073) ---

    def is_file_ready(self, path: Path) -> bool:
        """S-073: fisierul nu s-a mai schimbat de 3 secunde (data modificarii) si are
        aceeasi dimensiune ca la observatia anterioara."""
        path = Path(path)
        try:
            st = path.stat()
        except OSError:
            return False
        previous = self._seen.get(path)
        self._seen[path] = (st.st_size, st.st_mtime)
        if time.time() - st.st_mtime < self.FILE_STABLE_SECONDS:
            return False
        return previous is None or previous[0] == st.st_size

    def _processed(self, tid: int, path: Path) -> bool:
        """S-009: un succes dupa ultima modificare a fisierului."""
        row = self._con.execute(
            "SELECT finished_at FROM processing_log WHERE hot_folder_id = ? AND"
            " source_file = ? AND status = 'success' ORDER BY id DESC LIMIT 1",
            (tid, str(path))).fetchone()
        if row is None or not row[0]:
            return False
        mtime = datetime.fromtimestamp(path.stat().st_mtime).replace(microsecond=0)
        return datetime.fromisoformat(row[0]) >= mtime

    def _retries(self, tid: int, path: Path) -> int:
        """Incercarile esuate de dinainte (0, 1, 2)."""
        row = self._con.execute(
            "SELECT retry_count FROM processing_log WHERE hot_folder_id = ? AND"
            " source_file = ? AND status = 'error' ORDER BY id DESC LIMIT 1",
            (tid, str(path))).fetchone()
        return int(row[0]) + 1 if row else 0

    def pending_files(self, task: HotFolderTask) -> list[Path]:
        """Fisierele de procesat acum: potrivite tiparului (S-211), din subfoldere
        daca e bifat (S-037), fara `Errors` (S-072), fara cele procesate (S-009),
        numai cele complet copiate (S-073)."""
        tid = self._task_id(task.name)
        source = Path(task.source_path)
        if not source.is_dir() or tid is None:
            return []
        walker = source.rglob("*") if task.include_subfolders else source.glob("*")
        skip = {Path(s.output_folder).resolve() for s in task.steps
                if s.step_type == "save" and s.output_folder}
        if task.process.get("blank_folder"):
            skip.add(Path(task.process["blank_folder"]).resolve())
        if task.original_move_to:
            skip.add(Path(task.original_move_to).resolve())
        files = []
        for path in sorted(walker):
            if not path.is_file() or not matches(path, task.file_pattern):
                continue
            if ERRORS_FOLDER in path.relative_to(source).parts[:-1] or \
                    path.name.startswith("."):
                continue
            if any(parent in skip for parent in path.resolve().parents):
                continue
            if self._processed(tid, path) or not self.is_file_ready(path):
                continue
            files.append(path)
        return files

    # --- contorul de pagini (S-006, S-202, S-203) ---

    def _counter(self, now: datetime) -> dict[str, Any]:
        counter = dict(self._ctx.settings.get("hotfolder.page_counter") or {})
        start = counter.get("period_start")
        if not start or now - datetime.fromisoformat(start) >= timedelta(days=PERIOD_DAYS):
            counter = {"period_start": _now_iso(now), "used": 0}
            self._ctx.settings.set("hotfolder.page_counter", counter)
        return counter

    def page_limit(self) -> int:
        return int(self._ctx.settings.get("hotfolder.monthly_page_limit") or 0)

    def pages_remaining(self, now: datetime | None = None) -> int | None:
        """S-202: paginile ramase in perioada; None = fara limita."""
        limit = self.page_limit()
        if not limit:
            return None
        return max(limit - int(self._counter(now or self._clock())["used"]), 0)

    def days_to_renew(self, now: datetime | None = None) -> int:
        """S-202: zilele pana la reinnoirea contorului."""
        now = now or self._clock()
        start = datetime.fromisoformat(self._counter(now)["period_start"])
        left = start + timedelta(days=PERIOD_DAYS) - now
        return max(left.days + (1 if left.seconds else 0), 0)

    def _count_pages(self, pages: int, now: datetime) -> None:
        counter = self._counter(now)
        counter["used"] = int(counter["used"]) + pages
        self._ctx.settings.set("hotfolder.page_counter", counter)  # S-203

    # --- procesarea ---

    def _run(self, task: HotFolderTask, *, progress: ProgressCallback | None,
             cancel: CancelToken | None) -> RunSummary:
        tid = self._task_id(task.name)
        if tid is None:
            raise KeyError(task.name)
        started = self._clock()
        summary = RunSummary(task.name)
        self.processing = task.name
        self._stop.discard(task.name)

        def stopped() -> bool:
            return task.name in self._stop or (cancel is not None and bool(cancel()))

        try:
            source = Path(task.source_path)
            if is_ocr_project(source):  # S-036
                self._process_project(task, tid, source, summary, stopped)
            else:
                if not source.is_dir():
                    raise CoreError("folderul sursa nu exista", path=str(source))
                for group in self._groups(task, self.pending_files(task)):
                    if stopped():
                        summary.stopped = True
                        break
                    if not self._within_limit(summary):
                        break
                    self._process_group(task, tid, source, group, summary, progress, stopped)
        except CoreError as exc:
            summary.errors += 1
            summary.messages.append(("error", exc.message or exc.code))
        finally:
            self.processing = None
        self._finish(task, started, summary)
        return summary

    def _within_limit(self, summary: RunSummary) -> bool:
        """S-006: la depasire procesarea se opreste, cu mesaj."""
        remaining = self.pages_remaining()
        if remaining is not None and remaining <= 0:
            summary.limit_reached = True
            summary.errors += 1
            summary.messages.append(("error", self._tr("hotfolder.log.limit",
                                                       limit=self.page_limit())))
            return False
        return True

    @staticmethod
    def _groups(task: HotFolderTask, files: list[Path]) -> list[list[Path]]:
        """S-048…S-050 dupa primul pas de salvare: un document per fisier, per
        folder sau unul singur. Celelalte salvari folosesc aceleasi grupuri."""
        if not files:
            return []
        save = next(s for s in task.steps if s.step_type == "save")
        output = save.parameters.get("output", "per_file")
        if output == "single":
            return [files]
        if output == "per_folder":
            groups: dict[Path, list[Path]] = {}
            for f in files:
                groups.setdefault(f.parent, []).append(f)
            return list(groups.values())
        return [[f] for f in files]

    def _log_row(self, tid: int, source: Path, started: datetime) -> int:
        with self._con:
            return int(self._con.execute(
                "INSERT INTO processing_log (hot_folder_id, source_file, started_at, status)"
                " VALUES (?, ?, ?, 'running')", (tid, str(source), _now_iso(started))
            ).lastrowid or 0)

    def _process_group(self, task: HotFolderTask, tid: int, source: Path, group: list[Path],
                       summary: RunSummary, progress: ProgressCallback | None,
                       stopped: Callable[[], bool]) -> None:
        from app.core.project import OcrProject

        started = self._clock()
        rows = {f: self._log_row(tid, f, started) for f in group}
        if progress is not None:
            progress(Progress(summary.files, summary.files + len(group), "stage.hotfolder",
                              group[0].name))
        outputs: list[Path] = []
        failed: dict[Path, CoreError] = {}
        project = OcrProject.create(context=self._ctx)
        try:
            project.languages = list(task.process.get("languages") or ["ron"])
            _, errors = project.add_images(group, auto_process=None, cancel=stopped)
            failed = {Path(p): e for p, e in errors}
            if project.pages:
                self._process_pages(task, project, summary, stopped)
                outputs = self._save_all(task, project, source, group)
                pages = len(project.pages)
                summary.pages += pages
                summary.uncertain += sum(p.uncertain_count for p in project.pages)
                summary.warnings += sum(len(p.warnings) for p in project.pages)
                self._count_pages(pages, self._clock())
        except OperationCancelledError:
            summary.stopped = True
            failed = {f: CoreError("oprit") for f in group}
            outputs = []
        except (CoreError, ValueError, OSError) as exc:
            err = exc if isinstance(exc, CoreError) else CoreError(str(exc))
            failed = {f: err for f in group}
            outputs = []
        finally:
            project.close()
        summary.outputs += outputs
        finished = self._clock()
        for f in group:
            summary.files += 1
            err = failed.get(f)
            if err is None and outputs:
                self._success(task, rows[f], f, outputs[0], started, finished)
            else:
                self._failure(tid, rows[f], f, source, err or CoreError("nimic de salvat"),
                              finished, summary)

    def _process_pages(self, task: HotFolderTask, project: Any, summary: RunSummary,
                       stopped: Callable[[], bool]) -> None:
        """S-040…S-045: paginile goale se sterg fara confirmare (S-214), mutate
        intai in folderul ales (S-045); apoi analiza si recunoasterea."""
        p = task.process
        mode = p.get("mode", "recognize")
        if p.get("delete_blank"):
            blank = project.find_blank_pages()
            if blank and len(blank) < len(project.pages):
                if p.get("blank_folder"):
                    from app.core.export.base import export_page_images

                    folder = Path(p["blank_folder"])
                    folder.mkdir(parents=True, exist_ok=True)
                    pages = [project.page(n) for n in blank]
                    stem = (pages[0].source_file or Path("blank")).stem
                    export_page_images(pages, free_path(folder / f"{stem}.png"),
                                       ExportFormat.PNG)
                project.delete_pages(blank)
                summary.messages.append(("warning", self._tr("hotfolder.log.blank_deleted",
                                                             count=len(blank))))
        if mode == "preprocess":
            return
        todo = [pg.page_number for pg in project.pages
                if pg.status in (PageStatus.IMPORTED, PageStatus.PREPROCESSED)]
        if todo:
            if p.get("template"):  # S-043
                from app.core.layout.areas import AreaEditor

                AreaEditor(project).load_library_template([project.page(n) for n in todo],
                                                          p["template"], scale=True)
            else:
                project.analyze_pages(todo, cancel=stopped)
        if mode == "recognize":
            from app.core.ocr.service import RecognitionService

            RecognitionService(project, engine=self._engine).recognize_pages(
                skip_recognized=True, cancel=stopped)

    def _save_all(self, task: HotFolderTask, project: Any, source: Path,
                  group: list[Path]) -> list[Path]:
        """S-046…S-052: fiecare pas de salvare scrie documentul lui (S-052)."""
        outputs: list[Path] = []
        when = self._clock()
        counter = self._counter_value(task) + 1
        for step in (s for s in task.steps if s.step_type == "save"):
            output = step.parameters.get("output", "per_file")
            folder = Path(step.output_folder or source)
            first = group[0]
            if output == "per_folder":
                try:  # S-049: ierarhia de foldere se pastreaza
                    rel = first.parent.relative_to(source)
                except ValueError:
                    rel = Path()
                folder = folder / rel.parent if rel.parts else folder
                first = first.parent.with_suffix(first.suffix)
            elif output == "single":
                first = source.with_suffix(first.suffix)
            folder.mkdir(parents=True, exist_ok=True)
            name = expand_name(step.name_template, first, when, counter)
            kind = step.parameters.get("kind", "document")
            if kind == "project":  # S-206: `Save OCR project`
                target = folder / name
                if target.exists():
                    if step.on_name_clash == "skip":
                        continue
                    if step.on_name_clash == "number":
                        target = free_path(target)
                project.save(target)
                outputs.append(target)
                continue
            fmt = ExportFormat(step.output_format or "pdf")
            if kind == "images":  # S-206: `Save images`
                from app.core.export.base import export_page_images

                suffix = {ExportFormat.TIFF: "tif", ExportFormat.JPEG: "jpg",
                          ExportFormat.PNG: "png"}[fmt]
            else:
                suffix = "pdf" if fmt in (ExportFormat.PDF, ExportFormat.PDFA) else fmt.value
            target = folder / f"{name}.{suffix}"
            if target.exists():
                if step.on_name_clash == "skip":
                    continue
                if step.on_name_clash == "overwrite":
                    target.unlink()
            if kind == "images":
                outputs += export_page_images(
                    project.pages, free_path(target), fmt,
                    multipage=bool(step.parameters.get("multipage")) and
                    fmt is ExportFormat.TIFF)
                continue
            outputs += export_document(project, folder / name, fmt,
                                       image_only=bool(step.parameters.get("image_only")))
        return outputs

    def _counter_value(self, task: HotFolderTask) -> int:
        row = self._con.execute(
            "SELECT COUNT(*) FROM processing_log WHERE hot_folder_id = ? AND status = 'success'",
            (self._task_id(task.name),)).fetchone()
        return int(row[0])

    def _success(self, task: HotFolderTask, row: int, path: Path, output: Path,
                 started: datetime, finished: datetime) -> None:
        with self._con:
            self._con.execute(
                "UPDATE processing_log SET status = 'success', output_file = ?,"
                " finished_at = ?, duration_ms = ? WHERE id = ?",
                (str(output), _now_iso(finished),
                 max(int((finished - started).total_seconds() * 1000), 0), row))
        self._handle_original(task, path)

    @staticmethod
    def _handle_original(task: HotFolderTask, path: Path) -> None:
        """S-038: originalul ramane, se sterge sau se muta."""
        try:
            if task.original_action == "delete":
                path.unlink(missing_ok=True)
            elif task.original_action == "move" and task.original_move_to:
                target = Path(task.original_move_to)
                target.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(free_path(target / path.name)))
        except OSError:
            pass  # rezultatul e scris; originalul ramane unde e

    def _failure(self, tid: int, row: int, path: Path, source: Path, err: CoreError,
                 finished: datetime, summary: RunSummary) -> None:
        """S-072: dupa 3 incercari esuate fisierul trece in `Errors` si nu se mai
        proceseaza."""
        retries = min(self._retries(tid, path), self.MAX_RETRIES)
        summary.errors += 1
        summary.messages.append(("error", f"{path.name}: {err.message or err.code}"))
        with self._con:
            self._con.execute(
                "UPDATE processing_log SET status = 'error', finished_at = ?, error_code = ?,"
                " error_message = ?, retry_count = ? WHERE id = ?",
                (_now_iso(finished), err.code, err.message, retries, row))
        if retries + 1 >= self.MAX_RETRIES and path.exists():
            folder = (source if source.is_dir() else path.parent) / ERRORS_FOLDER
            folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(free_path(folder / path.name)))
            summary.messages.append(("error", self._tr("hotfolder.log.moved_to_errors",
                                                       file=path.name)))

    def _process_project(self, task: HotFolderTask, tid: int, source: Path,
                         summary: RunSummary, stopped: Callable[[], bool]) -> None:
        """S-036: sursa e un proiect OCR; se recunosc paginile nerecunoscute, se
        salveaza documentul si proiectul."""
        from app.core.project import OcrProject

        folder = source if source.is_dir() else source.parent
        row = self._log_row(tid, folder, self._clock())
        project = OcrProject.open(folder, context=self._ctx)
        try:
            todo = sum(1 for p in project.pages
                       if p.status not in (PageStatus.RECOGNIZED, PageStatus.VERIFIED))
            self._process_pages(task, project, summary, stopped)
            outputs = self._save_all(task, project, folder.parent, [folder])
            project.save()
        finally:
            project.close()
        summary.files += 1
        summary.pages += todo
        self._count_pages(todo, self._clock())
        summary.outputs += outputs
        with self._con:
            self._con.execute(
                "UPDATE processing_log SET status = 'success', finished_at = ?, page_count = ?,"
                " output_file = ? WHERE id = ?",
                (_now_iso(self._clock()), todo, str(outputs[0]) if outputs else None, row))

    def _finish(self, task: HotFolderTask, started: datetime, summary: RunSummary) -> None:
        """Statusul de dupa rulare (S-016…S-020) si jurnalul (S-067…S-069)."""
        now = self._clock()
        fields: dict[str, Any] = {"last_run_at": _now_iso(now)}
        current = self.task(task.name)
        failed = summary.limit_reached or (summary.errors > 0 and not summary.outputs)
        if summary.stopped:
            fields.update(status="stopped", next_run_at=None)
        elif failed:
            fields.update(status="error", next_run_at=None,
                          last_error=summary.messages[-1][1] if summary.messages else None)
        elif current.status == "running" and task.schedule_kind != "once":
            nxt = next_start(task, now, now)  # `Watching...`
            fields.update(next_run_at=_now_iso(nxt) if nxt else None, last_error=None)
        else:
            fields.update(status="completed", next_run_at=None, last_error=None)
        self._set(task.name, **fields)
        if self._ctx.settings.get("hotfolder.logging"):
            self._write_log(task, started, now, summary)

    def log_path(self, task: HotFolderTask) -> Path | None:
        """S-068: jurnalul TXT e in folderul rezultatelor (primul pas de salvare)."""
        save = next((s for s in task.steps if s.step_type == "save" and s.output_folder), None)
        if save is None or not save.output_folder:
            return None
        return Path(save.output_folder) / f"{safe_name(task.name) or 'hotfolder'}.log.txt"

    def _write_log(self, task: HotFolderTask, started: datetime, finished: datetime,
                   summary: RunSummary) -> None:
        """S-069: numele si setarile sarcinii, erorile si avertismentele, statisticile."""
        path = self.log_path(task)
        if path is None:
            return
        tr = self._tr
        settings = {k: v for k, v in asdict(task).items()
                    if k not in ("status", "last_run_at", "next_run_at", "last_error",
                                 "credential_ref")}
        lines = [
            tr("hotfolder.log.header", task=task.name, start=_now_iso(started),
               end=_now_iso(finished)),
            tr("hotfolder.log.settings", settings=json.dumps(settings, ensure_ascii=False,
                                                             default=str)),
        ]
        lines += [tr(f"hotfolder.log.{level}", text=text) for level, text in summary.messages]
        lines.append(tr("hotfolder.log.stats", pages=summary.pages, errors=summary.errors,
                        warnings=summary.warnings, uncertain=summary.uncertain))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n\n")
        except OSError:
            pass

    def log_entries(self, name: str, *, limit: int = 200) -> list[Mapping[str, Any]]:
        """S-070: randurile din `processing_log`, cele mai noi intai."""
        rows = self._con.execute(
            "SELECT source_file, output_file, started_at, finished_at, status, page_count,"
            " error_code, error_message, retry_count FROM processing_log"
            " WHERE hot_folder_id = ? ORDER BY id DESC LIMIT ?",
            (self._task_id(name), limit)).fetchall()
        keys = ("source_file", "output_file", "started_at", "finished_at", "status",
                "page_count", "error_code", "error_message", "retry_count")
        return [dict(zip(keys, r, strict=True)) for r in rows]

    # --- exportul si importul (S-065) ---

    def export_task(self, name: str, path: Path) -> None:
        data = asdict(self.task(name))
        for key in ("status", "last_run_at", "next_run_at", "last_error", "credential_ref",
                    "is_enabled"):
            data.pop(key, None)
        payload = {"format": HFT_FORMAT, "format_version": HFT_VERSION, "task": data}
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    def import_task(self, path: Path) -> HotFolderTask:
        """S-065: sarcina se incarca pe alt calculator; un nume existent primeste
        un numar; sarcina importata e oprita."""
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CoreError(f"fisier de sarcina ilizibil: {exc}", path=str(path)) from exc
        if not isinstance(payload, dict) or payload.get("format") != HFT_FORMAT:
            raise CoreError("nu e o sarcina Hot Folder DocuLens", path=str(path))
        version = int(payload.get("format_version", 0))
        if version > HFT_VERSION:
            raise ProjectVersionError("sarcina e dintr-o versiune mai noua", found=version,
                                      supported=HFT_VERSION)
        data = dict(payload["task"])
        steps = [HotFolderStep(**s) for s in data.pop("steps", [])]
        data["schedule_days"] = tuple(data.get("schedule_days") or ())
        known = set(HotFolderTask.__dataclass_fields__) - {"steps"}
        task = HotFolderTask(steps=steps, **{k: v for k, v in data.items() if k in known})
        task.name = self._free_name(task.name)
        task.status, task.is_enabled = "stopped", False
        self.save(task)
        return self.task(task.name)


def summary_text(summary: RunSummary, tr: Callable[..., str]) -> str:
    """S-066: textul notificarii de la final."""
    key = "hotfolder.notify.error" if summary.errors else "hotfolder.notify.done"
    return tr(key, task=summary.task, files=summary.files, pages=summary.pages,
              errors=summary.errors)
