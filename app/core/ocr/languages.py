"""Limbile de recunoastere: catalogul propriu (faza 4, pasul 4.5.5).

P-005 cere „201 limbi OCR”, dar P-100 (SPEC_09, anexa C) spune ca produsul
isi declara propriul numar si nu il copiaza pe al ABBYY. Catalogul de aici e
lista noastra, in cele trei categorii din P-005:

- naturale: modelele Tesseract (tesseract-ocr/tessdata);
- artificiale (P-104): Esperanto are model propriu; Ido, Interlingua si
  Occidental folosesc alfabetul latin al modelului englez;
- formale (P-105, P-106): modelul englez cu un alfabet permis
  (`tessedit_char_whitelist`), fara dictionar.

Romana apare de doua ori, `Romanian` si `RomanianMoldavia` (P-008, P-109),
cu acelasi model; varianta cu sedila o acopera setarea
`ocr.keep_cedilla_diacritics`. Numele afisate sunt chei de traducere
(`language.<cod>`): nucleul nu contine text de interfata (CLAUDE.md §6.5).

Limbile proprii si grupurile (faza 4b, pasul 4b.1, P-020..P-030) stau in
app.db (`ocr_language`, `language_group`); limbile livrate se scriu acolo numai
cand o limba proprie se bazeaza pe ele (`base_language_id`).
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from app.core.errors import BuiltinNotEditableError
from app.core.model import LanguageCode

if TYPE_CHECKING:  # pragma: no cover
    from app.core.settings import SettingsStore

NATURAL, ARTIFICIAL, FORMAL = "natural", "artificial", "formal"

RECENT_MAX = 8
"""P-004: cate limbi recente tine combo-ul din bara principala."""

_DIGITS = "0123456789"
_LATIN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_CODE_CHARS = _LATIN + _DIGITS + "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"


@dataclass(frozen=True, slots=True)
class Language:
    code: LanguageCode
    category: str
    models: tuple[str, ...]
    """Modelele Tesseract folosite (fisierele tessdata/<model>.traineddata)."""
    has_dictionary: bool
    """P-006, P-112: dictionarul permite semnalarea cuvintelor nesigure."""
    alphabet: str | None = None
    """Caracterele permise (limbile formale si cele proprii cu alfabet)."""
    forbidden: str = ""
    """P-026, P-029: caracterele interzise."""
    dictionary_mode: str = "builtin"
    """P-022: none / builtin / user / regex."""
    dictionary_regex: str | None = None
    is_user: bool = False
    advanced: dict[str, Any] = field(default_factory=dict)
    """P-026: inceput/sfarsit de cuvant, ne-litere, ignorate, cifre, abrevieri."""

    @property
    def display_name(self) -> str:
        """Cheia de traducere a numelui (CLAUDE.md §6.5)."""
        return f"language.{self.code}"


# Modelele naturale din tesseract-ocr/tessdata (fara variantele verticale,
# fara `osd` si `equ`, care nu sunt limbi). Toate au lista de cuvinte.
_TESSERACT_NATURAL = (  # noqa: SIM905 - lista se citeste mai usor ca text
    "afr amh ara asm aze aze_cyrl bel ben bod bos bre bul cat ceb ces chi_sim chi_tra chr "
    "cos cym dan deu div dzo ell eng enm est eus fao fas fil fin fra frk frm fry gla gle "
    "glg grc guj hat heb hin hrv hun hye iku ind isl ita ita_old jav jpn kan kat kat_old "
    "kaz khm kir kmr kor lao lat lav lit ltz mal mar mkd mlt mon mri msa mya nep nld nor "
    "oci ori pan pol por pus que ron rus san sin slk slv snd spa spa_old sqi srp srp_latn "
    "sun swa swe syr tam tat tel tgk tha tir ton tur uig ukr urd uzb uzb_cyrl vie yid yor"
).split()

_CATALOG: dict[LanguageCode, Language] = {
    code: Language(code, NATURAL, (code,), True) for code in _TESSERACT_NATURAL
}
_CATALOG.update({
    # P-008, P-109: RomanianMoldavia, acelasi model si acelasi dictionar
    "ron-MD": Language("ron-MD", NATURAL, ("ron",), True),
    # P-104
    "epo": Language("epo", ARTIFICIAL, ("epo",), True),
    "ido": Language("ido", ARTIFICIAL, ("eng",), False),
    "ina": Language("ina", ARTIFICIAL, ("eng",), False),
    "ile": Language("ile", ARTIFICIAL, ("eng",), False),
    # P-105, P-106
    "digits": Language("digits", FORMAL, ("eng",), False, _DIGITS + "+-.,:/()%"),
    "math": Language("math", FORMAL, ("eng",), False, _LATIN + _DIGITS + "+-*/=<>()[].,^%"),
    "chem": Language("chem", FORMAL, ("eng",), False, _LATIN + _DIGITS + "+-=()[]→."),
    "phonetic-en": Language("phonetic-en", FORMAL, ("eng",), False,
                            _LATIN + "ɑæɒʌəɜɪʊɛɔŋθðʃʒːˈˌ/[]"),
    "basic": Language("basic", FORMAL, ("eng",), False, _CODE_CHARS),
    "cpp": Language("cpp", FORMAL, ("eng",), False, _CODE_CHARS),
    "cobol": Language("cobol", FORMAL, ("eng",), False, _CODE_CHARS),
    "fortran": Language("fortran", FORMAL, ("eng",), False, _CODE_CHARS),
    "java": Language("java", FORMAL, ("eng",), False, _CODE_CHARS),
    "pascal": Language("pascal", FORMAL, ("eng",), False, _CODE_CHARS),
})

MINIMUM = ("ron", "ron-MD", "eng", "fra", "deu", "ita", "spa", "hun", "digits")
"""P-110: obiectivul minim declarat (romana in ambele variante, cifrele)."""


def get(code: LanguageCode) -> Language:
    """Limba din catalog; un cod necunoscut e tratat ca model Tesseract cu
    acelasi nume (limbile instalate de utilizator), fara dictionar declarat."""
    return _CATALOG.get(code) or Language(code, NATURAL, (code,), False)


def tesseract_spec(codes: Sequence[LanguageCode],
                   registry: LanguageRegistry | LanguageSnapshot | None = None,
                   ) -> tuple[tuple[str, ...], str | None]:
    """Modelele Tesseract pentru o lista de limbi si alfabetul permis. Alfabetul
    se aplica numai cand toate limbile au unul (formale sau proprii cu alfabet);
    altfel ar taia literele limbilor naturale."""
    langs = [registry.get(c) if registry else get(c) for c in codes]
    models: list[str] = []
    for lang in langs:
        for m in lang.models:
            if m not in models:
                models.append(m)
    alphabet = None
    if langs and all(lang.alphabet for lang in langs):
        alphabet = "".join(dict.fromkeys("".join(lang.alphabet or "" for lang in langs)))
    return tuple(models), alphabet


_OTHER_SCRIPTS = {"amh", "asm", "ben", "bod", "chr", "div", "dzo", "guj", "iku", "kan", "kat",
                  "kat_old", "khm", "lao", "mal", "mya", "ori", "pan", "sin", "syr", "tam",
                  "tel", "tir"}
_SCRIPTS = {
    "cyrillic": "rus ukr bul srp bel mkd kaz kir mon tat tgk uzb_cyrl aze_cyrl",
    "greek": "ell grc", "hebrew": "heb yid", "arabic": "ara fas urd pus snd uig",
    "cjk": "chi_sim chi_tra jpn kor", "thai": "tha", "devanagari": "hin mar nep san",
    "latin": " ".join(c for c in _TESSERACT_NATURAL if c not in _OTHER_SCRIPTS),
}


def script_of(code: LanguageCode) -> str:
    """Scrierea unei limbi, pentru coloana `ocr_language.script` (SPEC_04)."""
    for script, codes in _SCRIPTS.items():
        if code in codes.split():
            return script
    lang = get(code)
    return "latin" if lang.category != NATURAL else "other"


_ADVANCED = ("chars_word_start", "chars_word_end", "chars_nonalpha", "chars_ignored",
             "allow_arabic_numerals", "allow_roman_numerals", "allow_abbreviations")
"""P-026: proprietatile din `Advanced...` (coloanele din ocr_language)."""
DICTIONARY_MODES = ("none", "builtin", "user", "regex")
GROUP_PREFIX = "group:"


class LanguageSnapshot:
    """Limbile proprii si grupurile la un moment dat, fara baza de date."""

    def __init__(self, languages: dict[LanguageCode, Language]) -> None:
        self._languages = languages

    def get(self, code: LanguageCode) -> Language:
        return self._languages.get(code) or get(code)


# SPEC_05 sect. 7 (P-001..P-029; aici P-002..P-008)
class LanguageRegistry:
    """Catalogul limbilor si limbile recente. `available` sunt modelele
    Tesseract instalate (de obicei `TesseractEngine.available_languages()`)."""

    def __init__(self, available: Sequence[str] = (),
                 settings: SettingsStore | None = None,
                 con: sqlite3.Connection | None = None) -> None:
        self._available = set(available)
        self._settings = settings
        self._con = con
        """app.db: limbile proprii si grupurile (4b.1). Fara ea, numai catalogul."""

    # P-005, P-100, P-111
    def all(self) -> list[LanguageCode]:
        return [*_CATALOG, *self.user_languages(), *(GROUP_PREFIX + g for g in self.groups())]

    def get(self, code: LanguageCode) -> Language:
        """Limba din catalog, o limba proprie sau un grup (folosit ca o singura
        limba, P-027)."""
        if self._con is not None:
            if code.startswith(GROUP_PREFIX):
                return self._group(code[len(GROUP_PREFIX):])
            row = self._con.execute(
                "SELECT l.code, b.code, l.alphabet, l.chars_forbidden, l.dictionary_mode,"
                " l.dictionary_regex, l.chars_word_start, l.chars_word_end, l.chars_nonalpha,"
                " l.chars_ignored, l.allow_arabic_numerals, l.allow_roman_numerals,"
                " l.allow_abbreviations FROM ocr_language l"
                " LEFT JOIN ocr_language b ON b.id = l.base_language_id"
                " WHERE l.code = ? AND l.is_builtin = 0", (code,)).fetchone()
            if row is not None:
                base = get(row[1] or "eng")
                return Language(code, base.category, base.models,
                                row[4] in ("builtin", "user") and base.has_dictionary,
                                alphabet=row[2] or None, forbidden=row[3] or "",
                                dictionary_mode=row[4], dictionary_regex=row[5], is_user=True,
                                advanced=dict(zip(_ADVANCED, row[6:], strict=True)))
        return get(code)

    def snapshot(self) -> LanguageSnapshot:
        """Limbile proprii si grupurile, citite acum; se pot folosi din firele
        de lucru (conexiunea SQLite nu se poate)."""
        codes = [*self.user_languages(), *(GROUP_PREFIX + g for g in self.groups())]
        return LanguageSnapshot({c: self.get(c) for c in codes})

    # P-020..P-026
    def user_languages(self) -> list[LanguageCode]:
        if self._con is None:
            return []
        return [r[0] for r in self._con.execute(
            "SELECT code FROM ocr_language WHERE is_builtin = 0 ORDER BY display_name")]

    def create_user_language(
        self,
        name: str,
        base: LanguageCode,
        *,
        alphabet: str | None = None,
        forbidden_chars: str | None = None,
        dictionary_mode: str = "builtin",
        dictionary_regex: str | None = None,
    ) -> LanguageCode:
        """P-020..P-026: o limba noua, pe baza uneia existente. Numele e unic;
        `dictionary_regex` trebuie sa compileze, altfel `ValueError` cu
        mesajul erorii (P-025). Intoarce codul limbii."""
        from app.core.ocr.regex import compile_expression

        con = self._require_db()
        name = (name or "").strip()
        if not name:
            raise ValueError("limba are nevoie de un nume")
        if base not in _CATALOG:
            raise ValueError(f"limba sursa {base!r} nu e o limba livrata")
        if dictionary_mode not in DICTIONARY_MODES:
            raise ValueError(f"dictionary_mode: {dictionary_mode!r} nu e in {DICTIONARY_MODES}")
        if dictionary_mode == "regex":
            if not dictionary_regex:
                raise ValueError("dictionarul de tip expresie cere o expresie")
            compile_expression(dictionary_regex)
        code = "user:" + re.sub(r"\s+", "_", name.lower())
        if con.execute("SELECT 1 FROM ocr_language WHERE code = ? OR display_name = ?",
                       (code, name)).fetchone():
            raise ValueError(f"exista deja o limba cu numele {name!r}")
        with con:
            base_id = self._builtin_row(base)
            con.execute(
                "INSERT INTO ocr_language (code, display_name, script, is_builtin,"
                " base_language_id, model_available, has_dictionary, alphabet,"
                " chars_forbidden, dictionary_mode, dictionary_regex)"
                " VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)",
                (code, name, script_of(base), base_id, int(self.is_model_available(base)),
                 int(dictionary_mode in ("builtin", "user")), alphabet or None,
                 forbidden_chars or None, dictionary_mode,
                 dictionary_regex if dictionary_mode == "regex" else None))
        return code

    def set_advanced(self, code: LanguageCode, **props: Any) -> None:
        """P-026: proprietatile din `Advanced...` ale unei limbi proprii."""
        con = self._require_db()
        unknown = set(props) - set(_ADVANCED) - {"chars_forbidden"}
        if unknown:
            raise ValueError(f"proprietati necunoscute: {sorted(unknown)}")
        self._require_user(code)
        values = {k: (int(bool(v)) if k.startswith("allow_") else (v or None))
                  for k, v in props.items()}
        with con:
            for key, value in values.items():
                con.execute(f"UPDATE ocr_language SET {key} = ? WHERE code = ?", (value, code))

    def delete_user_language(self, code: LanguageCode) -> None:
        """P-006 (SPEC_05): limbile livrate nu se sterg."""
        con = self._require_db()
        if code in _CATALOG:
            raise BuiltinNotEditableError("limbile livrate nu se sterg", code=code)
        self._require_user(code)
        with con:
            con.execute("DELETE FROM ocr_language WHERE code = ?", (code,))

    # P-027..P-029
    def groups(self) -> list[str]:
        if self._con is None:
            return []
        return [r[0] for r in self._con.execute("SELECT name FROM language_group ORDER BY name")]

    def create_group(self, name: str, codes: Sequence[LanguageCode], *,
                     forbidden_chars: str | None = None) -> str:
        """P-027, P-028: un grup are nume unic si cel putin doua limbi; se
        foloseste ca o singura limba, cu codul `group:<nume>`. P-029: caracterele
        interzise ale grupului."""
        con = self._require_db()
        name = (name or "").strip()
        unique = list(dict.fromkeys(codes))
        if not name:
            raise ValueError("grupul are nevoie de un nume")
        if len(unique) < 2:
            raise ValueError("un grup de limbi are nevoie de cel putin doua limbi")
        if con.execute("SELECT 1 FROM language_group WHERE name = ?", (name,)).fetchone():
            raise ValueError(f"exista deja un grup {name!r}")
        with con:
            gid = con.execute("INSERT INTO language_group (name, chars_forbidden) VALUES (?, ?)",
                              (name, forbidden_chars or None)).lastrowid
            for code in unique:
                lid = self._language_id(code)
                con.execute("INSERT INTO language_group_member (group_id, language_id)"
                            " VALUES (?, ?)", (gid, lid))
        return GROUP_PREFIX + name

    def group_members(self, name: str) -> list[LanguageCode]:
        con = self._require_db()
        return [r[0] for r in con.execute(
            "SELECT l.code FROM language_group_member m JOIN language_group g ON g.id = m.group_id"
            " JOIN ocr_language l ON l.id = m.language_id WHERE g.name = ? ORDER BY l.code",
            (name,))]

    def _group(self, name: str) -> Language:
        con = self._require_db()
        row = con.execute("SELECT chars_forbidden FROM language_group WHERE name = ?",
                          (name,)).fetchone()
        if row is None:
            raise ValueError(f"grupul {name!r} nu exista")
        members = [self.get(c) for c in self.group_members(name)]
        models = tuple(dict.fromkeys(m for lang in members for m in lang.models))
        forbidden = (row[0] or "") + "".join(lang.forbidden for lang in members)
        return Language(GROUP_PREFIX + name, NATURAL, models,
                        any(lang.has_dictionary for lang in members), forbidden=forbidden)

    # --- ajutoare app.db ------------------------------------------------------------

    def _require_db(self) -> sqlite3.Connection:
        if self._con is None:
            raise RuntimeError("registrul nu are app.db: limbile proprii nu sunt disponibile")
        return self._con

    def _require_user(self, code: LanguageCode) -> None:
        if not self._require_db().execute(
                "SELECT 1 FROM ocr_language WHERE code = ? AND is_builtin = 0",
                (code,)).fetchone():
            raise ValueError(f"limba proprie {code!r} nu exista")

    def _builtin_row(self, code: LanguageCode) -> int:
        """Randul unei limbi livrate in ocr_language, creat la nevoie."""
        con = self._require_db()
        row = con.execute("SELECT id FROM ocr_language WHERE code = ?", (code,)).fetchone()
        if row:
            return int(row[0])
        lang = get(code)
        return int(con.execute(
            "INSERT INTO ocr_language (code, display_name, script, is_builtin, model_path,"
            " model_available, has_dictionary, alphabet) VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
            (code, lang.display_name, script_of(code), "+".join(lang.models),
             int(self.is_model_available(code)), int(lang.has_dictionary),
             lang.alphabet)).lastrowid)

    def _language_id(self, code: LanguageCode) -> int:
        con = self._require_db()
        row = con.execute("SELECT id FROM ocr_language WHERE code = ?", (code,)).fetchone()
        if row:
            return int(row[0])
        if code not in _CATALOG:
            raise ValueError(f"limba {code!r} nu exista")
        return self._builtin_row(code)

    # P-030: limbile proprii ale unui proiect, in folderul lui
    def export_user_languages(self, codes: Sequence[LanguageCode]) -> list[dict[str, Any]]:
        """Descrierea limbilor proprii din `codes` (celelalte se ignora)."""
        out = []
        for code in dict.fromkeys(codes):
            if not code.startswith("user:") or self._con is None:
                continue
            row = self._con.execute(
                "SELECT l.display_name, b.code, l.alphabet, l.chars_forbidden,"
                " l.dictionary_mode, l.dictionary_regex, l.chars_word_start, l.chars_word_end,"
                " l.chars_nonalpha, l.chars_ignored, l.allow_arabic_numerals,"
                " l.allow_roman_numerals, l.allow_abbreviations FROM ocr_language l"
                " LEFT JOIN ocr_language b ON b.id = l.base_language_id"
                " WHERE l.code = ? AND l.is_builtin = 0", (code,)).fetchone()
            if row:
                out.append({"code": code, "name": row[0], "base": row[1], "alphabet": row[2],
                            "forbidden": row[3], "dictionary_mode": row[4],
                            "dictionary_regex": row[5],
                            "advanced": dict(zip(_ADVANCED, row[6:], strict=True))})
        return out

    def import_user_languages(self, items: Sequence[dict[str, Any]]) -> list[LanguageCode]:
        """Adauga limbile care lipsesc din app.db; cele existente raman."""
        added = []
        for item in items:
            if item["code"] in self.user_languages():
                continue
            code = self.create_user_language(
                item["name"], item["base"] or "eng", alphabet=item.get("alphabet"),
                forbidden_chars=item.get("forbidden"),
                dictionary_mode=item.get("dictionary_mode") or "builtin",
                dictionary_regex=item.get("dictionary_regex"))
            advanced = {k: v for k, v in (item.get("advanced") or {}).items() if v is not None}
            if advanced:
                self.set_advanced(code, **advanced)
            added.append(code)
        return added

    def by_category(self, category: str) -> list[LanguageCode]:
        return [c for c, lang in _CATALOG.items() if lang.category == category]

    def display_name(self, code: LanguageCode) -> str:
        """Cheia de traducere a unei limbi livrate; numele dat de utilizator al
        unei limbi proprii sau al unui grup."""
        if self._con is not None and code.startswith("user:"):
            row = self._con.execute("SELECT display_name FROM ocr_language WHERE code = ?",
                                    (code,)).fetchone()
            if row:
                return str(row[0])
        if code.startswith(GROUP_PREFIX):
            return code[len(GROUP_PREFIX):]
        return get(code).display_name

    def is_builtin(self, code: LanguageCode) -> bool:
        return code in _CATALOG

    # P-006, P-112
    def has_dictionary(self, code: LanguageCode) -> bool:
        return self.get(code).has_dictionary

    # Y-004
    def is_model_available(self, code: LanguageCode) -> bool:
        return all(m in self._available for m in self.get(code).models)

    def available(self) -> list[LanguageCode]:
        """Limbile din catalog care se pot folosi acum (P-111)."""
        return [c for c in _CATALOG if self.is_model_available(c)]

    # P-004: combo-ul din bara principala, limbile recente
    def recent(self) -> list[LanguageCode]:
        return list(self._settings.get("lang.recent")) if self._settings else []

    def remember(self, codes: Sequence[LanguageCode]) -> None:
        """Pune limbile folosite in fruntea listei recente (fara dubluri)."""
        if self._settings is None:
            return
        merged = list(dict.fromkeys([*codes, *self.recent()]))[:RECENT_MAX]
        self._settings.set("lang.recent", merged)

    # P-001 (SPEC_05 il numeste P-002)
    def autodetect(self, page: Any, engine: Any = None,
                   settings: Any = None) -> tuple[LanguageCode, ...]:
        """Limba paginii dintre candidatii din setari care au dictionar.
        Fara motor, sau cu un singur candidat, prima limba (SPEC_05: nu o
        eroare). Alegerea e aceeasi ca in RecognitionService (P-001)."""
        languages = tuple(settings.languages) if settings is not None else ()
        if not languages:
            return ()
        candidates = tuple(c for c in languages if self.has_dictionary(c))
        if engine is None or len(candidates) < 2:
            return (candidates or languages)[:1]
        from app.core.ocr.service import pick_language

        return (pick_language(engine, page, replace(settings, languages=candidates)),)
