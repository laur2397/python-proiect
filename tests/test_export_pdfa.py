"""Faza 6, pasul 6.3: PDF/A, PDF/UA si reducerea dimensiunii (I-008..I-012,
I-016, Q-103)."""

from __future__ import annotations

import numpy as np
import pikepdf
import pytest
from PIL import Image

from app.core.errors import PdfAEncryptionConflictError
from app.core.export.base import ExportOptions, default_service
from app.core.export.pdfa import reduce_file_size, verify_pdfa
from app.core.model import (
    AreaData,
    AreaType,
    BlockData,
    ColorMode,
    ExportFormat,
    ImageQuality,
    LayoutMode,
    LineData,
    PageData,
    PageStatus,
    PdfAVersion,
    Rect,
    WordData,
)


@pytest.fixture
def pages(tmp_path):
    rng = np.random.default_rng(3)
    path = tmp_path / "p.png"
    Image.fromarray(rng.integers(0, 255, (1754, 1240, 3), dtype=np.uint8)).save(
        path, dpi=(150, 150))
    p = PageData(1, 1, path, path, 1240, 1754, 150, 150, ColorMode.COLOR,
                 status=PageStatus.RECOGNIZED)
    for i, (text, style) in enumerate((("Cerere de finanțare", "Heading 1"),
                                       ("Județul Brașov, anul 2026", None))):
        words = [WordData(None, t, 95.0, bbox=Rect(100 + 200 * j, 200 + 100 * i, 180, 40))
                 for j, t in enumerate(text.split())]
        p.areas.append(AreaData(i + 1, AreaType.TEXT, [], i, bbox=Rect(0, 0, 10, 10),
                                blocks=[BlockData(None, lines=[LineData(None, words=words)],
                                                  style_name=style)]))
    return [p]


def export(pages, path, fmt, **kw):
    options = ExportOptions(layout_mode=LayoutMode.EXACT, **kw)
    (out,) = default_service().export(pages, path, fmt, options)
    return out


@pytest.mark.parametrize("version", [PdfAVersion.A1B, PdfAVersion.A2B, PdfAVersion.A2U,
                                     PdfAVersion.A3B, PdfAVersion.A1A, PdfAVersion.A2A])
def test_T_I008_1_pdfa_versions_conform(pages, tmp_path, version):
    """T-I008.1 / I-009, I-011: fiecare versiune trece verificarea pe fisier."""
    out = export(pages, tmp_path / f"a{version.value}.pdf", ExportFormat.PDFA,
                 pdfa_version=version)
    assert verify_pdfa(out, version) == []
    with pikepdf.open(out) as pdf:
        assert pdf.pdf_version == ("1.4" if version.value[0] == "1" else "1.7")
        assert pdf.open_metadata()["pdfaid:part"] == version.value[0]
        if version.value[1] == "a":
            assert "/StructTreeRoot" in pdf.Root


def test_T_I010_1_pdfa_refuses_a_password_and_external_links(pages, tmp_path):
    from app.core.text.links import Link

    with pytest.raises(PdfAEncryptionConflictError):
        export(pages, tmp_path / "p.pdf", ExportFormat.PDFA, password="x")
    link = Link(1, 1, "https://fonduri.ro", "x", (), Rect(100, 200, 180, 40))
    out = export(pages, tmp_path / "l.pdf", ExportFormat.PDFA,
                 format_options={"links": {1: [link]}})
    with pikepdf.open(out) as pdf:
        assert "/Annots" not in pdf.pages[0]


def test_T_I008_2_violations_are_reported(pages, tmp_path):
    """T-I008.2: un fisier fara OutputIntent si cu legatura externa: abaterile."""
    from app.core.text.links import Link

    link = Link(1, 1, "https://fonduri.ro", "x", (), Rect(100, 200, 180, 40))
    plain = export(pages, tmp_path / "simplu.pdf", ExportFormat.PDF,
                   format_options={"links": {1: [link]}})
    problems = verify_pdfa(plain, PdfAVersion.A2B)
    assert any("OutputIntent" in p for p in problems)
    assert any("pdfaid" in p for p in problems)
    assert any("legatura" in p for p in problems)


def test_T_I012_1_pdfua_is_tagged(pages, tmp_path):
    """T-I012.1 / Q-103: etichete, limba, titlul afisat, pdfuaid."""
    out = export(pages, tmp_path / "ua.pdf", ExportFormat.PDFUA, metadata={"title": "Dosar"})
    with pikepdf.open(out) as pdf:
        assert pdf.Root.MarkInfo.Marked and str(pdf.Root.Lang) == "ro"
        assert pdf.Root.ViewerPreferences.DisplayDocTitle
        meta = pdf.open_metadata()
        assert meta["pdfuaid:part"] == "1" and meta["dc:title"] == "Dosar"
        roles = [str(k.S) for k in pdf.Root.StructTreeRoot.K.K]
        assert roles == ["/H1", "/P"]
        assert b"/Artifact BMC" in pdf.pages[0].Contents.read_bytes()


def test_T_I016_1_reduce_file_size(pages, tmp_path):
    big = export(pages, tmp_path / "mare.pdf", ExportFormat.PDF,
                 image_quality=ImageQuality.BEST)
    before, after = reduce_file_size(big, tmp_path / "mic.pdf",
                                     image_quality=ImageQuality.COMPACT)
    assert after < before
    with pikepdf.open(tmp_path / "mic.pdf") as pdf:
        assert len(pdf.pages) == 1
