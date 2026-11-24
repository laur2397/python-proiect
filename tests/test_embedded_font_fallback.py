"""Fontul de rezerva (fara font de sistem): ș, ț, Ș, Ț nu devin `?`. Defect gasit
la auditul din 24.11.2026 (CLAUDE.md §6.4)."""

from __future__ import annotations

import pikepdf
import pypdfium2 as pdfium

from app.core.pdf.embedded_font import _helvetica


def test_romanian_letters_survive_in_the_fallback_font(tmp_path):
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(400, 200))
    font = _helvetica(pdf)
    text = "Brașov, județul Ţara Şirul ȘȚ"
    encoded = font.encode(text)
    assert "?" not in encoded
    page = pdf.pages[0]
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font.font))
    page.Contents = pdf.make_stream(f"BT /F1 14 Tf 20 100 Td {encoded} Tj ET".encode("latin-1"))
    pdf.save(tmp_path / "f.pdf")
    extracted = pdfium.PdfDocument(tmp_path / "f.pdf")[0].get_textpage().get_text_range()
    assert "Brașov" in extracted and "județul" in extracted
    assert "Țara Șirul ȘȚ" in extracted  # sedila se scrie cu virgula
