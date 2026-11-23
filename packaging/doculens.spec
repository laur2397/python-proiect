# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: DocuLens pentru Windows (onedir). Folosit de
# .github/workflows/build-windows.yml si de packaging/build_windows.ps1:
#     python -m PyInstaller --noconfirm --clean packaging/doculens.spec
# Tesseract si limbile lui se copiaza dupa construire, in dist/DocuLens/tesseract.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH vine de la PyInstaller

# Fisierele citite la rulare, la aceleasi cai relative ca in sursa:
# schema bazei de date (app/core/db.py), datele nucleului, traducerile.
datas = [
    (str(ROOT / "docs" / "spec" / "SPEC_04_schema_bd.sql"), "docs/spec"),
    (str(ROOT / "app" / "core" / "data"), "app/core/data"),
    (str(ROOT / "app" / "gui" / "i18n" / "ro.json"), "app/gui/i18n"),
    (str(ROOT / "app" / "gui" / "i18n" / "en.json"), "app/gui/i18n"),
]
datas.append((str(ROOT / "docs" / "LICENTE_COMPONENTE.md"), "docs"))  # Y-021
manual = ROOT / "docs" / "manual"
if manual.is_dir():
    datas.append((str(manual), "docs/manual"))

binaries = []
hiddenimports = ["app.gui.main", "app.core", "app.gui"]
# pdfium.dll, sabloanele Word/PowerPoint, datele pyHanko
for package in ("pypdfium2", "pypdfium2_raw", "pyhanko", "pyhanko_certvalidator"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden
for package in ("docx", "pptx", "openpyxl"):
    datas += collect_data_files(package)

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "doculens_launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "pytest_qt"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DocuLens",
    console=False,
    upx=False,
)
# Faza 14: linia de comanda, doua executabile de consola in acelasi folder
# (U-001 `DocuLensOCR`, U-020 `DocuLensCompare`; faza_14_pasi.md decizia 1).
consoles = []
for script, name in (("cli_ocr.py", "DocuLensOCR"), ("cli_compare.py", "DocuLensCompare")):
    analysis = Analysis(  # noqa: F821
        [str(ROOT / "packaging" / script)],
        pathex=[str(ROOT), str(ROOT / "packaging")],
        binaries=binaries,
        datas=datas,
        hiddenimports=hiddenimports,
        excludes=["tkinter", "pytest", "pytest_qt", "PySide6"],
        noarchive=False,
    )
    console_exe = EXE(  # noqa: F821
        PYZ(analysis.pure),  # noqa: F821
        analysis.scripts,
        [],
        exclude_binaries=True,
        name=name,
        console=True,
        upx=False,
    )
    consoles.append((console_exe, analysis))

coll = COLLECT(  # noqa: F821
    exe,
    *(item for console_exe, _ in consoles for item in (console_exe,)),
    a.binaries,
    a.datas,
    *(item for _, analysis in consoles for item in (analysis.binaries, analysis.datas)),
    upx=False,
    name="DocuLens",
)

# Y-009: pe macOS pachetul e o aplicatie (.app) pusa apoi intr-un .dmg
# (packaging/build_macos.sh); pe Windows si Linux ramane folderul `DocuLens`.
import sys  # noqa: E402

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name="DocuLens.app",
        bundle_identifier="ro.doculens.app",
        info_plist={"CFBundleShortVersionString": "0.1.0", "NSHighResolutionCapable": True},
    )
