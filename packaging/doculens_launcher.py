"""Punctul de intrare al executabilului Windows (faza 16, pregatire Y-*).

Rolul lui e doar sa spuna nucleului unde e Tesseract-ul livrat cu programul,
apoi sa porneasca interfata (app.gui.main). Logica nu sta aici.

Structura folderului livrat (PyInstaller, onedir):
    DocuLens/
      DocuLens.exe
      tesseract/tesseract.exe, tessdata/ron.traineddata, eng.traineddata, osd...
      _internal/ ...

`--self-test` verifica fara fereastra ca programul impachetat porneste,
gaseste Tesseract-ul livrat si recunoaste un text romanesc. Il foloseste
build-ul din CI; utilizatorul il poate rula si el.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _use_bundled_tesseract() -> None:
    tess = _base_dir() / "tesseract" / ("tesseract.exe" if os.name == "nt" else "tesseract")
    if tess.is_file() and "DOCULENS_TESSERACT" not in os.environ:
        os.environ["DOCULENS_TESSERACT"] = str(tess)
        os.environ.setdefault("TESSDATA_PREFIX", str(tess.parent / "tessdata"))


def _self_test() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import tempfile

    from PIL import Image, ImageDraw, ImageFont

    from app.core.context import AppContext
    from app.core.ocr.engine import find_tesseract
    from app.core.ocr.service import RecognitionService
    from app.core.project import OcrProject

    cmd = find_tesseract()
    print("tesseract:", cmd)
    if cmd is None:
        return 2
    font = None
    for cand in (r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(cand).is_file():
            font = ImageFont.truetype(cand, 48)
            break
    lines = ["Beneficiarul depune cererea de rambursare in termen de 30 de zile",
             "de la data efectuarii platii, impreuna cu documentele justificative.",
             "Cheltuielile eligibile se ramburseaza conform contractului de finanțare,",
             "dupa verificarea efectuată de ofițerul de monitorizare."]
    img = Image.new("L", (2480, 3508), 255)  # A4, 300 dpi
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((220, 400 + i * 90), line, font=font or ImageFont.load_default(), fill=0)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.png"
        img.save(path, dpi=(300, 300))
        context = AppContext.start()
        try:
            project = OcrProject.create("self-test", context=context)
            project.add_images([path])
            RecognitionService(project).recognize_pages([1])
            page = project.page(1)
            words = [w.text for a in page.areas for b in a.blocks for line in b.lines
                     for w in line.words]
            result = " ".join(words)
        finally:
            context.close()
    print("recunoscut:", result)
    ok = "rambursare" in result and "finanțare" in result and "ofițerul" in result
    print("SELF-TEST", "OK" if ok else "ESUAT")
    return 0 if ok else 1


def _self_test_logged() -> int:
    """Executabilul fara consola (windowed) nu are `sys.stdout`: rezultatul probei
    se scrie si in `self-test.txt`, langa DocuLens.exe, ca sa-l poata citi CI-ul
    si utilizatorul."""
    import io

    log = _base_dir() / "self-test.txt"
    buffer = io.StringIO()
    previous = sys.stdout
    sys.stdout = buffer
    try:
        code = _self_test()
    except Exception as exc:  # noqa: BLE001 - proba raporteaza orice eroare
        print("SELF-TEST ESUAT:", repr(exc))
        code = 3
    finally:
        sys.stdout = previous
    text = buffer.getvalue()
    try:
        log.write_text(text, encoding="utf-8")
    except OSError:
        pass
    if previous is not None:
        previous.write(text)
    return code


def main() -> int:
    if not getattr(sys, "frozen", False):  # rulat din sursa: radacina proiectului pe cale
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    _use_bundled_tesseract()
    if "--self-test" in sys.argv[1:]:
        return _self_test_logged()
    from app.gui.main import main as gui_main

    return gui_main([a for a in sys.argv if a != "--self-test"])


if __name__ == "__main__":
    sys.exit(main())
