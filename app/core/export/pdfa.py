"""PDF/A, PDF/UA si reducerea dimensiunii (faza 6, pasul 6.3): I-008..I-012,
I-016, Q-103.

PDF/A (I-008..I-011): pornind de la PDF-ul din 6.2, fisierul primeste
versiunea de baza (PDF 1.4 pentru PDF/A-1, 1.7 pentru PDF/A-2 si -3), un
OutputIntent sRGB (culori independente de dispozitiv), metadatele `pdfaid`,
fonturile incorporate (fontul textului invizibil e incorporat), fara criptare,
fara scripturi, fara LZW si fara legaturi catre continut extern (I-010).
Nivelul A adauga etichetele de structura; nivelul U cere Unicode (ToUnicode).

[DECIZIE AUTONOMA] Verificarea (`verify_pdfa`, SPEC_05) e a noastra si
verifica regulile de mai sus pe fisierul scris; nu e un validator complet
(veraPDF e Java). O abatere ridica `PdfAComplianceError` cu motivele (I-008).

PDF/UA (I-012, Q-103): PDF etichetat cu imaginea paginii ca artefact, limba,
titlul afisat, metadatele `pdfuaid`.

**INCOMPLET, marcat:** compresia MRC (I-016, X-086): `use_mrc` nu schimba inca
imaginile; reducerea se face prin recomprimarea lor.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import fields
from pathlib import Path
from typing import Any

import pikepdf
from PIL import ImageCms

from app.core.errors import PdfAComplianceError
from app.core.export.base import BaseExporter, ExportOptions
from app.core.export.pdf import JPEG_QUALITY, PdfExporter
from app.core.model import (
    CancelToken,
    ExportFormat,
    ImageQuality,
    LayoutMode,
    PageData,
    PdfAVersion,
    ProgressCallback,
)

DEFAULT_PDFA = PdfAVersion.A2B


def _srgb() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _output_intent(pdf: pikepdf.Pdf) -> None:
    profile = pdf.make_stream(_srgb(), N=3)
    pdf.Root.OutputIntents = pikepdf.Array([pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.OutputIntent, S=pikepdf.Name.GTS_PDFA1,
        OutputConditionIdentifier=pikepdf.String("sRGB IEC61966-2.1"),
        Info=pikepdf.String("sRGB IEC61966-2.1"), DestOutputProfile=profile))])


def _fields(options: ExportOptions) -> dict[str, Any]:
    return {f.name: getattr(options, f.name) for f in fields(ExportOptions)}


# I-008..I-011
class PdfAExporter(BaseExporter):
    format = ExportFormat.PDFA

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.EXACT, pdfa_version=DEFAULT_PDFA)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        version = PdfAVersion(options.pdfa_version or DEFAULT_PDFA)
        part, level = version.value[0], version.value[1]
        tagged = level == "a" or options.tagged_pdf
        build_options = ExportOptions(**{**_fields(options), "tagged_pdf": tagged})
        pdf = PdfExporter().build(pages, build_options, progress=progress, cancel=cancel,
                                  links=False)  # I-010: fara legaturi externe
        target = Path(target)
        _output_intent(pdf)
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            meta["pdfaid:part"] = part
            meta["pdfaid:conformance"] = level.upper()
            meta["dc:title"] = options.metadata.get("title") or target.stem
        pdf.save(target, force_version="1.4" if part == "1" else "1.7")
        violations = verify_pdfa(target, version)
        if violations:
            target.unlink(missing_ok=True)
            raise PdfAComplianceError("fisierul nu respecta PDF/A", violations=violations,
                                      version=version.value)
        return [target]


# I-012, Q-103
class PdfUaExporter(BaseExporter):
    format = ExportFormat.PDFUA

    def default_options(self) -> ExportOptions:
        return ExportOptions(layout_mode=LayoutMode.EXACT, tagged_pdf=True,
                             create_bookmarks_from_headings=True)

    def export(self, pages: Sequence[PageData], target: Path, options: ExportOptions, *,
               progress: ProgressCallback | None = None,
               cancel: CancelToken | None = None) -> list[Path]:
        build_options = ExportOptions(**{**_fields(options), "tagged_pdf": True})
        pdf = PdfExporter().build(pages, build_options, progress=progress, cancel=cancel)
        target = Path(target)
        pdf.Root.ViewerPreferences = pikepdf.Dictionary(DisplayDocTitle=True)
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            meta["pdfuaid:part"] = "1"
            meta["dc:title"] = options.metadata.get("title") or target.stem
        pdf.save(target, force_version="1.7")
        return [target]


# SPEC_05 ExportService.verify_pdfa. I-008, I-009, I-010
def verify_pdfa(path: Path, version: PdfAVersion) -> list[str]:
    """Abaterile fisierului scris de la PDF/A; lista goala = conform."""
    version = PdfAVersion(version)
    part, level = version.value[0], version.value[1]
    out: list[str] = []
    with pikepdf.open(path) as pdf:
        if part == "1" and pdf.pdf_version > "1.4":
            out.append(f"versiunea PDF {pdf.pdf_version} > 1.4 (PDF/A-1)")
        if pdf.is_encrypted or "/Encrypt" in pdf.trailer:
            out.append("criptare (I-010)")
        intents = pdf.Root.get("/OutputIntents")
        if not intents or not any(i.get("/S") == pikepdf.Name.GTS_PDFA1
                                  and "/DestOutputProfile" in i for i in intents):
            out.append("lipseste OutputIntent GTS_PDFA1 (culori independente, I-009)")
        meta = pdf.open_metadata()
        if meta.get("pdfaid:part") != part:
            out.append("metadatele pdfaid:part lipsesc sau difera")
        if (meta.get("pdfaid:conformance") or "").lower() != level:
            out.append("metadatele pdfaid:conformance lipsesc sau difera")
        if "/JavaScript" in pdf.Root.get("/Names", {}) or "/OpenAction" in pdf.Root:
            out.append("scripturi (I-010)")
        if level == "a" and ("/StructTreeRoot" not in pdf.Root
                             or not pdf.Root.get("/MarkInfo", {}).get("/Marked")):
            out.append("nivelul A cere etichete de structura")
        for number, page in enumerate(pdf.pages, start=1):
            for annot in page.get("/Annots", []):
                if annot.get("/Subtype") == pikepdf.Name.Link and "/A" in annot:
                    out.append(f"pagina {number}: legatura catre continut extern (I-010)")
            for name, font in (page.Resources.get("/Font") or {}).items():
                out += [f"pagina {number}, fontul {name}: {m}"
                        for m in _font_problems(font, level)]
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Stream):
                filters = obj.get("/Filter")
                names = list(filters) if isinstance(filters, pikepdf.Array) else [filters]
                if pikepdf.Name.LZWDecode in names:
                    out.append("compresie LZW (I-010)")
                if part == "1" and "/SMask" in obj:
                    out.append("transparenta (nepermisa in PDF/A-1)")
    return list(dict.fromkeys(out))


def _font_problems(font: Any, level: str) -> list[str]:
    problems = []
    fonts = [font, *font.get("/DescendantFonts", [])]
    if not any("/FontDescriptor" in f and any(k in f.FontDescriptor for k in (
            "/FontFile", "/FontFile2", "/FontFile3")) for f in fonts):
        problems.append("nu e incorporat (I-009)")
    if level == "u" and "/ToUnicode" not in font:
        problems.append("fara ToUnicode (nivelul U)")
    return problems


# SPEC_05 ExportService.reduce_file_size. I-016
def reduce_file_size(source: Path, target: Path, *, image_quality: ImageQuality,
                     use_mrc: bool = False, languages: Sequence[str] = ()) -> tuple[int, int]:
    """Recomprima imaginile color si gri ale PDF-ului (JPEG, calitatea aleasa)
    cand rezultatul e mai mic; intoarce (dimensiunea inainte, dupa).
    `use_mrc`, `languages`: INCOMPLET, marcat (vezi antetul modulului)."""
    source, target = Path(source), Path(target)
    before = source.stat().st_size
    quality = JPEG_QUALITY[ImageQuality(image_quality)]
    with pikepdf.open(source) as pdf:
        for page in pdf.pages:
            # pikepdf.Dictionary nu are values()
            for _, image in (page.Resources.get("/XObject") or {}).items():  # noqa: PERF102
                if image.get("/Subtype") != pikepdf.Name.Image:
                    continue
                if int(image.get("/BitsPerComponent", 8)) != 8 or "/SMask" in image:
                    continue
                try:
                    pil = pikepdf.PdfImage(image).as_pil_image()
                except Exception:  # noqa: BLE001, S112 - o imagine nedecodabila ramane neschimbata
                    continue
                if pil.mode not in ("L", "RGB"):
                    pil = pil.convert("RGB")
                out = io.BytesIO()
                pil.save(out, "JPEG", quality=quality, optimize=True)
                if len(out.getvalue()) < len(image.read_raw_bytes()):
                    image.write(out.getvalue(), filter=pikepdf.Name.DCTDecode)
                    image.ColorSpace = (pikepdf.Name.DeviceGray if pil.mode == "L"
                                        else pikepdf.Name.DeviceRGB)
                    image.BitsPerComponent = 8
                    for key in ("/DecodeParms", "/Decode"):
                        if key in image:
                            del image[key]
        pdf.save(target, compress_streams=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate)
    return before, target.stat().st_size
