# Construieste DocuLens.exe pe un calculator cu Windows 10/11 (64 de biti).
# Rulare, din radacina proiectului, in PowerShell:
#     powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
# Cere: Python 3.12 instalat (python.org, cu "Add to PATH") si internet
# (numai pentru construire; programul rezultat lucreaza offline).
# Rezultat: dist\DocuLens-windows.zip, plus folderul dist\DocuLens.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "1/5 Mediu Python izolat"
if (-not (Test-Path .venv-build)) { python -m venv .venv-build }
$py = ".venv-build\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt PySide6 pyinstaller

Write-Host "2/5 Tesseract (UB Mannheim)"
$tessDir = "C:\Program Files\Tesseract-OCR"
if (-not (Test-Path "$tessDir\tesseract.exe")) {
    winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements
}
if (-not (Test-Path "$tessDir\tesseract.exe")) { throw "Tesseract nu s-a instalat in $tessDir" }

Write-Host "3/5 Executabilul"
& $py -m PyInstaller --noconfirm --clean packaging\doculens.spec

Write-Host "4/5 Tesseract si limbile in pachet"
$dest = "dist\DocuLens\tesseract"
Copy-Item -Recurse -Force $tessDir $dest
foreach ($lang in @("ron", "eng", "osd")) {
    $f = "$dest\tessdata\$lang.traineddata"
    if (-not (Test-Path $f)) {
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/$lang.traineddata" -OutFile $f
    }
}

Write-Host "5/5 Proba si arhiva"
$p = Start-Process -FilePath "dist\DocuLens\DocuLens.exe" -ArgumentList "--self-test" -Wait -PassThru
Get-Content "dist\DocuLens\self-test.txt" | Out-Host
if ($p.ExitCode -ne 0) { throw "Proba executabilului a esuat" }
Compress-Archive -Force -Path "dist\DocuLens" -DestinationPath "dist\DocuLens-windows.zip"
Write-Host "Gata: dist\DocuLens-windows.zip"
