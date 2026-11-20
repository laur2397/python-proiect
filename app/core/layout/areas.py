"""Zonele de pe o pagina: creare, editare, proprietati, ordine.

Implementeaza `AreaEditor` din SPEC_05 sectiunea 6: pasul 3a (zone,
proprietati, ordine), 3b (poligoane: add/cut part, manere, suprapunerea
exacta), 3c (sabloanele de zone) si 3d (salvarea tabelelor; analiza e in
tables.py) din docs/plan/faza_3_pasi.md.

Toate operatiile pe zone trec prin aici, ca regula suprapunerii sa fie
intr-un singur loc. Editorul lucreaza pe paginile unui `OcrProject`: fiecare
operatie se salveaza in tabela `area` si intra in istoricul de undo (J-041).

ID-urile sunt cele reale din SPEC_02; SPEC_05 foloseste numerotarea veche
(tabelul din docs/plan/faza_3_pasi.md).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.errors import (
    AreaOutOfBoundsError,
    AreaOverlapError,
    AreaTooSmallError,
    FileCorruptError,
    TemplateSizeMismatchError,
    UnsupportedFormatError,
    WrongAreaTypeError,
)
from app.core.layout.geometry import (
    ShapeError,
    add_rect,
    cut_rect,
    insert_vertex,
    polygons_overlap,
)
from app.core.layout.tables import TableAnalyzer
from app.core.model import (
    AreaData,
    AreaType,
    LanguageCode,
    Orientation,
    PageData,
    PageWarning,
    Point,
    Polygon,
    PrintType,
    Rect,
    TableCellData,
    TableData,
    TextFunction,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.core.project import OcrProject

BARCODE_AUTODETECT = "autodetect"
"""M-056: tipul implicit al unei zone de cod de bare."""

CJK_DIRECTIONS = ("horizontal", "vertical")
TEMPLATE_EXTENSION = ".blkx"
TEMPLATE_FORMAT = "doculens-area-template"
TEMPLATE_VERSION = 1
"""M-031: formatul propriu al sabloanelor (docs/plan/faza_3_pasi.md, decizia 5).
Fisierele .blk / .blkx facute de ABBYY au un format nepublicat."""
"""M-028, SPEC_04 area.cjk_direction."""

AREA_COLUMNS = (
    "id, page_id, order_index, area_type, bbox_x, bbox_y, bbox_w, bbox_h, polygon,"
    " is_polygon, language_codes, text_function, orientation, print_type, is_inverted,"
    " cjk_direction, barcode_type, barcode_value"
)


# --- conversia rand <-> AreaData ------------------------------------------------


def bbox_of(polygon: Polygon) -> Rect:
    """Dreptunghiul care cuprinde poligonul."""
    if len(polygon) < 3:
        raise ValueError("o zona are nevoie de cel putin trei puncte")
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return Rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def rect_polygon(rect: Rect) -> list[Point]:
    return [(rect.x, rect.y), (rect.right, rect.y), (rect.right, rect.bottom),
            (rect.x, rect.bottom)]


def area_from_row(row: Sequence[Any]) -> tuple[int, AreaData]:
    """(page_id, AreaData) dintr-un rand cu coloanele AREA_COLUMNS."""
    (aid, page_id, order, kind, x, y, w, h, polygon, _is_poly, langs, func, orient,
     print_type, inverted, cjk, barcode_type, barcode_value) = row
    return page_id, AreaData(
        id=aid,
        area_type=AreaType(kind),
        polygon=[tuple(p) for p in json.loads(polygon)],
        order_index=order,
        bbox=Rect(x, y, w, h),
        language_codes=None if langs is None else tuple(json.loads(langs)),
        text_function=None if func is None else TextFunction(func),
        orientation=Orientation(orient),
        print_type=PrintType(print_type),
        is_inverted=bool(inverted),
        cjk_direction=cjk,
        barcode_type=barcode_type,
        barcode_value=barcode_value,
    )


# --- AreaEditor ------------------------------------------------------------------


# SPEC_05 sect. 6. M-008, M-011, M-016..M-028, M-034, M-110
class AreaEditor:
    """Operatiile pe zonele paginilor unui proiect."""

    MIN_SIZE = 8
    """M-008: latimea si inaltimea minime (si CHECK-ul din SPEC_04)."""

    def __init__(self, project: OcrProject) -> None:
        self._project = project

    # --- creare si geometrie ---------------------------------------------------

    # M-008, M-016, M-034
    def create(self, page: PageData, polygon: Polygon, area_type: AreaType) -> AreaData:
        """Zona noua, ultima in ordine.

        Erori: `AreaTooSmallError` (sub 8x8 px), `AreaOutOfBoundsError` (iese din
        imagine), `AreaOverlapError` (intra peste alta zona; fundalul, M-110,
        poate sta sub celelalte). Suprapunerea se calculeaza exact pe poligon.
        """
        kind = AreaType(area_type)
        points = [(int(x), int(y)) for x, y in polygon]
        bbox = bbox_of(points)
        pg = self._fresh(page)
        self._check_geometry(pg, points, kind, ignore_id=None)
        with self._project._history("create_area", {"page": pg.page_number,
                                                    "type": kind.value}), self._con:
            (order,) = self._con.execute(
                "SELECT COALESCE(MAX(order_index) + 1, 0) FROM area WHERE page_id = ?",
                (pg.id,)).fetchone()
            cur = self._con.execute(
                "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y, bbox_w,"
                " bbox_h, polygon, is_polygon, barcode_type) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (pg.id, order, kind.value, bbox.x, bbox.y, bbox.w, bbox.h, json.dumps(points),
                 int(_is_polygon(points, bbox)),
                 BARCODE_AUTODETECT if kind is AreaType.BARCODE else None))
        return self._after(pg, int(cur.lastrowid))

    # M-016: nu poate iesi din imagine
    def move(self, page: PageData, area: AreaData, dx: int, dy: int) -> AreaData:
        polygon = [(x + dx, y + dy) for x, y in area.polygon]
        return self._reshape(page, area, polygon, "move_area")

    # M-011
    def resize(self, page: PageData, area: AreaData, new_polygon: Polygon) -> AreaData:
        return self._reshape(page, area, [(int(x), int(y)) for x, y in new_polygon],
                             "resize_area")

    def _reshape(self, page: PageData, area: AreaData, polygon: list[Point],
                 op: str) -> AreaData:
        pg = self._fresh(page)
        current = self._area(pg, area)
        bbox = bbox_of(polygon)
        self._check_geometry(pg, polygon, current.area_type, ignore_id=current.id)
        with self._project._history(op, {"page": pg.page_number}), self._con:
            self._con.execute(
                "UPDATE area SET bbox_x = ?, bbox_y = ?, bbox_w = ?, bbox_h = ?, polygon = ?,"
                " is_polygon = ? WHERE id = ?",
                (bbox.x, bbox.y, bbox.w, bbox.h, json.dumps(polygon),
                 int(_is_polygon(polygon, bbox)), current.id))
            self._con.execute("DELETE FROM text_block WHERE area_id = ?", (current.id,))
        return self._after(pg, current.id)

    # M-017: invalideaza textul paginii
    def change_type(self, page: PageData, area: AreaData, new_type: AreaType) -> AreaData:
        """Schimba tipul; textul zonei se sterge, iar proprietatile care nu se
        potrivesc noului tip (functia, tabelul, codul de bare) se golesc."""
        pg = self._fresh(page)
        current = self._area(pg, area)
        kind = AreaType(new_type)
        if kind is current.area_type:
            return current
        if kind is AreaType.BACKGROUND_PICTURE or current.area_type is AreaType.BACKGROUND_PICTURE:
            self._check_geometry(pg, list(current.polygon), kind, ignore_id=current.id)
        with self._project._history("change_area_type", {"page": pg.page_number,
                                                         "type": kind.value}), self._con:
            self._con.execute("DELETE FROM text_block WHERE area_id = ?", (current.id,))
            self._con.execute("DELETE FROM table_cell WHERE area_id = ?", (current.id,))
            self._con.execute("DELETE FROM table_separator WHERE area_id = ?", (current.id,))
            self._con.execute(
                "UPDATE area SET area_type = ?,"
                " text_function = CASE WHEN ? = 'text' THEN text_function END,"
                " barcode_type = CASE WHEN ? = 'barcode' THEN COALESCE(barcode_type, ?) END,"
                " barcode_value = NULL WHERE id = ?",
                (kind.value, kind.value, kind.value, BARCODE_AUTODETECT, current.id))
        return self._after(pg, current.id)

    # --- poligoane (3b) -------------------------------------------------------------

    _PART_TYPES = (AreaType.TEXT, AreaType.PICTURE, AreaType.BACKGROUND_PICTURE)
    """M-013, M-014: numai text, imagine si imagine de fundal."""

    # M-013: zona devine poligon
    def add_part(self, page: PageData, area: AreaData, rect: Rect) -> AreaData:
        """Adauga un dreptunghi la zona. Dreptunghiul trebuie sa atinga zona."""
        return self._part(page, area, rect, "add")

    # M-014: zona capata o scobitura
    def cut_part(self, page: PageData, area: AreaData, rect: Rect) -> AreaData:
        """Taie un dreptunghi din zona. Nu poate despica zona in doua si nu
        poate face o gaura in mijlocul ei."""
        return self._part(page, area, rect, "cut")

    def _part(self, page: PageData, area: AreaData, rect: Rect, op: str) -> AreaData:
        pg = self._fresh(page)
        current = self._area(pg, area)
        if current.area_type not in self._PART_TYPES:
            raise WrongAreaTypeError(
                "add/cut part numai pe zone de text, imagine si imagine de fundal",
                area_type=current.area_type.value, operation=f"{op}_part",
                allowed_types=[t.value for t in self._PART_TYPES])
        combine = add_rect if op == "add" else cut_rect
        try:
            polygon = combine(list(current.polygon), rect)
        except ShapeError as exc:
            raise ValueError(f"{op}_part: {exc}") from exc
        return self._reshape(pg, current, polygon, f"{op}_area_part")

    # M-012: Ctrl+Shift+clic pe chenar
    def add_handle(self, page: PageData, area: AreaData, point: Point) -> AreaData:
        """Un punct de control nou pe chenar, unde s-a dat clic. Zona isi
        pastreaza forma; manerul se poate trage apoi cu `resize`."""
        pg = self._fresh(page)
        current = self._area(pg, area)
        polygon = insert_vertex(list(current.polygon), point)
        if len(polygon) == len(current.polygon):
            return current
        with self._project._history("add_area_handle", {"page": pg.page_number}), self._con:
            self._con.execute("UPDATE area SET polygon = ?, is_polygon = 1 WHERE id = ?",
                              (json.dumps(polygon), current.id))
        return self._after(pg, current.id)

    # --- stergeri -----------------------------------------------------------------

    # M-018: pe o pagina recunoscuta se sterge si textul zonelor
    def delete(self, page: PageData, areas: Sequence[AreaData]) -> None:
        pg = self._fresh(page)
        ids = [self._area(pg, a).id for a in areas]
        if not ids:
            raise ValueError("nicio zona selectata")
        with self._project._history("delete_areas", {"page": pg.page_number,
                                                     "count": len(ids)}), self._con:
            self._con.executemany("DELETE FROM area WHERE id = ?", [(i,) for i in ids])
            self._compact_order(pg.id)
        self._project._after_change()

    # M-019: toate zonele si tot textul paginii
    def delete_areas_and_text(self, page: PageData) -> None:
        pg = self._fresh(page)
        with self._project._history("delete_areas_and_text",
                                    {"page": pg.page_number}), self._con:
            self._con.execute("DELETE FROM area WHERE page_id = ?", (pg.id,))
        self._project._after_change()

    # M-020: textul dispare, zonele raman
    def delete_text(self, page: PageData) -> None:
        pg = self._fresh(page)
        with self._project._history("delete_text", {"page": pg.page_number}), self._con:
            self._con.execute(
                "DELETE FROM text_block WHERE area_id IN (SELECT id FROM area WHERE page_id = ?)",
                (pg.id,))
            self._con.execute(
                "UPDATE page SET status = CASE WHEN status IN ('recognized','verified')"
                " THEN 'analyzed' ELSE status END, avg_confidence = NULL, uncertain_count = 0"
                " WHERE id = ?", (pg.id,))
        self._project._after_change()

    # --- proprietati ----------------------------------------------------------------

    # M-023, M-030: limba pe zona; numai pentru zone de acelasi tip
    def set_language(self, page: PageData, areas: Sequence[AreaData],
                     languages: Sequence[LanguageCode] | None) -> None:
        """None = limbile proiectului (M-023). Pentru mai multe zone deodata,
        toate trebuie sa fie de acelasi tip (M-030)."""
        pg = self._fresh(page)
        current = [self._area(pg, a) for a in areas]
        if not current:
            raise ValueError("nicio zona selectata")
        if len({a.area_type for a in current}) > 1:
            raise WrongAreaTypeError(
                "limba se seteaza doar pe zone de acelasi tip (M-030)",
                area_type=sorted({a.area_type.value for a in current}), operation="set_language")
        value = None
        if languages is not None:
            codes = list(languages)
            if not codes or not all(isinstance(c, str) and c.strip() for c in codes):
                raise ValueError("trebuie selectata cel putin o limba")
            value = json.dumps(codes)
        with self._project._history("set_area_language", {"page": pg.page_number}), self._con:
            self._con.executemany("UPDATE area SET language_codes = ? WHERE id = ?",
                                  [(value, a.id) for a in current])
        self._project._after_change()

    # M-024..M-028, M-056
    def set_properties(self, page: PageData, area: AreaData, **props: Any) -> AreaData:
        """Proprietatile din bara zonei: `text_function` (doar text, M-024),
        `orientation` (M-025), `print_type` (M-026), `is_inverted` (M-027),
        `cjk_direction` (M-028), `barcode_type` (doar cod de bare, M-056)."""
        pg = self._fresh(page)
        current = self._area(pg, area)
        allowed = {"text_function", "orientation", "print_type", "is_inverted",
                   "cjk_direction", "barcode_type"}
        unknown = set(props) - allowed
        if unknown:
            raise ValueError(f"proprietati necunoscute: {sorted(unknown)}")
        values: dict[str, Any] = {}
        if "text_function" in props:
            if current.area_type is not AreaType.TEXT and props["text_function"] is not None:
                raise WrongAreaTypeError("functia e doar pentru zonele de text (M-024)",
                                         area_type=current.area_type.value,
                                         operation="text_function", allowed_types=["text"])
            f = props["text_function"]
            values["text_function"] = None if f is None else TextFunction(f).value
        if "orientation" in props:
            values["orientation"] = Orientation(props["orientation"]).value
        if "print_type" in props:
            values["print_type"] = PrintType(props["print_type"]).value
        if "is_inverted" in props:
            if not isinstance(props["is_inverted"], bool):
                raise ValueError("is_inverted: se asteapta bool")
            values["is_inverted"] = int(props["is_inverted"])
        if "cjk_direction" in props:
            d = props["cjk_direction"]
            if d is not None and d not in CJK_DIRECTIONS:
                raise ValueError(f"cjk_direction: {d!r} nu e in {list(CJK_DIRECTIONS)}")
            values["cjk_direction"] = d
        if "barcode_type" in props:
            if current.area_type is not AreaType.BARCODE:
                raise WrongAreaTypeError("tipul de cod e doar pentru zonele de cod de bare",
                                         area_type=current.area_type.value,
                                         operation="barcode_type", allowed_types=["barcode"])
            b = props["barcode_type"]
            if not isinstance(b, str) or not b.strip():
                raise ValueError("barcode_type: se asteapta un nume de tip")
            values["barcode_type"] = b
        if not values:
            return current
        sets = ", ".join(f"{k} = ?" for k in values)
        with self._project._history("set_area_properties",
                                    {"page": pg.page_number, "properties": sorted(values)}), \
                self._con:
            self._con.execute(f"UPDATE area SET {sets} WHERE id = ?",
                              (*values.values(), current.id))
        return self._after(pg, current.id)

    # --- ordine -----------------------------------------------------------------------

    # M-021: clic pe zone in ordinea dorita
    def reorder(self, page: PageData, order: Sequence[int]) -> None:
        """`order` = id-urile zonelor in noua ordine; toate zonele paginii, o data."""
        pg = self._fresh(page)
        ids = [a.id for a in pg.areas]
        if sorted(order) != sorted(ids) or len(set(order)) != len(order):
            raise ValueError("noua ordine trebuie sa contina fiecare zona a paginii o data")
        with self._project._history("reorder_areas", {"page": pg.page_number}), self._con:
            self._set_order(pg.id, list(order))
        self._project._after_change()

    # M-022: de la stanga la dreapta, apoi de sus in jos (pe coloane; decizia 4)
    def renumber_automatically(self, page: PageData) -> None:
        """Coloanele de la stanga la dreapta; in fiecare, zonele de sus in jos.
        La fel indiferent de directia textului (T-M022: si in ebraica)."""
        pg = self._fresh(page)
        order = [a.id for a in column_order(pg.areas)]
        if order == [a.id for a in pg.areas]:
            return
        with self._project._history("renumber_areas", {"page": pg.page_number}), self._con:
            self._set_order(pg.id, order)
        self._project._after_change()

    # --- sabloane (3c) ----------------------------------------------------------------

    # M-031
    def save_template(self, page: PageData, path: Path, name: str) -> None:
        """Scrie zonele paginii intr-un sablon `.blkx` si il pastreaza si in
        biblioteca din app.db, sub `name` (un nume existent se inlocuieste)."""
        pg = self._fresh(page)
        if not name.strip():
            raise ValueError("sablonul are nevoie de un nume")
        path = Path(path)
        if path.suffix.lower() != TEMPLATE_EXTENSION:
            raise ValueError(f"sablonul se salveaza cu extensia {TEMPLATE_EXTENSION}")
        if not pg.areas:
            raise ValueError("pagina nu are zone de salvat")
        payload = {
            "format": TEMPLATE_FORMAT, "version": TEMPLATE_VERSION, "name": name,
            "source": {"width": pg.width_px, "height": pg.height_px,
                       "dpi_x": pg.dpi_x, "dpi_y": pg.dpi_y},
            "areas": [_template_item(a) for a in pg.areas],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        self._store_in_library(payload)

    def _store_in_library(self, payload: dict[str, Any]) -> None:
        con = self._project._ctx.app_db
        src = payload["source"]
        with con:
            con.execute("DELETE FROM area_template WHERE name = ?", (payload["name"],))
            cur = con.execute(
                "INSERT INTO area_template (name, source_width, source_height, source_dpi)"
                " VALUES (?, ?, ?, ?)",
                (payload["name"], src["width"], src["height"], src["dpi_x"]))
            con.executemany(
                "INSERT INTO area_template_item (template_id, area_type, polygon, order_index,"
                " properties) VALUES (?, ?, ?, ?, ?)",
                [(cur.lastrowid, it["type"], json.dumps(it["polygon"]), i,
                  json.dumps(it["properties"])) for i, it in enumerate(payload["areas"])])

    # Adaugare fata de SPEC_05: biblioteca din app.db (area_template).
    def library_templates(self) -> list[str]:
        """Numele sabloanelor din biblioteca."""
        return [r[0] for r in self._project._ctx.app_db.execute(
            "SELECT name FROM area_template ORDER BY name")]

    def load_library_template(self, pages: Sequence[PageData], name: str, *,
                              scale: bool = False) -> None:
        con = self._project._ctx.app_db
        row = con.execute("SELECT id, source_width, source_height, source_dpi"
                          " FROM area_template WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise ValueError(f"sablonul {name!r} nu e in biblioteca")
        tid, w, h, dpi = row
        items = [{"type": t, "polygon": json.loads(poly), "properties": json.loads(props or "{}")}
                 for t, poly, props in con.execute(
                     "SELECT area_type, polygon, properties FROM area_template_item"
                     " WHERE template_id = ? ORDER BY order_index", (tid,))]
        self._apply_template(pages, {"name": name, "source": {
            "width": w, "height": h, "dpi_x": dpi, "dpi_y": dpi}, "areas": items}, scale)

    # M-032
    def load_template(self, pages: Sequence[PageData], path: Path, *,
                      scale: bool = False) -> None:
        """Inlocuieste zonele paginilor cu cele din sablon („Apply to”: paginile
        selectate sau toate, dupa ce primeste apelantul).

        Daca o pagina are alta dimensiune sau rezolutie decat pagina din care
        s-a facut sablonul si `scale` e False: `TemplateSizeMismatchError`, fara
        sa se schimbe nimic. Cu `scale=True` zonele se scaleaza pe fiecare axa.
        Erori de fisier: `UnsupportedFormatError` (.blk / format ABBYY),
        `FileCorruptError` (fisier stricat).
        """
        path = Path(path)
        if path.suffix.lower() != TEMPLATE_EXTENSION:
            raise UnsupportedFormatError("format de sablon nesuportat", path=str(path),
                                         extension=path.suffix.lower(), reason="unsupported")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnsupportedFormatError(
                "sablonul nu e in formatul DocuLens (poate e facut de ABBYY)",
                path=str(path), extension=TEMPLATE_EXTENSION, reason="unsupported") from exc
        if not isinstance(payload, dict) or payload.get("format") != TEMPLATE_FORMAT:
            raise UnsupportedFormatError("sablonul nu e in formatul DocuLens", path=str(path),
                                         extension=TEMPLATE_EXTENSION, reason="unsupported")
        try:
            src = payload["source"]
            int(src["width"]), int(src["height"]), int(src["dpi_x"])
            if not isinstance(payload["areas"], list):
                raise TypeError("areas nu e o lista")
            for item in payload["areas"]:
                AreaType(item["type"])
                [(int(x), int(y)) for x, y in item["polygon"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise FileCorruptError("sablonul e incomplet", path=str(path),
                                   detail=str(exc)) from exc
        self._apply_template(pages, payload, scale)

    def _apply_template(self, pages: Sequence[PageData], payload: dict[str, Any],
                        scale: bool) -> None:
        src = payload["source"]
        sw, sh = int(src["width"]), int(src["height"])
        sdx, sdy = int(src["dpi_x"]), int(src.get("dpi_y", src["dpi_x"]))
        targets = [self._fresh(p) for p in pages]
        if not targets:
            raise ValueError("nicio pagina selectata")
        for pg in targets:  # intai verificarea, pe toate paginile
            same = (pg.width_px, pg.height_px, pg.dpi_x, pg.dpi_y) == (sw, sh, sdx, sdy)
            if not same and not scale:
                raise TemplateSizeMismatchError(
                    "sablonul vine de la o pagina de alta dimensiune sau rezolutie",
                    page=pg.page_number, template_size=[sw, sh], page_size=[pg.width_px,
                                                                           pg.height_px],
                    template_dpi=[sdx, sdy], page_dpi=[pg.dpi_x, pg.dpi_y])
        prepared = []
        for pg in targets:
            fx, fy = pg.width_px / sw, pg.height_px / sh
            rows = []
            for i, item in enumerate(payload["areas"]):
                kind = AreaType(item["type"])
                poly = [(min(pg.width_px, max(0, round(x * fx))),
                         min(pg.height_px, max(0, round(y * fy)))) for x, y in item["polygon"]]
                box = bbox_of(poly)
                if box.w < self.MIN_SIZE or box.h < self.MIN_SIZE:
                    raise AreaTooSmallError("o zona din sablon devine prea mica la scalare",
                                            w=box.w, h=box.h, min_size=self.MIN_SIZE)
                props = _template_properties(item.get("properties", {}), kind)
                rows.append((pg.id, i, kind.value, box.x, box.y, box.w, box.h,
                             json.dumps(poly), int(_is_polygon(poly, box)), *props))
            prepared.append((pg.id, rows))
        name = payload.get("name", "")
        with self._project._history("load_area_template",
                                    {"template": name, "pages": [p.page_number for p in targets]}), \
                self._con:
            for page_id, rows in prepared:
                self._con.execute("DELETE FROM area WHERE page_id = ?", (page_id,))
                self._con.executemany(
                    "INSERT INTO area (page_id, order_index, area_type, bbox_x, bbox_y, bbox_w,"
                    " bbox_h, polygon, is_polygon, language_codes, text_function, orientation,"
                    " print_type, is_inverted, cjk_direction, barcode_type)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        self._project._after_change()

    # --- tabele (3d) -------------------------------------------------------------------

    # M-040, M-041, M-049
    def analyze_table(self, page: PageData, area: AreaData) -> AreaData:
        """`Analyze Table Structure`: numai pe zone de tip tabel (M-040).
        Structura nedetectabila: o celula si un avertisment pe pagina (M-049)."""
        pg = self._fresh(page)
        current = self._area(pg, area)
        self._require_table(current, "analyze_table")
        before = len(pg.warnings)
        table = TableAnalyzer().analyze_structure(current, pg)
        new_warnings = pg.warnings[before:]
        return self._store_table(pg, current, table, "analyze_table", new_warnings)

    # M-042..M-048: rezultatul operatiilor TableAnalyzer, salvat
    def set_table(self, page: PageData, area: AreaData, table: TableData) -> AreaData:
        """Salveaza structura tabelului zonei (dupa separatoare, uniri, M-048).
        Adaugare fata de SPEC_05: operatiile TableAnalyzer sunt pure."""
        pg = self._fresh(page)
        current = self._area(pg, area)
        self._require_table(current, "set_table")
        return self._store_table(pg, current, table, "edit_table", [])

    def _require_table(self, area: AreaData, operation: str) -> None:
        if area.area_type is not AreaType.TABLE:
            raise WrongAreaTypeError("operatia e doar pentru zonele de tabel (M-040)",
                                     area_type=area.area_type.value, operation=operation,
                                     allowed_types=["table"])

    def _store_table(self, page: PageData, area: AreaData, table: TableData, op: str,
                     warnings: Sequence[PageWarning]) -> AreaData:
        with self._project._history(op, {"page": page.page_number}), self._con:
            self._con.execute("DELETE FROM text_block WHERE area_id = ?", (area.id,))
            self._con.execute("DELETE FROM table_cell WHERE area_id = ?", (area.id,))
            self._con.execute("DELETE FROM table_separator WHERE area_id = ?", (area.id,))
            self._con.executemany(
                "INSERT INTO table_cell (area_id, row_index, col_index, row_span, col_span,"
                " bbox_x, bbox_y, bbox_w, bbox_h, as_picture, is_header)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(area.id, c.row, c.col, c.row_span, c.col_span, c.bbox.x, c.bbox.y,
                  c.bbox.w, c.bbox.h, int(c.as_picture), int(c.is_header))
                 for c in table.cells])
            self._con.executemany(
                "INSERT INTO table_separator (area_id, axis, position_px, is_manual)"
                " VALUES (?, ?, ?, ?)",
                [(area.id, axis, pos, int(op == "edit_table"))
                 for axis, positions in (("horizontal", table.h_separators),
                                         ("vertical", table.v_separators))
                 for pos in positions])
            self._con.executemany(
                "INSERT INTO page_warning (page_id, severity, code, message) VALUES (?,?,?,?)",
                [(page.id, w.severity, w.code, w.message_key) for w in warnings])
            # M-033: dupa o schimbare de structura, recunoasterea se reia
            self._con.execute(
                "UPDATE page SET status = CASE WHEN status IN ('recognized','verified')"
                " THEN 'analyzed' ELSE status END WHERE id = ?", (page.id,))
        return self._after(page, area.id)

    # --- ajutoare ---------------------------------------------------------------------

    @property
    def _con(self) -> Any:
        return self._project._con

    def _fresh(self, page: PageData) -> PageData:
        """Pagina, citita din nou din proiect (dupa id, nu dupa obiectul primit)."""
        self._project._require_open()
        for pg in self._project.pages:
            if pg.id == page.id:
                return pg
        raise ValueError(f"pagina {page.page_number} nu e in proiect")

    def _area(self, page: PageData, area: AreaData) -> AreaData:
        for a in page.areas:
            if a.id == area.id:
                return a
        raise ValueError(f"zona {area.id} nu e pe pagina {page.page_number}")

    def _after(self, page: PageData, area_id: int) -> AreaData:
        self._project._after_change()
        return self._area(self._fresh(page), AreaData(area_id, AreaType.TEXT, [], 0))

    def _check_geometry(self, page: PageData, polygon: list[Point], kind: AreaType,
                        ignore_id: int | None) -> None:
        bbox = bbox_of(polygon)
        if bbox.w < self.MIN_SIZE or bbox.h < self.MIN_SIZE:
            raise AreaTooSmallError("zona e prea mica", w=bbox.w, h=bbox.h,
                                    min_size=self.MIN_SIZE)
        if bbox.x < 0 or bbox.y < 0 or bbox.right > page.width_px or bbox.bottom > page.height_px:
            raise AreaOutOfBoundsError("zona iese din imagine", x=bbox.x, y=bbox.y, w=bbox.w,
                                       h=bbox.h, page_w=page.width_px, page_h=page.height_px)
        if kind is AreaType.BACKGROUND_PICTURE:
            return  # M-110: fundalul poate sta sub celelalte zone
        for other in page.areas:
            if other.id == ignore_id or other.area_type is AreaType.BACKGROUND_PICTURE:
                continue
            if polygons_overlap(polygon, list(other.polygon)):
                raise AreaOverlapError("zonele nu se pot suprapune (M-034)",
                                       area_id=ignore_id, other_id=other.id)

    def _set_order(self, page_id: int, ids: list[int]) -> None:
        offset = 1_000_000
        self._con.execute("UPDATE area SET order_index = order_index + ? WHERE page_id = ?",
                          (offset, page_id))
        self._con.executemany("UPDATE area SET order_index = ? WHERE id = ?",
                              [(i, aid) for i, aid in enumerate(ids)])

    def _compact_order(self, page_id: int) -> None:
        ids = [r[0] for r in self._con.execute(
            "SELECT id FROM area WHERE page_id = ? ORDER BY order_index", (page_id,))]
        self._set_order(page_id, ids)


def load_tables(con: Any) -> dict[int, TableData]:
    """Tabelele tuturor zonelor din proiect, dupa id-ul zonei."""
    seps: dict[int, tuple[list[int], list[int]]] = {}
    for area_id, axis, pos in con.execute(
        "SELECT area_id, axis, position_px FROM table_separator ORDER BY position_px"
    ):
        h, v = seps.setdefault(area_id, ([], []))
        (h if axis == "horizontal" else v).append(pos)
    tables: dict[int, TableData] = {}
    for (cid, area_id, r, c, rs, cs, x, y, w, h, pic, head) in con.execute(
        "SELECT id, area_id, row_index, col_index, row_span, col_span, bbox_x, bbox_y,"
        " bbox_w, bbox_h, as_picture, is_header FROM table_cell ORDER BY row_index, col_index"
    ):
        hs, vs = seps.get(area_id, ([], []))
        table = tables.setdefault(area_id, TableData(rows=len(hs) + 1, cols=len(vs) + 1,
                                                     h_separators=list(hs),
                                                     v_separators=list(vs)))
        table.cells.append(TableCellData(cid, r, c, rs, cs, Rect(x, y, w, h), bool(pic),
                                         bool(head)))
    return tables


def _template_item(area: AreaData) -> dict[str, Any]:
    return {
        "type": area.area_type.value,
        "polygon": [list(p) for p in area.polygon],
        "properties": {
            "language_codes": None if area.language_codes is None else list(area.language_codes),
            "text_function": None if area.text_function is None else area.text_function.value,
            "orientation": area.orientation.value,
            "print_type": area.print_type.value,
            "is_inverted": area.is_inverted,
            "cjk_direction": area.cjk_direction,
            "barcode_type": area.barcode_type,
        },
    }


def _template_properties(props: dict[str, Any], kind: AreaType) -> tuple[Any, ...]:
    """Valorile coloanelor (language_codes ... barcode_type), validate."""
    langs = props.get("language_codes")
    func = props.get("text_function") if kind is AreaType.TEXT else None
    barcode = props.get("barcode_type") or (BARCODE_AUTODETECT if kind is AreaType.BARCODE
                                            else None)
    cjk = props.get("cjk_direction")
    if cjk is not None and cjk not in CJK_DIRECTIONS:
        cjk = None
    return (
        None if langs is None else json.dumps(list(langs)),
        None if func is None else TextFunction(func).value,
        Orientation(props.get("orientation", "auto")).value,
        PrintType(props.get("print_type", "auto")).value,
        int(bool(props.get("is_inverted", False))),
        cjk,
        barcode if kind is AreaType.BARCODE else None,
    )


def _is_polygon(points: Sequence[Point], bbox: Rect) -> bool:
    return set(points) != set(rect_polygon(bbox))


WIDE_AREA_FACTOR = 1.5
"""O zona mai lata de 1,5 ori decat latimea tipica (mediana) e „lata”: un titlu
peste mai multe coloane. Nu are voie sa lipeasca coloanele intre ele."""


# M-022
def column_order(areas: Sequence[AreaData]) -> list[AreaData]:
    """Ordinea pe coloane: zonele care se suprapun pe orizontala formeaza o
    coloana; coloanele de la stanga la dreapta, zonele din coloana de sus in jos.

    Coloanele se formeaza intai din zonele obisnuite. O zona lata (titlu peste
    doua coloane) intra apoi in prima coloana, de la stanga, pe care o atinge."""
    if not areas:
        return []
    widths = sorted(a.bbox.w for a in areas)
    typical = widths[len(widths) // 2]
    narrow = [a for a in areas if a.bbox.w <= WIDE_AREA_FACTOR * typical]
    wide = [a for a in areas if a.bbox.w > WIDE_AREA_FACTOR * typical]
    columns: list[list[Any]] = []  # [stanga, dreapta, zone]
    for area in sorted(narrow, key=lambda a: (a.bbox.x, a.bbox.y)):
        b = area.bbox
        for col in columns:
            overlap = min(col[1], b.right) - max(col[0], b.x)
            if overlap > 0.5 * min(col[1] - col[0], b.w):
                col[2].append(area)
                col[0], col[1] = min(col[0], b.x), max(col[1], b.right)
                break
        else:
            columns.append([b.x, b.right, [area]])
    columns.sort(key=lambda c: c[0])
    for area in wide:
        b = area.bbox
        target = next((c for c in columns if min(c[1], b.right) > max(c[0], b.x)), None)
        if target is None:
            columns.append([b.x, b.right, [area]])
            columns.sort(key=lambda c: c[0])
        else:
            target[2].append(area)
    return [a for col in columns for a in sorted(col[2], key=lambda a: (a.bbox.y, a.bbox.x))]
