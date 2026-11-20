"""Zonele de pe o pagina: creare, editare, proprietati, ordine.

Implementeaza `AreaEditor` din SPEC_05 sectiunea 6, pasul 3a din
docs/plan/faza_3_pasi.md. Poligoanele (add/cut part) vin in 3b, sabloanele in
3c, tabelele in 3d.

Toate operatiile pe zone trec prin aici, ca regula suprapunerii sa fie
intr-un singur loc. Editorul lucreaza pe paginile unui `OcrProject`: fiecare
operatie se salveaza in tabela `area` si intra in istoricul de undo (J-041).

ID-urile sunt cele reale din SPEC_02; SPEC_05 foloseste numerotarea veche
(tabelul din docs/plan/faza_3_pasi.md).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from app.core.errors import (
    AreaOutOfBoundsError,
    AreaOverlapError,
    AreaTooSmallError,
    WrongAreaTypeError,
)
from app.core.model import (
    AreaData,
    AreaType,
    LanguageCode,
    Orientation,
    PageData,
    Point,
    Polygon,
    PrintType,
    Rect,
    TextFunction,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.core.project import OcrProject

BARCODE_AUTODETECT = "autodetect"
"""M-056: tipul implicit al unei zone de cod de bare."""

CJK_DIRECTIONS = ("horizontal", "vertical")
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
        poate sta sub celelalte).
        INCOMPLET, marcat: un poligon se verifica deocamdata dupa dreptunghiul
        care il cuprinde; calculul exact pe poligon vine in 3b.
        """
        kind = AreaType(area_type)
        points = [(int(x), int(y)) for x, y in polygon]
        bbox = bbox_of(points)
        pg = self._fresh(page)
        self._check_geometry(pg, bbox, kind, ignore_id=None)
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
        self._check_geometry(pg, bbox, current.area_type, ignore_id=current.id)
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
            self._check_geometry(pg, current.bbox, kind, ignore_id=current.id)
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

    def _check_geometry(self, page: PageData, bbox: Rect, kind: AreaType,
                        ignore_id: int | None) -> None:
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
            if other.bbox.intersects(bbox):
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
