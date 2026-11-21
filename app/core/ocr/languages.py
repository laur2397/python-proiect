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

INCOMPLET, marcat: limbile proprii, grupurile si dictionarele utilizatorului
(P-020..P-128) sunt faza 4b.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

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
    """Numai pentru limbile formale: caracterele permise."""

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


def tesseract_spec(codes: Sequence[LanguageCode]) -> tuple[tuple[str, ...], str | None]:
    """Modelele Tesseract pentru o lista de limbi si alfabetul permis. Alfabetul
    se aplica numai cand toate limbile sunt formale (altfel ar taia literele
    limbilor naturale)."""
    langs = [get(c) for c in codes]
    models: list[str] = []
    for lang in langs:
        for m in lang.models:
            if m not in models:
                models.append(m)
    alphabet = None
    if langs and all(lang.category == FORMAL for lang in langs):
        alphabet = "".join(dict.fromkeys("".join(lang.alphabet or "" for lang in langs)))
    return tuple(models), alphabet


# SPEC_05 sect. 7 (P-001..P-029; aici P-002..P-008)
class LanguageRegistry:
    """Catalogul limbilor si limbile recente. `available` sunt modelele
    Tesseract instalate (de obicei `TesseractEngine.available_languages()`)."""

    def __init__(self, available: Sequence[str] = (),
                 settings: SettingsStore | None = None) -> None:
        self._available = set(available)
        self._settings = settings

    # P-005, P-100, P-111
    def all(self) -> list[LanguageCode]:
        return list(_CATALOG)

    def by_category(self, category: str) -> list[LanguageCode]:
        return [c for c, lang in _CATALOG.items() if lang.category == category]

    def display_name(self, code: LanguageCode) -> str:
        return get(code).display_name

    def is_builtin(self, code: LanguageCode) -> bool:
        return code in _CATALOG

    # P-006, P-112
    def has_dictionary(self, code: LanguageCode) -> bool:
        return get(code).has_dictionary

    # Y-004
    def is_model_available(self, code: LanguageCode) -> bool:
        return all(m in self._available for m in get(code).models)

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
