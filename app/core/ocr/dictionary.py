"""Dictionarele utilizatorului (faza 4b, pasul 4b.2): P-040..P-045, J-080..J-085.

`DictionaryService` din SPEC_05. Cuvintele stau in app.db
(`user_dictionary_word`, o limba pe rand), sau, cu un folder partajat
(`areas.user_dictionaries_folder`, X-163, P-045), cate un fisier text pe limba:
`<cod>.txt`, UTF-8, un cuvant pe rand.

Folderul partajat (J-080..J-085):
- un utilizator care editeaza tine fisierul `<cod>.lock`; ceilalti folosesc
  dictionarul, dar nu adauga si nu sterg cuvinte (J-084);
- modificarile altora se vad dupa repornire: fisierele se citesc la crearea
  serviciului (J-085);
- un folder inaccesibil nu e o eroare: se revine la dictionarul local si se
  adauga un avertisment (P-045, SPEC_05).

[DECIZIE AUTONOMA] `add` intoarce False pentru un duplicat (P-041 cere un
avertisment, nu o eroare); interfata il afiseaza.

INCOMPLET, marcat: dictionarul livrat al limbii (din modelul Tesseract) si
sugestiile din el vin cu verificarea ortografica, faza 5 (O-010).
"""

from __future__ import annotations

import difflib
import os
import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.model import LanguageCode

if TYPE_CHECKING:  # pragma: no cover
    from app.core.settings import SettingsStore

WARNING_SHARED_UNAVAILABLE = "warning.shared_dictionary_unavailable"
IMPORT_SUFFIXES = (".txt", ".dic", ".pmd")
"""P-043: fisierele care se pot importa."""


def _file_name(language: LanguageCode) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", language)


def _language_of(file: Path) -> LanguageCode:
    """Codul limbii dintr-un fisier al folderului partajat (`ron.txt` → `ron`).
    INCOMPLET, marcat: codurile cu caractere inlocuite (`user:x` → `user_x`) nu
    se refac; dictionarul lor partajat se vede dupa prima editare proprie."""
    return file.stem


_COMMA = str.maketrans({"ş": "ș", "ţ": "ț", "Ş": "Ș", "Ţ": "Ț"})


def romanian_form(word: str) -> str:
    """§6.4: ş/ţ (sedila) devin ș/ț (virgula), forma pe care o da recunoasterea:
    un cuvant importat dintr-un dictionar vechi se potriveste cu textul recunoscut."""
    return word.translate(_COMMA)


def _plain(word: str) -> str:
    """Cuvantul fara diacritice, cu litere mici, pentru comparare."""
    import unicodedata

    return "".join(ch for ch in unicodedata.normalize("NFKD", word.lower())
                   if not unicodedata.combining(ch))


def check_word(word: str) -> str:
    """Cuvantul curatat; ValueError daca e gol sau are spatii (P-041, SPEC_04)."""
    word = (word or "").strip()
    if not word or any(ch.isspace() for ch in word):
        raise ValueError("un cuvant de dictionar nu poate fi gol si nu poate avea spatii")
    return word


# SPEC_05 sect. 7. P-040..P-045, O-010, O-006
class DictionaryService:
    def __init__(self, con: sqlite3.Connection, settings: SettingsStore | None = None) -> None:
        self._con = con
        self._settings = settings
        self.warnings: list[str] = []
        """Chei de traducere ale avertismentelor (folder partajat inaccesibil)."""
        self._shared: Path | None = None
        self._cache: dict[LanguageCode, set[str]] = {}
        self._locks: set[LanguageCode] = set()
        folder = settings.get("areas.user_dictionaries_folder") if settings else None
        self.set_shared_folder(Path(folder) if folder else None)

    # --- cautare -------------------------------------------------------------------

    def contains(self, word: str, language: LanguageCode) -> bool:
        form = romanian_form(word)
        return form in self.words(language) or \
            any(romanian_form(w) == form for w in self.words(language))

    def suggest(self, word: str, language: LanguageCode, limit: int = 8) -> list[str]:
        """O-010: cuvintele din dictionarul utilizatorului cele mai apropiate.
        Diacriticele nu despart cuvintele („Fagaras” → „Făgăraș”)."""
        by_plain: dict[str, list[str]] = {}
        for w in sorted(self.words(language)):
            by_plain.setdefault(_plain(w), []).append(w)
        close = difflib.get_close_matches(_plain(word), list(by_plain), n=limit, cutoff=0.6)
        return [w for key in close for w in by_plain[key]][:limit]

    def words(self, language: LanguageCode) -> set[str]:
        if self._shared is not None:
            # J-085: ce era in folder la pornire (sau la ultima editare proprie)
            return self._cache.setdefault(language, set())
        return {r[0] for r in self._con.execute(
            "SELECT w.word FROM user_dictionary_word w JOIN ocr_language l"
            " ON l.id = w.language_id WHERE l.code = ?", (language,))}

    # --- P-041, P-042 ----------------------------------------------------------------

    def add(self, word: str, language: LanguageCode) -> bool:
        """P-041: True daca s-a adaugat, False pentru un duplicat (avertisment)."""
        word = romanian_form(check_word(word))
        if self.contains(word, language):
            return False
        if self._shared is not None:
            self._edit(language)
            self._cache[language].add(word)
            self._write(language)
        else:
            from app.core.ocr.languages import LanguageRegistry

            with self._con:
                lid = LanguageRegistry(con=self._con)._language_id(language)
                self._con.execute(
                    "INSERT INTO user_dictionary_word (language_id, word) VALUES (?, ?)",
                    (lid, word))
        return True

    def remove(self, word: str, language: LanguageCode) -> None:
        if self._shared is not None:
            self._edit(language)
            self._cache[language].discard(word)
            self._write(language)
            return
        with self._con:
            self._con.execute(
                "DELETE FROM user_dictionary_word WHERE word = ? AND language_id ="
                " (SELECT id FROM ocr_language WHERE code = ?)", (word, language))

    # --- P-023, P-043, P-044 -----------------------------------------------------------

    def import_words(self, path: Path, language: LanguageCode) -> int:
        """P-043: un cuvant pe rand; `.dic` in stilul Hunspell (prima linie e
        numarul de cuvinte, `/` incepe marcajele). Codificarea se detecteaza
        (UTF-8 cu sau fara BOM, UTF-16 cu BOM, altfel Windows-1252, P-023).
        Fisier binar → ValueError. Intoarce cate cuvinte s-au adaugat."""
        path = Path(path)
        if path.suffix.lower() not in IMPORT_SUFFIXES:
            raise ValueError(f"se pot importa numai fisiere {', '.join(IMPORT_SUFFIXES)}")
        lines = _read_lines(path.read_bytes())
        if path.suffix.lower() == ".dic" and lines and lines[0].isdigit():
            lines = lines[1:]
        added = 0
        for line in lines:
            word = line.split("/", 1)[0].strip() if path.suffix.lower() == ".dic" else line
            if not word or any(ch.isspace() for ch in word):
                continue
            added += self.add(word, language)
        return added

    def export_words(self, path: Path, language: LanguageCode) -> int:
        words = sorted(self.words(language))
        Path(path).write_text("".join(w + "\n" for w in words), encoding="utf-8")
        return len(words)

    # --- P-045, X-163, J-080..J-085 -----------------------------------------------------

    @property
    def shared_folder(self) -> Path | None:
        return self._shared

    def set_shared_folder(self, path: Path | None) -> None:
        """Folderul partajat; inaccesibil → dictionarul local si un avertisment."""
        self.end_edit()
        self._cache.clear()
        self._shared = None
        if path is None:
            return
        path = Path(path)
        if path.is_dir() and os.access(path, os.R_OK | os.W_OK):  # J-082
            self._shared = path
            # J-085: dictionarele se citesc acum; modificarile altora, la repornire
            for file in path.glob("*.txt"):
                try:
                    self._cache[_language_of(file)] = set(_read_lines(file.read_bytes()))
                except (OSError, ValueError):
                    continue
        else:
            self.warnings.append(WARNING_SHARED_UNAVAILABLE)

    def is_locked_by_other(self, language: LanguageCode) -> bool:
        """J-084: altcineva editeaza acum dictionarul limbii."""
        if self._shared is None or language in self._locks:
            return False
        return (self._shared / f"{_file_name(language)}.lock").exists()

    def end_edit(self, language: LanguageCode | None = None) -> None:
        """Elibereaza dictionarul (sau toate) pentru ceilalti utilizatori."""
        if self._shared is None:
            self._locks.clear()
            return
        for code in [language] if language else list(self._locks):
            if code in self._locks:
                (self._shared / f"{_file_name(code)}.lock").unlink(missing_ok=True)
                self._locks.discard(code)

    def close(self) -> None:
        self.end_edit()

    def _edit(self, language: LanguageCode) -> None:
        """J-084: primul care modifica tine dictionarul pana la end_edit()."""
        assert self._shared is not None
        self.words(language)
        if language in self._locks:
            return
        lock = self._shared / f"{_file_name(language)}.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise PermissionError(
                "dictionarul e editat de alt utilizator; il puteti folosi, dar nu il "
                "puteti modifica acum (J-084)") from exc
        os.close(fd)
        self._locks.add(language)
        # cine incepe sa editeze porneste de la fisierul de acum, ca sa nu
        # piarda cuvintele adaugate intre timp de altii
        path = self._shared / f"{_file_name(language)}.txt"
        self._cache[language] = set(_read_lines(path.read_bytes())) if path.is_file() else set()

    def _write(self, language: LanguageCode) -> None:
        assert self._shared is not None
        target = self._shared / f"{_file_name(language)}.txt"
        temp = target.with_suffix(".tmp")
        temp.write_text("".join(w + "\n" for w in sorted(self._cache[language])),
                        encoding="utf-8")
        os.replace(temp, target)


def _read_lines(data: bytes) -> list[str]:
    """Liniile unui fisier text; ValueError pentru un fisier binar."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        if b"\x00" in data:
            raise ValueError("fisierul nu e text (P-044: dictionarele binare nu se importa)")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")  # P-023
            # [DECIZIE AUTONOMA] Windows-1252 nu are ş/ţ/ș/ț: un dictionar romanesc
            # vechi e de fapt Windows-1250 (ş=0xBA, ţ=0xFE), care in 1252 apar ca º, þ
            if sum(text.count(c) for c in "ºþªÞ") > sum(text.count(c) for c in "áéíóú") \
                    and any(c in text for c in "ºþ"):
                text = data.decode("cp1250", errors="replace")
    return [line.strip() for line in text.splitlines() if line.strip()]
