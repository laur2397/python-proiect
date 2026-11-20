"""Folderele aplicatiei: date, jurnal, temporare, recuperare.

Y-022 (setarile stau in profilul utilizatorului), Y-023, Y-024, Y-026.
Caile vin din platformdirs, ca sa fie corecte pe Windows, macOS si Linux.
`AppPaths.portable(root)` tine totul intr-un singur folder (Y-010, si teste).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import platformdirs

APP_NAME = "DocuLens"


# Y-022, Y-023, Y-024, Y-026
@dataclass(frozen=True, slots=True)
class AppPaths:
    data_dir: Path
    """app.db, dictionarele utilizatorului, recuperarea. Y-022."""
    log_dir: Path
    """Jurnalul rotativ si rapoartele de eroare. Y-024, Y-025."""
    temp_root: Path
    """Folderul de temporare implicit, cand X-150 nu e setat. Y-023."""

    @classmethod
    def default(cls) -> AppPaths:
        """Folderele standard ale utilizatorului curent.

        Windows: %APPDATA%/DocuLens si %LOCALAPPDATA%/DocuLens/Logs;
        macOS: ~/Library/Application Support/DocuLens si ~/Library/Logs/DocuLens;
        Linux: ~/.local/share/DocuLens si ~/.local/state/DocuLens/log.
        """
        return cls(
            data_dir=Path(platformdirs.user_data_dir(APP_NAME, appauthor=False, roaming=True)),
            log_dir=Path(platformdirs.user_log_dir(APP_NAME, appauthor=False)),
            temp_root=Path(tempfile.gettempdir()) / APP_NAME,
        )

    # Y-010: varianta portabila scrie doar intr-un folder ales.
    @classmethod
    def portable(cls, root: Path) -> AppPaths:
        root = Path(root)
        return cls(data_dir=root / "data", log_dir=root / "logs", temp_root=root / "temp")

    @property
    def app_db(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def recovery_dir(self) -> Path:
        """Fisierele de siguranta (Y-026). In folderul de date, nu in temporare,
        ca sa nu le stearga curatarea de la pornire (Y-023)."""
        return self.data_dir / "recovery"

    @property
    def dictionaries_dir(self) -> Path:
        """Implicitul pentru `areas.user_dictionaries_folder` (X-163)."""
        return self.data_dir / "dictionaries"

    def ensure(self) -> None:
        """Creeaza folderele care lipsesc."""
        for d in (self.data_dir, self.log_dir, self.temp_root, self.recovery_dir):
            d.mkdir(parents=True, exist_ok=True)
