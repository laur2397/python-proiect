# Faza 6d — Scanarea si fotografiile de documente

**Cerinte:** `K-002`…`K-017` (SPEC_02), plus tabul `Scan` al Lansatorului
(`A-080`…`A-090`, SPEC_01), lasat din faza 6c pentru ca cere modulul de scanare.
**Status:** 6d.1, 6d.2 gata; urmeaza 6d.3.

**Dupa faza 6d urmeaza oprirea obligatorie (CLAUDE.md §11):** prima versiune
folosibila, verificata de utilizator inainte de faza 7.

---

## Pasii

### 6d.1 — Nucleul scanarii

- `app/core/images/scanner.py`: `ScanSettings` (modul de culoare K-005,
  luminozitatea 0-100 K-006, rezolutia K-007, decuparea K-008, duplex K-009,
  alimentatorul K-010, pauza K-011, previzualizarea K-012), avertismentele
  (luminozitate prea mica sau prea mare; rezolutie sub 250, peste 600, diferita
  pe orizontala si verticala sau nestandard), `ScanDevice` cu capabilitatile lui
  (duplex si ADF numai daca le raporteaza), `ScannerBackend` (interfata),
  `ScanSession`: lista de dispozitive reinterogata la fiecare deschidere (K-003),
  scanarea paginilor si adaugarea lor in proiect, cu prelucrarea automata din
  setari; erorile `NoScannerError` (niciun scaner) si `ScannerError` (hartie
  blocata la ADF: mesaj si oprire). Interfata driverului care nu merge revine la
  interfata proprie (K-004). Teste cu un dispozitiv simulat, in teste.
- Paginile alaturate (K-013) folosesc setarea si unealta `Split` existente.

**Gata:** `app/core/images/scanner.py`: `ScanSettings` si `ScannerService` ca in
SPEC_05, avertismentele (luminozitate in afara 30-70, rezolutie sub 250, peste
600, nestandard, diferita pe orizontala si verticala), validarea dupa
capabilitati (duplex, ADF, rezolutii, moduri de culoare), `ScanSession`:
dispozitivele reinterogate la fiecare deschidere, previzualizarea la 75 dpi,
ADF cu tot alimentatorul, duplex, hartia blocata care opreste fara pagini
partiale, pauza intre scanarile pe geam, anularea care pastreaza foile deja
scanate, revenirea la interfata proprie, paginile adaugate in proiect cu
prelucrarea automata. Teste: `tests/test_scanner.py` (dispozitiv simulat).

### 6d.2 — Dispozitivele WIA

- Backend WIA (Windows Image Acquisition) prin `comtypes` (MIT): dispozitivele,
  capabilitatile, scanarea cu setarile din 6d.1. Se incarca numai pe Windows;
  pe celelalte sisteme lista de dispozitive e goala si mesajul spune de ce.

**Gata:** `app/core/images/wia.py` (`WiaScanner`, `default_scanner`): numai
scanerele din lista WIA, capabilitatile din proprietatile driverului (ADF,
duplex, rezolutii), maparea setarilor pe proprietatile WIA (intentia de culoare,
rezolutia egala pe ambele axe, luminozitatea 0-100 → -1000…1000), alimentatorul
pana se goleste, hartia blocata si alimentatorul gol ca `ScannerError`,
previzualizarea la 75 dpi, interfata driverului cu revenire la cea proprie.
`comtypes` (MIT) numai pe Windows. Testul Q-065 („fara automatizare Office”)
permite `comtypes` numai in modulul WIA si interzice acum identificatorii COM
ai Office in tot nucleul. Teste: `tests/test_wia.py`, cu obiecte COM simulate.
**De verificat de utilizator:** scanarea pe un aparat real, pe Windows.

### 6d.3 — Interfata scanarii

- Dialogul `Scan Pages...` din OCR Editor (K-002, `Ctrl+K`): dispozitivul,
  `Preview`, setarile, `Scan`, apoi `Scan Again` / `Finish Scanning` (A-082).
- `Select Device...` din Options (X-404, X-407).
- Tabul `Scan` din Lansator (A-080…A-090): cele sase sarcini, pasii comuni,
  setarile fiecarui format (PDF cu `Recognize text on images`, Word, Excel,
  imagini cu compresia TIFF, alte formate), `Image preprocessing settings...`.

### 6d.4 — Fotografiile de documente

- Recomandarile pentru fotografiere (K-014…K-016), accesibile din meniul Help
  si din Lansator; `Photo Correction` din Image Editor pentru pozele neclare
  (K-017, unealta existenta).

---

## Decizii autonome

1. **[DECIZIE AUTONOMA] Fara `pytwain`.** Biblioteca indicata in
   `docs/MASTER_PROMPT.md` pentru TWAIN e GPLv2 (verificat in metadatele
   pachetului 2.3.0), deci nu se foloseste (CLAUDE.md §9, §11). WIA se face prin
   `comtypes` (MIT, verificat in metadatele pachetului 1.5.0).
2. **[DECIZIE AUTONOMA] TWAIN mai tarziu, printr-o legatura proprie.** K-003
   cere „TWAIN sau WIA”. TWAIN se poate face fara GPL, cu o legatura `ctypes`
   proprie la managerul de surse al sistemului (TWAINDSM, instalat de driverele
   scanerelor, incarcat la rulare, nedistribuit de noi). Fara un scaner real
   legatura nu se poate verifica; ramane INCOMPLET si intra in lista pentru
   utilizator la oprirea de dupa 6d.
3. **[DECIZIE AUTONOMA] Testele scanarii folosesc un dispozitiv simulat.**
   Regulile (setari, avertismente, capabilitati, ADF, pauza, erori) se verifica
   in CI; scanarea cu un aparat real o verifica utilizatorul la oprire.
