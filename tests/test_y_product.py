"""Faza 16, pasul 16.2: localizarea, licentele, produsul fara activare si editii,
cerintele de sistem (Y-002…Y-008, Y-012, Y-020, Y-021, Y-130…Y-140, Y-316)."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "app" / "gui" / "i18n"

DISPLAY_CALLS = {"setText", "setToolTip", "setWindowTitle", "setPlaceholderText", "QLabel",
                 "QPushButton", "QCheckBox", "QRadioButton", "QAction", "QGroupBox", "addItem",
                 "addAction", "addMenu", "setTitle", "showMessage", "information", "warning",
                 "question", "critical", "setStatusTip"}
LOGGERS = {"_log", "log", "logger", "_logger"}
WORD = re.compile(r"[A-Za-zĂÂÎȘȚăâîșț]{2,}")
TECHNICAL = re.compile(r"^(https?://|mailto:|file://)")


def _literal_display_texts() -> list[str]:
    found = []
    for path in sorted((ROOT / "app" / "gui").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name not in DISPLAY_CALLS:
                continue
            owner = getattr(getattr(func, "value", None), "id", "")
            if owner in LOGGERS:
                continue  # jurnalul nu e text afisat
            args = node.args[:1] if name == "addItem" else node.args[:3]  # addItem(text, data)
            for arg in args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and \
                        WORD.search(arg.value) and not TECHNICAL.search(arg.value):
                    found.append(f"{path.relative_to(ROOT)}:{node.lineno}: {arg.value!r}")
    return found


def test_T_Y316_Y020_no_display_text_in_code():
    """Y-316, Y-020, CLAUDE.md §6.5: textele afisate vin din fisierele de traducere."""
    assert _literal_display_texts() == []


def test_T_Y020_romanian_and_english_complete():
    ro = json.loads((I18N / "ro.json").read_text(encoding="utf-8"))
    en = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
    assert set(ro) == set(en)
    assert not [k for k, v in {**ro, **en}.items() if not str(v).strip()]


def test_T_Y021_component_licenses_listed_and_no_agpl():
    text = (ROOT / "docs" / "LICENTE_COMPONENTE.md").read_text(encoding="utf-8")
    requirements = [re.split(r"[<>=;\s]", line.strip())[0]
                    for line in (ROOT / "requirements.txt").read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
    for name in requirements:
        assert name.lower() in text.lower(), name
    rows = [line for line in text.splitlines() if line.startswith("| ") and "AGPL" in line]
    assert rows == []
    sources = " ".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py"))
    assert "import fitz" not in sources and "import pymupdf" not in sources.lower()
    spec = (ROOT / "packaging" / "doculens.spec").read_text(encoding="utf-8")
    assert "LICENTE_COMPONENTE.md" in spec  # se livreaza cu programul


def test_T_Y012_Y013_Y136_Y137_no_activation_registration_or_trial():
    """Fara activare, inregistrare sau perioada de proba: nicio limita de timp sau de
    pagini legata de licenta in cod (limita Hot Folder e o setare, S-006)."""
    sources = {p: p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py")}
    for path, text in sources.items():
        low = text.lower()
        for word in ("product_key", "activation_key", "trial_days", "license_key",
                     "registration_code"):
            assert word not in low, (path, word)
    ro = json.loads((I18N / "ro.json").read_text(encoding="utf-8"))
    assert "activare" in ro["about.notice"] and "înregistrare" in ro["about.notice"]


def test_T_Y130_Y133_Y134_all_features_without_editions():
    """Y-133: fara editii; Hot Folder, sarcinile automate si compararea (ce era
    Corporate, Y-130…Y-132) sunt in meniurile oricarei instalari."""
    from app.gui.main_window import MainWindow

    tools = MainWindow.menu_layout()["tools"]
    assert {"compare_documents", "automated_tasks", "hot_folder"} <= set(tools)
    sources = " ".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py"))
    for gate in ("is_corporate", "edition ==", "EDITION", "license_level"):
        assert gate not in sources  # nicio functie conditionata de o editie


def test_T_Y138_ribbon_organize_pages_64_bit():
    """Y-138: interfata ribbon si `Organize Pages` in PDF Editor; pachet pe 64 de biti."""
    from app.gui.pdf_editor import RIBBON_TABS

    assert "organize" in RIBBON_TABS or any("organize" in k for k in RIBBON_TABS)
    iss = (ROOT / "packaging" / "doculens.iss").read_text(encoding="utf-8")
    assert "ArchitecturesAllowed=x64compatible" in iss


def test_T_Y002_Y003_Y004_Y005_system_requirements_declared():
    """Y-002…Y-004: Windows 10/11 pe 64 de biti (programul de instalare refuza restul);
    Y-005: pe servere de terminal fiecare utilizator are instanta lui (canalul de
    instanta unica e per utilizator)."""
    iss = (ROOT / "packaging" / "doculens.iss").read_text(encoding="utf-8")
    assert "MinVersion=10.0" in iss
    from app.gui.instance import server_name

    assert server_name().startswith("DocuLens-") and len(server_name()) > len("DocuLens-")
    doc = (ROOT / "docs" / "cerinte_sistem.md").read_text(encoding="utf-8")
    for word in ("Windows 10", "64", "RAM", "GB"):
        assert word in doc


def test_T_Y006_wia_scanning_available():
    """Y-006: WIA e facut (faza 6d); TWAIN e INCOMPLET (faza_6d_pasi.md, decizia 2)."""
    from app.core.images import wia

    assert hasattr(wia, "WiaScanner") and callable(wia.default_scanner)


def test_T_Y007_Y008_office_files_read_without_office(tmp_path):
    """Y-007: formatele editabile cu biblioteci proprii; Y-008: fisierele scrise de
    Word, Excel, PowerPoint (OOXML) si LibreOffice (ODF) se citesc."""
    from docx import Document
    from openpyxl import Workbook
    from pptx import Presentation

    from app.core.compare.sources import editable_blocks

    doc = Document()
    doc.add_paragraph("Contract de finanțare")
    doc.save(tmp_path / "a.docx")
    book = Workbook()
    book.active["A1"] = "Buget"
    book.save(tmp_path / "a.xlsx")
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = "Prezentare"
    deck.save(tmp_path / "a.pptx")
    texts = {ext: " ".join(t for _k, t in editable_blocks(tmp_path / f"a.{ext}"))
             for ext in ("docx", "xlsx", "pptx")}
    assert "finanțare" in texts["docx"] and "Buget" in texts["xlsx"]
    assert "Prezentare" in texts["pptx"]
    sources = " ".join(p.read_text(encoding="utf-8") for p in (ROOT / "app").rglob("*.py"))
    assert "Word.Application" not in sources and "Excel.Application" not in sources


def test_T_Y135_Y140_reference_is_the_windows_product():
    """Y-135: referinta e produsul Windows (cu Hot Folder); Y-140: imprimanta virtuala
    a fost retrasa din original, la noi e INCOMPLET (faza_15_pasi.md, decizia 10)."""
    plan = (ROOT / "docs" / "plan" / "faza_15_pasi.md").read_text(encoding="utf-8")
    assert "imprimanta virtuala" in plan
    from app.gui.main_window import MainWindow

    assert "hot_folder" in MainWindow.menu_layout()["tools"]
