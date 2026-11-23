#!/bin/bash
# Y-009: DocuLens pentru macOS (.dmg). Rulare din radacina proiectului:
#     bash packaging/build_macos.sh
# Cere: Python 3.12, Homebrew (pentru Tesseract) si internet numai la construire.
# Rezultat: dist/DocuLens.app si dist/DocuLens-macos.dmg
set -euo pipefail
cd "$(dirname "$0")/.."

echo "1/5 Mediu Python izolat"
[ -d .venv-build ] || python3.12 -m venv .venv-build
PY=.venv-build/bin/python
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt PySide6 pyinstaller

echo "2/5 Tesseract"
command -v tesseract >/dev/null || brew install tesseract tesseract-lang

echo "3/5 Numarul de build (Y-015) si executabilul"
printf '%s' "$(date +%Y.%m.%d)-$(git rev-parse --short HEAD 2>/dev/null || echo local)" \
    > app/core/data/build.txt
"$PY" -m PyInstaller --noconfirm --clean packaging/doculens.spec

echo "4/5 Tesseract si limbile in pachet"
APP=dist/DocuLens.app/Contents/MacOS
mkdir -p "$APP/tesseract/tessdata"
cp "$(command -v tesseract)" "$APP/tesseract/tesseract"
DATA="$(brew --prefix)/share/tessdata"
for lang in ron eng osd; do cp "$DATA/$lang.traineddata" "$APP/tesseract/tessdata/"; done

echo "5/5 Proba si imaginea .dmg"
"$APP/DocuLens" --self-test || { cat "$APP/self-test.txt"; exit 1; }
"$APP/DocuLensOCR" /version
hdiutil create -volname DocuLens -srcfolder dist/DocuLens.app -ov -format UDZO \
    dist/DocuLens-macos.dmg
echo "Gata: dist/DocuLens-macos.dmg"
