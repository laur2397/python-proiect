"""Contextul aplicatiei: ce e deschis o singura data, la pornire.

SPEC_05 da `OcrProject.create(name)`, `open(path)` si `find_recovery()` fara
argumente despre folderele aplicatiei, setari sau recuperare. Le iau dintr-un
context pornit la lansare (GUI sau CLI). Adaugare fata de contract, marcata in
raportul pasului 1c. Fiecare metoda primeste si `context=`, pentru teste.

Pornire:   ctx = AppContext.start();   configure(ctx)
Inchidere: ctx.close()   (iesire curata: Y-023, Y-026)
"""

from __future__ import annotations

import sqlite3
import weakref
from dataclasses import dataclass, field
from typing import Protocol

from app.core import db
from app.core.health import ApplicationHealth
from app.core.paths import AppPaths
from app.core.recovery import RecoveryRegistry
from app.core.settings import AppSettingsStore

APP_VERSION = "0.1.0"


class _Closable(Protocol):
    def close(self) -> None: ...


# Y-022..Y-026: tot ce porneste o data per sesiune
@dataclass(slots=True)
class AppContext:
    paths: AppPaths
    app_db: sqlite3.Connection
    settings: AppSettingsStore
    health: ApplicationHealth
    recovery: RecoveryRegistry
    app_version: str = APP_VERSION
    closed: bool = False
    open_documents: weakref.WeakSet[_Closable] = field(default_factory=weakref.WeakSet)
    """Proiectele (si, din faza 7, documentele PDF) deschise in sesiune. La
    iesire se inchid inainte de curatare: pe Windows un fisier deschis nu se
    poate sterge."""

    @classmethod
    def start(cls, paths: AppPaths | None = None, *, app_version: str = APP_VERSION) -> AppContext:
        """Deschide app.db, setarile si evidenta recuperarii, si curata
        temporarele ramase de la o cadere (Y-023). Acelasi id de sesiune pentru
        temporare si pentru recuperare."""
        paths = paths or AppPaths.default()
        paths.ensure()
        con = db.open_app_db(paths.app_db)
        settings = AppSettingsStore(con)
        health = ApplicationHealth(paths, settings)
        recovery = RecoveryRegistry(con, paths.recovery_dir, session_id=health.session_id)
        health.cleanup_temp()
        return cls(paths, con, settings, health, recovery, app_version)

    def close(self) -> None:
        """Iesirea curata: documentele ramase deschise se inchid fara salvare
        (GUI-ul a intrebat inainte), nimic de recuperat, temporarele sesiunii
        sterse. Se poate apela de mai multe ori."""
        if self.closed:
            return
        self.closed = True
        for doc in list(self.open_documents):
            doc.close()
        self.recovery.mark_clean_exit()
        self.health.cleanup_temp(include_current=True)
        self.app_db.close()
        global _current
        if _current is self:
            _current = None


_current: AppContext | None = None


def configure(ctx: AppContext) -> None:
    """Contextul folosit cand o metoda nu primeste `context=`."""
    global _current
    _current = ctx


def current() -> AppContext:
    if _current is None:
        raise RuntimeError("contextul aplicatiei nu e pornit: AppContext.start() + configure()")
    return _current
