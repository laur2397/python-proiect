"""Fonturile pentru afisarea textului recunoscut (faza 4b, pasul 4b.4).

P-071, P-120..P-125: fonturile recomandate pe scrieri, din original. P-126
(`X`): produsul nu presupune Microsoft Office instalat; pentru scrierile
neeuropene livreaza fonturi Unicode libere (familia Noto) si declara ce
acopera fiecare. P-127, P-128: cand fontul de afisare lipseste, produsul spune
care font lipseste, nu doar arata patrate.

[DECIZIE AUTONOMA] Fonturile libere livrate sunt familia Noto (SIL OFL 1.1),
cate unul pe scriere (`FREE_FONTS`). **INCOMPLET, marcat:** fisierele lor intra
in pachet la faza 16; pana atunci `display_font` le alege doar daca sunt
instalate.

`FontMatcher` (SPEC_05) e aici; potrivirea unui font PDF (`match`, F-004) vine
cu editorul PDF, faza 9.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Sequence
from functools import lru_cache
from pathlib import Path

from app.core.model import LanguageCode

ARIAL_UNICODE = "Arial Unicode MS"

RECOMMENDED: dict[str, tuple[str, ...]] = {
    # P-071, P-121: numai Arial Unicode MS
    **dict.fromkeys(("ara", "hye", "vie", "yid", "tha"), (ARIAL_UNICODE,)),
    # P-123: plus Palatino Linotype (tadjica; basmira si rusa veche nu au model)
    "tgk": (ARIAL_UNICODE, "Palatino Linotype"),
    # P-124: grupa ebraica
    "heb": (ARIAL_UNICODE, "Aharoni", "David", "Levenim MT", "Miriam", "Narkisim", "Rod"),
    # P-125: grupa CJK
    **dict.fromkeys(("chi_sim", "chi_tra", "jpn", "kor"), (
        ARIAL_UNICODE, "SimSun", "SimSun Founder Extended", "SimSun-18030", "NSimSun",
        "SimHei", "YouYuan", "PMingLiU", "MingLiU", "Ming for-ISO10646", "STSong")),
}
"""Fonturile recomandate de original, pe limba. P-122 (grupa „plus Lucida Sans
Unicode”: avara, zulu, hausa, cecena...) nu are limbi cu model Tesseract in
catalog; `LUCIDA_GROUP` le pastreaza pentru limbile proprii."""
LUCIDA_GROUP = (ARIAL_UNICODE, "Lucida Sans Unicode")

FREE_FONTS: dict[str, str] = {
    "latin": "Noto Sans", "cyrillic": "Noto Sans", "greek": "Noto Sans",
    "arabic": "Noto Sans Arabic", "hebrew": "Noto Sans Hebrew", "thai": "Noto Sans Thai",
    "cjk": "Noto Sans CJK SC", "devanagari": "Noto Sans Devanagari", "other": "Noto Sans",
}
"""P-126: fontul liber livrat si scrierea pe care o acopera."""

DEFAULT_FONTS = ("Arial", "Times New Roman", "Courier New")
"""P-078: fara font gotic, textul gotic se afiseaza in Arial, Times sau Courier."""


def _font_dirs() -> list[Path]:
    home = Path.home()
    if sys.platform.startswith("win"):
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
        return [windir / "Fonts", local / "Microsoft/Windows/Fonts"]
    if sys.platform == "darwin":
        return [Path("/System/Library/Fonts"), Path("/Library/Fonts"), home / "Library/Fonts"]
    return [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), home / ".fonts",
            home / ".local/share/fonts"]


@lru_cache(maxsize=1)
def _system_fonts() -> tuple[str, ...]:
    from PIL import ImageFont

    names: set[str] = set()
    for folder in _font_dirs():
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            try:
                names.add(ImageFont.truetype(str(path), 12).getname()[0])
            except (OSError, ValueError):
                continue
    return tuple(sorted(names))


# SPEC_05, F-004 (aici numai lista fonturilor)
class FontMatcher:
    def __init__(self, installed: Iterable[str] | None = None) -> None:
        self._installed = tuple(installed) if installed is not None else None

    def installed_fonts(self) -> list[str]:
        """Familiile de fonturi instalate (din folderele sistemului)."""
        return list(self._installed if self._installed is not None else _system_fonts())


def _has(font: str, installed: Sequence[str]) -> bool:
    return font.casefold() in {f.casefold() for f in installed}


# P-071, P-078, P-126, P-127
def display_font(language: LanguageCode, installed: Sequence[str],
                 preferred: str | None = None) -> str | None:
    """Fontul cu care se afiseaza textul unei limbi: cel ales de utilizator
    (`areas.plain_text_font`, P-127) daca e instalat; altfel primul recomandat
    instalat; altfel fontul liber al scrierii (P-126); pentru gotic, Arial,
    Times sau Courier (P-078). None cand niciunul nu e instalat."""
    from app.core.ocr.languages import GOTHIC, script_of

    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    candidates += RECOMMENDED.get(language, ())
    candidates.append(FREE_FONTS.get(script_of(language), "Noto Sans"))
    if language in GOTHIC:
        candidates += DEFAULT_FONTS
    for font in candidates:
        if _has(font, installed):
            return font
    return None


# P-128
def missing_fonts(languages: Sequence[LanguageCode], installed: Sequence[str],
                  preferred: str | None = None) -> dict[LanguageCode, list[str]]:
    """Pentru fiecare limba al carei text nu se poate afisa corect: fonturile
    care ar trebui instalate (cel ales de utilizator, apoi cele recomandate si
    fontul liber al scrierii). Gol cand totul se afiseaza."""
    from app.core.ocr.languages import script_of

    out: dict[LanguageCode, list[str]] = {}
    for code in dict.fromkeys(languages):
        if preferred and not _has(preferred, installed):
            out.setdefault(code, []).append(preferred)
        if display_font(code, installed, preferred) is None:
            wanted = [*RECOMMENDED.get(code, ()), FREE_FONTS.get(script_of(code), "Noto Sans")]
            out.setdefault(code, []).extend(f for f in wanted if f not in out.get(code, []))
    return out
