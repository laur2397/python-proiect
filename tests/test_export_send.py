"""Faza 6, pasul 6.8: trimiterea si tiparirea, partea din nucleu (Q-040..Q-050,
Q-060..Q-065)."""

from __future__ import annotations

import email
import email.policy
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from app.core.export import send
from app.core.export.base import ExportOptions
from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    ColorMode,
    ExportFormat,
    LayoutMode,
    LineData,
    PageData,
    PageStatus,
    Rect,
    WordData,
)


@pytest.fixture
def pages(tmp_path):
    out = []
    for n in (1, 2, 3, 4):
        path = tmp_path / f"p{n}.png"
        Image.new("L", (1240, 1754), 255).save(path, dpi=(150, 150))
        p = PageData(n, n, path, path, 1240, 1754, 150, 150, ColorMode.GRAY,
                     status=PageStatus.RECOGNIZED, blank_score=1.0 if n == 3 else 0.1)
        if n != 3:
            words = [WordData(None, t, 95.0, bbox=Rect(100 + 200 * i, 200, 180, 40))
                     for i, t in enumerate(f"Pagina {n} Brașov".split())]
            p.areas.append(AreaData(n, AreaType.TEXT, [], 0, bbox=Rect(100, 200, 800, 60),
                                    blocks=[BlockData(None, "heading", style_name="Heading 1",
                                                      lines=[LineData(None, words=words)])]))
        out.append(p)
    return out


def attachments(eml: Path) -> list[str]:
    msg = email.message_from_bytes(eml.read_bytes(), policy=email.policy.default)
    return [part.get_filename() for part in msg.iter_attachments()]


def test_T_Q043_1_split_options(pages):
    """T-Q043.1: toate intr-un fisier, fiecare separat, impartite la paginile goale."""
    assert [len(g) for g in send.split_pages(pages, send.ALL)] == [4]
    assert [len(g) for g in send.split_pages(pages, send.PER_PAGE)] == [1, 1, 1, 1]
    groups = send.split_pages(pages, send.BLANK_PAGES)
    assert [[p.page_number for p in g] for g in groups] == [[1, 2], [4]]
    with pytest.raises(ValueError):
        send.split_pages(pages, "altceva")


def test_T_Q042_1_email_document(pages, tmp_path):
    """T-Q042.1: mesajul cu atasamentele; HTML nu se trimite; nimic nu pleaca."""
    eml = send.email_document(pages, tmp_path / "mail", "dosar", ExportFormat.DOCX,
                              ExportOptions(layout_mode=LayoutMode.EDITABLE),
                              split=send.BLANK_PAGES)
    assert attachments(eml) == ["dosar_001.docx", "dosar_002.docx"]
    with pytest.raises(ValueError, match="HTML"):
        send.email_document(pages, tmp_path / "m2", "d", ExportFormat.HTML,
                            ExportOptions(layout_mode=LayoutMode.FORMATTED))


def test_T_Q044_1_email_images(pages, tmp_path):
    eml = send.email_images(pages, tmp_path / "img", "scan", ExportFormat.TIFF, multipage=True)
    assert attachments(eml) == ["scan.tif"]


def test_T_Q045_1_kindle(pages, tmp_path):
    """T-Q045.1: adresa Kindle, EPUB atasat, mesajul il trimite utilizatorul."""
    eml = send.send_to_kindle(pages, tmp_path / "k", "carte", "ion@kindle.com")
    msg = email.message_from_bytes(eml.read_bytes(), policy=email.policy.default)
    assert msg["To"] == "ion@kindle.com" and attachments(eml) == ["carte.epub"]
    with pytest.raises(ValueError, match="kindle"):
        send.send_to_kindle(pages, tmp_path / "k2", "c", "ion@gmail.com")


def test_T_Q041_1_what_is_lost_in_pdf_editor(pages, tmp_path):
    """T-Q041.1: fara semne de carte, comentarii si legaturi."""
    out = send.send_to_pdf_editor(pages, tmp_path / "pe", "dosar")
    with pikepdf.open(out) as pdf, pdf.open_outline() as outline:
        assert len(pdf.pages) == 4 and list(outline.root) == []
        assert all("/Annots" not in p for p in pdf.pages)
    assert set(send.LOST_ON_SEND) == {"attachments", "bookmarks", "comments", "annotations"}


@pytest.mark.parametrize("fmt", [ExportFormat.DOCX, ExportFormat.XLSX, ExportFormat.PPTX,
                                 ExportFormat.HTML])
def test_T_Q046_1_send_to_applications(pages, tmp_path, fmt):
    """T-Q046.1, T-Q048.1: fisierul pentru Word, Excel, PowerPoint, browser."""
    out = send.send_to_application(pages, tmp_path / "app", "dosar", fmt)
    assert out.is_file() and out.suffix == f".{fmt.value}"


def test_T_Q047_Q050_clipboard_and_print(pages):
    texts = send.text_pages(pages)
    assert texts[0] == "Pagina 1 Brașov" and texts[2] == ""
    assert send.image_pages(pages) == [p.image_path for p in pages]


def test_T_Q065_1_no_office_automation():
    """T-Q065.1: nucleul nu depinde de Office instalat (CLAUDE.md §6.3)."""
    core = Path(__file__).resolve().parents[1] / "app" / "core"
    for path in core.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for banned in ("win32com", "comtypes", "pywin32", "appscript"):
            assert f"import {banned}" not in text, (path, banned)
