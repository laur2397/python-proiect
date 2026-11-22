"""Adnotarile si comentariile din PDF Editor (faza 7, pasul 7.4a):
D-001…D-044.

[DECIZIE AUTONOMA] (faza_7_pasi.md, decizia 2) Adnotarile sunt cele standard
din PDF, cu aspect (/AP) generat aici, ca documentul sa arate la fel in orice
cititor: nota `/Text`, marcajele `/Highlight` `/Underline` `/StrikeOut`,
`/Caret`, `/Ink`, `/Line` (si sageata, cu /LE), `/Square`, `/Circle`,
`/Polygon` (si norul, cu /BE), `/PolyLine`, `/FreeText`. Raspunsurile sunt
adnotari `/Text` cu `/IRT` (D-026), statusurile adnotari de stare cu
`/StateModel /Review` (D-031, istoricul ramane in fisier), bifa personala
`/StateModel /Marked` (D-030).

Identificatorul unei adnotari (`AnnotationData.id`) e numarul obiectului ei in
documentul deschis. Ramane acelasi cat timp documentul e deschis si
nesalvat; dupa o salvare, interfata reciteste lista.

Coordonatele: puncte, originea sus-stanga a MediaBox-ului (ca in `text.py`).
Geometria, pe tip: marcaje `{"rects": [Rect...]}`; nota si `Insert Text`
`{"point": (x, y)}`; `Ink` `{"paths": [[(x, y)...]...]}`; linie, sageata,
poligon, nor, polilinie `{"points": [(x, y)...]}`; dreptunghi, oval si caseta
de text folosesc `bbox` (caseta: `{"font_size": 12, "text_color": "#000000",
"text_block": bool}`).
"""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pikepdf

from app.core.errors import NoTextFoundError
from app.core.model import AnnotationData, AnnotationType, Rect, ReviewStatus
from app.core.pdf.markup import TEXT_MARKUPS, _appearance, pdf_date, rgb
from app.core.pdf.text import from_pdf_rect, page_geometry, to_pdf_rect

if TYPE_CHECKING:
    from app.core.pdf.document import PdfDocument

SUBTYPES: dict[AnnotationType, str] = {
    AnnotationType.NOTE: "/Text",
    **TEXT_MARKUPS,
    AnnotationType.INSERT_TEXT: "/Caret",
    AnnotationType.INK: "/Ink",
    AnnotationType.LINE: "/Line",
    AnnotationType.ARROW: "/Line",
    AnnotationType.RECTANGLE: "/Square",
    AnnotationType.OVAL: "/Circle",
    AnnotationType.POLYGON: "/Polygon",
    AnnotationType.CLOUD: "/Polygon",
    AnnotationType.POLYLINE: "/PolyLine",
    AnnotationType.TEXT_BOX: "/FreeText",
    AnnotationType.STAMP: "/Stamp",
    AnnotationType.REDACTION: "/Redact",
}
"""Tipul din SPEC_05 → subtipul adnotarii PDF."""

CREATABLE = frozenset(SUBTYPES) - {AnnotationType.STAMP, AnnotationType.REDACTION}
"""Ce se creeaza aici. Stampilele vin in 7.4b; redactarea e in `security.py`."""

REVIEW_STATES = {
    ReviewStatus.ACCEPTED: "Accepted",
    ReviewStatus.REJECTED: "Rejected",
    ReviewStatus.CANCELLED: "Cancelled",
    ReviewStatus.COMPLETED: "Completed",
}
"""D-031: statusurile, cu numele din standardul PDF."""

MIN_LINE_WIDTH, MAX_LINE_WIDTH = 0.5, 12.0
"""D-016: grosimea liniei, in puncte."""

NOTE_SIZE = 20.0
"""Latura iconului unei note pe pagina, in puncte."""

DEFAULT_FONT_SIZE = 12.0

NOTE_COLOR = "#FFD84D"
SHAPE_COLOR = "#D92D20"
"""Culorile implicite cand adnotarea nu are culoare; interfata trimite de obicei
culoarea aleasa in bara de unelte (D-018), iar marcajele pe cea din setari (C-010)."""


def default_color(kind: AnnotationType) -> str:
    from app.core.settings import MARKUP_COLORS

    if kind in TEXT_MARKUPS:
        return MARKUP_COLORS[kind.value]
    if kind is AnnotationType.NOTE:
        return NOTE_COLOR
    if kind in (AnnotationType.TEXT_BOX, AnnotationType.INSERT_TEXT):
        return "#000000"
    return SHAPE_COLOR
_SKIPPED = {"/Link", "/Widget", "/Popup"}
_DA = re.compile(r"([\d.]+)\s+Tf.*?([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg", re.DOTALL)


# --- conversii ------------------------------------------------------------------------


def iso_date(value: Any) -> str:
    """O data PDF (D:AAAALLZZOOMMSS, cu fus orar optional) → ISO 8601 UTC;
    sir gol daca lipseste sau nu se poate citi."""
    from datetime import timedelta

    text = str(value or "")
    match = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?"
                     r"(?:([Zz+-])(\d{2})?'?(\d{2})?'?)?", text)
    if not match:
        return ""
    parts = [int(p) if p else d for p, d in zip(match.groups()[:6], (0, 1, 1, 0, 0, 0),
                                                  strict=True)]
    try:
        moment = datetime(*parts, tzinfo=UTC)  # type: ignore[misc]
    except ValueError:
        return ""
    sign, hours, minutes = match.group(7), match.group(8), match.group(9)
    if sign in ("+", "-"):
        offset = timedelta(hours=int(hours or 0), minutes=int(minutes or 0))
        moment = moment - offset if sign == "+" else moment + offset
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _color_hex(value: Any) -> str | None:
    try:
        parts = [float(v) for v in value]
    except (TypeError, ValueError):
        return None
    if len(parts) == 1:
        parts = parts * 3
    if len(parts) != 3:
        return None
    return "#" + "".join(f"{max(0, min(255, round(p * 255))):02X}" for p in parts)


def _num(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".") or "0"


def _point(geometry: tuple[float, float, float], p: Sequence[float]) -> tuple[float, float]:
    left, bottom, height = geometry
    return left + float(p[0]), bottom + height - float(p[1])


def _unpoint(geometry: tuple[float, float, float], x: float, y: float) -> tuple[float, float]:
    left, bottom, height = geometry
    return x - left, bottom + height - y


def _bounds(points: Iterable[tuple[float, float]], pad: float) -> list[float]:
    pts = list(points)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]


# --- citirea --------------------------------------------------------------------------


def _annots(pdf: pikepdf.Pdf) -> list[tuple[int, pikepdf.Object]]:
    """(pagina, adnotare) pentru toate adnotarile; cele directe devin indirecte,
    ca sa aiba un numar de obiect stabil."""
    out: list[tuple[int, pikepdf.Object]] = []
    for number, page in enumerate(pdf.pages, start=1):
        annots = page.obj.get("/Annots")
        if annots is None:
            continue
        for i, annot in enumerate(list(annots)):
            if not isinstance(annot, pikepdf.Dictionary):
                continue
            if not annot.is_indirect:
                annot = pdf.make_indirect(annot)
                annots[i] = annot
            out.append((number, annot))
    return out


def _is_state(annot: pikepdf.Object) -> bool:
    return "/IRT" in annot and ("/State" in annot or "/StateModel" in annot)


def _is_reply(annot: pikepdf.Object) -> bool:
    return "/IRT" in annot and not _is_state(annot) and \
        str(annot.get("/RT", "/R")) == "/R"


def _kind(annot: pikepdf.Object) -> AnnotationType | None:
    subtype = str(annot.get("/Subtype", ""))
    if subtype == "/Line":
        ends = annot.get("/LE")
        has_arrow = ends is not None and any(str(e) != "/None" for e in ends)
        return AnnotationType.ARROW if has_arrow else AnnotationType.LINE
    if subtype == "/Polygon":
        border = annot.get("/BE")
        cloudy = border is not None and str(border.get("/S", "")) == "/C"
        return AnnotationType.CLOUD if cloudy else AnnotationType.POLYGON
    for kind, name in SUBTYPES.items():
        if name == subtype and kind not in (AnnotationType.ARROW, AnnotationType.CLOUD):
            return kind
    return None


def _id(annot: pikepdf.Object) -> int:
    return int(annot.objgen[0])


def _geometry(kind: AnnotationType, annot: pikepdf.Object,
              geo: tuple[float, float, float]) -> dict[str, Any]:
    def pairs(values: Any) -> list[tuple[float, float]]:
        nums = [float(v) for v in values]
        return [_unpoint(geo, nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]

    if kind in TEXT_MARKUPS and "/QuadPoints" in annot:
        q = [float(v) for v in annot.QuadPoints]
        rects = []
        for i in range(0, len(q) - 7, 8):
            xs, ys = q[i:i + 8:2], q[i + 1:i + 8:2]
            rects.append(from_pdf_rect(geo, (min(xs), min(ys), max(xs), max(ys))))
        return {"rects": rects}
    if kind is AnnotationType.INK and "/InkList" in annot:
        return {"paths": [pairs(path) for path in annot.InkList]}
    if kind in (AnnotationType.LINE, AnnotationType.ARROW) and "/L" in annot:
        return {"points": pairs(annot.L)}
    if kind in (AnnotationType.POLYGON, AnnotationType.CLOUD, AnnotationType.POLYLINE) \
            and "/Vertices" in annot:
        return {"points": pairs(annot.Vertices)}
    if kind in (AnnotationType.NOTE, AnnotationType.INSERT_TEXT):
        box = from_pdf_rect(geo, annot.Rect)
        return {"point": (box.x, box.y)} if kind is AnnotationType.NOTE else \
            {"point": (box.x + box.w / 2, box.y + box.h * 0.8)}
    if kind is AnnotationType.TEXT_BOX:
        match = _DA.search(str(annot.get("/DA", "")))
        size = float(match.group(1)) if match else DEFAULT_FONT_SIZE
        color = _color_hex([match.group(i) for i in (2, 3, 4)]) if match else "#000000"
        block = str(annot.get("/IT", "")) == "/FreeTextTypeWriter"
        return {"font_size": size, "text_color": color, "text_block": block}
    if kind is AnnotationType.STAMP:
        return {"stamp": str(annot.get("/Name", "")).lstrip("/")}
    return {}


def _states(children: Sequence[pikepdf.Object], model: str) -> list[pikepdf.Object]:
    found = [c for c in children if _is_state(c) and str(c.get("/StateModel", "")) == model]
    return sorted(found, key=lambda c: (str(c.get("/M", c.get("/CreationDate", ""))),
                                        _id(c)))


def _to_data(number: int, annot: pikepdf.Object, kind: AnnotationType,
             geo: tuple[float, float, float],
             children: Mapping[tuple[int, int], list[pikepdf.Object]]) -> AnnotationData:
    own = children.get(annot.objgen, [])
    review = _states(own, "Review")
    marked = _states(own, "Marked")
    status = None
    if review:
        state = str(review[-1].get("/State", ""))
        status = next((s for s, name in REVIEW_STATES.items() if name == state), None)
    border = annot.get("/BS")
    width = float(border.get("/W")) if border is not None and "/W" in border else None
    data = AnnotationData(
        id=_id(annot), annot_type=kind, page_number=number,
        geometry=_geometry(kind, annot, geo),
        bbox=from_pdf_rect(geo, annot.Rect) if "/Rect" in annot else Rect(0, 0, 0, 0),
        author=str(annot.T) if "/T" in annot else None,
        subject=str(annot.Subj) if "/Subj" in annot else None,
        content=str(annot.Contents) if "/Contents" in annot else None,
        color=_color_hex(annot.get("/C")), fill_color=_color_hex(annot.get("/IC")),
        opacity=float(annot.get("/CA", 1.0)), line_width=width,
        review_status=status,
        is_checked=bool(marked) and str(marked[-1].get("/State", "")) == "Marked",
        parent_id=_id(annot.IRT) if "/IRT" in annot and annot.IRT.is_indirect else None,
        created_at=iso_date(annot.get("/CreationDate", annot.get("/M"))),
        modified_at=iso_date(annot.get("/M", annot.get("/CreationDate"))),
    )
    data.replies = [_to_data(number, r, AnnotationType.NOTE, geo, children)
                    for r in sorted(own, key=lambda c: (str(c.get("/CreationDate", "")),
                                                        _id(c)))
                    if _is_reply(r)]
    return data


def _children(entries: Sequence[tuple[int, pikepdf.Object]]
              ) -> dict[tuple[int, int], list[pikepdf.Object]]:
    out: dict[tuple[int, int], list[pikepdf.Object]] = {}
    for _number, annot in entries:
        parent = annot.get("/IRT")
        if parent is not None and parent.is_indirect:
            out.setdefault(parent.objgen, []).append(annot)
    return out


# D-024
def list_annotations(document: PdfDocument, page: int | None = None) -> list[AnnotationData]:
    """Adnotarile de nivel unu (raspunsurile si starile stau in `replies`,
    `review_status`, `is_checked`), in ordinea paginilor. Linkurile, campurile
    de formular si ferestrele popup nu sunt comentarii."""
    pdf = document._pike()
    entries = _annots(pdf)
    children = _children(entries)
    out: list[AnnotationData] = []
    for number, annot in entries:
        if page is not None and number != page:
            continue
        if str(annot.get("/Subtype", "")) in _SKIPPED or "/IRT" in annot:
            continue
        kind = _kind(annot)
        if kind is None:
            continue
        out.append(_to_data(number, annot, kind, page_geometry(pdf.pages[number - 1]),
                            children))
    return out


def _find(document: PdfDocument, annot_id: int) -> tuple[int, pikepdf.Object]:
    for number, annot in _annots(document._pike()):
        if _id(annot) == annot_id:
            return number, annot
    raise KeyError(annot_id)


# D-032
def status_history(document: PdfDocument, annot_id: int
                   ) -> list[tuple[ReviewStatus | None, str | None, str]]:
    """D-032: istoricul statusurilor (status, autor, data ISO), cel mai vechi primul."""
    _number, annot = _find(document, annot_id)
    own = _children(_annots(document._pike())).get(annot.objgen, [])
    history = []
    for state in _states(own, "Review"):
        name = str(state.get("/State", ""))
        status = next((s for s, n in REVIEW_STATES.items() if n == name), None)
        history.append((status, str(state.T) if "/T" in state else None,
                        iso_date(state.get("/M", state.get("/CreationDate")))))
    return history


# --- scrierea -------------------------------------------------------------------------


def _validate(data: AnnotationData) -> None:
    if data.line_width is not None and not MIN_LINE_WIDTH <= data.line_width <= MAX_LINE_WIDTH:
        raise ValueError(f"grosimea liniei e intre {MIN_LINE_WIDTH} si {MAX_LINE_WIDTH} pt"
                         " (D-016)")
    if not 0 <= data.opacity <= 1:
        raise ValueError("opacitatea e intre 0 si 1")
    for color in (data.color, data.fill_color):
        if color is not None:
            rgb(color)


def _form(pdf: pikepdf.Pdf, bbox: Sequence[float], ops: str, opacity: float,
          resources: pikepdf.Dictionary | None = None) -> pikepdf.Stream:
    resources = resources if resources is not None else pikepdf.Dictionary()
    if opacity < 1:
        resources.ExtGState = pikepdf.Dictionary(GSa=pikepdf.Dictionary(
            Type=pikepdf.Name.ExtGState, CA=opacity, ca=opacity))
        ops = "/GSa gs " + ops
    stream = pdf.make_stream(ops.encode("ascii"))
    stream.Type = pikepdf.Name.XObject
    stream.Subtype = pikepdf.Name.Form
    stream.BBox = [float(v) for v in bbox]
    stream.Resources = resources
    return stream


def _rgb_op(color: str | None, op: str) -> str:
    r, g, b = rgb(color or "#000000")
    return f"{_num(r)} {_num(g)} {_num(b)} {op}"


def _ellipse(x0: float, y0: float, x1: float, y1: float) -> str:
    k = 0.5523
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    pts = [
        (cx + rx, cy), (cx + rx, cy + ry * k), (cx + rx * k, cy + ry), (cx, cy + ry),
        (cx - rx * k, cy + ry), (cx - rx, cy + ry * k), (cx - rx, cy),
        (cx - rx, cy - ry * k), (cx - rx * k, cy - ry), (cx, cy - ry),
        (cx + rx * k, cy - ry), (cx + rx, cy - ry * k), (cx + rx, cy),
    ]
    ops = [f"{_num(pts[0][0])} {_num(pts[0][1])} m"]
    for i in range(1, 13, 3):
        ops.append(" ".join(f"{_num(x)} {_num(y)}" for x, y in pts[i:i + 3]) + " c")
    return " ".join(ops) + " h"


def _cloud(points: Sequence[tuple[float, float]], radius: float) -> str:
    """D-015: conturul ondulat al norului: arce spre exterior pe fiecare latura."""
    n = len(points)
    area = sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
               for i in range(n))
    sign = 1 if area > 0 else -1
    ops = [f"{_num(points[0][0])} {_num(points[0][1])} m"]
    for i, p in enumerate(points):
        q = points[(i + 1) % n]
        length = math.dist(p, q)
        if length == 0:
            continue
        count = max(1, round(length / (2 * radius)))
        dx, dy = (q[0] - p[0]) / length, (q[1] - p[1]) / length
        nx, ny = dy * sign, -dx * sign
        step = length / count
        bulge = step / 2 * 4 / 3
        for j in range(count):
            a = (p[0] + dx * step * j, p[1] + dy * step * j)
            b = (p[0] + dx * step * (j + 1), p[1] + dy * step * (j + 1))
            ops.append(f"{_num(a[0] + nx * bulge)} {_num(a[1] + ny * bulge)} "
                       f"{_num(b[0] + nx * bulge)} {_num(b[1] + ny * bulge)} "
                       f"{_num(b[0])} {_num(b[1])} c")
    return " ".join(ops) + " h"


def _arrow_head(p1: tuple[float, float], p2: tuple[float, float], width: float) -> str:
    length = math.dist(p1, p2) or 1.0
    dx, dy = (p2[0] - p1[0]) / length, (p2[1] - p1[1]) / length
    head = max(6.0, width * 3)
    bx, by = p2[0] - dx * head, p2[1] - dy * head
    px, py = -dy * head / 2, dx * head / 2
    return (f"{_num(bx + px)} {_num(by + py)} m {_num(p2[0])} {_num(p2[1])} l "
            f"{_num(bx - px)} {_num(by - py)} l S")


def _points(data: AnnotationData, key: str, minimum: int) -> list[Sequence[float]]:
    points = list(data.geometry.get(key, ()))
    if len(points) < minimum:
        raise ValueError(f"{data.annot_type.value}: cel putin {minimum} puncte in '{key}'")
    return points


def _markup(pdf: pikepdf.Pdf, geo: tuple[float, float, float], data: AnnotationData,
            annot: pikepdf.Object, kind: AnnotationType, color: str) -> None:
    rects = list(data.geometry.get("rects") or ([data.bbox] if data.bbox.w else []))
    if not rects:
        raise ValueError("marcajul are nevoie de dreptunghiurile textului")
    boxes = [to_pdf_rect(geo, r) for r in rects]
    bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))
    annot.Rect = list(bbox)
    annot.QuadPoints = [v for x0, y0, x1, y1 in boxes
                        for v in (x0, y1, x1, y1, x0, y0, x1, y0)]
    appearance = _appearance(pdf, kind, boxes, bbox, rgb(color))
    if data.opacity < 1:
        states = appearance.Resources.get("/ExtGState", pikepdf.Dictionary())
        states.GSa = pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, CA=data.opacity,
                                        ca=data.opacity)
        appearance.Resources.ExtGState = states
        appearance.write(b"/GSa gs " + appearance.read_bytes())
    annot.AP = pikepdf.Dictionary(N=appearance)


def _fill(document: PdfDocument, number: int, data: AnnotationData,
          annot: pikepdf.Object) -> None:
    """Scrie campurile si aspectul adnotarii `data` in dictionarul `annot`."""
    pdf = document._pike()
    page = pdf.pages[number - 1]
    geo = page_geometry(page)
    kind = AnnotationType(data.annot_type)
    width = data.line_width if data.line_width is not None else 1.0
    color = data.color or default_color(kind)
    annot.Type = pikepdf.Name.Annot
    annot.Subtype = pikepdf.Name(SUBTYPES[kind])
    annot.P = page.obj
    annot.F = 4
    annot.C = list(rgb(color))
    if data.opacity < 1:
        annot.CA = data.opacity
    if data.fill_color:
        annot.IC = list(rgb(data.fill_color))
    for key, value in (("/T", data.author), ("/Subj", data.subject),
                       ("/Contents", data.content)):
        if value:
            annot[key] = pikepdf.String(value)
    annot.M = pikepdf.String(pdf_date())
    if kind in TEXT_MARKUPS:
        _markup(pdf, geo, data, annot, kind, color)
        return
    if kind is AnnotationType.TEXT_BOX:
        _text_box(pdf, geo, data, annot)
        return
    if kind is AnnotationType.NOTE:
        _note(pdf, geo, data, annot, color)
        return
    if kind is AnnotationType.INSERT_TEXT:
        x, y = _point(geo, data.geometry.get("point") or (data.bbox.x, data.bbox.bottom))
        box = [x - 5, y - 2, x + 5, y + 8]
        annot.Rect = box
        ops = (f"{_rgb_op(color, 'rg')} {_num(x - 5)} {_num(y - 2)} m {_num(x)} {_num(y + 8)} l "
               f"{_num(x + 5)} {_num(y - 2)} l {_num(x)} {_num(y + 2)} l h f")
        annot.AP = pikepdf.Dictionary(N=_form(pdf, box, ops, data.opacity))
        return
    annot.BS = pikepdf.Dictionary(Type=pikepdf.Name.Border, W=width, S=pikepdf.Name.S)
    stroke = _rgb_op(color, "RG")
    fill_op = _rgb_op(data.fill_color, "rg") if data.fill_color else ""
    paint = "B" if data.fill_color else "S"
    if kind is AnnotationType.INK:
        paths = [[_point(geo, p) for p in path] for path in data.geometry.get("paths", ())]
        paths = [p for p in paths if p]
        if not paths:
            raise ValueError("ink: cel putin un traseu in 'paths'")
        box = _bounds((p for path in paths for p in path), width)
        annot.Rect = box
        annot.InkList = [[v for p in path for v in p] for path in paths]
        ops = [f"{stroke} {_num(width)} w 1 J 1 j"]
        for path in paths:
            ops.append(f"{_num(path[0][0])} {_num(path[0][1])} m " + " ".join(
                f"{_num(x)} {_num(y)} l" for x, y in path[1:]) + " S")
        annot.AP = pikepdf.Dictionary(N=_form(pdf, box, " ".join(ops), data.opacity))
        return
    if kind in (AnnotationType.LINE, AnnotationType.ARROW):
        p1, p2 = (_point(geo, p) for p in _points(data, "points", 2)[:2])
        arrow = kind is AnnotationType.ARROW
        box = _bounds((p1, p2), width + (max(6.0, width * 3) if arrow else 0))
        annot.Rect = box
        annot.L = [p1[0], p1[1], p2[0], p2[1]]
        if arrow:
            annot.LE = [pikepdf.Name("/None"), pikepdf.Name.OpenArrow]
        ops = (f"{stroke} {_num(width)} w 1 J {_num(p1[0])} {_num(p1[1])} m "
               f"{_num(p2[0])} {_num(p2[1])} l S")
        if arrow:
            ops += " " + _arrow_head(p1, p2, width)
        annot.AP = pikepdf.Dictionary(N=_form(pdf, box, ops, data.opacity))
        return
    if kind in (AnnotationType.POLYGON, AnnotationType.CLOUD, AnnotationType.POLYLINE):
        closed = kind is not AnnotationType.POLYLINE
        pts = [_point(geo, p) for p in _points(data, "points", 3 if closed else 2)]
        radius = max(4.0, width * 3)
        box = _bounds(pts, width + (radius * 1.4 if kind is AnnotationType.CLOUD else 0))
        annot.Rect = box
        annot.Vertices = [v for p in pts for v in p]
        if kind is AnnotationType.CLOUD:
            annot.BE = pikepdf.Dictionary(S=pikepdf.Name.C, I=1)
            path = _cloud(pts, radius)
        else:
            path = f"{_num(pts[0][0])} {_num(pts[0][1])} m " + " ".join(
                f"{_num(x)} {_num(y)} l" for x, y in pts[1:]) + (" h" if closed else "")
        ops = (f"{stroke} {fill_op if closed else ''} {_num(width)} w 1 j {path} "
               f"{paint if closed else 'S'}")
        annot.AP = pikepdf.Dictionary(N=_form(pdf, box, ops, data.opacity))
        return
    if kind in (AnnotationType.RECTANGLE, AnnotationType.OVAL):
        if data.bbox.w <= 0 or data.bbox.h <= 0:
            raise ValueError(f"{kind.value}: dreptunghiul incadrator e gol")
        x0, y0, x1, y1 = to_pdf_rect(geo, data.bbox)
        annot.Rect = [x0, y0, x1, y1]
        h = width / 2
        shape = (f"{_num(x0 + h)} {_num(y0 + h)} {_num(x1 - x0 - width)} "
                 f"{_num(y1 - y0 - width)} re") if kind is AnnotationType.RECTANGLE \
            else _ellipse(x0 + h, y0 + h, x1 - h, y1 - h)
        ops = f"{stroke} {fill_op} {_num(width)} w {shape} {paint}"
        annot.AP = pikepdf.Dictionary(N=_form(pdf, [x0, y0, x1, y1], ops, data.opacity))
        return
    raise ValueError(f"tipul {kind.value} nu se creeaza aici")


def _note(pdf: pikepdf.Pdf, geo: tuple[float, float, float], data: AnnotationData,
          annot: pikepdf.Object, color: str) -> None:
    """D-001: iconul notei, un balon colorat de 20 pt."""
    x, y = _point(geo, data.geometry.get("point") or (data.bbox.x, data.bbox.y))
    s = NOTE_SIZE
    box = [x, y - s, x + s, y]
    annot.Rect = box
    annot.Name = pikepdf.Name.Comment
    lines = " ".join(f"{_num(x + 4)} {_num(y - 5 - i * 3.5)} m {_num(x + s - 4)} "
                     f"{_num(y - 5 - i * 3.5)} l S" for i in range(3))
    ops = (f"{_rgb_op(color, 'rg')} 0.25 G 1 w {_num(x + 1)} {_num(y - s + 4)} "
           f"{_num(s - 2)} {_num(s - 5)} re B "
           f"{_num(x + 5)} {_num(y - s + 4)} m {_num(x + 4)} {_num(y - s + 0.5)} l "
           f"{_num(x + 9)} {_num(y - s + 4)} l f 1 1 1 RG 1.2 w {lines}")
    annot.AP = pikepdf.Dictionary(N=_form(pdf, box, ops, data.opacity))


def _text_box(pdf: pikepdf.Pdf, geo: tuple[float, float, float], data: AnnotationData,
              annot: pikepdf.Object) -> None:
    """D-017, D-019, D-020: caseta cu text; fundalul e transparent implicit (D-020)."""
    from app.core.pdf.embedded_font import embed_text_font, wrap

    if data.bbox.w <= 0 or data.bbox.h <= 0:
        raise ValueError("text_box: dreptunghiul casetei e gol")
    size = float(data.geometry.get("font_size", DEFAULT_FONT_SIZE))
    text_color = str(data.geometry.get("text_color", "#000000"))
    border = data.line_width if data.line_width is not None else 1.0
    if not data.color:
        border = 0.0
    text = data.content or ""
    x0, y0, x1, y1 = to_pdf_rect(geo, data.bbox)
    annot.Rect = [x0, y0, x1, y1]
    r, g, b = rgb(text_color)
    annot.DA = pikepdf.String(f"/F1 {_num(size)} Tf {_num(r)} {_num(g)} {_num(b)} rg")
    if data.geometry.get("text_block"):
        annot.IT = pikepdf.Name.FreeTextTypeWriter
    annot.BS = pikepdf.Dictionary(Type=pikepdf.Name.Border, W=border, S=pikepdf.Name.S)
    font = embed_text_font(pdf, [text])
    pad = 2 + border
    ops = [f"{_num(x0)} {_num(y0)} {_num(x1 - x0)} {_num(y1 - y0)} re W n"]
    if data.fill_color:
        ops.append(f"{_rgb_op(data.fill_color, 'rg')} {_num(x0)} {_num(y0)} "
                   f"{_num(x1 - x0)} {_num(y1 - y0)} re f")
    if border > 0:
        h = border / 2
        ops.append(f"{_rgb_op(data.color, 'RG')} {_num(border)} w {_num(x0 + h)} "
                   f"{_num(y0 + h)} {_num(x1 - x0 - border)} {_num(y1 - y0 - border)} re S")
    leading = size * 1.2
    baseline = y1 - pad - size * font.ascent / 1000
    text_ops = [f"BT /F1 {_num(size)} Tf {_rgb_op(text_color, 'rg')}"]
    for i, line in enumerate(wrap(font, text, size, max(1.0, x1 - x0 - 2 * pad))):
        y = baseline - i * leading
        if y < y0 + pad + size * font.descent / 1000 - 0.01:
            break  # ce nu incape nu se deseneaza; textul intreg ramane in /Contents
        text_ops.append(f"1 0 0 1 {_num(x0 + pad)} {_num(y)} Tm {font.encode(line)} Tj")
    ops.append(" ".join([*text_ops, "ET"]))
    resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font.font))
    annot.AP = pikepdf.Dictionary(N=_form(pdf, [x0, y0, x1, y1], " ".join(ops),
                                          data.opacity, resources))


def _append(page: pikepdf.Page, pdf: pikepdf.Pdf, annot: pikepdf.Object) -> None:
    if "/Annots" not in page.obj:
        page.obj.Annots = pdf.make_indirect(pikepdf.Array())
    page.obj.Annots.append(annot)


# D-001…D-017, D-019
def add_annotation(document: PdfDocument, data: AnnotationData) -> AnnotationData:
    """Creeaza adnotarea si intoarce datele ei, cu `id`. Marcajele pe text cer
    strat de text (D-003): fara el, `NoTextFoundError`, iar interfata pregateste
    textul (recunoasterea in fundal, 7.6) si reia."""
    kind = AnnotationType(data.annot_type)
    if kind not in CREATABLE:
        raise ValueError(f"tipul {kind.value} nu se creeaza cu add_annotation")
    _validate(data)
    total = document.page_count
    if not 1 <= data.page_number <= total:
        raise ValueError(f"pagina {data.page_number} nu exista (1..{total})")
    if kind in TEXT_MARKUPS and not document.has_text_layer(data.page_number):
        raise NoTextFoundError("marcajele cer strat de text (D-003)",
                               page_number=data.page_number)
    pdf = document._pike()
    page = pdf.pages[data.page_number - 1]
    annot = pdf.make_indirect(pikepdf.Dictionary())
    annot.NM = pikepdf.String(uuid.uuid4().hex)
    annot.CreationDate = pikepdf.String(pdf_date())
    _fill(document, data.page_number, data, annot)
    _append(page, pdf, annot)
    document._changed()
    return read_annotation(document, _id(annot))


def read_annotation(document: PdfDocument, annot_id: int) -> AnnotationData:
    """O singura adnotare (sau un raspuns), dupa id."""
    pdf = document._pike()
    entries = _annots(pdf)
    children = _children(entries)
    for number, annot in entries:
        if _id(annot) == annot_id:
            kind = _kind(annot) or AnnotationType.NOTE
            return _to_data(number, annot, kind, page_geometry(pdf.pages[number - 1]),
                            children)
    raise KeyError(annot_id)


# D-002, D-018, D-052
def update_annotation(document: PdfDocument, data: AnnotationData) -> AnnotationData:
    """Rescrie adnotarea `data.id` (culoare, text, grosime, pozitie si marime,
    D-052). Raspunsurile si statusurile raman legate de ea. La un raspuns se
    schimba numai textul si autorul."""
    if data.id is None:
        raise ValueError("adnotarea nu are id")
    _validate(data)
    number, annot = _find(document, data.id)
    if "/IRT" in annot:
        for key, value in (("/Contents", data.content), ("/T", data.author)):
            if value is not None:
                annot[key] = pikepdf.String(value)
        annot.M = pikepdf.String(pdf_date())
        document._changed()
        return read_annotation(document, data.id)
    kind = _kind(annot)
    if kind is None or kind not in CREATABLE:
        raise ValueError("adnotarea nu se poate modifica aici")
    data = replace(data, annot_type=kind, page_number=number)
    keep = {key: annot[key] for key in ("/NM", "/CreationDate", "/Popup") if key in annot}
    for key in list(annot.keys()):
        del annot[key]
    for key, value in keep.items():
        annot[key] = value
    _fill(document, number, data, annot)
    document._changed()
    return read_annotation(document, data.id)


def _descendants(entries: Sequence[tuple[int, pikepdf.Object]], roots: set[tuple[int, int]]
                 ) -> set[tuple[int, int]]:
    children = _children(entries)
    out = set(roots)
    stack = list(roots)
    while stack:
        for child in children.get(stack.pop(), []):
            if child.objgen not in out:
                out.add(child.objgen)
                stack.append(child.objgen)
    return out


def _remove(document: PdfDocument, doomed: set[tuple[int, int]]) -> None:
    pdf = document._pike()
    for _number, annot in _annots(pdf):
        if annot.objgen in doomed and "/Popup" in annot and annot.Popup.is_indirect:
            doomed.add(annot.Popup.objgen)
    for page in pdf.pages:
        annots = page.obj.get("/Annots")
        if annots is None:
            continue
        kept = [a for a in annots if not (a.is_indirect and a.objgen in doomed)]
        if len(kept) != len(annots):
            page.obj.Annots = pdf.make_indirect(pikepdf.Array(kept))


# D-027, D-028, D-051
def delete_annotations(document: PdfDocument, ids: Sequence[int]) -> None:
    """Sterge adnotarile (sau raspunsurile) date, cu tot ce atarna de ele:
    raspunsuri, statusuri, popup (D-028)."""
    if not ids:
        return
    entries = _annots(document._pike())
    by_id = {_id(a): a for _n, a in entries}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise KeyError(missing[0])
    _remove(document, _descendants(entries, {by_id[i].objgen for i in ids}))
    document._changed()


# D-029
def delete_all_annotations(document: PdfDocument) -> int:
    """`Delete Comments and Markup...`: toate comentariile si marcajele (nu
    linkurile si nici campurile de formular). Intoarce cate adnotari de nivel
    unu au fost; apelantul confirma intai, cu `len(list_annotations(...))`."""
    top = [a.id for a in list_annotations(document) if a.id is not None]
    delete_annotations(document, top)
    return len(top)


def _child(document: PdfDocument, parent_id: int, author: str | None,
           **fields: Any) -> pikepdf.Object:
    number, parent = _find(document, parent_id)
    pdf = document._pike()
    page = pdf.pages[number - 1]
    now = pikepdf.String(pdf_date())
    child = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Text, IRT=parent,
        Rect=[float(v) for v in parent.get("/Rect", [0, 0, 0, 0])], F=28, P=page.obj,
        NM=pikepdf.String(uuid.uuid4().hex), CreationDate=now, M=now))
    if author:
        child.T = pikepdf.String(author)
    for key, value in fields.items():
        child["/" + key] = value
    child.AP = pikepdf.Dictionary(N=_form(pdf, [float(v) for v in child.Rect], "", 1.0))
    _append(page, pdf, child)
    return child


# D-026
def add_reply(document: PdfDocument, parent_id: int, content: str, author: str
              ) -> AnnotationData:
    """Raspuns imbricat, cu autor si data; se poate raspunde si unui raspuns.
    Raspunsul nu se deseneaza pe pagina (aspect gol)."""
    child = _child(document, parent_id, author, RT=pikepdf.Name.R,
                   Contents=pikepdf.String(content))
    document._changed()
    return read_annotation(document, _id(child))


# D-031
def set_review_status(document: PdfDocument, annot_id: int, status: ReviewStatus | None,
                      author: str) -> None:
    """Statusul de revizie. Fiecare schimbare ramane in fisier (istoricul,
    D-032); None = fara status."""
    name = "None" if status is None else REVIEW_STATES[ReviewStatus(status)]
    _child(document, annot_id, author, State=pikepdf.String(name),
           StateModel=pikepdf.String("Review"))
    document._changed()


# D-030
def set_checked(document: PdfDocument, annot_id: int, checked: bool, author: str) -> None:
    """Bifa personala; nu e status de revizie (D-030)."""
    _child(document, annot_id, author,
           State=pikepdf.String("Marked" if checked else "Unmarked"),
           StateModel=pikepdf.String("Marked"))
    document._changed()


# --- panoul Comments (D-033…D-044) ----------------------------------------------------


@dataclass
class CommentFilter:
    """Filtrele panoului `Comments`; None = fara filtru pe acel criteriu."""

    types: set[AnnotationType] | None = None          # D-037
    authors: set[str] | None = None                   # D-038
    pages: tuple[int, int] | None = None              # D-039 (inclusiv)
    dates: tuple[str, str] | None = None              # D-040: AAAA-LL-ZZ, inclusiv
    checked: bool | None = None                       # D-041
    statuses: set[ReviewStatus | None] | None = None  # D-042
    hidden: set[int] = field(default_factory=set)     # D-036 `Hide Current Comments`

    def reset(self) -> None:
        """D-043: toate filtrele se golesc (si comentariile ascunse reapar)."""
        self.types = self.authors = self.statuses = None
        self.pages = self.dates = None
        self.checked = None
        self.hidden = set()


def _matches_text(annot: AnnotationData, needle: str) -> bool:
    """D-034: textul se cauta in comentariu, in raspunsuri si in autori."""
    from app.core.pdf.text import fold

    for value in (annot.content, annot.author):
        if value and needle in fold(value, False):
            return True
    return any(_matches_text(r, needle) for r in annot.replies)


def filter_comments(annots: Sequence[AnnotationData], comment_filter: CommentFilter,
                    text: str = "") -> list[AnnotationData]:
    from app.core.pdf.text import fold

    f = comment_filter
    needle = fold(text, False) if text else ""
    out = []
    for a in annots:
        day = a.created_at[:10]
        if a.id in f.hidden \
                or (f.types is not None and a.annot_type not in f.types) \
                or (f.authors is not None and (a.author or "") not in f.authors) \
                or (f.pages is not None and not f.pages[0] <= a.page_number <= f.pages[1]) \
                or (f.dates is not None and not f.dates[0] <= day <= f.dates[1]) \
                or (f.checked is not None and a.is_checked != f.checked) \
                or (f.statuses is not None and a.review_status not in f.statuses) \
                or (needle and not _matches_text(a, needle)):
            continue
        out.append(a)
    return out


SORT_KEYS = ("page", "author", "date", "type")
"""D-035: criteriile de sortare."""


def sort_comments(annots: Sequence[AnnotationData], key: str = "page") -> list[AnnotationData]:
    if key == "page":
        return sorted(annots, key=lambda a: (a.page_number, a.bbox.y, a.bbox.x))
    if key == "author":
        return sorted(annots, key=lambda a: ((a.author or "").casefold(), a.page_number))
    if key == "date":
        return sorted(annots, key=lambda a: (a.created_at, a.page_number))
    if key == "type":
        return sorted(annots, key=lambda a: (a.annot_type.value, a.page_number))
    raise ValueError(f"sortare necunoscuta: {key}")
