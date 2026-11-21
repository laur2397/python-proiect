"""Editarea si verificarea textului recunoscut (faza 5): pasul 5.1 (O-001..O-012,
O-020) si pasul 5.2 (cautarea si inlocuirea O-024..O-026, formatarea O-022,
O-023, redactarea O-070..O-072, celulele de tabel O-027, O-060..O-063,
copierea O-080..O-083).

`TextEditor` din SPEC_05. Fiecare modificare trece prin proiect: un pas de undo
si proiectul marcat ca modificat. Metodele primesc `WordData` (cu id) din
paginile proiectului; dupa o modificare, paginile se reincarca, deci apelantul
ia din nou cuvintele din `project.page(n)`.
"""

from __future__ import annotations

import io
import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    PageData,
    PageStatus,
    TableCellData,
    WordData,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.core.project import OcrProject

_PUNCTUATION = ".,;:!?()[]{}\"'„”«»"

CJK_LOOKALIKES: tuple[str, ...] = (
    "未末", "己已巳", "土士", "人入八", "日曰", "千干于", "天夫", "刀力", "大太犬", "王玉主",
    "田由甲申", "木本未", "口囗", "白自", "斤斥", "免兔", "贝见", "侯候", "戍戌戊", "ロ口",
    "カ力", "エ工", "ニ二", "ハ八", "タ夕", "へヘ", "ー一", "기키", "이리",
)
"""O-010: grupuri de caractere CJK cu aspect asemanator.
[DECIZIE AUTONOMA] Lista e a noastra; originalul nu o publica."""


@dataclass(frozen=True, slots=True)
class VerifyOptions:
    """O-012 (X-160..X-162)."""

    check_uncertain: bool = True
    ignore_words_with_digits: bool = True
    check_compound_words: bool = True
    fix_punctuation_spaces: bool = True

    @classmethod
    def from_settings(cls, settings: Any) -> VerifyOptions:
        return cls(bool(settings.get("areas.check_uncertain")),
                   bool(settings.get("areas.ignore_words_with_digits")),
                   bool(settings.get("areas.check_compound_words")),
                   bool(settings.get("areas.fix_punctuation_spaces")))


def bare(text: str) -> str:
    """Cuvantul fara punctuatia de la capete (pentru dictionar)."""
    return text.strip(_PUNCTUATION)


def fix_punctuation_spaces(text: str) -> str:
    """O-012: fara spatiu inainte de , . ; : ! ? si dupa ( [ „."""
    text = re.sub(r"\s+([,.;:!?)\]”»])", r"\1", text)
    return re.sub(r"([(\[„«])\s+", r"\1", text)


# SPEC_05 sect. 8. O-001..O-029
class TextEditor:
    def __init__(self, project: OcrProject) -> None:
        self._project = project

    # --- O-020: editarea directa -----------------------------------------------------

    def set_word_text(self, word: WordData, text: str) -> None:
        """Pastreaza `original_text`, pune `is_edited`, scoate `is_verified`.
        Cuvantul scris de utilizator nu mai e nesigur. Modificarea ajunge si in
        stratul de text exportat (exportul citeste textul cuvintelor)."""
        word_id = self._id(word)
        if VerifyOptions.from_settings(self._project.settings()).fix_punctuation_spaces:
            text = fix_punctuation_spaces(text)
        project = self._project
        with project._history("edit_text", {"words": 1}), project._con:
            project._con.execute(
                "UPDATE word SET original_text = COALESCE(original_text, text), text = ?,"
                " is_edited = 1, is_verified = 0, is_uncertain = 0 WHERE id = ?",
                (text, word_id))
            self._page_back_to_recognized([word_id])
        project._after_change()

    # O-008: un simbol care nu e pe tastatura
    def insert_symbol(self, word: WordData, position: int, symbol: str) -> None:
        if not symbol:
            raise ValueError("simbolul lipseste")
        position = max(0, min(position, len(word.text)))
        self.set_word_text(word, word.text[:position] + symbol + word.text[position:])

    # --- O-001, O-002: cuvintele nesigure ----------------------------------------------

    def _candidates(self, pages: Sequence[PageData]) -> Iterator[WordData]:
        options = VerifyOptions.from_settings(self._project.settings())
        if not options.check_uncertain:
            return
        for page in pages:
            for word in page.iter_words():
                if not word.is_uncertain or word.is_verified or word.is_redacted:
                    continue
                core = bare(word.text)
                if options.ignore_words_with_digits and (
                        any(ch.isdigit() for ch in core)
                        or any(not ch.isalnum() and ch != "-" for ch in core)):
                    continue  # O-012: cuvinte cu cifre si caractere speciale
                if not options.check_compound_words and "-" in core:
                    continue  # O-012: cuvintele compuse nu se verifica
                yield word

    def next_uncertain(self, pages: Sequence[PageData],
                       after: WordData | None = None) -> WordData | None:
        """O-002 (SPEC_05: O-004). None cand nu mai urmeaza niciunul (mesaj)."""
        if after is None:
            return next(self._candidates(pages), None)
        return self._after_position(pages, after, forward=True)

    def previous_uncertain(self, pages: Sequence[PageData],
                           before: WordData | None = None) -> WordData | None:
        """O-002 (SPEC_05: O-005)."""
        if before is None:
            words = list(self._candidates(pages))
            return words[-1] if words else None
        return self._after_position(pages, before, forward=False)

    def _after_position(self, pages: Sequence[PageData], word: WordData,
                        forward: bool) -> WordData | None:
        """Urmatorul (anteriorul) nesigur fata de pozitia unui cuvant oarecare."""
        order = {w.id: i for i, w in enumerate(w for p in pages for w in p.iter_words())}
        if word.id not in order:
            return None
        where = order[word.id]
        candidates = list(self._candidates(pages))
        if forward:
            return next((w for w in candidates if order[w.id] > where), None)
        before = [w for w in candidates if order[w.id] < where]
        return before[-1] if before else None

    # --- O-003..O-007, O-011: dialogul de verificare -------------------------------------

    def skip(self, word: WordData) -> None:
        """O-004: scoate evidentierea fara sa schimbe textul."""
        self._update([self._id(word)], "is_verified = 1", "verify_skip")

    def add_to_dictionary(self, word: WordData, language: str | None = None) -> bool:
        """O-006: cuvantul intra in dictionarul limbii lui si nu mai e semnalat
        nicaieri in proiect. False daca era deja (P-041)."""
        from app.core.ocr.dictionary import DictionaryService

        text = bare(word.text)
        code = language or word.language_code or self._project.settings().ocr_settings(
            ).languages[0]
        added = DictionaryService(self._project._ctx.app_db,
                                  self._project.settings()).add(text, code)
        same = [w.id for p in self._project.pages for w in p.iter_words()
                if bare(w.text) == text and w.id is not None]
        self._update(same, "in_dictionary = 1, is_uncertain = 0", "add_to_dictionary")
        return added

    def suggestions(self, word: WordData, limit: int = 8) -> list[str]:
        """O-005, O-010: din dictionarul utilizatorului; pentru CJK, cuvintele
        cu caractere de aspect asemanator."""
        from app.core.ocr.dictionary import DictionaryService
        from app.core.ocr.languages import CJK

        code = word.language_code or self._project.settings().ocr_settings().languages[0]
        if code in CJK:
            return cjk_variants(word.text, limit)
        return DictionaryService(self._project._ctx.app_db,
                                 self._project.settings()).suggest(bare(word.text), code, limit)

    def mark_verified(self, page: PageData) -> None:
        """O-011 (`Ctrl+T`): pagina devine `VERIFIED`, cuvintele ei verificate."""
        project = self._project
        with project._history("mark_verified", {"page": page.page_number}), project._con:
            project._con.execute(
                "UPDATE word SET is_verified = 1 WHERE line_id IN (SELECT l.id FROM text_line l"
                " JOIN text_block b ON b.id = l.block_id JOIN area a ON a.id = b.area_id"
                " WHERE a.page_id = ?)", (page.id,))
            project._con.execute("UPDATE page SET status = ? WHERE id = ?",
                                 (PageStatus.VERIFIED.value, page.id))
        project._after_change()

    # --- O-024..O-026: cautarea si inlocuirea ------------------------------------------

    def find(self, pages: Sequence[PageData], query: str, *, match_case: bool = False,
             whole_word: bool = False, ignore_diacritics: bool = True) -> list[WordData]:
        """O-024 (SPEC_05: O-028). Cuvintele in care apare `query`; o expresie
        de mai multe cuvinte se cauta pe cuvinte consecutive din acelasi rand si
        intoarce toate cuvintele potrivirii. Implicit fara diacritice:
        „hotarare” gaseste „hotărâre”."""
        def norm(text: str) -> str:
            if ignore_diacritics:
                text = _plain(text)
            return text if match_case else text.casefold()

        parts = [norm(q) for q in query.split()]
        if not parts:
            return []
        found: list[WordData] = []
        for page in pages:
            for line in _lines(page):
                keys = [norm(w.text) for w in line]
                for i in range(len(line) - len(parts) + 1):
                    window = keys[i:i + len(parts)]
                    if len(parts) == 1:
                        hit = (bare(window[0]) == parts[0] if whole_word
                               else parts[0] in window[0])
                    else:
                        hit = (all(bare(a) == b for a, b in zip(window, parts, strict=True))
                               if whole_word else
                               window[0].endswith(parts[0]) and window[-1].startswith(parts[-1])
                               and all(a == b for a, b in zip(window[1:-1], parts[1:-1],
                                                              strict=True)))
                    if hit:
                        found += [w for w in line[i:i + len(parts)] if w not in found]
        return found

    def replace(self, words: Sequence[WordData], new_text: str) -> int:
        """O-026 (SPEC_05: O-029). Fiecare cuvant primeste `new_text`; textul
        gol sterge cuvintele. Un singur pas de undo. Intoarce cate s-au inlocuit."""
        ids = [self._id(w) for w in words]
        if not ids:
            return 0
        project = self._project
        marks = ",".join("?" * len(ids))
        with project._history("replace_text", {"words": len(ids)}), project._con:
            self._page_back_to_recognized(ids)
            if new_text:
                project._con.execute(
                    f"UPDATE word SET original_text = COALESCE(original_text, text), text = ?,"
                    f" is_edited = 1, is_verified = 0, is_uncertain = 0 WHERE id IN ({marks})",
                    (new_text, *ids))
            else:
                project._con.execute(f"DELETE FROM word WHERE id IN ({marks})", tuple(ids))
        project._after_change()
        return len(ids)

    # --- O-022, O-023: formatarea ---------------------------------------------------------

    def apply_formatting(self, words: Sequence[WordData], **attrs: Any) -> None:
        """O-022, O-023 (`Ctrl+B`, `Ctrl+I`, `Ctrl+U`): font, marime, bold,
        italic, subliniere, exponent, indice, culoare; None scoate formatarea
        locala (ramane cea a stilului)."""
        unknown = set(attrs) - set(_FORMAT)
        if unknown:
            raise ValueError(f"atribute necunoscute: {sorted(unknown)}")
        if attrs.get("is_superscript") and attrs.get("is_subscript"):
            raise ValueError("un cuvant nu poate fi si exponent, si indice")
        values: dict[str, Any] = {}
        for key, value in attrs.items():
            if value is None:
                values[key] = None
            elif key == "font_size":
                if not 1 <= float(value) <= 1638:
                    raise ValueError("font_size: intre 1 si 1638")
                values[key] = float(value)
            elif key == "text_color":
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(value)):
                    raise ValueError("text_color: se asteapta #RRGGBB")
                values[key] = str(value).upper()
            elif key == "font_name":
                values[key] = str(value)
            else:
                values[key] = int(bool(value))
        if values.get("is_superscript"):
            values["is_subscript"] = 0
        if values.get("is_subscript"):
            values["is_superscript"] = 0
        ids = [self._id(w) for w in words]
        if not ids or not values:
            return
        project = self._project
        marks = ",".join("?" * len(ids))
        assignment = ", ".join(f"{k} = ?" for k in values)
        with project._history("format_text", {"words": len(ids)}), project._con:
            project._con.execute(f"UPDATE word SET {assignment} WHERE id IN ({marks})",
                                 (*values.values(), *ids))
        project._after_change()

    # --- O-035: stilurile -------------------------------------------------------------------

    def apply_style(self, blocks: Sequence[BlockData], style: Any) -> None:
        """O-035 (SPEC_05: O-027): blocurile primesc stilul (din StyleManager)."""
        ids = [b.id for b in blocks if b.id is not None]
        if not ids:
            return
        name = style.name if hasattr(style, "name") else str(style)
        project = self._project
        marks = ",".join("?" * len(ids))
        with project._history("apply_style", {"style": name}), project._con:
            project._con.execute(f"UPDATE text_block SET style_name = ? WHERE id IN ({marks})",
                                 (name, *ids))
        project._after_change()

    # --- O-070..O-072: redactarea -----------------------------------------------------------

    def redact_words(self, words: Sequence[WordData]) -> None:
        """O-070, O-071: cuvintele marcate, un singur pas de undo (`Ctrl+Z`
        anuleaza ultima redactare)."""
        self._update([self._id(w) for w in words], "is_redacted = 1", "redact_text")

    # --- O-027, O-060..O-063: tabelele in panoul Text ---------------------------------------

    def merge_cells(self, page: PageData, area: AreaData,
                    cells: Sequence[TableCellData]) -> None:
        """O-060: celulele se unesc, textul lor ramane, in ordine."""
        from app.core.layout.tables import TableAnalyzer

        self._restructure(page, area, TableAnalyzer().merge_cells(self._table(area), cells),
                          "merge_table_cells")

    def split_cells(self, page: PageData, area: AreaData, cell: TableCellData) -> None:
        """O-061: numai celulele unite anterior; textul ramane in prima celula."""
        from app.core.layout.tables import TableAnalyzer

        self._restructure(page, area, TableAnalyzer().split_cells(self._table(area), cell),
                          "split_table_cells")

    def merge_rows(self, page: PageData, area: AreaData, rows: Sequence[int]) -> None:
        """O-062."""
        from app.core.layout.tables import TableAnalyzer

        self._restructure(page, area, TableAnalyzer().merge_rows(self._table(area), rows),
                          "merge_table_rows")

    def clear_cell(self, cell: TableCellData) -> None:
        """O-063 (`Delete`): sterge continutul celulei, nu structura."""
        if cell.id is None:
            raise ValueError("celula nu e salvata in proiect")
        project = self._project
        with project._history("clear_cell", {"cell": cell.id}), project._con:
            project._con.execute("DELETE FROM text_block WHERE table_cell_id = ?", (cell.id,))
        project._after_change()

    @staticmethod
    def neighbor_cell(area: AreaData, cell: TableCellData, direction: str) -> TableCellData:
        """O-027: celula de langa, cu tastele cu sageti; la margine ramane pe loc."""
        table = TextEditor._table(area)
        moves = {"left": (0, -1), "right": (0, 1), "up": (-1, 0), "down": (1, 0)}
        if direction not in moves:
            raise ValueError(f"directie necunoscuta: {direction!r}")
        dr, dc = moves[direction]
        row = cell.row + (cell.row_span if dr > 0 else dr) if dr else cell.row
        col = cell.col + (cell.col_span if dc > 0 else dc) if dc else cell.col
        return table.cell_at(row, col) or cell

    @staticmethod
    def _table(area: AreaData) -> Any:
        if area.area_type is not AreaType.TABLE or area.table is None or not area.table.cells:
            raise ValueError("zona nu e un tabel cu structura")
        return area.table

    def _restructure(self, page: PageData, area: AreaData, table: Any, op: str) -> None:
        """Structura noua a tabelului, cu textul mutat in celulele noi dupa
        pozitie; starea paginii ramane (nu e o noua recunoastere)."""
        from app.core.layout.areas import AreaEditor
        from app.core.ocr.store import insert_blocks

        project = self._project
        old = [(c, list(c.blocks)) for c in self._table(area).cells]
        status = project.page(page.page_number).status
        with project._history(op, {"page": page.page_number}):
            AreaEditor(project).set_table(project.page(page.page_number), area, table)
            fresh = next(a for a in project.page(page.page_number).areas if a.id == area.id)
            con = project._con
            with con:
                start = 0
                for new in sorted(fresh.table.cells, key=lambda c: (c.row, c.col)):
                    blocks = [b for c, bs in sorted(old, key=lambda x: (x[0].row, x[0].col))
                              # coltul celulei vechi: la impartire textul ramane
                              # in prima celula noua (O-061)
                              if new.bbox.contains((c.bbox.x + 1, c.bbox.y + 1)) for b in bs]
                    insert_blocks(con, area.id, blocks, new.id, start=start)
                    start += len(blocks)
                con.execute("UPDATE page SET status = ? WHERE id = ?", (status.value, page.id))
        project._after_change()

    # --- O-080..O-083: copierea ---------------------------------------------------------------

    def area_text(self, page: PageData, area: AreaData) -> str:
        """O-081 (`Recognize and Copy Text`): textul zonei, fara export. Zona
        nerecunoscuta se recunoaste intai (O-108)."""
        from app.core.model import _area_blocks

        current = next(a for a in self._project.page(page.page_number).areas if a.id == area.id)
        if not any(True for _ in _area_blocks(current)) and current.area_type in (
                AreaType.TEXT, AreaType.RECOGNITION, AreaType.TABLE):
            from app.core.ocr.service import RecognitionService

            RecognitionService(self._project).recognize_area_again(page.page_number, area.id)
            current = next(a for a in self._project.page(page.page_number).areas
                           if a.id == area.id)
        return "\n".join(_block_text(b) for b in _area_blocks(current))

    def area_image(self, page: PageData, area: AreaData) -> bytes:
        """O-082 (`Copy area as image`, `Ctrl+Shift+C`): imaginea zonei, PNG."""
        from PIL import Image, ImageOps

        b = area.bbox
        with Image.open(page.image_path) as src:
            crop = ImageOps.exif_transpose(src).crop((b.x, b.y, b.right, b.bottom))
        out = io.BytesIO()
        crop.save(out, "PNG")
        return out.getvalue()

    def pages_text(self, numbers: Sequence[int]) -> str:
        """O-083: textul mai multor pagini, in ordine, separate printr-un
        sfarsit de pagina (\\f)."""
        return "\f".join(self._project.page(n).text for n in numbers)

    # --- ajutoare ------------------------------------------------------------------------

    @staticmethod
    def _id(word: WordData) -> int:
        if word.id is None:
            raise ValueError("cuvantul nu e salvat in proiect")
        return word.id

    def _update(self, ids: Sequence[int], assignment: str, op: str) -> None:
        if not ids:
            return
        project = self._project
        marks = ",".join("?" * len(ids))
        with project._history(op, {"words": len(ids)}), project._con:
            project._con.execute(f"UPDATE word SET {assignment} WHERE id IN ({marks})",
                                 tuple(ids))
        project._after_change()

    def _page_back_to_recognized(self, word_ids: Sequence[int]) -> None:
        """O pagina verificata in care se schimba textul nu mai e verificata."""
        marks = ",".join("?" * len(word_ids))
        self._project._con.execute(
            f"UPDATE page SET status = 'recognized' WHERE status = 'verified' AND id IN ("
            f"SELECT a.page_id FROM word w JOIN text_line l ON l.id = w.line_id"
            f" JOIN text_block b ON b.id = l.block_id JOIN area a ON a.id = b.area_id"
            f" WHERE w.id IN ({marks}))", tuple(word_ids))


_FORMAT = ("font_name", "font_size", "is_bold", "is_italic", "is_underline", "is_superscript",
           "is_subscript", "text_color")
"""O-022: formatarea locala a cuvantului (coloanele din SPEC_04 `word`)."""

REDACTION_DOT = "•"


def redacted_text(word: WordData) -> str:
    """O-072: cum apare un cuvant redactat in formatele fara culori (puncte);
    formatele cu culori deseneaza un dreptunghi negru peste el."""
    return REDACTION_DOT * len(word.text) if word.is_redacted else word.text


def _plain(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch))


def _lines(page: PageData) -> Iterator[list[WordData]]:
    from app.core.model import _area_blocks

    for area in page._ordered_areas():
        for block in _area_blocks(area):
            for line in block.lines:
                yield list(line.words)


def _block_text(block: BlockData) -> str:
    return "\n".join(" ".join(redacted_text(w) for w in ln.words) for ln in block.lines)


def cjk_variants(text: str, limit: int = 8) -> list[str]:
    """O-010: textul cu cate un caracter inlocuit de unul cu aspect asemanator."""
    out: list[str] = []
    for i, ch in enumerate(text):
        for group in CJK_LOOKALIKES:
            if ch in group:
                out += [text[:i] + other + text[i + 1:] for other in group if other != ch]
    return list(dict.fromkeys(out))[:limit]
