"""Etichetele de data si ora din stampile, antete, subsoluri si numerotarea
Bates: SPEC_03 Z.1 (Z-001…Z-012), folosite de D-049.

Etichete: `<d/>` data scurta, `<date/>` data lunga, `<t12/>`, `<t24/>`,
`<time/>` (HH:MM:SS). Cu cod de regiune: `<d=RUS/>` (Z-006); fara cod, formatul
regional al sistemului.

[DECIZIE AUTONOMA] (faza_7_pasi.md, decizia 16) Formatele proprii (Z-007…Z-012)
se scriu in locul codului de regiune: `<d=%#d %B %Y/>`; numele lunilor si ale
zilelor vin din regiunea implicita. Textul din afara etichetelor ramane cum e.
Datele regionale (nume de luni, formate) sunt in `app/core/data/date_regions.json`.
"""

from __future__ import annotations

import json
import locale
import os
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

REGIONS_FILE = Path(__file__).resolve().parent / "data" / "date_regions.json"
TAGS = ("d", "date", "t12", "t24", "time")
"""Z-001…Z-005."""

DEFAULT_REGION = "ROM"
"""[DECIZIE AUTONOMA] Cand regiunea sistemului nu se poate afla sau nu e in lista."""

_TAG = re.compile(r"<(d|date|t12|t24|time)(?:=([^/>]*))?\s*/>")
_FORMAT = re.compile(r"%(#?)([yYbBmdaAHIpMS%])")
_LOCALES = {"ro": "ROM", "ru": "RUS", "hu": "HUN", "cs": "CZ", "en_US": "USA", "en": "ENG"}


@lru_cache(maxsize=1)
def regions() -> dict[str, dict[str, Any]]:
    return json.loads(REGIONS_FILE.read_text(encoding="utf-8"))


def system_region() -> str:
    """Z-006: regiunea din setarile sistemului (fara retea), sau `DEFAULT_REGION`."""
    names = [os.environ.get(var, "") for var in ("LC_ALL", "LC_TIME", "LANG")]
    try:
        names.insert(0, locale.getlocale(locale.LC_TIME)[0] or "")
    except (ValueError, AttributeError):
        pass
    for name in names:
        code = name.split(".")[0].replace("-", "_")
        if code in _LOCALES:
            return _LOCALES[code]
        lang = code.split("_")[0].lower()
        if lang in _LOCALES:
            return _LOCALES[lang]
    return DEFAULT_REGION


# Z-007…Z-012
def format_moment(moment: datetime, fmt: str, region: str = DEFAULT_REGION) -> str:
    """Un format propriu: `%Y`, `%#m`, `%B`, `%p`... `#` scoate zeroul din fata.
    `%p` da AM/PM numai in regiunile care il au (Z-010: USA, ENG, HUN, CZ);
    in rest, sir gol."""
    table = regions()
    data = table.get(region.upper(), table[DEFAULT_REGION])

    def number(value: int, plain: bool) -> str:
        return str(value) if plain else f"{value:02d}"

    def token(match: re.Match[str]) -> str:
        plain, code = bool(match.group(1)), match.group(2)
        hour12 = moment.hour % 12 or 12
        values = {
            "y": lambda: number(moment.year % 100, plain),
            "Y": lambda: str(moment.year),
            "b": lambda: data["months_short"][moment.month - 1],
            "B": lambda: data["months"][moment.month - 1],
            "m": lambda: number(moment.month, plain),
            "d": lambda: number(moment.day, plain),
            "a": lambda: data["days_short"][moment.weekday()],
            "A": lambda: data["days"][moment.weekday()],
            "H": lambda: number(moment.hour, plain),
            "I": lambda: number(hour12, plain),
            "p": lambda: data["ampm"][moment.hour >= 12] if data["ampm"] else "",
            "M": lambda: number(moment.minute, plain),
            "S": lambda: number(moment.second, plain),
            "%": lambda: "%",
        }
        return values[code]()

    return _FORMAT.sub(token, fmt).strip()


# Z-001…Z-006
def expand(text: str, moment: datetime | None = None, *, region: str | None = None) -> str:
    """Inlocuieste etichetele din `text` cu data si ora lui `moment` (implicit
    acum). `region` e regiunea implicita (fara ea, a sistemului)."""
    moment = moment or datetime.now()
    default = (region or system_region()).upper()
    if default not in regions():
        default = DEFAULT_REGION

    def tag(match: re.Match[str]) -> str:
        name, arg = match.group(1), (match.group(2) or "").strip()
        if "%" in arg:  # format propriu
            return format_moment(moment, arg, default)
        code = arg.upper() if arg.upper() in regions() else default
        data = regions()[code]
        fmt = {"d": data["short"], "date": data["long"], "t12": data["t12"],
               "t24": data["t24"], "time": "%H:%M:%S"}[name]
        return format_moment(moment, fmt, code)

    return _TAG.sub(tag, text)


def has_tags(text: str) -> bool:
    return bool(_TAG.search(text))
