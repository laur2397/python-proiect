; Y-009: programul de instalare pentru Windows (Inno Setup 6).
; Se compileaza din packaging\build_windows.ps1, dupa PyInstaller:
;     ISCC.exe /DAppVersion=0.1.0 packaging\doculens.iss
; Intrare: dist\DocuLens (executabilul, bibliotecile, Tesseract cu limbile).
; Rezultat: dist\DocuLens-Setup-<versiune>.exe
;
; Y-010: implicit se instaleaza fara drepturi de administrator, in profilul
; utilizatorului (%LOCALAPPDATA%\Programs\DocuLens); expertul ofera si
; instalarea pentru toti utilizatorii, cu administrator.
; Y-011: instalarea fara intrebari, din linia de comanda sau din scripturi de
; desfasurare: DocuLens-Setup-<versiune>.exe /VERYSILENT /SUPPRESSMSGBOXES
; (optional /ALLUSERS sau /CURRENTUSER, /DIR="...").
; Dezinstalarea nu sterge setarile si proiectele din profilul utilizatorului.
; Niciun serviciu, nicio activare, nicio conexiune la internet (Y-001, Y-012).

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6E0B4C1A-7D52-4F0B-9C3E-2A5D8B1F4E70}
AppName=DocuLens
AppVersion={#AppVersion}
AppVerName=DocuLens {#AppVersion}
DefaultDirName={autopf}\DocuLens
DefaultGroupName=DocuLens
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=DocuLens-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\DocuLens.exe
UninstallDisplayName=DocuLens {#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\DocuLens\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\DocuLens"; Filename: "{app}\DocuLens.exe"
; J-001: OCR Editor din meniul Start
Name: "{autoprograms}\DocuLens OCR Editor"; Filename: "{app}\DocuLens.exe"; Parameters: "--action ocr_editor"
; V-001: Screenshot Reader din meniul Start
Name: "{autoprograms}\DocuLens Screenshot Reader"; Filename: "{app}\DocuLens.exe"; Parameters: "--screenshot-reader"
Name: "{autodesktop}\DocuLens"; Filename: "{app}\DocuLens.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DocuLens.exe"; Description: "{cm:LaunchProgram,DocuLens}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; W-017, X-005: comenzile din Explorer, asocierile si pornirea la logare se sterg
Filename: "{app}\DocuLens.exe"; Parameters: "--unregister-integration"; Flags: runhidden waituntilterminated; RunOnceId: "DocuLensIntegration"

[UninstallDelete]
; numai fisierele scrise de proba de la construire, langa executabil
Type: files; Name: "{app}\self-test.txt"
