"""Stampilele (faza 7, pasul 7.4b): D-045…D-052, cu etichetele de data si ora
din SPEC_03 Z.1 (Z-001…Z-012)."""

from __future__ import annotations

import io
import sqlite3
from datetime import datetime

import pikepdf
import pytest
from PIL import Image
from test_pdf_search import text_pdf

from app.core import datetags
from app.core.context import AppContext
from app.core.errors import BuiltinNotEditableError, UnsupportedFormatError
from app.core.model import AnnotationData, AnnotationType, Rect, ReviewStatus
from app.core.paths import AppPaths
from app.core.pdf.document import PdfDocument
from app.core.pdf.stamps import StampLibrary, place_stamp, stamp_text

MOMENT = datetime(2026, 2, 7, 15, 4, 9)  # sambata


@pytest.fixture
def ctx(tmp_path):
    c = AppContext.start(AppPaths.portable(tmp_path / "app"))
    yield c
    c.close()


@pytest.fixture
def library(ctx):
    return StampLibrary(ctx.app_db)


@pytest.fixture
def doc(tmp_path):
    with PdfDocument.open(text_pdf(tmp_path / "dosar.pdf", [["Cerere de finantare"]])) as d:
        yield d


def png(size=(300, 120), color=(200, 0, 0, 255)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", size, color).save(out, "PNG")
    return out.getvalue()


def render(doc):
    return Image.open(io.BytesIO(doc.render_page(1, 1.0))).convert("RGB")


def px_box(rect):
    return tuple(round(v * 96 / 72) for v in (rect.x, rect.y, rect.x + rect.w,
                                              rect.y + rect.h))


# --- Z-001…Z-012 ----------------------------------------------------------------------


@pytest.mark.parametrize(("tag", "rom", "usa"), [
    ("<d/>", "07.02.2026", "2/7/2026"),                      # Z-001
    ("<date/>", "7 februarie 2026", "February 7, 2026"),     # Z-002
    ("<t12/>", "3:04", "3:04 PM"),                           # Z-003 (%p numai unde exista)
    ("<t24/>", "15:04", "15:04"),                            # Z-004
    ("<time/>", "15:04:09", "15:04:09"),                     # Z-005
])
def test_T_Z001_tags(tag, rom, usa):
    assert datetags.expand(tag, MOMENT, region="ROM") == rom
    assert datetags.expand(tag, MOMENT, region="USA") == usa


def test_T_Z006_1_region_code_in_tag():
    assert datetags.expand("<d=USA/>", MOMENT, region="ROM") == "2/7/2026"
    assert datetags.expand("<date=RUS/>", MOMENT, region="ROM") == "7 февраля 2026 г."
    assert datetags.expand("<t12=HUN/>", MOMENT, region="ROM") == "du. 3:04"
    assert datetags.expand("<d=XYZ/>", MOMENT, region="ROM") == "07.02.2026"


def test_T_Z006_2_system_region(monkeypatch):
    monkeypatch.setattr(datetags.locale, "getlocale", lambda *_: (None, None))
    monkeypatch.setenv("LC_ALL", "hu_HU.UTF-8")
    assert datetags.system_region() == "HUN"
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    assert datetags.system_region() == "USA"
    for var in ("LC_ALL", "LC_TIME", "LANG"):
        monkeypatch.setenv(var, "")
    assert datetags.system_region() == datetags.DEFAULT_REGION


@pytest.mark.parametrize(("fmt", "rom"), [
    ("%y|%#y|%Y|%#Y", "26|26|2026|2026"),                       # Z-007
    ("%b|%B|%m|%#m", "feb.|februarie|02|2"),                     # Z-008
    ("%d|%#d|%a|%A", "07|7|sâm.|sâmbătă"),                       # Z-009
    ("%H|%#H|%I|%#I", "15|15|03|3"),                             # Z-010
    ("%M|%#M|%S|%#S", "04|4|09|9"),                              # Z-011
    ("100%%", "100%"),                                           # Z-012
])
def test_T_Z007_custom_formats(fmt, rom):
    assert datetags.expand(f"<d={fmt}/>", MOMENT, region="ROM") == rom


def test_T_Z010_1_am_pm_only_in_some_regions():
    assert datetags.format_moment(MOMENT, "%p", "USA") == "PM"
    assert datetags.format_moment(MOMENT, "%p", "ENG") == "PM"
    assert datetags.format_moment(MOMENT, "%p", "HUN") == "du."
    assert datetags.format_moment(MOMENT, "%p", "CZ") == "odp."
    assert datetags.format_moment(MOMENT, "%p", "ROM") == ""
    assert datetags.format_moment(MOMENT, "%p", "RUS") == ""


def test_text_outside_tags_is_kept():
    assert datetags.expand("Primit la <d/>, ora <t24/>", MOMENT, region="ROM") == \
        "Primit la 07.02.2026, ora 15:04"
    assert datetags.has_tags("x <time/>") and not datetags.has_tags("fara etichete")


# --- biblioteca (D-045, D-047, D-048, D-050) ------------------------------------------


def test_T_D045_1_builtin_stamps_are_seeded_once(ctx, library):
    names = [s.name for s in library.stamps()]
    assert names[:3] == ["approved", "rejected", "final"]
    assert all(s.is_builtin for s in library.stamps())
    assert [s.name for s in StampLibrary(ctx.app_db).stamps()] == names  # fara dubluri


def test_T_D107_1_final_stamp_has_date_and_time(library):
    assert stamp_text(library.get("final"), language="ro", moment=MOMENT, region="ROM") == \
        "FINAL\n07.02.2026 15:04"
    assert stamp_text(library.get("draft"), language="en") == "DRAFT"
    assert stamp_text(library.get("confidential"), language="ro") == "CONFIDENȚIAL"


def test_T_D048_1_text_stamp_with_tags(library):
    stamp = library.create_text("Inregistrare", "ÎNREGISTRAT\nNr. ____ din <d/>",
                                font_size=14, text_color="#2F6DF6", border_style="double")
    assert (stamp.kind, stamp.include_date, stamp.include_time) == ("text", True, False)
    assert stamp_text(stamp, moment=MOMENT, region="ROM") == \
        "ÎNREGISTRAT\nNr. ____ din 07.02.2026"
    assert [s.name for s in library.stamps()][-1] == "Inregistrare"
    with pytest.raises(ValueError):
        library.create_text("Inregistrare", "alt text")
    with pytest.raises(ValueError):
        library.create_text("Gol", "   ")
    with pytest.raises(ValueError):
        library.create_text("Chenar", "x", border_style="ondulat")


def test_T_D047_1_image_stamp_with_size(library):
    stamp = library.create_image("Sigla", png((300, 120)), scale=0.5)
    with Image.open(io.BytesIO(stamp.image)) as image:
        assert image.size == (150, 60)
    with pytest.raises(UnsupportedFormatError):
        library.create_image("Stricata", b"nu e imagine")
    with pytest.raises(ValueError):
        library.create_image("Mare", png(), scale=10)


def test_T_D050_1_edit_and_delete_own_but_not_builtin(ctx, library):
    library.create_text("Ciorna mea", "CIORNĂ <d/>")
    edited = library.update("Ciorna mea", new_name="Ciorna", text="CIORNĂ v2",
                            border_style="none")
    assert (edited.name, edited.text, edited.border_style, edited.include_date) == \
        ("Ciorna", "CIORNĂ v2", "none", False)
    library.delete("Ciorna")
    with pytest.raises(KeyError):
        library.get("Ciorna")
    with pytest.raises(BuiltinNotEditableError):
        library.update("approved", text="altceva")
    with pytest.raises(BuiltinNotEditableError):
        library.delete("approved")
    with pytest.raises(sqlite3.IntegrityError), ctx.app_db:  # si baza refuza (SPEC_04)
        ctx.app_db.execute("DELETE FROM stamp WHERE name = 'approved'")


# --- pe pagina (D-045, D-046, D-051, D-052) -------------------------------------------


def test_T_D045_2_place_text_stamp(doc, library, tmp_path):
    created = place_stamp(doc, 1, library.get("approved"), (300, 100), author="Ana",
                          moment=MOMENT, region="ROM")
    assert created.annot_type is AnnotationType.STAMP
    assert created.content == "APROBAT\n07.02.2026"
    assert (created.bbox.x, created.bbox.y) == pytest.approx((300, 100))
    assert created.author == "Ana"
    box = render(doc).crop(px_box(created.bbox))
    red, green, _blue = box.split()
    assert any(g > r + 40 for r, g in zip(red.tobytes(), green.tobytes(), strict=True))  # verde
    doc.save_as(tmp_path / "stampilat.pdf")
    with pikepdf.open(tmp_path / "stampilat.pdf") as pdf:
        stamp = next(a for a in pdf.pages[0].Annots if a.Subtype == "/Stamp")
        assert str(stamp.Name) == "/Approved" and "/N" in stamp.AP


def test_T_D047_2_place_image_stamp(doc, library):
    stamp = library.create_image("Sigla", png((300, 150), (0, 0, 200, 255)))
    created = place_stamp(doc, 1, stamp, (100, 400), scale=0.5)
    assert (created.bbox.w, created.bbox.h) == pytest.approx((72.0, 36.0))
    center = (round((100 + 36) * 96 / 72), round((400 + 18) * 96 / 72))
    assert render(doc).getpixel(center)[2] > 150


def test_T_D046_D051_stamp_takes_comments_and_is_deleted_with_them(doc, library):
    created = place_stamp(doc, 1, library.get("verified"), (100, 100))
    doc.add_reply(created.id, "Verificat de mine", "Ion")
    doc.set_review_status(created.id, ReviewStatus.COMPLETED, "Ion")
    item = next(a for a in doc.annotations() if a.id == created.id)
    assert item.review_status is ReviewStatus.COMPLETED
    assert [r.content for r in item.replies] == ["Verificat de mine"]
    doc.delete_annotations([created.id])
    assert all(a.annot_type is not AnnotationType.STAMP for a in doc.annotations())


def test_T_D052_1_move_and_resize_stamp(doc, library):
    created = place_stamp(doc, 1, library.get("received"), (100, 100))
    moved = doc.update_annotation(AnnotationData(
        created.id, AnnotationType.STAMP, 1, {},
        bbox=Rect(250, 300, created.bbox.w * 2, created.bbox.h * 2)))
    assert moved.bbox.x == pytest.approx(250)
    assert moved.bbox.w == pytest.approx(created.bbox.w * 2)
    assert moved.content == created.content
    old = render(doc).crop(px_box(created.bbox))
    assert old.getextrema() == ((255, 255), (255, 255), (255, 255))  # a plecat de acolo


def test_place_stamp_rejects_bad_input(doc, library):
    with pytest.raises(ValueError):
        place_stamp(doc, 5, library.get("final"), (0, 0))
    with pytest.raises(ValueError):
        place_stamp(doc, 1, library.get("final"), (0, 0), scale=0)
    assert not doc.is_modified
