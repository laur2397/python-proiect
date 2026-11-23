# Faza 15 — Screenshot Reader si integrari

Cerinte: `V-001`…`V-026`, `V-100`…`V-104` (Screenshot Reader), `W-001`…`W-094`,
`W-200`…`W-205` (integrari). 96 de cerinte.

## Pasii

| Pas | Ce | Cerinte |
|---|---|---|
| 15.1 | Nucleul Screenshot Reader (`app/core/screenshot.py`): capturile (zona, fereastra, ecranul, cu intarziere), ultima zona, textul, tabelul, imaginea, trimiterea in fisiere | V-002…V-019, V-023, V-025, V-026 (partea de nucleu) |
| 15.2 | Fereastra Screenshot Reader: combo-urile `Capture` / `Language` / `Send`, cele doua butoane, selectia zonei pe ecran, anularea cu `Esc` / clic dreapta, iconul din bara de sistem cu `Always on Top`, `Run at Startup`, `Enable Sounds`; pornirea ca proces separat si din `Tools > Screenshot Reader` (Lansator, PDF Editor, OCR Editor) | V-001, V-003…V-008, V-020…V-022, V-026, V-100…V-104 |
| 15.3 | Integrarile Windows: o singura instanta (al doilea lansaj trimite fisierele primei), fisierele din linia de comanda si trase in ferestre, comenzile din meniul contextual Explorer (inregistrate per utilizator, fara administrator), PDF-ul implicit si asocierile, conversia formatelor editabile in PDF si „trimiterea”, aplicatia mobila si stocarea in cloud prin folderele locale | W-001…W-017, W-080…W-094, W-200, W-203…W-205 |

## Decizii

1. **Confirmat de utilizator pe 23.11.2026: add-in-urile Office (W-030…W-060,
   W-201, W-202) si SharePoint (W-070…W-075) sunt INCOMPLET.** Add-in-urile cer
   Microsoft Office instalat (CLAUDE.md §6.3), SharePoint e un serviciu online
   (§6.1). Se pot face separat, mai tarziu.
2. [DECIZIE AUTONOMA] **Nucleul nu face capturi de ecran:** capturarea e a
   sistemului de ferestre (Qt, in interfata). `ScreenshotReader` primeste un
   „grabber” (protocolul `ScreenGrabber`) si se ocupa de reguli: zona minima 10×10
   (SPEC_05), intarzierea, ultima zona, recunoasterea, trimiterea. Asa nucleul nu
   importa `gui` (CLAUDE.md §4).
3. [DECIZIE AUTONOMA] **`Timed Screen` (V-006, `D`):** intarzierea e fixa, 5 secunde,
   cum cere V-006. Semnatura din SPEC_05 (`delay_s`) ramane, dar interfata trimite
   intotdeauna 5.
4. [DECIZIE AUTONOMA] **`Send > Text to Microsoft Word` / `Table to Microsoft Excel`
   (V-013, V-014) fara Office:** se scrie un DOCX / XLSX temporar si se deschide cu
   aplicatia implicita (ca `/send` din faza 14, decizia 3). `Image to E-mail`
   (V-019): imaginea se scrie ca BMP si se deschid clientul de e-mail si folderul
   (atasarea automata cere Outlook).
5. [DECIZIE AUTONOMA] **Screenshot Reader ruleaza ca proces separat (V-001):**
   `DocuLens.exe --screenshot-reader`. `Send > Image to OCR Editor` (V-018, V-103,
   proiectul curent sau unul nou) ajunge la aplicatia principala prin canalul de
   instanta unica (W-094); daca aplicatia nu ruleaza, o porneste cu imaginea.
6. [DECIZIE AUTONOMA] **Scurtatura globala (V-024, `N`):** INCOMPLET — Qt nu are
   scurtaturi globale portabile; pe Windows cere `RegisterHotKey` intr-un filtru de
   evenimente native, de verificat pe un calculator real.
7. [DECIZIE AUTONOMA] **Meniul contextual Explorer (W-001…W-017):** comenzile se
   inregistreaza in `HKCU\Software\Classes\SystemFileAssociations\<ext>\shell`
   (per utilizator, fara administrator), ca submeniu „DocuLens”; setarea
   `general.shell_integration` (X-005) le adauga sau le sterge. Numele comenzilor
   sunt ale DocuLens (CLAUDE.md §6.6), nu `ABBYY FineReader PDF`. Comenzile
   pornesc `DocuLens.exe --action <comanda> <fisiere>`. W-016: ce comenzi apar
   depinde de tipul fisierului (cheile pe extensie) si de numarul fisierelor
   (`MultiSelectModel`). W-017: reinstalarea = setarea oprita si pornita.
8. [DECIZIE AUTONOMA] **PDF-ul implicit si asocierile (W-090, W-204):** DocuLens se
   inregistreaza ca program pentru PDF (ProgID `DocuLens.PDF`, per utilizator);
   alegerea finala o face utilizatorul in Setarile Windows, care se deschid
   (Windows 10/11 nu permite programelor sa se faca singure implicite).
9. [DECIZIE AUTONOMA] **Conversia formatelor editabile in PDF (W-012, W-013):** cu
   cititoarele proprii (cele de la comparare): textul si paragrafele. W-014
   (structura, semnele de carte, hyperlinkurile pastrate) e INCOMPLET: cere
   randarea completa a documentelor Office, fara Office. `Convert to PDF and
   send...` deschide clientul de e-mail cu subiectul din W-200
   (`<nume>.pdf (DocuLens)`) si folderul cu PDF-ul.
10. [DECIZIE AUTONOMA] **INCOMPLET, cu motiv:** previzualizarea PDF in Explorer si
    Outlook (W-203, cere o extensie COM nativa in-proces); imprimanta virtuala
    (W-093, W-205, `N`/`X`, cere un driver de imprimanta si administrator).
11. [DECIZIE AUTONOMA] **Aplicatia mobila si cloud-ul (W-080…W-087):** DocuLens nu
    vorbeste cu niciun serviciu (offline); lucreaza cu folderele locale ale
    clientilor de desktop (Google Drive, OneDrive, Dropbox), prin tabul
    `Mobile application` din Lansator (A-107…A-109) si prin salvarea obisnuita.
    Sincronizarea si `Always keep on this device` sunt ale clientului de cloud.
