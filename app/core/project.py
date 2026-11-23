"""Proiectul OCR: folderul cu paginile, zonele si textul.

Implementeaza din `OcrProject` (SPEC_05 sectiunea 9):
- pasul 1c: create, open, save, close, pages, page, add_images, set_metadata,
  settings, autosave, find_recovery;
- pasul 1d: delete_pages, rotate_pages, reorder_pages, interleave_duplex,
  swap_book_pages, move_pages_to, find_blank_pages;
- pasul 1e: can_undo, can_redo, undo_description, undo, redo (J-041);
- pasul 2d: preprocess_pages, revert_to_original, select_pages, preprocesarea
  automata la adaugare (J-051, L-030), undo pentru imagini (L-109);
- pasul 3a: zonele paginilor (PageData.areas), in istoricul de undo si la
  mutarea paginilor. Editarea zonelor e in app/core/layout/areas.py;
- pasul 3d: tabelele zonelor (AreaData.table), celulele, separatoarele si
  avertismentele paginii in istoricul de undo.

ID-urile sunt cele reale din SPEC_02. Docstring-urile `OcrProject` din SPEC_05
folosesc numerotarea veche (tabelul din docs/plan/faza_1_pasi.md).

Structura pe disc (SPEC_04 PARTEA II):
    <proiect>/project.db
    <proiect>/images/<id>.<ext>

Copie de lucru (docs/plan/faza_1_pasi.md, decizia 3): un proiect deschis se
editeaza intr-o copie din folderul temporar al sesiunii. Proiectul de pe disc
nu se schimba pana la `save`, deci o cadere nu il strica (J-036, J-037, J-040).
"""

from __future__ import annotations

import base64
import dataclasses
import errno
import io
import itertools
import json
import shutil
import sqlite3
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageOps, ImageStat

from app.core import db
from app.core.applog import get_logger
from app.core.context import AppContext, current
from app.core.errors import (
    CoreError,
    DiskFullError,
    FileCorruptError,
    InvalidProjectError,
    LastPageError,
    NoWritePermissionError,
    OperationCancelledError,
)
from app.core.images.loader import PDF_EXTENSIONS, ImageLoader, LoadedImage
from app.core.images.preprocess import (
    PreprocessPipeline,
    apply_chain,
    default_pipeline,
    estimate_is_photo,
    from_array,
    is_bilevel,
    to_array,
)
from app.core.layout.areas import AREA_COLUMNS, area_from_row, load_tables
from app.core.model import (
    AreaType,
    AutoProcessMode,
    CancelToken,
    ColorMode,
    LanguageCode,
    LayoutMode,
    PageData,
    PageStatus,
    PageWarning,
    PasswordCallback,
    PreprocessOp,
    Progress,
    ProgressCallback,
)
from app.core.ocr.store import load_cell_text, load_text
from app.core.settings import OverrideSettingsStore, SettingsStore

DB_NAME = "project.db"
IMAGES_DIR = "images"
RECOVERY_EXTENSION = "dlproj"

AUTOSAVE_INTERVAL_S = 300
"""J-036: la fiecare 5 minute. [DECIZIE] din SPEC_05. Ceasul il tine apelantul."""

THUMBNAIL_SIZE = 160
"""[DECIZIE] Latura maxima a miniaturii salvate in page.thumbnail_blob."""

METADATA_FIELDS = ("title", "author", "subject", "keywords")
"""J-038: nume, autor, subiect, cuvinte cheie."""

_COPY_AS_IS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"})
"""O imagine de o pagina in aceste formate se copiaza in proiect octet cu
octet (J-050), fara recomprimare. Restul (multipagina, PDF, alte formate,
fotografii cu rotire EXIF) se scriu ca PNG, fara pierderi."""

_RENUMBER_OFFSET = 1_000_000
"""Mutare temporara a numerelor de pagina, ca renumerotarea sa nu loveasca
UNIQUE(page_number) si nici CHECK(page_number >= 1)."""

BLANK_THRESHOLD = 0.98
"""[DECIZIE] O pagina e candidata la stergere cand blank_score >= 0.98, adica
cerneala acopera cel mult ~0,02% din pagina. Un numar de pagina singur ramane
sub prag; un rand de text, nu. De calibrat pe grupul `goale/` din SPEC_06
(precizie si rapel >= 95%)."""

_INK_FULL = 0.01
"""Proportia de cerneala la care blank_score ajunge la 0."""

_INK_DELTA = 40
"""Cat trebuie sa difere un pixel de fundal, pe orice canal, ca sa conteze."""

_BLANK_SAMPLE = 600
"""Latura mare a imaginii micsorate pentru detectie. Micsorarea prin medie
estompeaza praful de scaner (cativa pixeli izolati)."""

HISTORY_MIN_STEPS = 50
"""J-041: minimum 50 de pasi. Schema pastreaza 200 (triggerul undo_entry_cap)."""

_untitled = itertools.count(1)
_log = get_logger("core.project")

_PAGE_COLUMNS = (
    "id, page_number, image_path, original_path, width_px, height_px, dpi_x, dpi_y,"
    " color_mode, rotation, status, source_file, source_page, skew_angle,"
    " estimated_dpi, blank_score, avg_confidence, uncertain_count"
)


def _ignore_wal(_dir: str, names: list[str]) -> list[str]:
    return [n for n in names if n.endswith(("-wal", "-shm"))]


def _copy_project_tree(src: Path, dest: Path, keep_images: set[str] | None = None) -> None:
    """Copiaza proiectul. Cu `keep_images`, din images/ se copiaza doar acestea:
    imaginile ramase de la pagini sterse sau rotite stau in copia de lucru
    (pentru undo, pasul 1e), dar nu ajung in proiectul salvat."""

    def ignore(directory: str, names: list[str]) -> list[str]:
        skipped = _ignore_wal(directory, names)
        if keep_images is not None and Path(directory).name == IMAGES_DIR:
            skipped += [n for n in names if n not in keep_images]
        return skipped

    shutil.copytree(src, dest, ignore=ignore)


def _write_error(exc: OSError, path: Path) -> CoreError:
    if exc.errno == errno.ENOSPC:
        return DiskFullError(str(exc), path=str(path))
    return NoWritePermissionError(str(exc), path=str(path))


# SPEC_05 sect. 9. J-030..J-040, J-050, J-066
class OcrProject:
    """Detine paginile, zonele si textul; nu stie nimic despre interfata."""

    def __init__(
        self,
        ctx: AppContext,
        work_dir: Path,
        con: sqlite3.Connection,
        path: Path | None,
        untitled_number: int | None,
    ) -> None:
        self._ctx = ctx
        self._work = work_dir
        self._con = con
        self.path: Path | None = path
        self.untitled_number = untitled_number
        """Pentru `Untitled project N` (J-030): textul il pune GUI-ul, tradus."""
        self._loader = ImageLoader()
        self._dirty = False
        self._revision = 0
        """Creste la fiecare modificare; salvarea automata copiaza doar daca s-a
        schimbat ceva de la copia anterioara."""
        self._autosaved: tuple[int, dict[str, Any]] | None = None
        self._recovery_path: Path | None = None
        self._closed = False
        self._settings = self._load_settings()
        self._saved_overrides = self._settings.overrides
        self._pages: list[PageData] = []
        self._reload_pages()
        self._ocr_signature = self._signature()
        """N-026: setarile OCR si limbile fata de care paginile recunoscute sunt valabile."""
        self._settings.add_listener(self.check_ocr_settings)
        ctx.settings.add_listener(self.check_ocr_settings)
        ctx.open_documents.add(self)

    # ------------------------------------------------------------------ creare

    # J-030: proiect gol
    @classmethod
    def create(cls, name: str | None = None, *, context: AppContext | None = None) -> OcrProject:
        """Proiect gol. Fara nume, GUI-ul il afiseaza `Untitled project N`
        (`untitled_number`); la prima salvare primeste numele folderului."""
        ctx = context or current()
        work = cls._new_work_dir(ctx)
        con = db.create_project_db(work / DB_NAME, (name or "").strip(), ctx.app_version)
        (work / IMAGES_DIR).mkdir()
        return cls(ctx, work, con, None, None if name else next(_untitled))

    # J-031, J-032
    @classmethod
    def open(cls, path: Path, *, context: AppContext | None = None) -> OcrProject:
        """Deschide folderul de proiect (sau project.db din el).

        Erori: `InvalidProjectError` (structura stricata, imagini lipsa),
        `ProjectVersionError` (proiect dintr-o versiune mai noua).
        J-032 (proiecte din versiuni mai vechi): exista o singura versiune a
        schemei, deci nu e inca nimic de convertit. INCOMPLET, marcat.
        """
        ctx = context or current()
        folder = Path(path)
        if folder.name == DB_NAME:
            folder = folder.parent
        db.open_project_db(folder / DB_NAME).close()  # valideaza antetul si versiunea
        work = cls._new_work_dir(ctx, create=False)
        try:
            _copy_project_tree(folder, work)
        except OSError as exc:
            raise InvalidProjectError("proiectul nu se poate citi", path=str(folder),
                                      detail=str(exc)) from exc
        project = cls._from_work_dir(ctx, work, folder)
        project._read_user_languages()
        missing = [p.page_number for p in project._pages if not p.image_path.is_file()]
        if missing:
            project.close()
            raise InvalidProjectError(
                "lipsesc imagini din proiect", path=str(folder), detail="missing_images",
                pages=missing,
            )
        return project

    @classmethod
    def _from_work_dir(cls, ctx: AppContext, work: Path, path: Path | None) -> OcrProject:
        con = db.open_project_db(work / DB_NAME)
        (work / IMAGES_DIR).mkdir(exist_ok=True)
        return cls(ctx, work, con, path, None)

    @staticmethod
    def _new_work_dir(ctx: AppContext, *, create: bool = True) -> Path:
        work = ctx.health.temp_folder() / "projects" / uuid.uuid4().hex[:12]
        if create:
            work.mkdir(parents=True)
        else:
            work.parent.mkdir(parents=True, exist_ok=True)
        return work

    # ------------------------------------------------------------- salvare

    # J-034
    # P-030: limbile proprii folosite de proiect stau si in folderul lui
    _LANGUAGES_FILE = "languages.json"

    def _write_user_languages(self) -> None:
        from app.core.ocr.languages import LanguageRegistry

        codes = [*self._settings.get("lang.manual"), *self._settings.get("lang.auto_candidates")]
        codes += [r[0] for r in self._con.execute(
            "SELECT DISTINCT language_code FROM word WHERE language_code IS NOT NULL")]
        items = LanguageRegistry(con=self._ctx.app_db).export_user_languages(codes)
        target = self._work / self._LANGUAGES_FILE
        if items:
            target.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            target.unlink(missing_ok=True)

    def _read_user_languages(self) -> list[str]:
        """Limbile proprii ale proiectului care lipsesc pe acest calculator se
        adauga in app.db. Un fisier stricat nu impiedica deschiderea."""
        from app.core.ocr.languages import LanguageRegistry

        source = self._work / self._LANGUAGES_FILE
        if not source.is_file():
            return []
        try:
            items = json.loads(source.read_text(encoding="utf-8"))
            return LanguageRegistry(con=self._ctx.app_db).import_user_languages(items)
        except (ValueError, KeyError, TypeError):
            return []

    def save(self, path: Path | None = None) -> None:
        """Scrie proiectul in `path` (Save As) sau in folderul curent (Save).

        Scrierea e atomica: proiectul se copiaza alaturi si abia apoi ia locul
        celui vechi. `path` trebuie sa fie un folder nou, gol, sau un proiect
        existent: un folder cu alte fisiere nu se suprascrie (FileExistsError).

        Erori: `NoWritePermissionError`, `DiskFullError`, `ValueError` (prima
        salvare fara cale), `FileExistsError`.
        """
        self._require_open()
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ValueError("proiectul nu a fost salvat niciodata: dati o cale")
        target = target.resolve()
        if target == self._work.resolve() or self._work.resolve() in target.parents:
            raise ValueError("nu se poate salva in copia de lucru")
        _check_save_target(target)

        with self._con:
            if not self.name:
                self._con.execute("UPDATE project SET name = ?", (target.name,))
            self._con.execute(
                "UPDATE project SET settings_override = ?, updated_at = ?",
                (json.dumps(self._settings.overrides, ensure_ascii=False), db._utc_now()),
            )
        self._checkpoint()
        self._write_user_languages()

        tag = uuid.uuid4().hex[:8]
        staging = target.parent / f".{target.name}.saving-{tag}"
        backup = target.parent / f".{target.name}.old-{tag}"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_project_tree(self._work, staging, keep_images=self._referenced_images())
            _clear_saved_history(staging / DB_NAME)
            if target.exists():
                target.rename(backup)
            try:
                staging.rename(target)
            except OSError:
                if backup.exists():
                    backup.rename(target)
                raise
        except OSError as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise _write_error(exc, target) from exc
        shutil.rmtree(backup, ignore_errors=True)

        self.path = target
        self.untitled_number = None
        self._dirty = False
        self._saved_overrides = self._settings.overrides
        self._forget_autosave()
        _log.info("proiect salvat: %s (%d pagini)", target, len(self._pages))

    # J-035
    def close(self) -> None:
        """Nu intreaba nimic: apelantul verifica `is_modified` inainte."""
        if self._closed:
            return
        self._ctx.settings.remove_listener(self.check_ocr_settings)
        self._con.close()
        shutil.rmtree(self._work, ignore_errors=True)
        self._forget_autosave()
        self._closed = True
        self._ctx.open_documents.discard(self)

    # -------------------------------------------- salvare automata (J-036/37)

    # J-036
    def autosave(self) -> Path | None:
        """Copie de siguranta, doar daca exista modificari nesalvate.

        Intoarce calea copiei (cea noua, sau cea existenta daca nu s-a schimbat
        nimic de la ultima), ori None daca proiectul n-are nimic de salvat.
        SPEC_05 da tipul `Path`; None e adaugat pentru cazul fara modificari.
        """
        self._require_open()
        state = (self._revision, self._settings.overrides)
        if not self.is_modified or state == self._autosaved:
            return self._recovery_path
        self._checkpoint()
        registry = self._ctx.recovery
        dest = registry.new_recovery_path("ocr_project", RECOVERY_EXTENSION)
        try:
            _copy_project_tree(self._work, dest)
        except OSError as exc:
            shutil.rmtree(dest, ignore_errors=True)
            raise _write_error(exc, dest) from exc
        registry.register(dest, self.path, "ocr_project")
        self._forget_autosave()
        self._recovery_path = dest
        self._autosaved = state
        return dest

    # J-037, Y-026
    @classmethod
    def find_recovery(cls, *, context: AppContext | None = None) -> list[tuple[Path, Path | None]]:
        """(copia de siguranta, calea originala) pentru proiectele ramase de la
        o sesiune cazuta. None = proiect care nu fusese salvat niciodata."""
        ctx = context or current()
        return [
            (e.recovery_path, e.original_path)
            for e in ctx.recovery.find_pending()
            if e.doc_kind == "ocr_project"
        ]

    # J-037. Adaugare fata de SPEC_05: contractul gaseste copiile, dar nu spune
    # cum se deschide una. Marcat in raportul pasului 1c.
    @classmethod
    def recover(cls, recovery_path: Path, *, context: AppContext | None = None) -> OcrProject:
        """Deschide o copie de siguranta ca proiect nesalvat, cu calea originala.
        Copia se sterge din evidenta: de acum o protejeaza salvarea automata."""
        ctx = context or current()
        recovery_path = Path(recovery_path)
        entry = next(
            (e for e in ctx.recovery.find_pending() if e.recovery_path == recovery_path), None
        )
        if entry is None:
            raise InvalidProjectError("copia de siguranta nu exista", path=str(recovery_path),
                                      detail="not_pending")
        work = cls._new_work_dir(ctx, create=False)
        _copy_project_tree(recovery_path, work)
        project = cls._from_work_dir(ctx, work, entry.original_path)
        project._touch()
        ctx.recovery.discard(entry)
        return project

    def _forget_autosave(self) -> None:
        if self._recovery_path is not None:
            self._ctx.recovery.forget(self._recovery_path)
            self._recovery_path = None
        self._autosaved = None

    # ------------------------------------------------------------- stare

    @property
    def name(self) -> str:
        """Numele din antet. Gol pana la prima salvare, daca n-a fost dat."""
        return self._row("SELECT name FROM project")[0]

    # J-040
    @property
    def is_modified(self) -> bool:
        """Modificari nesalvate, inclusiv setarile de proiect (J-039)."""
        return self._dirty or self._settings.overrides != self._saved_overrides

    @property
    def languages(self) -> tuple[LanguageCode, ...]:
        return tuple(json.loads(self._row("SELECT language_codes FROM project")[0]))

    @languages.setter
    def languages(self, codes: Sequence[LanguageCode]) -> None:
        """P-001: minimum o limba, fara duplicate."""
        codes = list(codes)
        if not codes or not all(isinstance(c, str) and c.strip() for c in codes):
            raise ValueError("trebuie selectata cel putin o limba")
        if len(set(codes)) != len(codes):
            raise ValueError("o limba apare de doua ori")
        self._update("UPDATE project SET language_codes = ?", (json.dumps(codes),))
        self.check_ocr_settings()  # N-026

    @property
    def layout_mode(self) -> LayoutMode:
        return LayoutMode(self._row("SELECT layout_mode FROM project")[0])

    @layout_mode.setter
    def layout_mode(self, mode: LayoutMode) -> None:
        self._update("UPDATE project SET layout_mode = ?", (LayoutMode(mode).value,))

    # J-038
    def set_metadata(self, **fields: str) -> None:
        """title, author, subject, keywords. Se scriu la export."""
        unknown = set(fields) - set(METADATA_FIELDS)
        if unknown:
            raise ValueError(f"metadate necunoscute: {sorted(unknown)}; permise: {METADATA_FIELDS}")
        for key, value in fields.items():
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{key}: se asteapta text")
            self._update(f"UPDATE project SET meta_{key} = ?", (value or None,))

    # J-038. Adaugare fata de SPEC_05: citirea metadatelor, pentru dialog.
    @property
    def metadata(self) -> dict[str, str | None]:
        cols = ", ".join(f"meta_{k}" for k in METADATA_FIELDS)
        return dict(zip(METADATA_FIELDS, self._row(f"SELECT {cols} FROM project"), strict=True))

    # J-039
    def settings(self) -> SettingsStore:
        """Setarile globale, cu suprascrierile proiectului peste ele.
        Suprascrierile se salveaza odata cu proiectul."""
        self._require_open()
        return self._settings

    def _load_settings(self) -> OverrideSettingsStore:
        raw = self._row("SELECT settings_override FROM project")[0]
        store = self._ctx.settings.with_overrides({})
        try:
            saved = json.loads(raw)
        except json.JSONDecodeError:
            saved = {}
        for key, value in (saved.items() if isinstance(saved, dict) else ()):
            try:
                store.set(key, value)
            except ValueError as exc:
                _log.warning("setare de proiect ignorata %s: %s", key, exc)
        return store

    # ------------------------------------------------------------- pagini

    @property
    def pages(self) -> Sequence[PageData]:
        """Paginile, in ordine. Modificarile trec prin metodele proiectului,
        nu prin obiectele intoarse (altfel nu intra in istoric)."""
        self._require_open()
        return tuple(self._pages)

    def page(self, number: int) -> PageData:
        self._require_open()
        if not 1 <= number <= len(self._pages):
            raise ValueError(f"pagina {number} nu exista (1..{len(self._pages)})")
        return self._pages[number - 1]

    # J-050, J-066, J-052; J-051 (vezi `auto_process`)
    def add_images(
        self,
        paths: Sequence[Path],
        *,
        at: int | None = None,
        password: PasswordCallback | None = None,
        auto_process: AutoProcessMode | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> tuple[list[PageData], list[tuple[Path, CoreError]]]:
        """Adauga paginile fisierelor, copiate in proiect, apoi (J-051) le
        preproceseaza daca setarile o cer.

        `at`: numarul paginii inaintea careia se insereaza (1..n+1); None = la
        sfarsit. Paginile urmatoare se renumeroteaza (J-066).

        Un fisier nesuportat, stricat sau cu parola refuzata NU opreste lotul:
        se sare si se raporteaza in a doua lista (J-050). Un fisier se adauga
        intreg sau deloc. Anularea se verifica intre fisiere si intre pagini;
        paginile deja adaugate raman, apoi se ridica `OperationCancelledError`.

        `auto_process` (J-051, X-012): None = din setari (X-011, X-012).
        Orice mod in afara de NONE preproceseaza paginile noi cu lantul
        recomandat (L-010). INCOMPLET, marcat: analiza (faza 3) si
        recunoasterea (faza 4) se adauga atunci.
        """
        self._require_open()
        insert_at = len(self._pages) + 1 if at is None else at
        if not 1 <= insert_at <= len(self._pages) + 1:
            raise ValueError(f"pozitie de inserare invalida: {at} (1..{len(self._pages) + 1})")
        paths = [Path(p) for p in paths]
        added: list[PageData] = []
        skipped: list[tuple[Path, CoreError]] = []
        with self._history("add_images", {"files": [p.name for p in paths]},
                           barrier_if_empty=True):
            self._add_all(paths, insert_at, password, progress, cancel, added, skipped)
        if progress is not None:
            progress(Progress(len(paths), len(paths), "stage.adding_pages"))
        # J-051, X-011, X-012, L-030: doar paginile adaugate acum
        mode = auto_process
        if mode is None:
            mode = self._settings.preprocess_settings().auto_mode
        if added and AutoProcessMode(mode) is not AutoProcessMode.NONE:
            ids = {pg.id for pg in added}
            earlier = {pg.id for pg in self._pages if pg.id not in ids}
            self.preprocess_pages([pg.page_number for pg in self._pages if pg.id in ids],
                                  progress=progress, cancel=cancel)
            # paginile noi, inclusiv cele nascute dintr-o impartire (L-016)
            added = [pg for pg in self._pages if pg.id not in earlier]
            if AutoProcessMode(mode) is not AutoProcessMode.PREPROCESS_ONLY:
                self._auto_recognize([pg.id for pg in added], AutoProcessMode(mode),
                                     progress, cancel)
                added = [pg for pg in self._pages if pg.id not in earlier]
        return added, skipped

    # N-001, X-012, X-017: dupa preprocesare, orientarea, analiza si recunoasterea
    def _auto_recognize(self, ids: list[int], mode: AutoProcessMode,
                        progress: ProgressCallback | None, cancel: CancelToken | None) -> None:
        """READ (X-012 `recognize`): orientare, analiza, recunoastere.
        ANALYZE_AND_READ (X-012 `analyze`): orientare si analiza; recunoasterea
        se porneste manual. Fara Tesseract, paginile raman analizate."""
        from app.core.errors import LanguageModelMissingError
        from app.core.layout.analyzer import LayoutAnalyzer  # analyzer importa project
        from app.core.ocr.service import RecognitionService

        numbers = [pg.page_number for pg in self._pages if pg.id in ids]
        analyzer = LayoutAnalyzer()
        if self._settings.get("image.correct_orientation"):
            for n in numbers:
                turn = analyzer.detect_orientation(self.page(n))
                if turn:
                    self.rotate_pages([n], turn)
        self.analyze_pages(numbers, analyzer=analyzer, cancel=cancel)
        if mode is AutoProcessMode.READ:
            try:
                RecognitionService(self, analyzer=analyzer).recognize_pages(
                    numbers, progress=progress, cancel=cancel)
            except LanguageModelMissingError as exc:
                _log.warning("recunoasterea automata sarita: %s", exc)

    def _add_all(
        self,
        paths: list[Path],
        insert_at: int,
        password: PasswordCallback | None,
        progress: ProgressCallback | None,
        cancel: CancelToken | None,
        added: list[PageData],
        skipped: list[tuple[Path, CoreError]],
    ) -> None:
        for i, path in enumerate(paths):
            if cancel is not None and cancel():
                raise OperationCancelledError(done=i, total=len(paths))
            if progress is not None:
                progress(Progress(i, len(paths), "stage.adding_pages", path.name))
            try:
                images = self._loader.load(path, password=password, cancel=cancel)
                numbers = self._add_file(path, images, insert_at)
            except OperationCancelledError:
                self._reload_pages()
                raise
            except CoreError as exc:
                skipped.append((path, exc))
                _log.info("fisier sarit %s: %s", path, exc.code)
                continue
            except FileNotFoundError:
                skipped.append((path, FileCorruptError(
                    "fisierul lipseste", path=str(path), detail="not_found")))
                continue
            self._reload_pages()
            added.extend(self._pages[n - 1] for n in numbers)
            insert_at += len(numbers)

    def _add_file(self, path: Path, images: list[LoadedImage], at: int) -> list[int]:
        """Scrie imaginile si randurile unui fisier, totul sau nimic."""
        written: list[Path] = []
        single = len(images) == 1 and self._loader.read_page_count(path) == 1
        try:
            with self._con:
                numbers = []
                for offset, img in enumerate(images):
                    rel, thumb, size = self._store_image(img, single, written)
                    number = at + offset
                    self._make_room(number)
                    self._con.execute(
                        "INSERT INTO page (page_number, image_path, original_path, thumbnail_blob,"
                        " width_px, height_px, dpi_x, dpi_y, color_mode, source_file,"
                        " source_page, source_kind) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (number, rel, rel, thumb, size[0], size[1], img.dpi_x, img.dpi_y,
                         img.color_mode.value, str(path), img.source_page,
                         "pdf" if path.suffix.lower() in PDF_EXTENSIONS
                         else "camera" if img.is_photo else "file"),
                    )
                    numbers.append(number)
        except BaseException:
            for f in written:
                f.unlink(missing_ok=True)
            raise
        self._touch()
        return numbers

    def _store_image(
        self, img: LoadedImage, single: bool, written: list[Path]
    ) -> tuple[str, bytes, tuple[int, int]]:
        """Copiaza sau scrie imaginea paginii in images/. Intoarce calea relativa,
        miniatura PNG si dimensiunea reala in pixeli."""
        ext = img.path.suffix.lower()
        name = uuid.uuid4().hex[:12]
        if single and ext in _COPY_AS_IS and not _needs_exif_rotation(img.path):
            dest = self._work / IMAGES_DIR / f"{name}{'.jpg' if ext == '.jpeg' else ext}"
            shutil.copyfile(img.path, dest)
            written.append(dest)
            with Image.open(dest) as pixels:
                return dest.relative_to(self._work).as_posix(), _thumbnail(pixels), pixels.size
        pixels = ImageOps.exif_transpose(self._loader.open_pixels(img))
        if pixels.mode not in ("1", "L", "LA", "P", "RGB", "RGBA", "I;16"):
            pixels = pixels.convert("L" if img.color_mode is not ColorMode.COLOR else "RGB")
        dest = self._work / IMAGES_DIR / f"{name}.png"
        pixels.save(dest, format="PNG", dpi=(img.dpi_x, img.dpi_y))
        written.append(dest)
        return dest.relative_to(self._work).as_posix(), _thumbnail(pixels), pixels.size

    def _make_room(self, number: int) -> None:
        """Muta cu o pozitie paginile de la `number` in sus (J-066)."""
        self._con.execute(
            "UPDATE page SET page_number = page_number + ? WHERE page_number >= ?",
            (_RENUMBER_OFFSET, number),
        )
        self._con.execute(
            "UPDATE page SET page_number = page_number - ? + 1 WHERE page_number >= ?",
            (_RENUMBER_OFFSET, _RENUMBER_OFFSET),
        )

    def _reload_pages(self) -> None:
        rows = self._con.execute(
            f"SELECT {_PAGE_COLUMNS} FROM page ORDER BY page_number"
        ).fetchall()
        self._pages = [self._page_from_row(r) for r in rows]
        by_id = {pg.id: pg for pg in self._pages}
        tables = load_tables(self._con)
        texts = load_text(self._con)
        cell_texts = load_cell_text(self._con)
        for table in tables.values():
            for cell in table.cells:
                cell.blocks = cell_texts.get(cell.id, [])
        for row in self._con.execute(
            f"SELECT {AREA_COLUMNS} FROM area ORDER BY page_id, order_index"
        ):
            page_id, area = area_from_row(row)
            if page_id in by_id:
                area.table = tables.get(area.id)
                area.blocks = texts.get(area.id, [])
                by_id[page_id].areas.append(area)
        for page_id, severity, code, message, dismissed in self._con.execute(
            "SELECT page_id, severity, code, message, is_dismissed FROM page_warning ORDER BY id"
        ):
            if page_id in by_id:
                by_id[page_id].warnings.append(
                    PageWarning(severity, code, message, {}, bool(dismissed)))

    def _page_from_row(self, r: tuple[Any, ...]) -> PageData:
        (pid, number, image_rel, original_rel, w, h, dx, dy, color, rotation, status,
         source_file, source_page, skew, est_dpi, blank, conf, uncertain) = r
        return PageData(
            id=pid, page_number=number,
            image_path=self._work / image_rel, original_path=self._work / original_rel,
            width_px=w, height_px=h, dpi_x=dx, dpi_y=dy, color_mode=ColorMode(color),
            rotation=rotation, status=PageStatus(status),
            source_file=Path(source_file) if source_file else None, source_page=source_page,
            skew_angle=skew, estimated_dpi=est_dpi, blank_score=blank,
            avg_confidence=conf, uncertain_count=uncertain,
        )

    # ------------------------------------------------- operatii pe pagini (1d)

    # J-055
    def delete_pages(self, numbers: Sequence[int]) -> None:
        """Sterge paginile si tot ce tine de ele (zone, text, avertismente).
        `LastPageError` daca proiectul ar ramane fara nicio pagina."""
        chosen = self._validate_numbers(numbers)
        if len(chosen) >= len(self._pages):
            raise LastPageError("proiectul trebuie sa pastreze cel putin o pagina",
                                pages=chosen)
        ids = [self._pages[n - 1].id for n in chosen]
        with self._history("delete_pages", {"pages": chosen}), self._con:
            self._con.executemany("DELETE FROM page WHERE id = ?", [(i,) for i in ids])
            self._renumber([pg.id for pg in self._pages if pg.id not in ids])
        self._after_change()

    # J-058
    def rotate_pages(self, numbers: Sequence[int], degrees: int) -> None:
        """Roteste paginile in sensul acelor de ceasornic (`degrees` multiplu de
        90; negativ = invers). Rotirea invalideaza zonele si textul paginii:
        o pagina recunoscuta revine la `analyzed`. Imaginea originala ramane."""
        if not isinstance(degrees, int) or degrees % 90:
            raise ValueError(f"rotirea trebuie sa fie multiplu de 90: {degrees}")
        chosen = self._validate_numbers(numbers)
        turn = degrees % 360
        if turn == 0:
            return
        transpose = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                     270: Image.Transpose.ROTATE_90}[turn]
        written: list[Path] = []
        try:
            with self._history("rotate_pages", {"pages": chosen, "degrees": degrees}), self._con:
                for n in chosen:
                    pg = self._pages[n - 1]
                    with Image.open(pg.image_path) as src:
                        rotated = src.transpose(transpose)
                    dest = self._work / IMAGES_DIR / f"{uuid.uuid4().hex[:12]}.png"
                    rotated.save(dest, format="PNG", dpi=(pg.dpi_y, pg.dpi_x) if turn % 180
                                 else (pg.dpi_x, pg.dpi_y))
                    written.append(dest)
                    self._invalidate_text(pg.id)
                    w, h = rotated.size
                    dpi_x, dpi_y = (pg.dpi_y, pg.dpi_x) if turn % 180 else (pg.dpi_x, pg.dpi_y)
                    self._con.execute(
                        "UPDATE page SET image_path = ?, width_px = ?, height_px = ?, dpi_x = ?,"
                        " dpi_y = ?, rotation = ?, thumbnail_blob = ?, skew_angle = NULL,"
                        " updated_at = ? WHERE id = ?",
                        (dest.relative_to(self._work).as_posix(), w, h, dpi_x, dpi_y,
                         (pg.rotation + turn) % 360, _thumbnail(rotated), db._utc_now(), pg.id),
                    )
        except BaseException:
            for f in written:
                f.unlink(missing_ok=True)
            raise
        self._after_change()

    # N-026
    def _signature(self) -> str:
        """Setarile care schimba rezultatul recunoasterii: limbile proiectului si
        setarile OCR efective (fara numarul de fire, care schimba doar viteza)."""
        settings = dataclasses.asdict(self._settings.ocr_settings())
        settings.pop("max_threads", None)
        settings["project_languages"] = list(self.languages)
        return json.dumps(settings, sort_keys=True, default=str)

    def check_ocr_settings(self) -> list[int]:
        """N-026: daca setarile OCR sau limbile s-au schimbat de la ultima
        verificare, paginile recunoscute (si cele verificate) revin la `analyzed`:
        zonele raman, iar exportul avertizeaza ca trebuie recunoscute din nou
        (Q-034). Intoarce numerele paginilor afectate."""
        if self._closed:
            return []
        signature = self._signature()
        if signature == self._ocr_signature:
            return []
        self._ocr_signature = signature
        affected = [p.page_number for p in self._pages
                    if p.status in (PageStatus.RECOGNIZED, PageStatus.VERIFIED)]
        if affected:
            with self._con:
                self._con.execute(
                    "UPDATE page SET status = 'analyzed'"
                    " WHERE status IN ('recognized', 'verified')")
            self._after_change()
        return affected

    def _invalidate_text(self, page_id: int) -> None:
        """J-058, N-026: zonele si textul paginii nu mai sunt valabile."""
        self._con.execute("DELETE FROM area WHERE page_id = ?", (page_id,))
        self._con.execute(
            "UPDATE page SET status = CASE WHEN status IN ('recognized','verified')"
            " THEN 'analyzed' ELSE status END, avg_confidence = NULL, uncertain_count = 0,"
            " recognized_at = NULL, recognition_ms = NULL WHERE id = ?",
            (page_id,),
        )

    # J-059, J-060, J-064
    def reorder_pages(self, new_order: Sequence[int], *, undoable: bool = True) -> None:
        """`new_order` contine toate numerele de pagina actuale, o singura data,
        in ordinea noua: [3, 1, 2] pune pagina 3 prima.

        `undoable=False` e optiunea „Reorder pages (cannot be undone)” din J-060:
        nu intra in istoric, iar istoricul de dinainte se goleste (pasii vechi
        nu mai corespund ordinii)."""
        self._reorder(new_order, "reorder_pages", undoable=undoable)

    def _reorder(self, new_order: Sequence[int], op: str, *, undoable: bool = True,
                 params: dict[str, Any] | None = None) -> None:
        self._require_open()
        order = list(new_order)
        if sorted(order) != list(range(1, len(self._pages) + 1)):
            raise ValueError(
                f"noua ordine trebuie sa contina fiecare pagina 1..{len(self._pages)} o data"
            )
        if order == sorted(order):
            return
        if not undoable:
            with self._con:
                self._renumber([self._pages[n - 1].id for n in order])
            self._clear_history()
        else:
            with self._history(op, params or {"order": order}), self._con:
                self._renumber([self._pages[n - 1].id for n in order])
        self._after_change()

    # J-061
    def interleave_duplex(
        self, numbers: Sequence[int] | None = None, *, backs_reversed: bool = True
    ) -> None:
        """Reface ordinea dupa o scanare duplex in doua treceri.

        Paginile selectate (implicit toate) contin intai fetele, apoi versourile.
        `backs_reversed`: versourile au fost scanate de la ultima la prima
        (teancul intors); False = in ordine normala (J-061: ordine normala sau
        inversa). [DECIZIE] Implicit inversa, cazul obisnuit la intoarcerea
        teancului.

        J-061 cere minimum trei pagini consecutive. Numar impar de pagini: o fata
        in plus, fara verso. (SPEC_05 cerea ValueError la numar impar; J-061
        accepta 3 pagini, deci decide J-061.)
        """
        chosen = self._consecutive(numbers, minimum=3)
        n_front = (len(chosen) + 1) // 2
        fronts, backs = chosen[:n_front], chosen[n_front:]
        if backs_reversed:
            backs = backs[::-1]
        merged: list[int] = []
        for i, front in enumerate(fronts):
            merged.append(front)
            if i < len(backs):
                merged.append(backs[i])
        self._replace_range(chosen, merged, "interleave_duplex")

    # J-062
    def swap_book_pages(self, numbers: Sequence[int] | None = None) -> None:
        """Inverseaza paginile stanga-dreapta, doua cate doua: 1,2,3,4 -> 2,1,4,3.
        Minimum doua pagini consecutive. La numar impar, ultima ramane pe loc."""
        chosen = self._consecutive(numbers, minimum=2)
        swapped: list[int] = []
        for i in range(0, len(chosen) - 1, 2):
            swapped += [chosen[i + 1], chosen[i]]
        if len(chosen) % 2:
            swapped.append(chosen[-1])
        self._replace_range(chosen, swapped, "swap_book_pages")

    # J-065, J-067
    def move_pages_to(self, numbers: Sequence[int], target: OcrProject) -> None:
        """Muta paginile la sfarsitul altui proiect deschis.

        Proiectul sursa trebuie sa pastreze cel putin o pagina (J-055). Zonele
        se muta odata cu paginile (pasul 3a), impreuna cu structura tabelelor,
        textul recunoscut si avertismentele (4.5.2).
        """
        if target is self:
            raise ValueError("proiectul tinta trebuie sa fie altul")
        target._require_open()
        chosen = self._validate_numbers(numbers)
        if len(chosen) >= len(self._pages):
            raise LastPageError("proiectul trebuie sa pastreze cel putin o pagina",
                                pages=chosen)
        ids = [self._pages[n - 1].id for n in chosen]
        target._receive_pages(self._work, self._con, ids)
        with self._con:
            self._con.executemany("DELETE FROM page WHERE id = ?", [(i,) for i in ids])
            self._renumber([pg.id for pg in self._pages if pg.id not in ids])
        # [DECIZIE] Mutarea nu se anuleaza in proiectul sursa: paginile exista
        # deja in tinta. Pasii vechi nu mai corespund, deci istoricul se goleste.
        self._clear_history()
        self._after_change()

    _COPIED_COLUMNS = (
        "thumbnail_blob, width_px, height_px, dpi_x, dpi_y, color_mode, rotation,"
        " source_file, source_page, source_kind, status, skew_angle, estimated_dpi,"
        " blank_score, recognized_at, recognition_ms, avg_confidence, uncertain_count"
    )

    def _receive_pages(self, src_work: Path, src_con: sqlite3.Connection, ids: list[int]) -> None:
        """Copiaza imaginile si randurile paginilor `ids` la sfarsitul proiectului."""
        written: list[Path] = []
        try:
            with self._history("receive_pages", {"count": len(ids)}, barrier_if_empty=True), \
                    self._con:
                next_number = len(self._pages) + 1
                for pid in ids:
                    image_rel, original_rel, *rest = src_con.execute(
                        f"SELECT image_path, original_path, {self._COPIED_COLUMNS}"
                        " FROM page WHERE id = ?", (pid,)).fetchone()
                    copies: dict[str, str] = {}
                    for rel in (image_rel, original_rel):
                        if rel not in copies:
                            dest = (self._work / IMAGES_DIR
                                    / f"{uuid.uuid4().hex[:12]}{Path(rel).suffix}")
                            shutil.copyfile(src_work / rel, dest)
                            written.append(dest)
                            copies[rel] = dest.relative_to(self._work).as_posix()
                    cur = self._con.execute(
                        f"INSERT INTO page (page_number, image_path, original_path,"
                        f" {self._COPIED_COLUMNS}) VALUES ({','.join('?' * (3 + len(rest)))})",
                        (next_number, copies[image_rel], copies[original_rel], *rest),
                    )
                    self._con.executemany(
                        "INSERT INTO page_operation (page_id, order_index, operation,"
                        " parameters, applied_at) VALUES (?, ?, ?, ?, ?)",
                        [(cur.lastrowid, *op) for op in src_con.execute(
                            "SELECT order_index, operation, parameters, applied_at"
                            " FROM page_operation WHERE page_id = ? ORDER BY order_index",
                            (pid,))],
                    )
                    self._copy_areas(src_con, pid, int(cur.lastrowid))
                    next_number += 1
        except BaseException:
            for f in written:
                f.unlink(missing_ok=True)
            raise
        self._after_change()

    def _copy_areas(self, src_con: sqlite3.Connection, src_page: int, dest_page: int) -> None:
        """Copiaza zonele unei pagini din alt proiect (id-uri noi), cu celulele
        si separatoarele tabelelor, textul recunoscut (blocuri, randuri,
        cuvinte) si avertismentele paginii. In tranzactia apelantului."""
        areas = self._copy_rows(src_con, "area", "page_id = ?", (src_page,),
                                {"page_id": {src_page: dest_page}})
        marks = ",".join("?" * len(areas))
        cells = self._copy_rows(src_con, "table_cell", f"area_id IN ({marks})", tuple(areas),
                                {"area_id": areas})
        self._copy_rows(src_con, "table_separator", f"area_id IN ({marks})", tuple(areas),
                        {"area_id": areas})
        blocks = self._copy_rows(src_con, "text_block", f"area_id IN ({marks})", tuple(areas),
                                 {"area_id": areas, "table_cell_id": cells})
        bmarks = ",".join("?" * len(blocks))
        lines = self._copy_rows(src_con, "text_line", f"block_id IN ({bmarks})",
                                tuple(blocks), {"block_id": blocks})
        lmarks = ",".join("?" * len(lines))
        self._copy_rows(src_con, "word", f"line_id IN ({lmarks})", tuple(lines),
                        {"line_id": lines})
        self._copy_rows(src_con, "page_warning", "page_id = ?", (src_page,),
                        {"page_id": {src_page: dest_page}})
        # triggerul area_invalidates_page_on_insert (N-026) coboara pagina la
        # `analyzed`; o copiere nu schimba zonele, deci starea ramane cea din sursa
        (status,) = src_con.execute("SELECT status FROM page WHERE id = ?",
                                    (src_page,)).fetchone()
        self._con.execute("UPDATE page SET status = ? WHERE id = ?", (status, dest_page))

    def _copy_rows(self, src_con: sqlite3.Connection, table: str, where: str,
                   args: tuple[Any, ...], remap: dict[str, dict[int, int]]) -> dict[int, int]:
        """Copiaza randurile din `table` care satisfac `where`, cu id-uri noi;
        coloanele din `remap` primesc id-urile noi ale parintilor. Intoarce
        id vechi -> id nou."""
        if not args:
            return {}
        cur = src_con.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY id", args)
        cols = [d[0] for d in cur.description]
        names = [c for c in cols if c != "id"]
        new_ids: dict[int, int] = {}
        for row in cur.fetchall():
            values = dict(zip(cols, row, strict=True))
            for col, mapping in remap.items():
                if values[col] is not None:
                    values[col] = mapping[values[col]]
            ins = self._con.execute(
                f"INSERT INTO {table} ({', '.join(names)})"
                f" VALUES ({', '.join('?' * len(names))})",
                tuple(values[n] for n in names))
            new_ids[values["id"]] = int(ins.lastrowid)
        return new_ids

    # J-056, J-057 (E-021, E-022 in PDF Editor)
    # J-013
    def dismiss_warning(self, number: int, code: str) -> None:
        """J-013: `Delete` din panoul `Warnings`: avertismentul paginii nu se mai
        arata (ramane in baza, marcat `is_dismissed`)."""
        self._require_open()
        page = self.page(number)
        with self._con:
            self._con.execute("UPDATE page_warning SET is_dismissed = 1"
                              " WHERE page_id = ? AND code = ?", (page.id, code))
        for warning in page.warnings:
            if warning.code == code:
                warning.is_dismissed = True

    def find_blank_pages(self, threshold: float | None = None) -> list[int]:
        """Paginile candidate la stergere, fara sa sterga ceva: utilizatorul le
        revizuieste (E-023). `threshold` e pragul pentru blank_score (0..1),
        implicit BLANK_THRESHOLD.

        J-057: o pagina cu note de mana, imagini sau marcaje colorate nu e goala.
        Detectia compara fiecare pixel cu fundalul pe toate canalele, deci prinde
        si scrisul de creion si marcajul galben. INCOMPLET, marcat: o euristica;
        varianta buna vine cu analiza de layout (faza 3).
        """
        self._require_open()
        limit = BLANK_THRESHOLD if threshold is None else float(threshold)
        if not 0 <= limit <= 1:
            raise ValueError(f"pragul trebuie sa fie intre 0 si 1: {threshold}")
        result = []
        for pg in self._pages:
            score = pg.blank_score
            if score is None:
                score = _blank_score(pg.image_path)
                with self._con:
                    self._con.execute("UPDATE page SET blank_score = ? WHERE id = ?",
                                      (score, pg.id))
                pg.blank_score = score
            if score >= limit:
                result.append(pg.page_number)
        return result

    # ------------------------------------------------ preprocesare (2d)

    # L-003
    def select_pages(
        self, kind: str, *, current: int | None = None, selected: Sequence[int] = ()
    ) -> list[int]:
        """Combo-ul `Selection` din Image Editor: `odd`, `even`, `current`,
        `selected` (L-003)."""
        self._require_open()
        n = len(self._pages)
        if kind == "odd":
            return list(range(1, n + 1, 2))
        if kind == "even":
            return list(range(2, n + 1, 2))
        if kind == "current":
            if current is None:
                raise ValueError("selection=current cere pagina curenta")
            return self._validate_numbers([current])
        if kind == "selected":
            return self._validate_numbers(selected)
        raise ValueError(f"selectie necunoscuta: {kind!r}; permise: odd, even, current, selected")

    def _chain_for(self, page: PageData, array: Any, pipeline: PreprocessPipeline,
                   ) -> list[tuple[PreprocessOp, dict[str, Any]]]:
        """L-010: lantul recomandat dupa setarile proiectului si tipul imaginii."""
        (kind,) = self._con.execute(
            "SELECT source_kind FROM page WHERE id = ?", (page.id,)).fetchone()
        photo = kind == "camera" or estimate_is_photo(array)
        described = LoadedImage(page.image_path, page.width_px, page.height_px, page.dpi_x,
                                page.dpi_y, page.color_mode, page.source_page, photo)
        from app.core.ocr.languages import is_rtl

        rtl = any(is_rtl(c) for c in self._settings.ocr_settings().languages)
        return pipeline.recommended_chain(
            described, self._settings.preprocess_settings(), is_photo=photo,
            correct_trapezoid=bool(self._settings.get("image.correct_trapezoid")),
            right_to_left=rtl)

    # SPEC_05 PreprocessPipeline.run; L-010..L-034, J-013 (SPEC_05), N-024
    def preprocess_pages(
        self,
        numbers: Sequence[int],
        chain: Sequence[tuple[PreprocessOp, Any]] | None = None,
        *,
        pipeline: PreprocessPipeline | None = None,
        progress: ProgressCallback | None = None,
        cancel: CancelToken | None = None,
    ) -> list[PageData]:
        """Aplica lantul pe pagini; None = lantul recomandat pentru fiecare.

        Imaginea noua se scrie langa original (originalul ramane pentru
        revenire). Operatiile se adauga in `page_operation`. Pagina devine
        `preprocessed`; zonele si textul ei se invalideaza (N-024).
        SPLIT (L-016): a doua parte devine o pagina noua, imediat dupa.
        Intoarce paginile rezultate. Un singur pas de undo (L-109).
        """
        pipe = pipeline or default_pipeline()
        chosen = self._validate_numbers(numbers)
        ids = [self._pages[n - 1].id for n in chosen]
        results: list[int] = []
        written: list[Path] = []
        try:
            with self._history("preprocess_pages", {"pages": chosen}):
                for i, pid in enumerate(ids):
                    if cancel is not None and cancel():
                        raise OperationCancelledError(done=i, total=len(ids))
                    if progress is not None:
                        progress(Progress(i, len(ids), "stage.preprocessing"))
                    results += self._preprocess_one(pid, chain, pipe, written, cancel)
                if progress is not None:
                    progress(Progress(len(ids), len(ids), "stage.preprocessing"))
        except BaseException:
            for f in written:
                f.unlink(missing_ok=True)
            self._reload_pages()
            raise
        self._after_change()
        return [pg for pg in self._pages if pg.id in results]

    def _preprocess_one(self, page_id: int, chain: Any, pipe: PreprocessPipeline,
                        written: list[Path], cancel: CancelToken | None) -> list[int]:
        page = next(pg for pg in self._pages if pg.id == page_id)
        with Image.open(page.image_path) as src:
            array = to_array(src)
        steps = list(chain) if chain is not None else self._chain_for(page, array, pipe)
        if not steps:
            return [page_id]
        parts, applied = apply_chain(array, steps, pipe, cancel=cancel)
        (start,) = self._con.execute(
            "SELECT COALESCE(MAX(order_index) + 1, 0) FROM page_operation WHERE page_id = ?",
            (page_id,)).fetchone()
        result_ids = []
        with self._con:
            for k, (part, ops) in enumerate(zip(parts, applied, strict=True)):
                dpi_x, dpi_y, skew = page.dpi_x, page.dpi_y, page.skew_angle
                for op, _params, meta in ops:
                    if op is PreprocessOp.RESOLUTION:
                        dpi_x = dpi_y = int(meta["dpi"])
                    elif op is PreprocessOp.ROTATE and meta.get("swap_dpi"):
                        dpi_x, dpi_y = dpi_y, dpi_x
                    elif op is PreprocessOp.DESKEW:
                        skew = float(meta.get("angle", 0.0))
                rel, thumb = self._write_array(part, (dpi_x, dpi_y), written)
                values = (rel, part.shape[1], part.shape[0], dpi_x, dpi_y,
                          _color_of(part).value, thumb, skew)
                op_rows = [(op.value, json.dumps(params)) for op, params, _ in ops]
                if k == 0:
                    self._invalidate_text(page_id)
                    self._con.execute(
                        "UPDATE page SET image_path = ?, width_px = ?, height_px = ?, dpi_x = ?,"
                        " dpi_y = ?, color_mode = ?, thumbnail_blob = ?, skew_angle = ?,"
                        " status = 'preprocessed', blank_score = NULL, updated_at = ?"
                        " WHERE id = ?", (*values, db._utc_now(), page_id))
                    if len(parts) > 1:  # parte dintr-o impartire: devine noul original
                        self._con.execute("UPDATE page SET original_path = ? WHERE id = ?",
                                          (rel, page_id))
                    target_id = page_id
                else:
                    target_id = self._insert_after(page_id, rel, values)
                    # aceleasi operatii de dinainte ca pagina din care provine
                    self._con.execute(
                        "INSERT INTO page_operation (page_id, order_index, operation, parameters)"
                        " SELECT ?, order_index, operation, parameters FROM page_operation"
                        " WHERE page_id = ? AND order_index < ?",
                        (target_id, page_id, start))
                self._con.executemany(
                    "INSERT INTO page_operation (page_id, order_index, operation, parameters)"
                    " VALUES (?, ?, ?, ?)",
                    [(target_id, start + j, op, prm) for j, (op, prm) in enumerate(op_rows)],
                )
                result_ids.append(target_id)
        self._reload_pages()
        return result_ids

    def _insert_after(self, page_id: int, rel: str, values: tuple[Any, ...]) -> int:
        """O pagina noua, imediat dupa `page_id`, cu aceeasi provenienta (L-016)."""
        (number,) = self._con.execute(
            "SELECT page_number FROM page WHERE id = ?", (page_id,)).fetchone()
        self._make_room(number + 1)
        cur = self._con.execute(
            "INSERT INTO page (page_number, image_path, original_path, width_px, height_px,"
            " dpi_x, dpi_y, color_mode, thumbnail_blob, skew_angle, status, source_file,"
            " source_page, source_kind) SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'preprocessed',"
            " source_file, source_page, source_kind FROM page WHERE id = ?",
            (number + 1, rel, *values, page_id))
        return int(cur.lastrowid)

    def _write_array(self, array: Any, dpi: tuple[int, int], written: list[Path]
                     ) -> tuple[str, bytes]:
        img = from_array(array)
        if is_bilevel(array):
            img = img.convert("1")  # PNG alb-negru: mult mai mic
        dest = self._work / IMAGES_DIR / f"{uuid.uuid4().hex[:12]}.png"
        img.save(dest, format="PNG", dpi=dpi)
        written.append(dest)
        return dest.relative_to(self._work).as_posix(), _thumbnail(img)

    # SPEC_05 PreprocessPipeline.revert_to_original
    def revert_to_original(self, numbers: Sequence[int]) -> None:
        """Reincarca imaginea originala si goleste operatiile aplicate. Zonele si
        textul se invalideaza; pagina revine la `imported`."""
        chosen = self._validate_numbers(numbers)
        with self._history("revert_to_original", {"pages": chosen}), self._con:
            for n in chosen:
                pg = self._pages[n - 1]
                with Image.open(pg.original_path) as src:
                    upright = ImageOps.exif_transpose(src)
                    dpi = src.info.get("dpi")
                    array = to_array(upright)
                dx, dy = ((round(dpi[0]), round(dpi[1])) if dpi and min(dpi[:2]) > 1
                          else (pg.dpi_x, pg.dpi_y))
                self._invalidate_text(pg.id)
                self._con.execute("DELETE FROM page_operation WHERE page_id = ?", (pg.id,))
                self._con.execute(
                    "UPDATE page SET image_path = original_path, width_px = ?, height_px = ?,"
                    " dpi_x = ?, dpi_y = ?, color_mode = ?, rotation = 0, skew_angle = NULL,"
                    " blank_score = NULL, status = 'imported', thumbnail_blob = ?, updated_at = ?"
                    " WHERE id = ?",
                    (array.shape[1], array.shape[0], dx, dy, _color_of(array).value,
                     _thumbnail(from_array(array)), db._utc_now(), pg.id))
        self._after_change()

    def applied_operations(self, number: int) -> list[tuple[PreprocessOp, dict[str, Any]]]:
        """Operatiile aplicate paginii, in ordine (PageData.applied_operations)."""
        pg = self.page(number)
        return [(PreprocessOp(op), json.loads(params)) for op, params in self._con.execute(
            "SELECT operation, parameters FROM page_operation WHERE page_id = ?"
            " ORDER BY order_index", (pg.id,))]

    # ------------------------------------------------ analiza paginii (4.2)

    # N-006, N-007, M-022
    def analyze_pages(self, numbers: Sequence[int], *, analyzer: Any = None,
                      cancel: CancelToken | None = None) -> None:
        """`Analyze Page` / `Analyze All Pages`: zonele se gasesc automat.
        Zonele existente raman; cele noi completeaza spatiul liber; toate se
        renumeroteaza pe coloane. Pagina devine `analyzed`. Un singur pas de undo.
        Structura tabelelor gasite se calculeaza la recunoastere (4.5.2)."""
        from app.core.layout.analyzer import LayoutAnalyzer  # analyzer importa project
        from app.core.layout.areas import column_order

        chosen = self._validate_numbers(numbers)
        tool = analyzer or LayoutAnalyzer()
        settings = self._settings.ocr_settings()
        with self._history("analyze_pages", {"pages": chosen}), self._con:
            for n in chosen:
                if cancel is not None and cancel():
                    raise OperationCancelledError(done=chosen.index(n), total=len(chosen))
                page = self._pages[n - 1]
                new = tool.analyze(page, settings, cancel=cancel)
                ids = []
                (start,) = self._con.execute(
                    "SELECT COALESCE(MAX(order_index) + 1, 0) FROM area WHERE page_id = ?",
                    (page.id,)).fetchone()
                for i, area in enumerate(new):
                    b = area.bbox
                    cur = self._con.execute(
                        "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y,"
                        " bbox_w, bbox_h, polygon, barcode_type) VALUES (?,?,?,?,?,?,?,?,?)",
                        (page.id, start + i, area.area_type.value, b.x, b.y, b.w, b.h,
                         json.dumps([list(pt) for pt in area.polygon]),
                         "autodetect" if area.area_type is AreaType.BARCODE else None))
                    ids.append(cur.lastrowid)
                self._reload_pages()
                ordered = [a.id for a in column_order(self._pages[n - 1].areas)]
                self._con.execute(
                    "UPDATE area SET order_index = order_index + 1000000 WHERE page_id = ?",
                    (page.id,))
                self._con.executemany("UPDATE area SET order_index = ? WHERE id = ?",
                                      [(i, aid) for i, aid in enumerate(ordered)])
                self._con.execute(
                    "UPDATE page SET status = CASE WHEN status IN ('imported','preprocessed')"
                    " THEN 'analyzed' ELSE status END WHERE id = ?", (page.id,))
        self._after_change()

    # ------------------------------------------------------ istoric (1e)

    # J-041
    def can_undo(self) -> bool:
        return self._top_entry(undone=False) is not None

    def can_redo(self) -> bool:
        return self._top_entry(undone=True) is not None

    def undo_description(self) -> str | None:
        """Cheia de traducere a pasului care se anuleaza: 'undo.delete_pages'.

        SPEC_05 cere textul din meniu („Anuleaza stergerea paginii 3”), dar
        CLAUDE.md §6.5 interzice text afisabil in nucleu: GUI-ul il compune din
        cheie si din `undo_params()`."""
        entry = self._top_entry(undone=False)
        return None if entry is None else entry[2]

    def redo_description(self) -> str | None:
        entry = self._top_entry(undone=True)
        return None if entry is None else entry[2]

    def undo_params(self) -> dict[str, Any]:
        """Parametrii pentru textul tradus: {'pages': [3]}. Adaugare fata de SPEC_05."""
        entry = self._top_entry(undone=False)
        return {} if entry is None else json.loads(entry[3])["params"]

    def undo(self) -> None:
        """J-041: anuleaza ultimul pas. ValueError daca nu exista."""
        entry = self._top_entry(undone=False)
        if entry is None:
            raise ValueError("nimic de anulat")
        row_id, sequence, _, _, reverse = entry
        with self._con:
            self._apply_state(json.loads(reverse))
            self._con.execute("UPDATE undo_entry SET sequence = ? WHERE id = ?",
                              (-sequence, row_id))
        self._after_change()

    def redo(self) -> None:
        entry = self._top_entry(undone=True)
        if entry is None:
            raise ValueError("nimic de refacut")
        row_id, sequence, _, forward, _ = entry
        with self._con:
            self._apply_state(json.loads(forward))
            self._con.execute("UPDATE undo_entry SET sequence = ? WHERE id = ?",
                              (-sequence, row_id))
        self._after_change()

    def _top_entry(self, *, undone: bool) -> tuple[Any, ...] | None:
        """Pasii activi au sequence > 0; cei anulati, -sequence (pentru redo).
        Asa istoricul supravietuieste unei caderi, impreuna cu pozitia in el."""
        self._require_open()
        sql = ("SELECT id, sequence, description, forward_payload, reverse_payload"
               " FROM undo_entry WHERE sequence {} 0 ORDER BY sequence DESC LIMIT 1")
        return self._con.execute(sql.format("<" if undone else ">")).fetchone()

    def _clear_history(self) -> None:
        with self._con:
            self._con.execute("DELETE FROM undo_entry")

    @contextmanager
    def _history(
        self, op: str, params: dict[str, Any], *, barrier_if_empty: bool = False
    ) -> Iterator[None]:
        """Inregistreaza operatia din bloc ca pas de undo: starea paginilor
        inainte si dupa, doar ce s-a schimbat.

        `barrier_if_empty`: adaugarea primelor pagini intr-un proiect gol nu se
        anuleaza (ar goli proiectul, J-055); istoricul se goleste.
        INCOMPLET, marcat: starea cuprinde paginile; zonele si textul (fazele
        3-5) se adauga in istoric odata cu ele.
        """
        if getattr(self, "_history_open", False):
            # in interiorul altei operatii: face parte din pasul ei de undo
            yield
            return
        before = self._page_rows()
        self._history_open = True
        try:
            yield
        finally:
            self._history_open = False
            after = self._page_rows()
            if after != before:
                if barrier_if_empty and not before:
                    self._clear_history()
                else:
                    self._record(op, params, before, after)

    def _page_rows(self) -> dict[int, dict[str, Any]]:
        """Starea paginilor pentru istoric: randurile din `page`, plus, pentru
        fiecare pagina, operatiile de preprocesare (`_operations`, L-109),
        zonele (`_areas`, 3a) si celulele, separatoarele si avertismentele
        (`_children`, 3d) si textul recunoscut (text_block, text_line, word, 4.3)."""
        cur = self._con.execute("SELECT * FROM page ORDER BY page_number")
        names = [d[0] for d in cur.description]
        rows = {row[0]: dict(zip(names, row, strict=True)) for row in cur}
        for row in rows.values():
            row["_operations"] = []
            row["_areas"] = []
        cur_a = self._con.execute("SELECT * FROM area ORDER BY page_id, order_index")
        area_names = [d[0] for d in cur_a.description]
        area_page: dict[int, int] = {}
        for arow in cur_a:
            area = dict(zip(area_names, arow, strict=True))
            area_page[area["id"]] = area["page_id"]
            if area["page_id"] in rows:
                rows[area["page_id"]]["_areas"].append(area)
        for row in rows.values():
            row["_children"] = []
        owner: dict[str, dict[int, int]] = {"area": area_page, "block": {}, "line": {}}
        # ordinea conteaza la restaurare: parintii inaintea copiilor
        for table, link, key, owns in (
            ("table_cell", "area", "area_id", None),
            ("table_separator", "area", "area_id", None),
            ("text_block", "area", "area_id", "block"),
            ("text_line", "block", "block_id", "line"),
            ("word", "line", "line_id", None),
            ("page_warning", "page", "page_id", None),
            ("annotation", "page", "page_id", None),  # 5.4: legaturile din text
        ):
            cur_c = self._con.execute(f"SELECT * FROM {table} ORDER BY id")
            names = [d[0] for d in cur_c.description]
            for crow in cur_c:
                child = dict(zip(names, crow, strict=True))
                pid = child[key] if link == "page" else owner[link].get(child[key])
                if owns is not None:
                    owner[owns][child["id"]] = pid
                if pid in rows:
                    rows[pid]["_children"].append([table, child])
        for page_id, idx, op, params, at in self._con.execute(
            "SELECT page_id, order_index, operation, parameters, applied_at"
            " FROM page_operation ORDER BY page_id, order_index"
        ):
            if page_id in rows:
                rows[page_id]["_operations"].append([idx, op, params, at])
        return rows

    def _record(self, op: str, params: dict[str, Any],
                before: dict[int, dict[str, Any]], after: dict[int, dict[str, Any]]) -> None:
        def state(snapshot: dict[int, dict[str, Any]],
                  other: dict[int, dict[str, Any]]) -> dict[str, Any]:
            changed = {
                str(pid): _encode_row(row) for pid, row in snapshot.items()
                if pid not in other or _strip_number(other[pid]) != _strip_number(row)
            }
            return {"order": list(snapshot), "rows": changed, "params": params}

        forward, reverse = state(after, before), state(before, after)
        with self._con:
            self._con.execute("DELETE FROM undo_entry WHERE sequence < 0")  # ramura redo
            (top,) = self._con.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM undo_entry").fetchone()
            self._con.execute(
                "INSERT INTO undo_entry (sequence, operation, description, forward_payload,"
                " reverse_payload) VALUES (?, ?, ?, ?, ?)",
                (top + 1, op, f"undo.{op}", json.dumps(forward), json.dumps(reverse)),
            )

    def _apply_state(self, state: dict[str, Any]) -> None:
        """Aduce tabela page la `state`: aceleasi pagini, aceeasi ordine.
        In tranzactia apelantului."""
        order: list[int] = state["order"]
        rows = {int(k): _decode_row(v) for k, v in state["rows"].items()}
        current = {r[0] for r in self._con.execute("SELECT id FROM page")}
        gone = current - set(order)
        self._con.executemany("DELETE FROM page WHERE id = ?", [(i,) for i in gone])
        # SQLite verifica UNIQUE(page_number) rand cu rand: randurile restaurate
        # primesc numere temporare departe de cele pe care `_renumber` le muta
        # (1..n -> OFFSET+1..OFFSET+n), ca nicio stare intermediara sa nu se ciocneasca.
        temp = 5 * _RENUMBER_OFFSET
        for pid, row in rows.items():
            operations = row.get("_operations", [])
            areas = row.get("_areas", [])
            children = row.get("_children", [])
            row = {k: v for k, v in row.items()
                   if k not in ("_operations", "_areas", "_children")}
            row = {**row, "page_number": temp}
            temp += 1
            cols = [c for c in row if c != "id"]
            if pid not in current:
                self._con.execute(
                    f"INSERT INTO page (id, {', '.join(cols)})"
                    f" VALUES (?, {', '.join('?' * len(cols))})",
                    (pid, *(row[c] for c in cols)),
                )
            # zonele intai: triggerele lor ating starea paginii, care se reface dupa
            self._con.execute("DELETE FROM area WHERE page_id = ?", (pid,))
            self._con.execute("DELETE FROM page_warning WHERE page_id = ?", (pid,))
            for area in areas:
                acols = list(area)
                self._con.execute(
                    f"INSERT INTO area ({', '.join(acols)}) VALUES ({', '.join('?' * len(acols))})",
                    tuple(area[c] for c in acols),
                )
            for table, child in children:
                ccols = list(child)
                self._con.execute(
                    f"INSERT INTO {table} ({', '.join(ccols)})"
                    f" VALUES ({', '.join('?' * len(ccols))})",
                    tuple(child[c] for c in ccols),
                )
            self._con.execute(
                f"UPDATE page SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?",
                (*(row[c] for c in cols), pid),
            )
            self._con.execute("DELETE FROM page_operation WHERE page_id = ?", (pid,))
            self._con.executemany(
                "INSERT INTO page_operation (page_id, order_index, operation, parameters,"
                " applied_at) VALUES (?, ?, ?, ?, ?)",
                [(pid, *op) for op in operations],
            )
        self._renumber(order)

    # --- ajutoare pentru operatii pe pagini

    def _validate_numbers(self, numbers: Sequence[int]) -> list[int]:
        self._require_open()
        chosen = sorted(set(numbers))
        if not chosen:
            raise ValueError("nicio pagina selectata")
        bad = [n for n in chosen if not isinstance(n, int) or not 1 <= n <= len(self._pages)]
        if bad:
            raise ValueError(f"pagini inexistente (1..{len(self._pages)}): {bad}")
        return chosen

    def _consecutive(self, numbers: Sequence[int] | None, *, minimum: int) -> list[int]:
        chosen = (list(range(1, len(self._pages) + 1)) if numbers is None
                  else self._validate_numbers(numbers))
        if len(chosen) < minimum:
            raise ValueError(f"sunt necesare cel putin {minimum} pagini consecutive")
        if chosen != list(range(chosen[0], chosen[-1] + 1)):
            raise ValueError("paginile selectate trebuie sa fie consecutive")
        return chosen

    def _replace_range(self, old: list[int], new: list[int], op: str) -> None:
        """Pune paginile `old` (consecutive) in ordinea `new`, restul pe loc."""
        order = list(range(1, len(self._pages) + 1))
        start = old[0] - 1
        order[start:start + len(old)] = new
        self._reorder(order, op, params={"pages": old})

    def _renumber(self, ids_in_order: list[int]) -> None:
        """Numerele 1..n in ordinea data (J-066). In tranzactia apelantului."""
        self._con.execute("UPDATE page SET page_number = page_number + ?", (_RENUMBER_OFFSET,))
        self._con.executemany(
            "UPDATE page SET page_number = ? WHERE id = ?",
            [(i, pid) for i, pid in enumerate(ids_in_order, start=1)],
        )

    def _after_change(self) -> None:
        self._reload_pages()
        self._touch()

    def _referenced_images(self) -> set[str]:
        names: set[str] = set()
        for image_rel, original_rel in self._con.execute(
            "SELECT image_path, original_path FROM page"
        ):
            names.update((Path(image_rel).name, Path(original_rel).name))
        return names

    # ------------------------------------------------------------- ajutoare

    def _touch(self) -> None:
        """O modificare: proiectul are ceva nesalvat (J-040)."""
        self._dirty = True
        self._revision += 1

    def _require_open(self) -> None:
        if self._closed:
            raise ValueError("proiectul e inchis")

    def _row(self, sql: str) -> tuple[Any, ...]:
        self._require_open()
        return self._con.execute(sql).fetchone()

    def _update(self, sql: str, params: tuple[Any, ...]) -> None:
        self._require_open()
        with self._con:
            self._con.execute(sql, params)
        self._touch()

    def _checkpoint(self) -> None:
        """Muta jurnalul WAL in project.db, ca folderul sa fie complet fara -wal."""
        self._con.commit()
        self._con.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def _clear_saved_history(db_path: Path) -> None:
    """Proiectul salvat nu duce istoricul cu el: imaginile pasilor vechi nu se
    copiaza, iar SPEC_04 cere golirea undo_entry la inchiderea curata."""
    con = sqlite3.connect(db_path)
    try:
        with con:
            con.execute("DELETE FROM undo_entry")
    finally:
        con.close()


def _strip_number(row: dict[str, Any]) -> dict[str, Any]:
    """Ordinea se pastreaza separat; numarul paginii nu e o schimbare a randului."""
    return {k: v for k, v in row.items() if k != "page_number"}


def _encode_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: ({"b64": base64.b64encode(v).decode("ascii")} if isinstance(v, bytes) else v)
            for k, v in row.items()}


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: (base64.b64decode(v["b64"]) if isinstance(v, dict) and "b64" in v else v)
            for k, v in row.items()}


def _check_save_target(target: Path) -> None:
    if not target.exists():
        return
    if target.is_dir() and ((target / DB_NAME).is_file() or not any(target.iterdir())):
        return
    raise FileExistsError(f"{target} exista si nu e un proiect OCR; nu se suprascrie")


def _needs_exif_rotation(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            return img.getexif().get(0x0112, 1) not in (1, None)
    except OSError:
        return False


# J-057: cerneala = orice pixel care difera de fundal pe macar un canal
def _blank_score(image_path: Path) -> float:
    """0 = pagina plina, 1 = complet goala (SPEC_04 page.blank_score)."""
    with Image.open(image_path) as src:
        img = ImageOps.exif_transpose(src).convert("RGB")
    img.thumbnail((_BLANK_SAMPLE, _BLANK_SAMPLE), Image.Resampling.BOX)
    background = tuple(int(v) for v in ImageStat.Stat(img).median)
    diff = ImageChops.difference(img, Image.new("RGB", img.size, background))
    r, g, b = diff.split()
    strongest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    histogram = strongest.histogram()
    ink = sum(histogram[_INK_DELTA:])
    ratio = ink / (img.size[0] * img.size[1])
    return round(max(0.0, 1.0 - ratio / _INK_FULL), 4)


def _color_of(array: Any) -> ColorMode:
    if array.ndim == 2:
        return ColorMode.BW if is_bilevel(array) else ColorMode.GRAY
    spread = array.max(axis=2).astype(int) - array.min(axis=2)
    return ColorMode.GRAY if int(spread.max()) <= 6 else ColorMode.COLOR


def _thumbnail(pixels: Image.Image) -> bytes:
    thumb = pixels.copy()
    thumb.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
    if thumb.mode not in ("1", "L", "RGB", "RGBA"):
        thumb = thumb.convert("RGB")
    out = io.BytesIO()
    thumb.save(out, format="PNG")
    return out.getvalue()
