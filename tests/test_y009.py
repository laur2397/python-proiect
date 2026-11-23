"""Programul de instalare pentru Windows: Y-009 (Inno Setup), Y-010 (fara
administrator), Y-011 (instalare din linia de comanda).

Compilarea si instalarea reala se fac numai pe Windows (build_windows.ps1);
aici se verifica ce se poate verifica pe orice sistem: scriptul Inno Setup ia
executabilul construit de PyInstaller, cere implicit drepturi minime si e
compilat de scriptul de construire cu versiunea aplicatiei.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.context import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
ISS = ROOT / "packaging" / "doculens.iss"
BUILD = ROOT / "packaging" / "build_windows.ps1"


def _setup() -> dict[str, str]:
    text = ISS.read_text(encoding="utf-8")
    section = text.split("[Setup]", 1)[1].split("\n[", 1)[0]
    return dict(line.split("=", 1) for line in section.splitlines()
                if "=" in line and not line.startswith(";"))


def test_T_Y009_installer_packs_the_pyinstaller_folder():
    text = ISS.read_text(encoding="utf-8")
    setup = _setup()
    assert setup["AppName"] == "DocuLens"
    assert setup["OutputBaseFilename"] == "DocuLens-Setup-{#AppVersion}"
    assert re.search(r'Source: "\.\.\\dist\\DocuLens\\\*".*recursesubdirs', text)
    assert '{app}\\DocuLens.exe' in text
    spec = (ROOT / "packaging" / "doculens.spec").read_text(encoding="utf-8")
    assert 'name="DocuLens"' in spec  # folderul dist\DocuLens pe care il ia instalarea


def test_T_Y009_build_script_compiles_with_the_app_version():
    build = BUILD.read_text(encoding="utf-8")
    assert "packaging\\doculens.iss" in build and "/DAppVersion=" in build
    assert 'APP_VERSION = "([^"]+)"' in build
    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)
    # pasii sunt in ordine: executabilul inainte de instalare
    assert build.index("PyInstaller") < build.index("doculens.iss")


def test_T_Y010_installs_without_administrator_by_default():
    setup = _setup()
    assert setup["PrivilegesRequired"] == "lowest"
    assert "{autopf}" in setup["DefaultDirName"]  # profilul utilizatorului la `lowest`
    assert "dialog" in setup["PrivilegesRequiredOverridesAllowed"]


def test_T_Y011_silent_install_from_command_line_and_no_network():
    setup = _setup()
    assert "commandline" in setup["PrivilegesRequiredOverridesAllowed"]  # /ALLUSERS, /CURRENTUSER
    text = ISS.read_text(encoding="utf-8")
    body = "\n".join(line for line in text.splitlines() if not line.startswith(";"))
    assert "http" not in body.lower()  # nicio descarcare la instalare (Y-001)
    assert "[UninstallDelete]" in text and "{userappdata}" not in body  # setarile raman
