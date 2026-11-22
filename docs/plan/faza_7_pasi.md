# Faza 7 — PDF Editor: vizualizare, cautare, copiere, comentarii, salvare, tiparire

**Cerinte:** `B-*` (vizualizare si navigare), `C-*` (cautare, inlocuire,
redactare dupa text, copiere), `D-*` (comentarii, marcaje, stampile),
`I-001`…`I-007`, `I-017`…`I-024` (salvare, trimitere, tiparire).
Circa 190 de cerinte, din SPEC_01 si SPEC_10.
**Status:** faza 7 gata (7.1…7.10).

Contractul e `PdfDocument` din SPEC_05 sectiunea 10. Din faza 1 exista partea de
citire (`open`, `render_page`, `page_size`); faza 7 adauga restul, pe pasi.

---

## Pasii

### 7.1 — Documentul: salvarea si textul (nucleu)

- `PdfDocument`: `save` (obiectele nemodificate raman, versiunea PDF nu scade,
  I-001, I-007), `save_as` (I-002), PDF cautabil si doar-imagine (I-003, I-004),
  salvarea unor pagini (I-006), `create_empty`, `from_images`,
  `extract_text`, `has_text_layer`, metadatele, `is_modified`, permisiunile,
  salvarea automata de siguranta si recuperarea (I-024).
- **Gata.** `app/core/pdf/document.py`, testele in `tests/test_pdf_document_save.py`.
  Ceasul de 5 minute al salvarii automate (`AUTOSAVE_INTERVAL_S`) il porneste
  fereastra, in 7.7.

### 7.2a — Cautarea, marcarea rezultatelor, listele de cuvinte cheie (nucleu)

- `search` cu `Exact Match`, `Match Case`, rezultatele in text, comentarii,
  semne de carte, metadate (C-002…C-006); marcarea rezultatelor cu adnotari
  (C-007…C-010); listele de cuvinte cheie in app.db si cautarea cu ele
  (C-027…C-032).
- **Gata.** `app/core/pdf/text.py`, `markup.py`, `keywords.py`; testele in
  `tests/test_pdf_search.py`.

### 7.2b — Inlocuirea si redactarea dupa text (nucleu)

- `replace_text` (C-015…C-018); redactarea rezultatelor si a listelor de
  cuvinte (C-025, C-026), cu verificarea dupa redactare (G-021, CLAUDE.md §6.7).
- **Gata.** `app/core/pdf/redact.py`, `security.py` (numai redactarea; restul
  `SecurityService` in faza 10), `PdfDocument.replace_text`; testele in
  `tests/test_pdf_redact.py`.

### 7.3 — Copierea (nucleu)

- Zona de copiat: ca imagine, ca text, ca tabel cu grila editabila
  (C-040…C-049), pe PDF-uri cu strat de text si pe scanari (OCR pe zona).
- **Gata.** `app/core/pdf/copying.py` (imaginea, textul, selectia peste pagini,
  tabelul cu structura editabila, TSV si HTML pentru clipboard, avertismentul
  C-049); `structure_from_gray` in `app/core/layout/tables.py`; testele in
  `tests/test_pdf_copy.py`. Clipboard-ul il umple interfata (7.8).

### 7.4a — Adnotarile si comentariile (nucleu)

- Adnotari PDF standard, scrise cu pikepdf, cu aspect generat ca sa se vada si
  in alte programe: nota, marcaje pe text, forme, caseta si blocul de text
  (D-001…D-023); comentariile, raspunsurile, statusurile, bifa, filtrele,
  sortarea, stergerea (D-024…D-044).
- **Gata.** `app/core/pdf/annotations.py`, `embedded_font.py`, `AnnotationData`
  in `model.py`, metodele din contract in `PdfDocument`; testele in
  `tests/test_pdf_annotations.py`.

### 7.4b — Stampilele (nucleu)

- Stampilele predefinite, din imagine si de text cu etichete de data si ora,
  biblioteca lor in app.db (tabela `stamp`), plasarea, mutarea si stergerea
  (D-045…D-052, Z-*).
- **Gata.** `app/core/pdf/stamps.py`, `app/core/datetags.py` (Z-001…Z-012),
  `app/core/data/stamps.json`, `app/core/data/date_regions.json`; testele in
  `tests/test_pdf_stamps.py`.

### 7.5 — Navigarea si siguranta (nucleu)

- Semnele de carte, atasamentele, semnaturile listate (B-019…B-025); JavaScript
  dezactivat implicit si confirmarile pentru atasamente, linkuri, formulare
  (B-034…B-041); detectia linkurilor (B-042).
- **Gata.** `app/core/pdf/navigation.py` (semnele de carte, atasamentele,
  linkurile, JavaScript-ul), `app/core/pdf/signatures.py` (lista semnaturilor,
  validata offline cu pyHanko), `BookmarkData` in `model.py`; testele in
  `tests/test_pdf_navigation.py`.

### 7.6 — Recunoasterea in fundal (nucleu)

- Strat de text temporar, nesalvat, pe un singur nucleu, dezactivabil; salvarea
  lui permanenta la cerere (B-028…B-033).
- **Gata.** `app/core/pdf/background.py`, `PdfDocument.page_text`,
  `recognize_in_background`, `recognize_and_store`; cautarea, copierea,
  linkurile si marcajele folosesc stratul temporar. Testele in
  `tests/test_pdf_background.py`.

### 7.7a — Zona de pagina (interfata)

- `app/gui/pdf_view.py`: randarea lenesa cu pagina stricata ca chenar gri,
  cele patru moduri, paginile impare in dreapta, zoom-ul cu limite,
  potrivirile, navigarea, istoricul, uneltele `Select` si `Hand` (cu spatiu),
  transformarea coordonatelor si pe paginile rotite (B-001…B-018,
  B-300…B-302, B-311).
- **Gata.** Testele in `tests/test_gui_pdf_view.py`.

### 7.7b — Fereastra PDF Editor

- Randarea, cele patru moduri de vizualizare, paginile impare in dreapta,
  ecranul complet, zoom-ul, navigarea, istoricul, panoul de navigare cu Pages,
  Bookmarks, Search, Attachments, Signatures, Comments (B-001…B-027,
  B-300…B-314), tab-uri de documente si modul intunecat (B-043, B-044).
- **Gata.** `app/gui/pdf_editor.py` (ribbon-ul cu hamburger si cele cinci
  tab-uri, scurtaturile din SPEC_09 A.2, bara verticala cu panourile, bara de
  jos, tab-urile de documente, ecranul complet, banda JavaScript, recunoasterea
  in fundal la deschidere, salvarea de baza, copia de siguranta la 5 minute),
  `app/gui/pdf_panels.py`; testele in `tests/test_gui_pdf_editor.py`.
  Modul intunecat (B-044, `N`) nu e facut.

### 7.8a — Panoul de cautare

- Tab-urile `FIND`, `REPLACE`, `REDACT`, arborele de rezultate, bifele,
  evidentierea tuturor rezultatelor in pagina, marcarea, inlocuirea,
  redactarea, listele de cuvinte cheie (C-001…C-032, C-100…C-111).
- **Gata.** `app/gui/pdf_search.py`, legat in `pdf_editor.py`; testele in
  `tests/test_gui_pdf_search.py`.

### 7.8b — Selectia de text si zona de copiat

- Selectia directa de text, peste pagini (C-044); zona de copiat cu meniul ei,
  ca imagine, text sau tabel (C-040…C-043, C-049, C-112); grila tabelului si
  toolbarul plutitor de tabel (C-045…C-047, C-113…C-115).
- **Gata.** `app/gui/pdf_selection.py` (un controler pe fiecare document),
  comenzile `Copy`, `Copy Area as Text`, `Copy Area as Table`, `Select All`;
  `AreaTable.merge_rows` si `reanalyze` in nucleu; testele in
  `tests/test_gui_pdf_selection.py`.

### 7.9a — Panoul `Comments`, Undo/Redo, adnotarile din pagina

- Panoul cu filtre, sortare, raspunsuri, statusuri, bifa, proprietati
  (D-024…D-044, D-100…D-105); selectarea, stergerea si dublul clic pe o adnotare
  din pagina (D-008, D-028, D-106); Undo/Redo pe document.
- **Gata.** `app/gui/pdf_comments.py`; Undo/Redo, `modify()` si selectia
  adnotarilor in `pdf_editor.py`; testele in `tests/test_gui_pdf_comments.py`.

### 7.9b — Uneltele de adnotare

- Nota, marcajele pe text, `Insert Text`, formele (Ink, Line, Arrow, Rectangle,
  Oval, Polygon, Cloud, Polyline), caseta si blocul de text, setarile de desen
  (D-001…D-023, D-106); mutarea adnotarilor (D-052).
- **Gata.** `app/gui/pdf_tools.py` (unealta activa pe fiecare document, cu
  previzualizare, `Shift` pentru constrangeri si traseele Ink adunate), bara de
  stil si meniul `Draw ▾` in `pdf_editor.py`, mutarea prin tragere in
  `pdf_selection.py`; testele in `tests/test_gui_pdf_tools.py`.

### 7.9c — Stampilele

- Meniul `Add Stamp`, stampilele livrate, dialogurile de stampila din imagine
  si de text, `Manage Stamps` (D-045…D-052, D-107…D-110, Z-013).
- **Gata.** `app/gui/pdf_stamps.py` (dialogurile), meniul `Add Stamp ▾` si
  plasarea cu un clic in `pdf_editor.py` / `pdf_tools.py`; testele in
  `tests/test_gui_pdf_stamps.py`.

### 7.10 — Salvarea, trimiterea, tiparirea; legaturile

- Meniul `File` (I-001…I-006), trimiterea in OCR Editor si inapoi
  (I-017…I-019), e-mailul (I-020, D-053), tiparirea (I-021, I-022),
  avertismentul la inchidere (I-023); Lansatorul deschide PDF-urile in PDF
  Editor (A-010, A-011), nu in aplicatia sistemului.
- **Gata.** Meniurile `Save As ▾` (PDF, cautabil, doar-imagine, optiuni) si
  `Recognize ▾` (cu trimiterea in OCR Editor), salvarea paginilor selectate,
  e-mailul (mesaj `.eml` cu PDF-ul atasat, offline), tiparirea cu tabul propriu
  (`app/gui/pdf_print.py`), ajutorul (F1); `app/gui/application.py` deschide
  PDF-urile in PDF Editor, iar OCR Editor si PDF Editor isi trimit documentele
  unul altuia. Testele in `tests/test_gui_pdf_file.py` si
  `tests/test_gui_application.py`.

## Ce ramane marcat INCOMPLET dupa faza 7

- Motorul JavaScript (B-038, decizia 19; intrebare in STARE.md).
- Inlocuirea de text pe PDF-uri vectoriale face pagina imagine cu strat de text
  (decizia 11; editarea reala vine cu faza 9).
- Din optiunile B-032 (recunoasterea permanenta) se folosesc limbile; orientarea
  si deskew-ul nu (decizia 20).
- Increderea in semnatari se verifica abia in faza 10 (decizia 18).
- Comenzile paginilor (tabul `Organize Pages`, toolbarul panoului `Pages`) vin
  in faza 8; editarea continutului in faza 9; securitatea in faza 10;
  formularele in faza 11; compararea in faza 12.
- Modul intunecat (B-044, `N`, optional) nu e facut.

---

## Decizii autonome

1. **[DECIZIE AUTONOMA] Doua biblioteci, doua roluri.** PDFium (pypdfium2)
   randeaza si citeste textul; pikepdf modifica si salveaza. Dupa fiecare
   modificare, PDFium reciteste documentul din memorie, ca imaginea sa arate
   exact ce se va salva.
2. **[DECIZIE AUTONOMA] Adnotarile sunt adnotari PDF standard** (`/Highlight`,
   `/Text`, `/Square`, `/FreeText`, `/Stamp`...), cu aspect (`/AP`) generat de
   noi, nu un format propriu: documentul arata la fel in orice cititor PDF.
3. **[DECIZIE AUTONOMA] CI-ul.** La 22.11.2026 GitHub nu a pornit joburile
   (problema de plata a contului, mesajul din adnotarile joburilor). Cat timp
   se intampla asta, verificarile ruleaza local inainte de fiecare commit, iar
   CI-ul se reia singur cand contul e in regula.
4. **[DECIZIE AUTONOMA] `save_as` primeste in plus `pages`, `context`, `engine`.**
   Semnatura din SPEC_05 (`save_as(path, *, options=None)`) ramane valabila;
   argumentele noi sunt optionale: `pages` pentru salvarea unor pagini (I-006),
   `context` pentru proiectul OCR temporar, `engine` pentru motorul OCR din teste.
   La fel `from_images(..., context, engine)`, plus `autosave`, `find_recovery`,
   `recover`, dupa modelul `OcrProject` (I-024 nu are metode in contract).
5. **[DECIZIE AUTONOMA] PDF cautabil si doar-imagine din PDF Editor** trec prin
   acelasi drum ca OCR Editor-ul: proiect temporar, recunoastere (numai pentru
   cautabil), exportul PDF din faza 6. Documentul deschis trece pe fisierul nou.
6. **[DECIZIE AUTONOMA] Salvarea minim modificatoare (I-007)** foloseste pikepdf
   cu fluxurile copiate octet cu octet si versiunea minima egala cu cea a
   fisierului. Nu e o actualizare incrementala (pikepdf rescrie structura), dar
   continutul obiectelor neatinse ramane identic. Un fisier criptat se
   recripteaza, deci acolo copierea octet cu octet nu se poate.
7. **[DECIZIE AUTONOMA] Metadatele pe un fisier protejat** (SPEC_05: „campurile
   sunt blocate”, fara exceptie numita) dau `NoWritePermissionError`.
8. **[DECIZIE AUTONOMA] Pasul 7.2 s-a impartit in 7.2a si 7.2b**, ca fiecare
   commit sa ramana mic: cautarea si marcajele intai, apoi inlocuirea si
   redactarea, care rescriu continutul paginii.
9. **[DECIZIE AUTONOMA] Rezultatele cautarii** sunt tupluri `(pagina,
   dreptunghi, context)`, ca in SPEC_05, de tipul `SearchHit`, care adauga
   sursa (C-002 cere gruparea pe sursa, iar tuplul din contract nu o spune),
   pozitia si dreptunghiurile pe randuri. Coordonatele: puncte, originea
   sus-stanga a MediaBox-ului. Cautarea trateaza ş/ș si ţ/ț ca aceeasi litera
   (CLAUDE.md §6.4).
10. **[DECIZIE AUTONOMA] Culorile implicite ale marcajelor** (C-010) sunt
    setarile `pdf_editor.markup_color.*`, cu paleta proprie; nu apar in
    dialogul Options al OCR Editor-ului, ci se schimba din bara PDF Editor-ului
    (pasul 7.9).
11. **[DECIZIE AUTONOMA] Redactarea si inlocuirea reconstruiesc pagina atinsa**:
    imaginea ei la 300 dpi, fara adnotari, cu zonele acoperite (culoarea
    redactarii sau fondul detectat, C-018) si textul nou desenat, plus un strat
    de text invizibil numai cu caracterele ramase si cu textul nou. Continutul
    vechi al paginii iese din fisier, deci textul redactat nu mai poate fi
    recuperat, iar verificarea G-021 il cauta din nou si anuleaza operatia daca
    il gaseste. Pretul: pagina atinsa devine imagine cu strat de text (pe un
    PDF scanat nu se schimba nimic, C-018).
    **INCOMPLET, marcat:** pe un PDF cu text vectorial, inlocuirea ar trebui sa
    editeze textul cu fontul documentului; asta vine cu editarea de continut
    (F-*, faza 9), care va inlocui drumul de aici pentru paginile cu text.
12. **[DECIZIE AUTONOMA] Tabelul copiat** (C-045) foloseste aceeasi analiza ca
    OCR Editor-ul, pe imaginea zonei la 300 dpi, cu doua praguri in plus:
    marginile albe ale zonei se taie, o linie trasa are cel putin 30 pt, iar
    doua coloane fara linii sunt despartite de cel putin 10 pt. Altfel un rand
    de text simplu se rupea in coloane la fiecare litera. Textul celulelor vine
    din stratul de text, pe scanari din recunoasterea zonei.
13. **[DECIZIE AUTONOMA] Pasul 7.4 s-a impartit in 7.4a si 7.4b** (adnotarile,
    apoi stampilele cu biblioteca lor).
14. **[DECIZIE AUTONOMA] Identificatorul unei adnotari** e numarul obiectului ei
    in documentul deschis (PDF-ul nu are id-uri numerice). Ramane valabil cat
    timp documentul e deschis; dupa salvare interfata reciteste lista.
    Raspunsurile sunt adnotari `/Text` cu `/IRT`, statusurile adnotari de stare
    (`/StateModel Review`, istoricul ramane in fisier), bifa `/StateModel
    Marked`, ca in standardul PDF, deci le vad si alte programe.
15. **[DECIZIE AUTONOMA] Textul casetelor** foloseste un font de sistem cu
    diacritice (Arial, DejaVu Sans...), incorporat ca subset; fara un astfel de
    font, Helvetica standard (ș si ț devin varianta cu sedila). Marcajele pe
    text pe o pagina fara strat de text dau `NoTextFoundError` (D-003), iar
    interfata porneste recunoasterea in fundal (7.6) si reia.
16. **[DECIZIE AUTONOMA] Etichetele de data si ora (Z-001…Z-012)** sunt
    implementate acum, in `app/core/datetags.py`, pentru ca D-049 (faza 7) le
    cere; antetele si numerotarea Bates din faza 9 le vor folosi la fel.
    Formatele proprii se scriu in locul codului de regiune (`<d=%#d %B %Y/>`).
    Regiunea implicita e cea a sistemului (variabilele de locale), altfel ROM.
    Numele lunilor si formatele regionale sunt date, in
    `app/core/data/date_regions.json` (ROM, USA, ENG, RUS, HUN, CZ).
17. **[DECIZIE AUTONOMA] Stampilele livrate** (D-045) sunt ale noastre:
    APROBAT, RESPINS, FINAL (cu data si ora, D-107), CIORNĂ, CONFIDENȚIAL,
    PRIMIT, VERIFICAT, PENTRU OBSERVAȚII, cu textul in romana si engleza in
    `app/core/data/stamps.json`. In tabela `stamp` stau cu `is_builtin = 1` si
    cheia ca nume; textul se alege la plasare, dupa limba interfetei. Cele care
    au un nume standard in PDF (Approved, Final, Draft...) il primesc in `/Name`.
18. **[DECIZIE AUTONOMA] pyHanko intra in dependente** (MIT, era deja in stiva
    din CLAUDE.md §5) pentru lista semnaturilor (B-024). Validarea ruleaza
    strict offline (`allow_fetching=False`, fara radacini de incredere): starea
    spune daca semnatura e intacta si daca documentul s-a schimbat dupa
    semnare; increderea in semnatar ramane necunoscuta pana la faza 10, cand
    se vor putea folosi certificatele utilizatorului.
19. **[DECIZIE AUTONOMA] JavaScript (B-037…B-041).** Detectia scripturilor,
    regula de activare (implicit dezactivat, activare pentru un document sau
    pentru toate) si limita de 2 secunde sunt gata. **INCOMPLET, marcat:**
    DocuLens nu are un motor JavaScript, deci scripturile nu ruleaza inca.
    Motorul se alege la formulare (faza 11, H-006, H-058); propunerea e
    QuickJS (MIT). Intrebarea e trecuta in STARE.md.
20. **[DECIZIE AUTONOMA] Stratul de text temporar** (B-028) e un `PageText` in
    memorie pe pagina (`PdfDocument._ocr_layer`), cu pozitia fiecarui caracter
    calculata din cuvintele recunoscute. `page_text()` il da cand pagina nu
    are text in fisier; `extract_text()` si `has_text_layer()` raman ale
    fisierului (B-029). O pagina rescrisa (redactare, inlocuire) isi pierde
    stratul temporar. Stratul permanent (B-032) se adauga dupa continutul
    paginii, izolat cu q/Q, deci imaginea ramane neatinsa. **INCOMPLET,
    marcat:** din optiunile B-032 se folosesc limbile; orientarea si deskew-ul
    nu se aplica inca.
21. **[DECIZIE AUTONOMA] Zona de pagina deseneaza numai ce se vede.** Paginile
    sunt asezate intr-un spatiu virtual, iar fereastra vizibila se picteaza
    deplasata cu derularea (`QAbstractScrollArea`). Un singur widget cu toate
    paginile nu merge: Qt nu picteaza widgeturi mai inalte de ~32000 de pixeli,
    adica vreo 30 de pagini A4 la latimea ecranului (testul cu 40 de pagini).
22. **[DECIZIE AUTONOMA] Pasul 7.7 s-a impartit** in 7.7a (zona de pagina) si
    7.7b (ribbon-ul, panourile, bara de jos, tab-urile de documente).
23. **[DECIZIE AUTONOMA] Recunoasterea in fundal ruleaza pe firul ferestrei**,
    cate o pagina la fiecare pas de cronometru, cu evenimentele procesate in
    timpul recunoasterii, ca restul operatiilor lungi (faza_6b_pasi.md,
    decizia 11): conexiunile SQLite si documentul pikepdf nu se folosesc din
    alte fire. Interfata raspunde intre pagini.
24. **[DECIZIE AUTONOMA] Comenzile care vin in pasii sau fazele urmatoare** se
    vad in ribbon si in meniul principal, dezactivate, cu pasul sau faza in
    tooltip (`LATER` din `pdf_editor.py`), ca structura sa fie cea din B-200…B-207
    de acum.
25. **[DECIZIE AUTONOMA] Clipboard-ul in teste.** Pe platforma offscreen a Qt
    (folosita in teste si in CI), un `QMimeData` lasat in clipboard face ca
    procesul sa cada la iesire; pe macOS nativ nu. `tests/conftest.py` goleste
    clipboard-ul dupa fiecare test. In aplicatie, ce s-a copiat ramane in
    clipboard si dupa inchidere.
26. **[DECIZIE AUTONOMA] Undo/Redo in PDF Editor** pastreaza starea intreaga a
    documentului inainte de fiecare modificare (cel mult 20 de pasi pe
    document): adnotari, marcaje, inlocuire, redactare. Simplu si sigur;
    pentru documente foarte mari, costul e o salvare in memorie pe pas.
27. **[DECIZIE AUTONOMA] Pasul 7.9 s-a impartit** in 7.9a (panoul `Comments`,
    Undo/Redo), 7.9b (uneltele de adnotare) si 7.9c (stampilele).
