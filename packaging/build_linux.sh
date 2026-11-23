#!/bin/bash
# Y-009: DocuLens pentru Linux (AppImage). Rulare din radacina proiectului:
#     bash packaging/build_linux.sh
# Cere: Python 3.12, tesseract-ocr cu limbile ron/eng din distributie si internet
# numai la construire (pentru appimagetool).
# Rezultat: dist/DocuLens-x86_64.AppImage
set -euo pipefail
cd "$(dirname "$0")/.."

echo "1/5 Mediu Python izolat"
[ -d .venv-build ] || python3.12 -m venv .venv-build
PY=.venv-build/bin/python
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt PySide6 pyinstaller

echo "2/5 Numarul de build (Y-015) si executabilul"
printf '%s' "$(date +%Y.%m.%d)-$(git rev-parse --short HEAD 2>/dev/null || echo local)" \
    > app/core/data/build.txt
"$PY" -m PyInstaller --noconfirm --clean packaging/doculens.spec

echo "3/5 Tesseract si limbile in pachet"
mkdir -p dist/DocuLens/tesseract/tessdata
cp "$(command -v tesseract)" dist/DocuLens/tesseract/tesseract
DATA="$(dirname "$(find /usr/share -name ron.traineddata 2>/dev/null | head -1)")"
for lang in ron eng osd; do cp "$DATA/$lang.traineddata" dist/DocuLens/tesseract/tessdata/; done

echo "4/5 Structura AppDir (intr-un folder nou, cu data in nume)"
APPDIR="dist/DocuLens-$(date +%Y%m%d%H%M%S).AppDir"
mkdir -p "$APPDIR/usr"
cp -r dist/DocuLens "$APPDIR/usr/bin"
printf '#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/usr/bin/DocuLens" "$@"\n' \
    > "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
printf '[Desktop Entry]\nType=Application\nName=DocuLens\nExec=DocuLens %%F\nIcon=doculens\nCategories=Office;Graphics;\nMimeType=application/pdf;image/png;image/jpeg;image/tiff;\n' \
    > "$APPDIR/doculens.desktop"
printf '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" rx="12" fill="#2f6df6"/></svg>' \
    > "$APPDIR/doculens.svg"

echo "5/5 Proba si AppImage"
"$APPDIR/usr/bin/DocuLens" --self-test || { cat "$APPDIR/usr/bin/self-test.txt"; exit 1; }
TOOL=dist/appimagetool
[ -x "$TOOL" ] || { curl -L -o "$TOOL" \
    https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage \
    && chmod +x "$TOOL"; }
ARCH=x86_64 "$TOOL" "$APPDIR" dist/DocuLens-x86_64.AppImage
echo "Gata: dist/DocuLens-x86_64.AppImage"
