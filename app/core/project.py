"""Proiectul OCR: folderul cu paginile, zonele si textul.

Implementeaza din `OcrProject` (SPEC_05 sectiunea 9) partea de baza, pasul 1c:
create, open, save, close, pages, page, add_images, set_metadata, settings,
autosave, find_recovery. Operatiile pe pagini vin in 1d, undo/redo in 1e.

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

import errno
import io
import itertools
import json
import shutil
import sqlite3
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from app.core import db
from app.core.applog import get_logger
from app.core.context import AppContext, current
from app.core.errors import (
    CoreError,
    DiskFullError,
    FileCorruptError,
    InvalidProjectError,
    NoWritePermissionError,
    OperationCancelledError,
)
from app.core.images.loader import PDF_EXTENSIONS, ImageLoader, LoadedImage
from app.core.model import (
    AutoProcessMode,
    CancelToken,
    ColorMode,
    LanguageCode,
    LayoutMode,
    PageData,
    PageStatus,
    PasswordCallback,
    Progress,
    ProgressCallback,
)
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

_untitled = itertools.count(1)
_log = get_logger("core.project")

_PAGE_COLUMNS = (
    "id, page_number, image_path, original_path, width_px, height_px, dpi_x, dpi_y,"
    " color_mode, rotation, status, source_file, source_page, skew_angle,"
    " estimated_dpi, blank_score, avg_confidence, uncertain_count"
)


def _ignore_wal(_dir: str, names: list[str]) -> list[str]:
    return [n for n in names if n.endswith(("-wal", "-shm"))]


def _copy_project_tree(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, ignore=_ignore_wal)


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

        tag = uuid.uuid4().hex[:8]
        staging = target.parent / f".{target.name}.saving-{tag}"
        backup = target.parent / f".{target.name}.old-{tag}"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_project_tree(self._work, staging)
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
        self._con.close()
        shutil.rmtree(self._work, ignore_errors=True)
        self._forget_autosave()
        self._closed = True

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
        """Adauga paginile fisierelor, copiate in proiect.

        `at`: numarul paginii inaintea careia se insereaza (1..n+1); None = la
        sfarsit. Paginile urmatoare se renumeroteaza (J-066).

        Un fisier nesuportat, stricat sau cu parola refuzata NU opreste lotul:
        se sare si se raporteaza in a doua lista (J-050). Un fisier se adauga
        intreg sau deloc. Anularea se verifica intre fisiere si intre pagini;
        paginile deja adaugate raman, apoi se ridica `OperationCancelledError`.

        `auto_process` (J-051): INCOMPLET, marcat. Preprocesarea, analiza si
        recunoasterea vin in fazele 2-4; acum paginile raman `imported`.
        """
        self._require_open()
        insert_at = len(self._pages) + 1 if at is None else at
        if not 1 <= insert_at <= len(self._pages) + 1:
            raise ValueError(f"pozitie de inserare invalida: {at} (1..{len(self._pages) + 1})")
        _ = auto_process  # J-051: folosit din faza 2
        paths = [Path(p) for p in paths]
        added: list[PageData] = []
        skipped: list[tuple[Path, CoreError]] = []
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
        if progress is not None:
            progress(Progress(len(paths), len(paths), "stage.adding_pages"))
        return added, skipped

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
                         "pdf" if path.suffix.lower() in PDF_EXTENSIONS else "file"),
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


def _thumbnail(pixels: Image.Image) -> bytes:
    thumb = pixels.copy()
    thumb.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
    if thumb.mode not in ("1", "L", "RGB", "RGBA"):
        thumb = thumb.convert("RGB")
    out = io.BytesIO()
    thumb.save(out, format="PNG")
    return out.getvalue()
