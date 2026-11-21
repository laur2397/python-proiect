"""Traducerile interfetei (faza 6b, pasul 6b.1): CLAUDE.md §6.5.

Niciun text afisabil in cod: interfata foloseste chei (`menu.file`), iar textele
stau in `ro.json` si `en.json` (romana si engleza obligatorii). Cheile
nucleului (`warning.*`, `undo.*`, `stage.*`, `language.*`) se traduc tot aici.

[DECIZIE AUTONOMA] (faza_6b_pasi.md, decizia 1) Fisiere JSON proprii, nu
`.ts/.qm` ale Qt.

O cheie lipsa in limba curenta se cauta in engleza, apoi se afiseaza cheia
insasi (se vede imediat in interfata si in teste).
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

LANGUAGES = ("ro", "en")
DEFAULT = "ro"
_FOLDER = Path(__file__).parent
_state = {"language": DEFAULT}


@cache
def catalog(language: str) -> dict[str, str]:
    """Textele unei limbi (cheie → text)."""
    if language not in LANGUAGES:
        raise ValueError(f"limba interfetei necunoscuta: {language!r}")
    return json.loads((_FOLDER / f"{language}.json").read_text(encoding="utf-8"))


def set_language(language: str) -> None:
    catalog(language)
    _state["language"] = language


def language() -> str:
    return _state["language"]


def tr(key: str, **params: Any) -> str:
    """Textul cheii in limba curenta, cu parametrii inlocuiti (`{n}`)."""
    text = catalog(language()).get(key) or catalog("en").get(key) or key
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError):
            return text
    return text


# Y-013: mesajul afisat se construieste in GUI din codul erorii si parametri
def tr_error(error: Any) -> str:
    """`error.<COD>` cu parametrii exceptiei; codurile fara text dau mesajul generic."""
    code = getattr(error, "code", "CORE_ERROR")
    params = dict(getattr(error, "params", {}) or {})
    key = f"error.{code}"
    if key in catalog(language()) or key in catalog("en"):
        return tr(key, **params)
    return tr("error.generic", code=code)
