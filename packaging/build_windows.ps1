# Construieste DocuLens.exe pe un calculator cu Windows 10/11 (64 de biti).
# Rulare, din radacina proiectului, in PowerShell:
#     powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
# Cere: Python 3.12 instalat (python.org, cu "Add to PATH") si internet
# (numai pentru construire; programul rezultat lucreaza offline).
# Rezultat: dist\DocuLens-Setup-<versiune>.exe (programul de instalare, Y-009),
# dist\DocuLens-windows.zip (varianta portabila) si folderul dist\DocuLens.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "1/6 Mediu Python izolat"
if (-not (Test-Path .venv-build)) { python -m venv .venv-build }
$py = ".venv-build\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt PySide6 pyinstaller

Write-Host "2/6 Tesseract (UB Mannheim)"
# Instalarea fara drepturi de administrator il pune in profilul utilizatorului,
# nu in Program Files; se cauta in toate locurile obisnuite.
function Find-Tesseract {
    $candidates = @(
        "$env:ProgramFiles\Tesseract-OCR",
        "${env:ProgramFiles(x86)}\Tesseract-OCR",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR",
        "$env:LOCALAPPDATA\Tesseract-OCR"
    )
    foreach ($key in @("HKLM:\SOFTWARE\Tesseract-OCR", "HKCU:\SOFTWARE\Tesseract-OCR",
                       "HKLM:\SOFTWARE\WOW6432Node\Tesseract-OCR")) {
        $item = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
        if ($item -and $item.InstallDir) { $candidates = @($item.InstallDir) + $candidates }
    }
    $cmd = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    if ($cmd) { $candidates = @((Split-Path -Parent $cmd.Source)) + $candidates }
    foreach ($dir in $candidates) {
        if ($dir -and (Test-Path (Join-Path $dir "tesseract.exe"))) { return $dir }
    }
    return $null
}
$tessDir = Find-Tesseract
if (-not $tessDir) {
    winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements
    $tessDir = Find-Tesseract
}
if (-not $tessDir) {
    throw "Nu gasesc tesseract.exe. Instaleaza-l manual (github.com/UB-Mannheim/tesseract/wiki) si ruleaza din nou."
}
Write-Host "Tesseract gasit in $tessDir"

Write-Host "3/6 Executabilul"
& $py -m PyInstaller --noconfirm --clean packaging\doculens.spec

Write-Host "4/6 Tesseract si limbile in pachet"
$dest = "dist\DocuLens\tesseract"
Copy-Item -Recurse -Force $tessDir $dest
foreach ($lang in @("ron", "eng", "osd")) {
    $f = "$dest\tessdata\$lang.traineddata"
    if (-not (Test-Path $f)) {
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/$lang.traineddata" -OutFile $f
    }
}

Write-Host "5/6 Proba si arhiva"
$p = Start-Process -FilePath "dist\DocuLens\DocuLens.exe" -ArgumentList "--self-test" -Wait -PassThru
Get-Content -Encoding UTF8 "dist\DocuLens\self-test.txt" | Out-Host
if ($p.ExitCode -ne 0) { throw "Proba executabilului a esuat" }
Compress-Archive -Force -Path "dist\DocuLens" -DestinationPath "dist\DocuLens-windows.zip"

Write-Host "6/6 Programul de instalare (Inno Setup)"
function Find-Iscc {
    foreach ($dir in @("${env:ProgramFiles(x86)}\Inno Setup 6", "$env:ProgramFiles\Inno Setup 6",
                       "$env:LOCALAPPDATA\Programs\Inno Setup 6")) {
        if (Test-Path "$dir\ISCC.exe") { return "$dir\ISCC.exe" }
    }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}
$iscc = Find-Iscc
if (-not $iscc) {
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    $iscc = Find-Iscc
}
if (-not $iscc) { throw "Nu gasesc ISCC.exe (Inno Setup 6). Instaleaza-l de pe jrsoftware.org si ruleaza din nou." }
$version = (Select-String -Path "app\core\context.py" -Pattern 'APP_VERSION = "([^"]+)"').Matches[0].Groups[1].Value
& $iscc "/DAppVersion=$version" "packaging\doculens.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup a esuat" }
Write-Host "Gata: dist\DocuLens-Setup-$version.exe (instalare) si dist\DocuLens-windows.zip (portabil)"
