"""Fisierele de siguranta si detectarea lor la pornire (Y-026).

Partea de nucleu: evidenta fisierelor de siguranta in tabela `recovery_entry`
din app.db (SPEC_04) si gasirea celor ramase de la o sesiune cazuta. Cand si
ce se salveaza (autosave la 5 minute, J-005 in SPEC_05) vine cu OcrProject si
PdfDocument; dialogul care ofera recuperarea vine in faza GUI.

O sesiune e „cazuta” daca nu a inchis curat si procesul ei nu mai ruleaza.
Fisierele unei alte instante pornite in paralel nu se ofera spre recuperare.
"""

from __future__ import annotations

import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.process import new_session_id, pid_alive, session_pid

DOC_KINDS = ("pdf", "ocr_project")
"""Valorile din CHECK-ul recovery_entry.doc_kind (SPEC_04)."""


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# Y-026
@dataclass(frozen=True, slots=True)
class RecoveryEntry:
    id: int
    recovery_path: Path
    original_path: Path | None
    """None pentru un document care nu fusese salvat niciodata."""
    doc_kind: str
    session_id: str
    saved_at: str


# Y-026; SPEC_04 recovery_entry
class RecoveryRegistry:
    def __init__(
        self, con: sqlite3.Connection, recovery_dir: Path, session_id: str | None = None
    ) -> None:
        self._con = con
        self._dir = Path(recovery_dir)
        self.session_id = session_id or new_session_id()

    def new_recovery_path(self, doc_kind: str, extension: str) -> Path:
        """O cale noua, unica, in folderul de recuperare, pentru sesiunea curenta.
        Poate deveni fisier (PDF) sau folder (proiect OCR)."""
        _check_kind(doc_kind)
        self._dir.mkdir(parents=True, exist_ok=True)
        ext = extension.lstrip(".")
        return self._dir / f"{self.session_id}-{doc_kind}-{uuid.uuid4().hex[:8]}.{ext}"

    def register(
        self, recovery_path: Path, original_path: Path | None, doc_kind: str
    ) -> None:
        """Noteaza (sau reimprospateaza) un fisier de siguranta al sesiunii curente.
        Se apeleaza dupa fiecare salvare automata reusita."""
        _check_kind(doc_kind)
        with self._con:
            self._con.execute(
                "INSERT INTO recovery_entry (original_path, recovery_path, doc_kind,"
                " session_id, saved_at, is_clean_exit) VALUES (?, ?, ?, ?, ?, 0)"
                " ON CONFLICT(recovery_path) DO UPDATE SET"
                " original_path = excluded.original_path, saved_at = excluded.saved_at,"
                " session_id = excluded.session_id, is_clean_exit = 0",
                (
                    None if original_path is None else str(original_path),
                    str(recovery_path),
                    doc_kind,
                    self.session_id,
                    _utc_now(),
                ),
            )

    def forget(self, recovery_path: Path) -> None:
        """Documentul a fost salvat sau inchis normal: fisierul de siguranta nu
        mai trebuie. Sterge si fisierul, si randul."""
        _remove(Path(recovery_path))
        with self._con:
            self._con.execute(
                "DELETE FROM recovery_entry WHERE recovery_path = ?", (str(recovery_path),)
            )

    def mark_clean_exit(self) -> None:
        """Inchiderea normala a aplicatiei: sesiunea curenta nu lasa nimic de recuperat."""
        rows = self._con.execute(
            "SELECT recovery_path FROM recovery_entry WHERE session_id = ?", (self.session_id,)
        ).fetchall()
        for (path,) in rows:
            _remove(Path(path))
        with self._con:
            self._con.execute(
                "DELETE FROM recovery_entry WHERE session_id = ?", (self.session_id,)
            )

    def find_pending(self) -> list[RecoveryEntry]:
        """Fisierele de siguranta ramase de la sesiuni cazute, cele mai noi primele.

        Randurile al caror fisier nu mai exista se sterg din evidenta.
        """
        rows = self._con.execute(
            "SELECT id, recovery_path, original_path, doc_kind, session_id, saved_at"
            " FROM recovery_entry WHERE is_clean_exit = 0 AND session_id <> ?"
            " ORDER BY saved_at DESC, id DESC",
            (self.session_id,),
        ).fetchall()
        pending: list[RecoveryEntry] = []
        missing: list[int] = []
        for row_id, rpath, opath, kind, sid, saved in rows:
            pid = session_pid(sid)
            if pid is not None and pid_alive(pid):
                continue  # alta instanta, inca deschisa
            if not Path(rpath).exists():
                missing.append(row_id)
                continue
            pending.append(
                RecoveryEntry(row_id, Path(rpath), None if opath is None else Path(opath),
                              kind, sid, saved)
            )
        if missing:
            with self._con:
                self._con.executemany(
                    "DELETE FROM recovery_entry WHERE id = ?", [(i,) for i in missing]
                )
        return pending

    def discard(self, entry: RecoveryEntry) -> None:
        """Utilizatorul a refuzat recuperarea, sau documentul a fost recuperat."""
        self.forget(entry.recovery_path)


def _remove(path: Path) -> None:
    """Sterge un fisier de siguranta: fisier (PDF) sau folder (proiect OCR)."""
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _check_kind(doc_kind: str) -> None:
    if doc_kind not in DOC_KINDS:
        raise ValueError(f"tip de document necunoscut: {doc_kind!r}; permise: {DOC_KINDS}")
