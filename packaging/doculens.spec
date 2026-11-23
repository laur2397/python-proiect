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
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    upx=False,
    name="DocuLens",
)
