"""Elementele de structura ale documentului recunoscut (pasul 4.5.3).

N-018 antete si subsoluri, N-019 note de subsol, N-020 cuprins, N-021 liste.
Detectia lucreaza pe textul recunoscut al tuturor paginilor (SPEC_05,
`LayoutAnalyzer.detect_structural_elements`): antetul e un text care se repeta
in acelasi loc pe mai mult de `header_repeat_ratio` din pagini.

Rezultatul se marcheaza pe blocuri (`block_type`, `list_level`, `style_name`)
si pe zone (`text_function`). Exportul (faza 6) il transforma in elemente
clicabile; cu detectia dezactivata, blocurile raman paragrafe obisnuite.

[DECIZIE AUTONOMA] SPEC_04 nu are un tip de bloc pentru cuprins. Intrarile
de cuprins primesc `style_name = TOC_STYLE`; exportul le face legaturi.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from statistics import median

from app.core.model import AreaType, BlockData, PageData, TextFunction

TOC_STYLE = "TOC"

HEADER_BAND = 0.12
"""[DECIZIE AUTONOMA] Antetul sta in primele 12% din inaltimea paginii, subsolul
in ultimele 12%."""
FOOTNOTE_BAND = 0.70
"""Notele de subsol incep sub 70% din inaltimea paginii..."""
FOOTNOTE_SIZE = 0.9
"""...si au litera mai mica: randul, sub 90% din inaltimea obisnuita."""
TOC_MIN_LINES = 3
"""Un cuprins are cel putin 3 intrari pe pagina."""

_BULLET = re.compile(r"^[•·▪◦‣○●■□➢►✓–—\-*]$")
_NUMBERED = re.compile(r"^(\d{1,3}(\.\d{1,3})*|[a-zA-Z]|[ivxlcIVXLC]{1,5})[.)]$")
_FOOTNOTE_MARK = re.compile(r"^(\d{1,3}|[¹²³⁴⁵⁶⁷⁸⁹⁰]+|\*{1,3})[.)]?$")
_PAGE_NUMBER = re.compile(r"^(\d{1,4}|[ivxlcIVXLC]{1,6})$")
_LEADER = re.compile(r"(\.\s*){4,}|…")
_ONE_LOOKALIKES = {"l", "I", "|", "]", "["}
"""[DECIZIE AUTONOMA] O cifra „1” singura se citeste des „l” sau „I”; singura,
in banda de antet sau subsol, e tot un numar de pagina."""


def detect(pages: Sequence[PageData], *, headers: bool = True, footnotes: bool = True,
           toc: bool = True, lists: bool = True, repeat_ratio: float = 0.5,
           headings: bool = True) -> None:
    """Marcheaza elementele pe blocurile si zonele paginilor date. Fiecare
    bloc se recalculeaza (o detectie dezactivata il lasa paragraf)."""
    for page in pages:
        for block in _text_blocks(page):
            if block.block_type == "heading" and (block.style_name or "").startswith(
                    "Heading "):
                block.style_name = None
            block.block_type, block.list_level = "paragraph", None
            if block.style_name == TOC_STYLE:
                block.style_name = None
    if headers:
        _headers_footers(pages, repeat_ratio)
    if headings:
        _headings(pages)
    for page in pages:
        if footnotes:
            _footnotes(page)
        if toc:
            _table_of_contents(page)
        if lists:
            _lists(page)
        _area_functions(page)


def _text_blocks(page: PageData) -> list[BlockData]:
    return [b for a in page.areas if a.area_type in (AreaType.TEXT, AreaType.RECOGNITION)
            for b in a.blocks if b.lines]


def _words(block: BlockData) -> list[str]:
    return [w.text for ln in block.lines for w in ln.words]


# --- N-018 ---------------------------------------------------------------------------


def _signature(block: BlockData) -> str:
    """Textul fara cifre: „Pagina 3 din 12” si „Pagina 4 din 12” sunt la fel.
    Un numar de pagina singur are semnatura „#”."""
    words = _words(block)
    if len(words) == 1 and (_PAGE_NUMBER.match(words[0].strip("-–— "))
                            or words[0] in _ONE_LOOKALIKES):
        return "#"
    text = " ".join(words).lower()
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", text)).strip()


def _headers_footers(pages: Sequence[PageData], ratio: float) -> None:
    if len(pages) < 2:
        return  # „se repeta” cere cel putin doua pagini
    found: dict[tuple[str, str], list[tuple[int, BlockData]]] = {}
    for index, page in enumerate(pages):
        for block in _text_blocks(page):
            if block.bbox.bottom <= HEADER_BAND * page.height_px:
                band = "header"
            elif block.bbox.y >= (1 - HEADER_BAND) * page.height_px:
                band = "footer"
            else:
                continue
            signature = _signature(block)
            if signature:
                found.setdefault((band, signature), []).append((index, block))
    for (band, _), hits in found.items():
        if len({index for index, _ in hits}) / len(pages) > ratio:
            for _, block in hits:
                block.block_type = band


# --- O-111: titlurile ---------------------------------------------------------------

HEADING_SIZE = 1.3
"""[DECIZIE AUTONOMA] Un titlu are litera de cel putin 1,3 ori mai mare decat
randul obisnuit al paginii si cel mult HEADING_LINES randuri."""
HEADING_LINES = 2


def _headings(pages: Sequence[PageData]) -> None:
    """Titlurile primesc `block_type = heading` si stilul `Heading N`; nivelul
    vine din marime, pe tot documentul (cel mai mare = Heading 1)."""
    found: list[tuple[BlockData, float]] = []
    for page in pages:
        usual = _line_height(page)
        if not usual:
            continue
        for block in _text_blocks(page):
            if block.block_type != "paragraph" or len(block.lines) > HEADING_LINES:
                continue
            size = median(ln.bbox.h for ln in block.lines)
            if size >= HEADING_SIZE * usual:
                found.append((block, size / usual))
    levels: list[float] = []
    for _, ratio in sorted(found, key=lambda x: -x[1]):
        if not levels or ratio < levels[-1] * 0.9:  # o marime noua: un nivel nou
            levels.append(ratio)
    for block, ratio in found:
        level = next(i for i, r in enumerate(levels, start=1) if ratio >= r * 0.9)
        block.block_type = "heading"
        block.style_name = f"Heading {min(level, 10)}"


# --- N-019 ---------------------------------------------------------------------------


def _line_height(page: PageData) -> float:
    heights = [ln.bbox.h for b in _text_blocks(page) for ln in b.lines if ln.bbox.h > 0]
    return median(heights) if heights else 0.0


def _footnotes(page: PageData) -> None:
    usual = _line_height(page)
    if not usual:
        return
    for block in _text_blocks(page):
        if block.block_type != "paragraph" or block.bbox.y < FOOTNOTE_BAND * page.height_px:
            continue
        words = _words(block)
        size = median(ln.bbox.h for ln in block.lines)
        if words and _FOOTNOTE_MARK.match(words[0]) and size < FOOTNOTE_SIZE * usual:
            block.block_type = "footnote"


# --- N-020 ---------------------------------------------------------------------------


def _toc_line(words: list[str]) -> bool:
    """O intrare de cuprins se termina cu un numar de pagina, dupa puncte de
    legatura („Capitolul 1 ........ 5”)."""
    if len(words) < 2 or not _PAGE_NUMBER.match(words[-1].lstrip(".…")):
        return False
    return bool(_LEADER.search(" ".join(words)))


def _table_of_contents(page: PageData) -> None:
    counted: list[tuple[BlockData, int]] = []
    for block in _text_blocks(page):
        if block.block_type == "paragraph":
            hits = sum(_toc_line([w.text for w in ln.words]) for ln in block.lines)
            counted.append((block, hits))
    if sum(hits for _, hits in counted) < TOC_MIN_LINES:
        return
    for block, hits in counted:
        if hits and hits / len(block.lines) >= 0.6:
            block.style_name = TOC_STYLE


# --- N-021 ---------------------------------------------------------------------------


def _lists(page: PageData) -> None:
    items = []
    for block in _text_blocks(page):
        if block.block_type != "paragraph" or block.style_name == TOC_STYLE:
            continue
        words = _words(block)
        if len(words) >= 2 and (_BULLET.match(words[0]) or _NUMBERED.match(words[0])):
            items.append(block)
    if not items:
        return
    left = min(b.bbox.x for b in items)
    step = 2 * (_line_height(page) or 1)
    for block in items:
        block.block_type = "list_item"
        block.list_level = min(10, 1 + int((block.bbox.x - left) / step))


def _area_functions(page: PageData) -> None:
    """O zona de text in care toate blocurile sunt antet (subsol, nota de
    subsol) primeste acea functie (M-024). O functie pusa de utilizator
    (alta decat antet, subsol, nota) ramane."""
    kinds = {"header": TextFunction.HEADER, "footer": TextFunction.FOOTER,
             "footnote": TextFunction.FOOTNOTE}
    ours = (None, TextFunction.BODY, *kinds.values())
    for area in page.areas:
        if area.area_type is not AreaType.TEXT or area.text_function not in ours:
            continue
        types = {b.block_type for b in area.blocks if b.lines}
        only = next(iter(types)) if len(types) == 1 else None
        if only in kinds:
            area.text_function = kinds[only]
        elif area.text_function in kinds.values():
            area.text_function = None
