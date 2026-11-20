"""Starea aplicatiei la pornire si fisierele temporare.

Implementeaza `ApplicationHealth` din SPEC_05 (docstring-urile de acolo
folosesc numerotarea veche: Y-016 = acum Y-023, Y-006 = acum Y-024).

Fiecare pornire a aplicatiei primeste propriul folder temporar,
`<temp>/session-<pid>-<hex>`. Curatarea sterge doar foldere `session-*`
ale proceselor care nu mai ruleaza, deci:
- nu atinge temporarele altei instante pornite in paralel;
- nu sterge nimic altceva, chiar daca folderul de temporare (X-150) e
  setat pe un folder al utilizatorului.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from app.core.errors import CoreError, DiskFullError, NoWritePermissionError
from app.core.paths import APP_NAME, AppPaths
from app.core.process import new_session_id, pid_alive, session_pid
from app.core.settings import SettingsStore

SESSION_PREFIX = "session-"

MIN_FREE_BYTES = 200 * 1024 * 1024
"""[DECIZIE] Sub 200 MB liberi in folderul temporar, `check_startup` raporteaza
DiskFullError. Specificatia nu da un prag; originalul cere 1,6 GB (Y-003)."""


# Y-023, Y-024, X-150. SPEC_05: ApplicationHealth
class ApplicationHealth:
    def __init__(
        self,
        paths: AppPaths,
        settings: SettingsStore | None = None,
        session_id: str | None = None,
    ) -> None:
        self._paths = paths
        self._settings = settings
        self.session_id = session_id or new_session_id()

    # X-150: folderul ales de utilizator, altfel cel al sistemului
    def temp_root(self) -> Path:
        custom = self._settings.get("app.temp_folder") if self._settings else None
        if custom:
            return Path(custom) / APP_NAME
        return self._paths.temp_root

    def temp_folder(self) -> Path:
        """Folderul temporar al sesiunii curente. Se creeaza la prima cerere."""
        folder = self.temp_root() / f"{SESSION_PREFIX}{self.session_id}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def free_space_bytes(self) -> int:
        """Spatiul liber pe discul folderului temporar."""
        probe = self.temp_root()
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        return shutil.disk_usage(probe).free

    # Y-023: la pornire (resturile unei caderi) si la inchidere (include_current)
    def cleanup_temp(self, *, include_current: bool = False) -> int:
        """Sterge folderele temporare ramase de la sesiuni terminate.

        La pornire se apeleaza fara argumente: sterge resturile de la o cadere.
        La inchiderea normala, cu `include_current=True`, sterge si folderul
        sesiunii curente. Fisierele blocate (deschise in alt program) se sar si
        raman pentru data viitoare. Intoarce octetii eliberati.
        """
        root = self.temp_root()
        if not root.is_dir():
            return 0
        freed = 0
        for entry in root.iterdir():
            if not entry.is_dir() or not entry.name.startswith(SESSION_PREFIX):
                continue
            sid = entry.name[len(SESSION_PREFIX):]
            if sid == self.session_id:
                if not include_current:
                    continue
            else:
                pid = session_pid(sid)
                if pid is not None and pid_alive(pid):
                    continue  # alta instanta care ruleaza
            freed += _remove_tree(entry)
        return freed

    def log_folder(self) -> Path:
        """Y-024: folderul jurnalului; GUI-ul il deschide din Options."""
        return self._paths.log_dir

    # Y-005 (numerotarea SPEC_05)
    def check_startup(self) -> list[CoreError]:
        """Problemele gasite la pornire. Nu arunca: aplicatia trebuie sa
        porneasca si sa spuna ce lipseste.

        Verifica deocamdata folderul temporar (scriere si spatiu liber).
        INCOMPLET, marcat: verificarea fonturilor vine cu FontMatcher (faza 6),
        cea a modelelor de limba cu LanguageRegistry (faza 4).
        """
        problems: list[CoreError] = []
        root = self.temp_root()
        try:
            root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=root, prefix=".write-test-"):
                pass
        except OSError as exc:
            problems.append(NoWritePermissionError(str(exc), path=str(root)))
            return problems
        free = self.free_space_bytes()
        if free < MIN_FREE_BYTES:
            problems.append(
                DiskFullError(
                    "putin spatiu liber", path=str(root), free_bytes=free,
                    required_bytes=MIN_FREE_BYTES,
                )
            )
        return problems


def _remove_tree(folder: Path) -> int:
    """Sterge fisier cu fisier; ce nu se poate sterge ramane. Intoarce octetii."""
    freed = 0
    for dirpath, dirnames, filenames in os.walk(folder, topdown=False):
        for name in filenames:
            path = Path(dirpath) / name
            try:
                size = path.lstat().st_size
                path.unlink()
                freed += size
            except OSError:
                continue
        for name in dirnames:
            try:
                (Path(dirpath) / name).rmdir()
            except OSError:
                continue
    try:
        folder.rmdir()
    except OSError:
        pass
    return freed
