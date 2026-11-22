# MASTER PROMPT - Construirea unei alternative desktop la ABBYY FineReader PDF 16 (Corporate)

> Copiaza acest document integral intr-o conversatie noua cu un AI programator.
> Versiune specificatie: **5.0**, 19 noiembrie 2026.
> Sursa: documentatia publica ABBYY FineReader PDF 16 (build 16.0.14.7295) **plus 22 de tutoriale video analizate cadru cu cadru** (doua webinarii oficiale ABBYY de 56 si 26 de minute, 12 tutoriale scurte oficiale, 8 independente). Textele de interfata din sectiunea 6 sunt citite de pe ecran, nu inventate.

---

## 0.0 CITESTE ASTA INAINTE DE ORICE

Acest document este **harta**. Specificatia executabila e in cele 7 fisiere de mai jos, care se livreaza impreuna cu el. Nu incepe sa scrii cod pana nu le-ai citit pe toate.

| Fisier | Ce conține |
|---|---|
| `SPEC_01_lansator_si_pdf_editor.md` | 409 cerinte A-001 … I-033: Lansator, PDF Editor, cautare, copiere de continut, comentarii, pagini, editare, securitate, formulare, export |
| `SPEC_02_ocr_editor.md` | 358 de cerinte J-001 … Q-065: OCR Editor, achizitie, preprocesare, zone, recunoastere, verificare, limbi, export, lucru in grup |
| `SPEC_03_compare_automatizare_cli.md` | 357 de cerinte R-001 … Z-030: comparare, Hot Folder, sarcini automatizate, CLI, Screenshot Reader, integrari Office si SharePoint, toate setarile, etichete de data, expresii regulate |
| `SPEC_04_schema_bd.sql` | schema completa a bazei de date, SQL executabil: 51 de tabele, 34 de indecsi, 23 de triggere, 5 vederi |
| `SPEC_05_api_core.py` | contractul nucleului: 124 de clase, 308 semnaturi de metode, 42 de excepții cu coduri, toate adnotate cu ID-ul cerintei |
| `SPEC_06_plan_de_testare.md` | corpusul de test, 19 praguri de calitate masurabile, procedurile testelor critice, criteriile de acceptanta |
| `SPEC_07_matrice_trasabilitate.csv` | 1.501 de cerinte → 1.501 de teste, 1:1, cu nivel, prioritate si sursa |
| `SPEC_08_raport_divergente.md` | **citeste-l al doilea, dupa acest document.** Ce s-a corectat fata de versiunile anterioare ale specificatiei, si de ce |
| `SPEC_09_anexe_referinta.md` | tabelele de referinta: toate scurtaturile pe cele patru ferestre, formatele cu cele trei capabilitati fiecare, limbile, fonturile per scriere, diferentele intre editii, meniurile, ce se ia in seama inainte de OCR, si 21 de situatii de depanare |
| `SPEC_10_interfata_detaliata.md` | interfata la nivel de element: fiecare bara, fiecare panou, fiecare dialog, fiecare mesaj de stare, cu ordinea exacta a controalelor |

**Total: 1.501 de cerinte numerotate** (inclusiv 14 extinderi proprii in `SPEC_11_extinderi.md`). Fiecare are: ce primeste, ce valideaza, ce rezulta si ce eroare da.

**Coloana `Src` din fiecare cerinta spune de unde stim ce scrie acolo:**

| Marcaj | Inteles | Cate | Ce faci cu ea |
|---|---|---|---|
| `D` | confirmat in documentatia oficiala ABBYY | 1.063 | **se implementeaza exact asa.** O abatere aici e un defect |
| `V` | observat pe ecran in 22 de tutoriale analizate cadru cu cadru | 300 | se implementeaza asa; nu e confirmat in scris |
| `K` | din baza de cunostinte ABBYY | 9 | idem |
| `N` | adaugat de noi, nu exista in original | 72 | opțional. Se poate scoate dacă vrei strict 1:1 |
| `X` | diferit deliberat de original, cu motivul in nota | 25 | se implementeaza versiunea noastra, nu a originalului |

Cum lucrezi cu ele:

1. **ID-ul cerintei e unitatea de munca.** Scrie-l in comentariul de deasupra fiecarei functii pe care o implementezi. Pune-l in mesajul de commit.
2. **`SPEC_05_api_core.py` e contractul, nu o sugestie.** Numele, parametrii si excepțiile de acolo se implementeaza asa cum sunt. Fisierul se importa fara erori si se poate verifica cu `mypy`; porneste de la el.
3. **`SPEC_04_schema_bd.sql` ruleaza asa cum e.** Verifica-l cu `python3 -I verifica_schema.py` inainte si dupa fiecare modificare: 28 de reguli de business sunt impuse direct in schema si trebuie sa rămână impuse.
4. **Nu considera o cerinta terminata fara testul ei din matrice.** Un commit care implementeaza `M-008` adauga si `T-M008`.
5. **Cele 142 de cerinte de prioritate 1 din `SPEC_06` sunt obligatorii.** Nimic nu se livreaza cu una dintre ele picata. Ele conțin regulile care se rateaza cel mai usor: matricea mod de layout → formate permise, sintaxa reala a liniei de comanda (doua executabile, doua sintaxe), faptul ca Hot Folder nu e serviciu, cele trei confirmari de securitate, evenimentele de formular, prefixele `mailto:` si `file://`, pierderea semnelor de carte la impartire, si regula ca PDF-urile cautabile folosesc intotdeauna OCR.
6. **Nu adauga parametri de linie de comanda care nu exista in original** decat din secțiunea U.3, marcata `N`. Linia de comanda reala nu are `/format`, `/layout`, `/pages`, `/mrc`, `/pdfa`, `/split`, `/merge`, `/threads`, `/json`.
7. Acest document rămâne autoritatea pentru: stiva tehnica (sectiunea 2), arhitectura de foldere (3), aspectul interfetei si textele de pe ecran (6), etapele de lucru (12) si regulile de business (13).

---

## 0. Rolul tau si regulile de lucru

Esti un echipaj complet de dezvoltare software: arhitect, backend, frontend (Qt), specialist OCR/computer vision, QA si technical writer. Construiesti de la zero o aplicatie desktop Windows, scrisa in Python, care face tot ce face ABBYY FineReader PDF 16 Corporate pentru Windows, cu o interfata structurata la fel.

Reguli obligatorii:

1. Nu simplifica functionalitatile din aceasta specificatie. Nu elimina module.
2. Nu crea pagini, butoane sau meniuri decorative. Fiecare control trebuie sa faca ceea ce scrie aici.
3. Nu folosi date demonstrative in locul implementarii. Nu lasa mesaje "Coming soon" pentru functii specificate.
4. Interfata singura nu inseamna aplicatie terminata. Motorul (core), stocarea si validarile sunt obligatorii.
5. Implementeaza validari reale, gestionarea erorilor si mesaje clare. Nu ascunde erorile.
6. Nu marca o functionalitate ca terminata fara test automat sau verificare manuala documentata.
7. Nu inventa comportamente pentru produsul original. Unde specificatia spune [DECIZIE], este o alegere tehnica proprie, documenteaz-o in `docs/decizii.md`.
8. Daca o functie nu poate fi reprodusa identic (de exemplu calitatea OCR ABBYY sau compresia MRC), implementeaza un echivalent functional si documenteaza diferenta in `docs/diferente.md`.
9. Nu folosi numele, logo-ul, iconurile sau grafica ABBYY. Produsul are nume propriu: **[NUME_PRODUS]** (implicit "DocuLens").
10. Lucreaza pe etape (sectiunea 12). Fiecare etapa se verifica inainte de urmatoarea. Nu accepta o implementare care arata bine dar nu functioneaza, nici una functionala care ignora structura interfetei.
11. Cod organizat, tipizat (type hints, mypy), testat (pytest), documentat. Componente UI reutilizabile.
12. Interfata in limba romana si engleza (fisiere de traducere Qt), implicit romana.

---

## 1. Descrierea produsului

**Ce este:** o suita desktop offline pentru documente: OCR, conversie, editare PDF, comparare de documente si automatizare.

**Probleme rezolvate:**
- transforma scanari, fotografii si PDF-uri imagine in documente editabile (Word, Excel etc.) si in PDF-uri cautabile, pastrand aspectul;
- editeaza orice PDF, inclusiv unul scanat, fara conversie prealabila;
- compara doua versiuni ale unui document, chiar in formate diferite (Word vs PDF scanat);
- proceseaza automat volume mari de documente (foldere urmarite, programari).

**Utilizatori:** o singura persoana pe calculator (consultant, jurist, traducator, functionar). Nu exista conturi, login sau roluri in aplicatie.

**Cerinta speciala:** sa functioneze complet offline (fara internet), inclusiv OCR in limba romana cu diacritice (ă, â, î, ș, ț - inclusiv variantele cu sedila ş, ţ).

**Aplicatii (executabile) ale suitei:**

| Aplicatie | Rol |
|---|---|
| Lansator (New Task) | Ecran de start cu sarcini rapide |
| PDF Editor | Vizualizare, editare, adnotare, organizare, securitate, formulare |
| OCR Editor | OCR avansat cu zone, verificare, antrenare, export |
| Compare | Comparare a doua documente |
| Hot Folder | Programator de procesari automate (aplicatie cu icon in bara de sistem). **Nu e serviciu de sistem: ruleaza numai cu utilizatorul conectat.** Limite in original: 5.000 de pagini la 30 de zile, 2 nuclee |
| Screenshot | Captura de ecran cu OCR |
| CLI | `dl-ocr.exe` si `dl-compare.exe` |

Toate folosesc acelasi pachet `core` si aceleasi setari globale.

---

## 2. Stack tehnic obligatoriu

| Strat | Tehnologie |
|---|---|
| Limbaj | Python 3.12+ |
| GUI | PySide6 (Qt 6), QMainWindow + dock widgets + ribbon propriu |
| Randare PDF | pypdfium2 (implicit). PyMuPDF optional, sub flag, din cauza licentei AGPL [DECIZIE] |
| Structura PDF | pikepdf (pagini, outline, atasamente, metadate, criptare, AcroForm) |
| Adnotari si editare continut | pikepdf + generator propriu de content streams; PyMuPDF daca e activat |
| Preprocesare imagine | OpenCV, scikit-image, Pillow, NumPy |
| Analiza layout | PaddleOCR PP-Structure (layout + tabele) + euristici proprii |
| OCR | Tesseract 5 (pytesseract/tesserocr) cu `ron`, `eng` si limbile cerute; PaddleOCR ca motor secundar. Interfata abstracta `OcrEngine` |
| Coduri de bare | zxing-cpp |
| PDF cautabil / PDF/A | OCRmyPDF (hOCR->PDF), Ghostscript optional pentru PDF/A, jbig2enc |
| Export | python-docx, openpyxl, python-pptx, odfpy, ebooklib, writer propriu RTF/FB2/HTML/TXT/CSV, djvulibre (DjVu) |
| Comparare | difflib + rapidfuzz, aliniere pe cuvinte |
| Semnaturi digitale | pyHanko (PAdES, LTV, timestamp TSA, PKCS#11 pentru smartcard) |
| Scanare | TWAIN (pytwain) si WIA (comtypes) |
| Automatizare | APScheduler, watchdog, ftplib, imaplib; pywin32 pentru Outlook |
| Integrari Windows | pywin32: meniu contextual Explorer (shell extension prin registry), add-in COM Office [ETAPA FINALA] |
| Stocare | SQLite (sqlite3) cu migratii (alembic sau scripturi versionate) |
| Detectie limba | fastText lid.176 sau langdetect |
| Dictionare | Hunspell (pyspellchecker/hunspell) |
| Ambalare | Nuitka sau PyInstaller + Inno Setup; Tesseract si modelele incluse in instalator |
| Teste | pytest, pytest-qt, hypothesis; set de documente de test in `tests/corpus/` |

---

## 3. Arhitectura

```
app/
  core/
    settings/      # echivalentul dialogului Options, profiluri, import/export
    project/       # proiect OCR: modele, persistenta, undo/redo
    imaging/       # preprocesare: o functie pura per unealta
    layout/        # detectie zone, ordine citire, tabele, sabloane de zone
    ocr/           # OcrEngine (abstract), TesseractEngine, PaddleEngine, limbi, dictionare, patterns
    pdf/           # document PDF: randare, text layer, editare, pagini, adnotari, formulare, securitate, semnaturi
    export/        # un exporter per format; 5 moduri de layout
    compare/       # extragere text, aliniere, diff, grupare, rapoarte
    automation/    # pasi de sarcina, runner, scheduler, hot folder, log
    scanning/      # TWAIN, WIA, setari scanare
    licensing/     # [optional] contor pagini, mod trial
  gui/
    common/        # ribbon, page viewer, thumbnails, dock panes, dialoguri comune, teme
    launcher/
    pdf_editor/
    ocr_editor/
    compare/
    hotfolder/
    screenshot/
  cli/
  resources/       # iconuri proprii (Fluent/Lucide, licenta compatibila), traduceri, tessdata
tests/
docs/
```

Reguli de arhitectura:
- `core` nu importa nimic din `gui`. Toata logica poate rula fara interfata (CLI si Hot Folder o folosesc direct).
- Operatiile lungi (OCR, conversie, comparare) ruleaza in worker-e (`QThreadPool` / `concurrent.futures.ProcessPoolExecutor`), cu progres, anulare si raportare de erori. Numarul de procese = setarea "nuclee CPU".
- Toate comenzile de editare trec printr-un `CommandStack` (undo/redo) per document.
- Setarile globale sunt o singura sursa de adevar (`core/settings`), observabila de UI.
- Fiecare unealta de imagine, fiecare exporter si fiecare pas de automatizare implementeaza o interfata comuna si se inregistreaza intr-un registru (plugin-like).

---

## 4. Model de date

### 4.1 Proiect OCR (fisier `.dlproj` = arhiva zip, sau folder)

Contine: `project.json` (metadate, versiune format), `images/original/`, `images/processed/`, `project.db` (SQLite):

| Tabel | Campuri | Constrangeri |
|---|---|---|
| page | id PK, order_index, source_file, source_page_no, image_path, processed_image_path, width_px, height_px, dpi, rotation, status ENUM(new, preprocessed, analyzed, recognized, verified), has_warnings, created_at | UNIQUE(order_index) |
| area | id PK, page_id FK, type ENUM(recognition, text, table, picture, background, barcode), polygon_json, order_index, language, function ENUM(body, header, footer, footnote, caption), orientation ENUM(0,90,180,270, auto), print_type ENUM(auto, typewriter, fax), inverted BOOL, cjk_direction, barcode_type | ON DELETE CASCADE |
| table_grid | area_id PK FK, rows_json, cols_json, merges_json, picture_cells_json | doar pentru area.type=table |
| text_block | id PK, area_id FK, cell_ref NULL, paragraph_index, style_id FK NULL, text, chars_json (char, bbox, confidence, uncertain), verified BOOL | |
| style | id PK, name, font, size_pt, spacing, scale, bold, italic, underline | |
| warning | id PK, page_id FK, code, message, dismissed BOOL | |
| project_setting | key PK, value_json | suprascrie setarile globale |

### 4.2 Baza globala `app.db`

| Tabel | Campuri |
|---|---|
| setting | key PK, value_json |
| recent_item | id, kind ENUM(pdf, project, comparison), path, opened_at |
| area_template | id, name, page_width, page_height, dpi, areas_json |
| user_language | id, name, base_language, alphabet, dictionary_type ENUM(none, builtin, user, regex), dictionary_ref, regex, prohibited_chars, word_start_chars, word_end_chars, allow_numerals_abbrev |
| language_group | id, name, languages_json, prohibited_chars |
| user_dictionary_word | language, word (PK compus) |
| user_pattern | id, name, glyphs_json (max 1000), active BOOL |
| automated_task | id, name, steps_json, created_at, modified_at |
| hot_folder_task | id, name, schedule_type ENUM(once, every_minute, daily, weekly, monthly), schedule_json, source_type ENUM(folder, ftp, mail, project), source_json (cale, credentiale criptate cu DPAPI), originals_action ENUM(keep, delete, move), processing_json, outputs_json, status ENUM(running, scheduled, watching, stopped, completed, error), next_start_at, last_run_at, log_enabled, notify |
| task_run | id, task_id FK, started_at, ended_at, pages, errors, warnings, uncertain_chars, log_path |
| comparison | id, doc1_path, doc2_path, language, options_json, created_at |
| difference | id, comparison_id FK, kind ENUM(delete, add, change), group ENUM(body, header_footer, numbering), text1, text2, page1, page2, bbox1_json, bbox2_json, ignored BOOL |
| stamp | id, kind ENUM(builtin, image, text), name, data_json |
| signature_appearance | id, kind ENUM(text, image), name, data_json |
| redaction_keyword_list | id, name, words_json |
| usage_counter | month PK, pages_processed |

Adnotarile, campurile de formular, semnaturile, semnele de carte, atasamentele si metadatele PDF se pastreaza in fisierul PDF, nu in baza de date.

Migratii versionate, verificare de integritate la deschidere, backup automat al proiectului inainte de operatii distructive (stergere pagini, re-recunoastere totala).

---

## 5. Setari globale (dialogul Options) - 7 tab-uri

1. **General:** la pornire deschide (Lansator | OCR Editor cu proiect nou | OCR Editor cu ultimul proiect); dispozitiv de scanare + interfata (dialog propriu | interfata driverului); aplicatie implicita pentru PDF.
2. **Procesare imagine:** recunoastere in fundal in PDF Editor (+ limbi); procesare automata a paginilor adaugate in OCR Editor: Recunoaste (preprocesare+analiza+OCR) | Analizeaza (preprocesare+analiza) | Doar preprocesare | Nimic. Preprocesare: Recomandat (Split facing pages, Correct page orientation, Use recommended settings) sau Personalizat: Deskew, Straighten text lines, Correct image resolution, Detect page edges*, Whiten background*, Reduce ISO noise*, Remove motion blur*, Correct trapezoid distortions*, Fix inverted colors, Convert to black and white, Remove color marks (*doar fotografii).
3. **Limbi:** selectie manuala multipla sau detectie automata; limbi utilizator; grupuri de limbi; editor de limbi.
4. **OCR:** mod de recunoastere PDF (Automat intre OCR si text din PDF | Foloseste OCR | Doar text din PDF - implicit pentru PDF-uri cu strat text digital); Thorough | Fast; tip document (Auto | Typewriter | Fax); detectie elemente de structura (antete si subsoluri, note de subsol, cuprins, liste); "Converteste codurile de bare in text" (implicit oprit); training: foloseste patterns utilizator / antrenare caractere noi / si patterns integrate; fonturi folosite in rezultat; salvare/incarcare patterns si limbi (fisier unic).
5. **Setari formate:** sub-tab per format (vezi sectiunea 8.6).
6. **Altele:** limba interfetei; numar nuclee pentru OCR; verificare actualizari (oprita implicit, offline); JavaScript in PDF (oprit | per document | global); detectie automata URL; Reset la valori implicite.
7. **Zone si text** (doar in OCR Editor): prag si evidentiere caractere nesigure; verificare cuvinte din afara dictionarului (ignora cuvinte cu cifre sau caractere speciale, verifica compuse, corecteaza spatii la punctuatie); dictionare utilizator (vizualizare/editare/import .txt/.dic, folder partajat); font pentru text simplu; culoare si grosime chenar per tip de zona; culoare evidentiere.

Setarile se pot exporta/importa (JSON). Proiectul OCR poate suprascrie setarile de document.

---

## 6. Specificatii UI/UX

### 6.1 Design system [DECIZIE: paleta proprie, nu copia ABBYY]

| Token | Valoare luminoasa | Valoare intunecata |
|---|---|---|
| bg | #FFFFFF | #1E1F22 |
| surface (panouri) | #F3F4F6 | #2B2D31 |
| border | #D9DCE1 | #3A3D44 |
| text | #1F2328 | #E6E7EA |
| text-muted | #5F6670 | #A0A6AE |
| accent | #2563EB | #5B8DEF |
| danger | #D92D20 | #F97066 |
| success | #12B76A | #32D583 |
| warning | #F79009 | #FDB022 |
| uncertain-char | #FFE58F | #7A5C00 |

- Font: Segoe UI 9 pt (sistem), titluri 10.5 pt semibold, text monospace Consolas.
- Spatiere: grila de 4 px; padding butoane 6x10 px; raza colturi 4 px; umbre doar pe meniuri si popover-uri.
- Iconuri: set propriu, monocrom, 16 px (mici) si 32 px (mari in ribbon); fara iconuri ABBYY.
- Culori zone (implicite, dar **obligatoriu configurabile din Options > Areas and Text**, ca in original, unde difera de la o versiune la alta): Recognition gri #8E8E93, Text albastru #2563EB, Table verde #12B76A, Picture roz #D92D20, Background picture maro #8B5A2B, Barcode mov #7C3AED. Fundalul zonei e semitransparent (~15%), chenarul plin. Zona activa: chenar mai gros + manere patrate la colturi si la mijloace + toolbar contextual plutitor sub ea. Numarul de ordine intr-un patrat mic in coltul stanga sus. Zona in curs de desenare: chenar punctat, cursor "+".
- **Mod intunecat** si **suport High-DPI** obligatorii (originalul nu are mod intunecat pe Windows - avantaj competitiv).
- Accesibilitate: tot ce se face cu mouse-ul se poate face din tastatura; nume accesibile pe toate controalele; contrast AA.

### 6.2 Componente reutilizabile

`RibbonBar` (tab-uri, grupuri, butoane mari/mici/split cu sageata, dropdown-uri), `PageViewer` (zoom, moduri de vizualizare, selectie dreptunghi, overlay-uri), `ThumbnailStrip` (drag-and-drop, selectie multipla, insigne de stare), `DockPane` (titlu, toolbar propriu, redimensionabil, mutabil), `PropertiesBar`, `ProgressDialog` (bara, sfaturi, avertismente, Anuleaza), `PageRangeSelector` (toate/pare/impare/curenta/selectie/interval "2,3,5-7"), `ColorSwatchPicker` (7 culori + mai multe), `LanguagePicker` (multiplu, cautare), `FileListEditor` (adauga, scoate, sus/jos), `StepWizard`.

Fiecare componenta interactiva are starile: normal, hover, focus, active, disabled, loading, selected, expanded/collapsed, error, success, empty.

### 6.2b Texte de interfata citite de pe ecran (foloseste-le ca referinta exacta)

**Main toolbar OCR Editor, in ordine:**
`+ New Task` | icon proiect nou | icon deschide proiect | `Open` | `Scan` | `[ 1 / 17 ]` + sageti sus/jos | `Recognize` | combo limba `[English v]` | undo | redo | buton **Send/Save** (iconul se schimba dupa formatul ales: PDF rosu, W albastru) + sageata | combo mod salvare `[Exact copy v]` | 2 butoane toggle layout panouri | `Verify` | 2 iconuri eroare urmatoare/anterioara.

**Image pane toolbar, doua randuri:**
- rand 1: `Edit Image` · `Save Page` ‖ `Select` · `Hand Tool` · `Delete` · `Reorder`
- rand 2: `Recognize Page` · `Analyze Page` ‖ `Text` · `Picture` · `Table` · `Background Picture` · `Recognition Area`
- pentru PDF cu strat text, in dreapta: textul `This PDF file contains a text layer` + buton `PDF recognition mode ▾`

**Text pane toolbar, doua randuri:**
- rand 1: combo stil `[Body text v]` · font · marime · `A+` `A-` · `Ω` · link ‖ `Find`
- rand 2: `Style Editor` ‖ B I U x² x₂ ‖ aliniere ×4 ‖ spatiere, liste ‖ `Redaction`
- cand pagina nu e recunoscuta: mesaj gri centrat `Page not recognized`

**Bare de proprietati de jos, cu tab-uri:**
- sub Image: `Area Properties` | `Image Properties`. Image Properties afiseaza `Width x height: 2550 x 3300 pixels` · `Resolution: [300] dpi` · `Color mode: Color` · format · `Source image: <cale completa>`
- sub Text: `Text Properties`, pe 3 coloane: Style / Font / Size (+B I U) ‖ Language / Font color / Effects ‖ Alignment / Background color / Scale / Spacing

**Ribbon PDF Editor, pe tab-uri (exact):**
- Document: `New Task` `Open` `Save` `Save As ▾` `Print` `E-mail` `Note` `Draw ▾` `Highlight` `Underline` `Strikethrough` `Insert Text` `Add Stamp ▾` `Recognize ▾` `Compare` `Select` `Hand`
- Organize Pages: `Selected pages: [1 ▾]` cos · roteste stanga · roteste dreapta · auto-orientare · `Crop` `Add Pages ▾` `Move` `Replace` `Split` `Delete Blank Pages` `Recognize ▾` `Enhance` `Save As ▾`
- Edit Content: `Header and Footer ▾` `Picture` `Add Text` font · marime · `A+` `A-` · B I U · aliniere ×4 · directie text · spatiere randuri · spatiere paragraf · culoare `A ▾`
- Security: `Signature ▾` `Password Security` `Watermark ▾` `Erase` `Redact` `Delete Objects and Data...` `Select` `Hand`
- Form Editor: `Text Field` `Check Box` `Radio Button` `Drop-down List` `List Box` `Button` `Signature Field`
- dreapta randului 2: undo · redo · `Comments (N)`

**Bara verticala stanga PDF Editor (~30 px), 5 iconuri:** Pages · Bookmarks · Search · Attachments · Digital Signatures.

**Bara de jos PDF Editor:** sageata sus · sageata jos · `4 / 6` · icon potrivire ▾ · icon mod vizualizare · zoom `[75% ▾]` · `-` · `+`.

**Panoul Search:** tab-uri majuscule `FIND | REPLACE | REDACT` + X · `Find what:` + rotita setari ▾ · camp cu X de golire · `Replace with:` + camp · buton `[Replace]` dreapta, gri fara selectie · sageti `<` `>` · arbore de rezultate cu nodul `Document Text (58)` si rezultate cu fragment de context (potrivirea galbena) + `Page 1` dreapta, fiecare cu bifa · bara de stare `Found: 58` / `No matches found`. In pagina toate aparitiile sunt galbene simultan.

**Panoul Comments:** camp `Comment text filter` cu lupa · rand cu `<` `>` · `AZ ▾` · palnie filtrare ▾ · optiuni · fiecare comentariu cu icon de tip, `Today 19:02  Page 2`, bifa dreapta, camp `Enter your comment`, link `Add Reply`.

**Meniul Tools (OCR Editor), exact:**
```
View Dictionaries...    Ctrl+Alt+D
Pattern Editor...
Style Editor...
─────────────────────
Redaction Mode          Ctrl+Shift+H
─────────────────────
Automated Tasks
Hot Folder              Ctrl+Shift+F
Compare Documents
Screenshot Reader
─────────────────────
Options...              Ctrl+>
```

**Dialogul Options:** tab-uri ca iconuri mari cu eticheta dedesubt: General · Image Processing · Languages · OCR · Format Settings · `...` Other. **Al 7-lea tab, `Areas and Text`, apare DOAR cand dialogul e deschis din OCR Editor.**
- General: `When OCR Editor starts` (2 radio) · `Select device for acquiring images` + `[Select Device...]` · 2 radio de interfata de scanare + link · `<Produs> is not currently your default PDF viewer` + `[Make Default...]`
- Image Processing: bifa `Enable background recognition in the PDF Editor` + paragraf + `OCR languages:` link · bifa `Automatically process page images as they are added to the OCR Editor` + 3 radio (`Recognize page images (includes preprocessing and analysis)` / `Analyze page images (includes preprocessing)` / `Preprocess page images`) + modul `No preprocessing` · `Image preprocessing settings` pe 3 coloane (vezi 5.2) · buton `[Hide Advanced Settings]` · nota `* for photo images`
- OCR: `PDF recognition mode` combo + link · `Balance between OCR speed and accuracy` (Thorough / Fast) · `Document type` (**Auto / Fax / Typewriter**) · `Detection of structural elements` (Headers and footers · Numbered lists · Table of contents · Footnotes) · `Barcodes`: `Convert barcodes into strings` · grup radio sabloane (`Use built-in patterns` / `Use user patterns` + `Also use built-in patterns` indentat / `Use training to recognize new characters and ligatures` + aceeasi bifa) + link + butoane `[Pattern Editor...]` `[Load Patterns and Languages...]` `[Save Patterns and Languages...]` · `Select fonts to be used in recognized text` + `[Select Fonts...]`
- Format Settings: lista stanga `Document type` (PDF · DOC(X)/RTF/ODT · XLS(X) · PPTX · CSV · TXT · HTML · EPUB/FB2 · DjVu) si setarile in dreapta

**Dialogul Split Document:** `Split method:` 3 radio (`By file size` / `By page count` / `By bookmarks (first level only)`) · `Total files: 13` · `File name:` combo + bifa `Add numeration` + cifre + `Example: 01_Bookmark.pdf` · `Save to:` bifa `Same as source folder` + cale + `[Browse...]` · `[Split]` `[Cancel]`.

**Dialogul Text Field Properties:** tab-uri `General | Appearance | Format`. General: `Field Name:` · `Tooltip:` · bifa `Max Number of Symbols` + camp gri · `Required` · `Read-Only` · `Width` + lacat proportii + `Height` · `X` `Y` · `Units: [Centimeters ▾]`.

**Dialogul New Action (buton de formular):** `Trigger Event: [Click ▾]` · `Action: [Send form ▾]` · `Send to:` · `File Format: [PDF file ▾]` · nota `All form fields will be sent.` · `[Save] [Cancel]`.

**Dialogul Delete Objects and Data:** `Select objects and data to delete:` + bifele `Hidden text and objects` (cu avertismentul `The document will be converted to image-only PDF.`) · `Comments and markup` · `Links, media, actions, scripts, and form data` · `Bookmarks` · `Attachments` · `Metadata` · `[Apply] [Cancel]`.

**Dialogul Task Settings (Automated Tasks):** stanga panoul `Task steps` cu eticheta `OCR project:` si butoanele `Create new OCR project` / `Select existing OCR project` / `Use current OCR project`, apoi grupuri dezactivate: `Open image or PDF` `Scan` ‖ `Analyze` ‖ `OCR` ‖ `Save/Send ▾`. Dreapta: `Task name:` + mesaj centrat `Choose the first step`. Jos `[Help] [Finish] [Cancel]`.

**Fereastra Hot Folder:** tabel cu coloanele `Name · Path · Status · Next Start Time · Log`. Bara de stare jos: `Pages remaining to recognize 4999 / the limit to be renewed in 21 days`. Dialogul `Task Settings` are paleta de pasi pe categorii: `Schedule` (Run once · Recurring) · `Open` (File from folder · File from FTP · File from Outlook · OCR project) · `Process` (Process document) · `Save` (`Save results ▾` cu: **Save document · Save to SharePoint · Save images · Save OCR project**). Jos: link `Help` | buton plin `Create Task` | buton contur `Cancel`.

**Image Editor:** antet `Image Editor` + `< Exit Image Editor`; panou dreapta cu lista verticala a celor 14 unelte; unealta aleasa se expandeaza inline. Exemplu Crop: `Paper size: [Custom ▾]` · `Size: [152,7] Width [240,9] Height` · `Offset: [32,6] X [50,9] Y` · radio `( ) Inches (o) Millimeters` · `Selection: [Current Page ▾]` · `[Crop]`. Jos de tot bifa `[ ] Show next page after operation completes`.

**Screenshot Reader:** fereastra mica flotanta cu `Capture: [Area ▾]` · `Language: [English ▾]` · `Send: [Text to Clipboard ▾]` + 2 butoane mari cu iconuri.

**Mesaje si stari:** `Page not recognized` · `No matches found` · `Choose the first step` · `Select task steps` · `Loading the document. Please wait...` · `Differences found: 9` · `Process completed` · `N of M pages recognized` · `N of M files processed` · avertisment `Page 1: Please rescan your document at a higher resolution. This will improve the OCR of the fragments printed in a small font size.`

### 6.3 Lansator (New Task)

- Stanga: tab-uri verticale **Deschide**, **Scaneaza**, **Compara**, **Recente**, **Mobil**; sus meniu Fisier/Editare/Unelte/Ajutor; dreapta sus buton Setari.
- Dreapta: carduri de sarcini; la hover pop-up cu scenarii tipice.
  - Deschide: Document PDF, OCR Editor, Converteste in PDF, in Word, in Excel, in alte formate (PPTX, ODT, HTML, EPUB, FB2, RTF, TXT, CSV, DjVu).
  - Scaneaza: in OCR Editor, in PDF, in Word, in Excel, in fisiere imagine, in alte formate.
  - Compara: Deschide Compare; Comparatii recente.
  - Recente: PDF-uri si proiecte recente, cautare (Ctrl+F), eliminare din lista.
  - Mobil: alege folderul in care un telefon sincronizeaza poze/PDF (Google Drive/OneDrive local) si deschide-l.
- Sarcinile de conversie deschid un panou: lista de fisiere (adauga, scoate, Alt+Sus/Jos), limbi OCR, calitate imagine (Cea mai buna | Echilibrat | Compact | Personalizat), tip PDF (cautabil | doar imagine), PDF/A, "Combina intr-un singur fisier", buton Converteste. Rezultatul se deschide in aplicatia asociata sau in PDF Editor.
- Empty state Recente: mesaj + buton Deschide.
- Scurtaturi: Ctrl+N PDF nou, Ctrl+O deschide PDF, Ctrl+R deschide in OCR Editor, Ctrl+S scaneaza in OCR Editor, Ctrl+Shift+N/O proiect OCR nou/deschide, Ctrl+> setari, Ctrl+Q iesire.

### 6.4 PDF Editor

Layout: meniu sus; ribbon cu 5 tab-uri; bara dreapta sus (Lansator, Salveaza, Tipareste, Recunoaste cu sageata: "Recunoaste si verifica in OCR Editor", Setari); stanga bara verticala de iconuri (Pagini, Semne de carte, Cautare, Atasamente, Semnaturi digitale) care deschide panoul de navigare (F5, Alt+Shift+1..5); centru pagina; dreapta panou Comentarii (F7); jos: mod vizualizare, zoom (Potrivire latime, Potrivire pagina, +/-), numar pagina, Ecran complet.

**DOCUMENT tab:** navigare panouri; Nota (Ctrl+M); Evidentiaza (Ctrl+H), Subliniaza (Ctrl+Shift+U), Taie (Ctrl+K), Insereaza text (Ctrl+J) - fiecare cu culoare; Forme (Ink, Linie, Sageata, Dreptunghi, Oval, Poligon, Nor, Polilinie, Caseta text; Shift constrange); Stampile (predefinite, din imagine, text cu data/ora, borduri, gestiune); Recunoaste documentul (Ctrl+Shift+R; limbi, corecteaza orientarea, deskew si rezolutie); Adauga semn de carte (Ctrl+D); Cauta (Ctrl+F).

**ORGANIZEAZA PAGINI tab:** grila de miniaturi (mod dedicat); selectie prin clic, Ctrl/Shift, cadru de selectie, interval, pare/impare/toate; Sterge (Del, Ctrl+Backspace); Roteste stanga/dreapta (si iconuri la hover; Ctrl+Shift+</>); Corecteaza orientarea (Ctrl+Shift+/); Decupeaza (un cadru pentru toate sau per pagina; Enter aplica, Esc inchide); Adauga pagina goala (Ctrl+Shift+B), din PDF (Ctrl+Shift+P), din fisier (Ctrl+Shift+O, orice format suportat, pozitie: inainte de prima/dupa ultima/dupa selectie), din scanner (Ctrl+Shift+K, previzualizare); Muta (drag sau dialog, Ctrl+Shift+M); Inlocuieste (Ctrl+Shift+E, fisier sursa + intervale); Sterge paginile goale (detectie + revizuire); Imparte documentul (dupa marime, nr. pagini, semne de carte nivel 1; nume cu numerotare inainte/dupa, cifre; folder; atasamentele merg in subfolder; semnele de carte nu se pastreaza); Recunoaste paginile selectate; Trimite in OCR Editor; Imbunatateste imaginile (auto, deskew, netezire caractere); Creeaza PDF din selectie; Setari procesare imagine.

**EDITEAZA CONTINUT tab** (Ctrl+E): pregatire automata a paginii pentru editare (detectie paragrafe pe PDF digital/scanat; pentru scanat foloseste OCR in fundal); editare text cu reflow in paragraf; Adauga text (Ctrl+T); formatare (font, marime, stil, spatiere, aliniere, culoare, directie); editare celula de tabel; mutare (Ctrl+drag sau marginea blocului), redimensionare (manere), stergere bloc (Ctrl+clic, Del); Esc iese; imagini: adauga, sterge, roteste, redimensioneaza, aduce in fata; Radiera cu fundal detectat automat; Linkuri (Ctrl+L): pagina, destinatie, URL/e-mail/fisier; editare/copiere/stergere link; Antet si subsol (6 pozitii, distanta de margine, unitati; campuri Text, Nr. pagina, Nr. Bates, Data/ora; font; pagini: toate/interval/pare/impare; "Salveaza si adauga"; gestiune: copiaza/editeaza/sterge); Bates (Incepe de la / Continua de la); Strat text: "Recunoaste pagina si inlocuieste stratul text existent"; Corecteaza inclinarea si orientarea.

**SECURITATE tab:** Redactare (Ctrl+Shift+H; 7 culori + mai multe; selectie text/imagini; a doua unealta pentru metadate, comentarii, adnotari, semne de carte, atasamente cu Aplica); Cautare si redactare (inclusiv lista de cuvinte cheie: adauga, gaseste cu lista, editeaza lista, salveaza si gaseste); Sterge text si imagini (Ctrl+R); Parola (parola de deschidere cu "ascunde caractere"; parola de permisiuni - trebuie sa difere; tiparire: interzis/rezolutie mica/mare; editare: niciuna/... ; copiere; cititoare de ecran; criptare AES-128/AES-256 (RC4-40 doar la citire); toate continutul sau fara metadate; confirmare parole la OK); Semnatura digitala (zona sau clic; certificat din magazinul Windows sau smartcard; vezi certificat; Motiv, Locatie, Contact; campuri afisate + etichete; server timestamp implicit/personalizat; borduri si fundal; imagine proprie; "Salveaza si semneaza"; LTV; SHA-256/384/512; validare automata la deschidere; proprietati; stergere doar cu certificatul potrivit); Semnatura text si din imagine (din fisier sau clipboard, fundal transparent, gestiune); Filigran (9 pozitii, offset, text sau imagine, format, rotire, transparenta, deasupra/in spatele continutului, toate/selectie/interval; eliminare filigrane); Elimina datele ascunse dintr-un clic (strat OCR, comentarii, atasamente, metadate, scripturi, form data, semne de carte, linkuri/media/actiuni).

**EDITOR FORMULARE tab:** Evidentiaza campurile; Arata numele campurilor; Date formular: incarca (FDF, XFDF), salveaza (FDF, XFDF, HTML), reseteaza; 7 tipuri de campuri: Text, Lista derulanta, Bifa, Butoane radio, Buton, Semnatura, Lista; adaugare prin clic (dimensiune implicita) sau tragere; Proprietati (dublu clic): General (Nume obligatoriu si unic, fara punct la inceput/sfarsit/dublu; Tooltip; Obligatoriu; Doar citire; X, Y, latime, inaltime; unitati cm/inch/pt), Aspect (umplere, bordura, grosime, culoare font, font, marime, "seteaza ca stil implicit"; bifa: culoarea bifei), Format (text pe un rand/mai multe randuri, max caractere; data cu format si calendar), Elemente lista (adauga, editeaza, sterge, implicit, anuleaza implicit, sus, jos; "permite valori in afara listei" / "selectie multipla"), Actiuni (pentru Buton; evenimente Click, Drop, Mouse Over, Mouse Out, Focus, Focus Out; actiuni: adauga pagini din scanner, salveaza ca, inchide, tipareste, iesire, cauta, navigare pagini, moduri vizualizare, arata/ascunde panouri, ecran complet, proprietati document, deschide fisier, urmeaza link, reseteaza formular, trimite formular (PDF/FDF/XFDF/HTML), mergi la pagina, executa JavaScript); copiere/lipire, copie legata, aliniere cu ghidaje mov (Ctrl dezactiveaza ghidajele), stergere, redimensionare. Campurile obligatorii apar cu numele rosu in modul editare; obligatoriu doar avertizeaza, nu blocheaza salvarea. In modul normal: completare formular, inclusiv semnatura in camp.

**Panouri:**
- Pagini: miniaturi, meniu contextual cu toate operatiile de pagina.
- Semne de carte: creare (inclusiv din selectie), destinatie, drag pentru reordonare si imbricare, nivel stanga/dreapta, redenumire, stergere multipla (Ctrl+clic acelasi nivel).
- Cautare: camp; optiuni potrivire exacta / majuscule; rezultate grupate (text, comentarii, semne de carte, metadate); marcare rezultate (evidentiaza/taie/subliniaza + culoare); tab Inlocuire (bife pe rezultate, "inlocuieste cu"); tab Redactare; F3 urmatorul.
- Atasamente: deschide, salveaza, redenumeste, sterge, adauga.
- Semnaturi digitale: lista, proprietati, validare.
- Comentarii: lista, cautare, sortare, filtre (Tip, Autor, Pagina, Data, Bifa, Status), Reset, ascunde textul; raspuns (Ctrl+Enter); bifa; status (Acceptat, Respins, Anulat, Finalizat, Niciunul) cu istoric; Proprietati (autor, subiect, istoric status; "seteaza ca implicit" pentru autor); sterge toate comentariile.

**Vizualizare:** O pagina, O pagina cu derulare, Doua pagini, Doua pagini cu derulare (Ctrl+5..8); paginile impare la dreapta; Ecran complet (F11/Esc; bara apare la marginea de jos; meniu contextual cu comentarii, semne de carte, editare). Zoom: Ctrl++ / Ctrl+-, Potrivire (Ctrl+0), Dimensiune reala (Ctrl+1), Potrivire latime (Ctrl+2). Navigare: Ctrl+G, Ctrl+Sus/Jos, Home/End, Alt+Stanga/Dreapta.

**Recunoastere in fundal:** la deschiderea unui PDF fara strat text bun, se creeaza un strat text temporar (fara a modifica fisierul) pentru cautare, copiere si marcare; optiune de a-l salva permanent.

**Copiere:** Copiaza zona ca imagine (Ctrl+C), ca text (Ctrl+Shift+C), ca tabel (Ctrl+Alt+C) - la tabel apare un editor de separatori (adauga/sterge orizontal/vertical, imparte/uneste celule) inainte de copiere; copiere text pe mai multe pagini cand exista strat text.

**Fisier:** Salveaza; Salveaza ca PDF / PDF cautabil / PDF doar imagine / PDF/A (1a, 1b, 2a, 2b, 2u, 3a, 3b, 3u) / PDF/UA; Salveaza ca Word, Excel, PowerPoint, ODT, RTF, HTML, TXT, CSV, EPUB, FB2, DjVu, imagini (un fisier sau per pagina); Reduce dimensiunea (calitate imagine, compresie MRC, limbi OCR); Proprietati document (Titlu, Autor, Subiect, Cuvinte cheie editabile - nu pentru fisiere protejate; restul doar citire: nume, cale, marime, dimensiune pagina, nr. pagini, producator, aplicatie, versiune PDF, etichetat, fast web view, date creare/modificare, conformitate PDF/A sau PDF/UA declarata); E-mail (alege paginile); Tiparire (imprimanta, copii, pagini, configurare pagina, scalare si pozitie, alb-negru, tipareste in fisier, tipareste adnotarile); Compara documente; Trimite in OCR Editor. JavaScript: bara de notificare cu "Activeaza pentru acest document / pentru toate".

**Lipsa originalului de rezolvat in alternativa:** documente in tab-uri in aceeasi fereastra (originalul deschide ferestre separate).

### 6.5 OCR Editor

Layout: meniu (Fisier, Editare, Vizualizare, Recunoastere, Zona, Unelte, Ajutor); toolbar principal fix (Lansator, Deschide, Scaneaza, Recunoaste, limbi, mod salvare, Salveaza/Trimite cu sageata, Verifica); bara de acces rapid personalizabila (ascunsa implicit); panouri: Pagini (F5; miniaturi sau detalii cu proprietati; insigne de stare: neprocesata, analizata, recunoscuta, verificata, avertismente), Imagine (F6), Imagine+Text (F7), Text (F8), Zoom (Ctrl+F5; rand marit pentru comparatie caracter cu imagine), Avertismente (buton stanga jos; navigare; stergere). Alt+1..4 focus pe panou; Ctrl+Tab urmatorul panou. Panourile Pagini si Zoom se pot muta. Bare de proprietati jos in Imagine si Text.

**Panoul Imagine:** unelte zona: Recunoastere, Text, Imagine, Imagine de fundal, Tabel (+ scurtaturi fara unealta: Ctrl+Shift text, Alt+Shift imagine, Ctrl+Alt tabel, Ctrl+Shift+Alt fundal); Ordine zone; Editor imagine; zoom. Operatii pe zone: desenare, margini/colturi, adauga/scoate segment (nu pentru tabel si cod de bare), maner nou (Ctrl+Shift+clic pe margine), selectie multipla (Ctrl+clic), mutare (Ctrl+drag), stergere (Del, meniu, unealta; "Sterge zonele si textul"), schimbare tip (Ctrl+1..6 sau meniu), reordonare (clic in ordinea dorita; numerotare automata stanga-dreapta la analiza), toolbar contextual per tip. Proprietati zona: Limba, Functie (corp, antet, subsol, nota de subsol - doar text), Orientare, Tip tiparire, Inversare, Directie CJK; tabel: "Trateaza celulele selectate ca imagine". Tabel: analizeaza structura, adauga separator orizontal/vertical, sterge separatori, imparte celule (doar unite anterior), uneste celule, uneste randuri. Sabloane de zone: salveaza / incarca (pe pagini selectate sau toate).

**Editor imagine** (Ctrl+I): panou dreapta cu unelte: Preprocesare recomandata, Deskew, Indreapta randurile, Corectie foto (zgomot, blur, fundal alb), Corectie trapez (grila albastra cu 4 colturi trase pe colturile paginii, buton Corecteaza; elimina marginile goale), Roteste si oglindeste, Imparte (pagini fata in fata, vertical/orizontal), Decupeaza, Inverseaza, Rezolutie, Luminozitate si contrast, Niveluri (histograma: negru, gri, alb + nivel iesire), Radiera, Elimina marcaje color. Fiecare cu selector: toate, impare, pare, curenta, selectate. Buton Iesire. Toate operatiile au undo.

**Panoul Text:** text recunoscut cu formatare; caractere nesigure evidentiate; butoane anterior/urmator nesigur; evidentiaza nesigure on/off; formatare (B/I/U, font, marime, stil); proprietati text; editare celule tabel (sageti); clic in text sincronizeaza pozitia in Imagine si Zoom. Verificare (Ctrl+F7): dialog cu imaginea cuvantului, sugestii, Ignora, Ignora tot, Inlocuieste, Adauga in dictionar, font si efecte, simboluri (tabel de caractere + cod), Optiuni; Eroare urmatoare/anterioara (Alt+Jos/Sus); Marcheaza ca verificat (Ctrl+T). Editor de stiluri (nume, font, marime, spatiere, scalare; Nou, Uneste; fragment anterior/urmator). Mod redactare in text (puncte sau dreptunghiuri negre la export).

**Proiect OCR:** nou (Ctrl+Shift+N), deschide (Ctrl+Shift+O), salveaza (Ctrl+Shift+S), inchide; adauga imagini (Ctrl+O; optiune "proceseaza automat la adaugare"); scaneaza (Ctrl+K; previzualizare, setari, scaneaza, scaneaza mai mult); sterge pagini (Ctrl+Backspace), roteste (Ctrl+Shift+</>), reordoneaza (dialog: ordonare, restabilire ordine dupa scanare duplex, schimbare pagini de carte); muta pagini in proiect nou; drag pagini intre instante; sterge pagini goale (detectie + revizuire).

**Recunoastere:** Recunoaste tot (Ctrl+Shift+R), pagina (Ctrl+R), zona (Ctrl+Shift+B); Analizeaza tot (Ctrl+Shift+E), pagina (Ctrl+E); progres in panoul Pagini; schimbarea zonelor/setarilor invalideaza textul paginii (necesita re-recunoastere, cu avertisment).

**Salvare si trimitere:** mod layout (Copie exacta, Copie editabila, Text formatat, Text simplu, Layout flexibil-HTML); Salveaza ca PDF cautabil/imagine, Word, RTF, ODT, PowerPoint, TXT, Excel, CSV, FB2, EPUB, DjVu, HTML; Salveaza imaginile paginilor (TIFF multipagina, compresie ZIP/JPEG/CCITT G4/Packbits/LZW; PNG; JPEG; JPEG2000; BMP; PCX; JBIG2; un fisier per pagina sau multipagina); salvare doar pagini selectate; Trimite in Word, Excel, PowerPoint, PDF Editor, clipboard, browser, aplicatie e-mail; E-mail document (Ctrl+M) / imagini (Ctrl+Alt+M); Tipareste text (Ctrl+P) / imagine (Ctrl+Alt+P); Recunoaste si copiaza (Ctrl+C) / Copiaza zona ca imagine (Ctrl+Shift+C).

**Personalizare OCR:** Vezi dictionare (Ctrl+Alt+D; per limba; adauga/sterge cuvinte; import .txt/.dic); limbi utilizator (bazate pe una existenta; alfabet; dictionar niciunul/integrat/utilizator/expresie regulata; avansat: caractere de inceput/sfarsit de cuvant, non-alfabetice, ignorate, interzise; cifre arabe, romane, abrevieri); grupuri de limbi; Editor de patterns (nou, editeaza, proprietati, sterge, seteaza activ); antrenare (dialog: chenarul caracterului, introducere caracter, mutare limite stanga/dreapta, inapoi, sari; maxim 1000 caractere noi; ligaturi); salvare patterns si limbi intr-un fisier unic.

### 6.6 Compare

- Doua zone de afisare (Doc 1 stanga, Doc 2 dreapta), fiecare cu dropdown de documente recente si buton de deschidere; drag-and-drop; comutare Ctrl+Tab sau Alt+1/2; split orizontal optional; scroll sincronizat (implicit pornit; se poate opri din View, meniul contextual sau butonul de deasupra documentului).
- Panou dreapta, tab **Compara:** limba (lista + detectie automata); optiuni de baza: gaseste diferente de punctuatie, gaseste diferente de o litera; avansate: mod recunoastere PDF (doar text PDF | automat | OCR), gaseste automat antete si subsoluri, reseteaza; buton Compara (Ctrl+R); dialog de progres cu sfaturi si avertismente.
- Tab **Diferente:** numar (si pe o bara rosie deasupra documentelor); lista cu iconuri Sters/Adaugat/Modificat, text vechi si nou, pagina in fiecare document; grupare on/off (Corp text, Antete si subsoluri, Numerotare); navigare (clic in document sau lista, Ctrl+Sageata Dreapta/Stanga, butoane); ignora (Del, buton, meniu; selectie multipla cu Ctrl; "Ignora diferentele identice"); copiaza diferenta; selecteaza toate (Ctrl+A); undo/redo.
- Salveaza (sageata): Doc 1 sau Doc 2 ca PDF cu un comentariu per diferenta; Doc ca Word cu Track Changes; lista diferentelor ca tabel Word. Diferentele ignorate nu apar in raport.
- Comparatii recente; deschidere din Explorer ("Compara cu...", "Compara documentele...") si din PDF Editor.
- Algoritm: extrage textul (strat PDF sau OCR, dupa mod) cu pozitii; normalizeaza (spatii, cratime optionale, ligaturi); detecteaza antete/subsoluri (text repetat in aceeasi pozitie pe >50% din pagini [DECIZIE]) si numerotari; aliniere pe cuvinte (SequenceMatcher pe tokeni + rapidfuzz pentru potriviri aproximative); clasifica in delete/add/change; filtreaza dupa optiuni; grupeaza; mapeaza la bbox-uri pentru evidentiere.

### 6.7 Hot Folder

- Aplicatie in tray (icon apare dupa prima sarcina), porneste la logare (setabil), fereastra cu toolbar: Nou, Modifica (doar sarcini oprite), Copiaza, Sterge, Porneste, Opreste, Jurnal, Import/Export, Activeaza jurnal, Notificari.
- Tabel sarcini: Nume, Status, Urmatoarea pornire, Ultima rulare, Rezultat.
- Asistent sarcina noua (pasi): 1) Nume; 2) Program: o singura data (data+ora) sau recurent (la fiecare minut, zilnic, saptamanal, lunar + ora); 3) Sursa: folder local/retea, FTP (utilizator/parola sau anonim), cutie postala (IMAP/Outlook: atasamente noi), proiect OCR; originale: pastreaza/sterge/muta in folder; 4) Procesare: limbi, recunoaste/analizeaza/preprocesare, optiuni OCR si preprocesare, zone automat sau sablon de zone, stergere automata pagini goale (+ mutare in folder); 5) Salvare: unul sau mai multi pasi, fiecare cu format + optiuni, PDF cautabil sau imagine, folder destinatie, iesire: document separat per fisier (pastreaza ierarhia) | document separat per folder (pastreaza ierarhia) | un document pentru toate; nume fisier; 6) Creeaza sarcina.
- Statusuri: Ruleaza, Programat, Urmareste, Oprit, Finalizat, Eroare (vezi jurnalul).
- Jurnal TXT langa rezultate: nume si setari sarcina, erori, avertismente, statistici (pagini, nr. erori, nr. avertismente, caractere nesigure).
- Notificare desktop la final.
- Export/import sarcini (JSON).
- [OPTIONAL] contor de 5.000 pagini/luna pe 2 nuclee ca in original - implicit dezactivat.

### 6.8 Sarcini automatizate (Automated Tasks)

Dialog cu toolbar (Nou, Editeaza, Copiaza, Sterge, Import, Export) si lista; constructor de pasi:
1. Sursa proiect: nou (setari globale sau ale sarcinii) | existent | curent.
2. Obtinere imagini: deschide imagini/PDF din folder | scaneaza (optional daca proiectul e existent/curent).
3. Analiza: automata | desenare manuala a zonelor (sarcina se opreste si asteapta utilizatorul) | sablon (anume sau ales la pornire).
4. OCR (adauga automat Analiza).
5. Iesiri (una sau mai multe): Salveaza document (nume, format, optiuni, folder, subfolder cu marcaj de timp), Trimite document (aplicatie), E-mail document, Salveaza imagini (multipagina pentru TIFF/PDF/JBIG2/DCX), E-mail imagini, Salveaza proiect OCR.
Stergerea Analizei sterge si OCR. Paginile deja recunoscute nu se reproceseaza. Sarcinile apar in fereastra Sarcini si se pot rula dintr-un clic.

### 6.9 Screenshot

Icon in tray; captura: zona, fereastra, ecran, cu intarziere 5 s; trimite: text/tabel/imagine in clipboard, text in Word, tabel in Excel, text/tabel/imagine in fisier, imagine in OCR Editor (proiectul curent sau nou), imagine pe e-mail; optiuni: mereu deasupra, porneste la logare, sunete; limba OCR selectabila.

### 6.10 Integrari Windows [ETAPA FINALA]

- Meniu contextual Explorer: Editeaza cu [Produs]; Converteste cu [Produs] > PDF cautabil, PDF imagine, Word, Excel, alte formate; Deschide in OCR Editor; Compara cu...; Compara documentele... (2 fisiere selectate); Combina intr-un PDF...; pentru fisiere Office: Converteste in PDF / Converteste si trimite. Comenzile depind de numarul si tipul fisierelor.
- Add-in Office (COM sau VSTO): Word (Creeaza PDF, Creeaza PDF si trimite, Scaneaza in Word, Converteste in Word, Compara cu...), Excel (Creeaza PDF, ...si trimite), PowerPoint (Creeaza PDF; note vorbitor; slide-uri ascunse), Outlook (PDF din mesaje, din folder, din atasamente); setari PDF/A, PDF/UA, parola, etichete, semne de carte din titluri, pagini (toate/intreaba).
- Asocieri de fisiere si previzualizare PDF in Explorer [OPTIONAL].

---

## 7. Formate suportate

| Format | Intrare | Iesire |
|---|---|---|
| PDF (pana la 2.0), PDF/A, PDF/UA | Da | Da |
| DOC/DOCX, XLS/XLSX, PPTX | Da (PDF Editor, Compare; conversie prin LibreOffice headless daca exista) | Da |
| PPT, VSD/VSDX, ODS, ODP, SVG | Da (PDF Editor; convertite in PDF) | Nu |
| RTF, TXT, ODT, HTML | Da | Da |
| CSV, EPUB, FB2 | Nu | Da |
| XPS | Da | Nu |
| DjVu | Da | Da |
| JPEG, JPEG2000, PNG, TIFF (multipagina), BMP, PCX/DCX, JBIG2 | Da | Da |
| GIF | Da | Nu |

---

## 8. Specificatii backend (core)

### 8.1 Pipeline OCR
`ingest -> preprocess -> analyze(layout) -> recognize -> postprocess(dictionar, spatii, cratime) -> verify -> export`. Fiecare pagina are status si se poate relua de la orice etapa. Rezultatul OCR contine pe caracter: valoare, bbox, incredere (0-100) si flag `uncertain` (incredere < prag din setari, implicit 70 [DECIZIE]).

### 8.2 Preprocesare
Fiecare unealta: functie pura `apply(image: np.ndarray, params) -> np.ndarray` + metadate (nume, parametri, se aplica la fotografii/scanari). Deskew (Hough + proiectii), indreptare randuri (dewarp pe linii de text), trapez (detectie contur pagina + transformare de perspectiva; manual din 4 puncte), split facing pages (detectie cotor), orientare (OSD Tesseract), rezolutie (estimare din inaltimea literelor x), page edges, whiten background (estimare fundal + normalizare), ISO noise (non-local means), motion blur (deconvolutie Wiener/Richardson-Lucy), inversare (detectie text deschis pe fundal inchis), alb-negru (Sauvola adaptiv), remove color marks (segmentare HSV a culorilor saturate pe fundal alb), levels, brightness/contrast, eraser, crop.

### 8.3 Analiza layout
Detectie zone (PP-Structure) + clasificare text/tabel/imagine/fundal/cod de bare; detectie structura tabel (randuri, coloane, celule unite); ordine de citire (coloane, apoi sus-jos; respecta RTL); detectie antete/subsoluri/note de subsol/cuprins/liste (euristici pe pozitie, marime font, repetitie intre pagini); titluri pentru semne de carte automate; detectie limba per zona daca e activa.

### 8.4 Moduri PDF
- `UseOnlyPdfText`: foloseste stratul text existent (implicit pentru PDF digital).
- `AutoChoose`: evalueaza calitatea stratului (procent de caractere valide in dictionar, codificare corecta, acoperire) - daca e sub prag, OCR.
- `UseOcr`: OCR intotdeauna.
PDF-urile scanate / cautabile / imagine folosesc mereu OCR.

### 8.5 Editare PDF

**Potrivirea fonturilor (regula confirmata de ABBYY):** la editarea unui PDF, fontul NU se preia din fisier, ci se alege cel mai apropiat font instalat pe calculator. Implementeaza un `FontMatcher` care, pornind de la numele fontului, metricile glifelor (latime medie, inaltimea x, inaltimea majusculelor), serif sau sans, grosime si inclinare, alege cel mai apropiat font local; cand textul editat se reda, foloseste fontul potrivit, nu cel original.

**GlyphRecovery:** pentru PDF-urile cu codificare stricata (textul se vede dar nu se poate selecta), reconstruieste maparea caracterelor din formele glifelor, folosind OCR pe glifele randate. Tinta: doua din trei astfel de fisiere.

Model intern de pagina pentru editare: blocuri de text (paragrafe cu linii, run-uri cu font/marime/culoare), imagini, tabele detectate. La salvare se rescrie content stream-ul paginii (text ca obiecte text cu fonturile incorporate/subset; pentru scanari: zona editata se acopera cu culoarea fundalului si se scrie textul nou). Pastreaza tot ce nu a fost editat byte-identic. Versiunea PDF nu scade la salvare.

### 8.6 Exportori si setari per format

**Regula de baza: modul de layout limiteaza formatele disponibile.** Implementeaz-o exact asa (citita din dropdownul original):

| Mod de layout | Formate permise |
|---|---|
| Exact copy | RTF, DOC(X), PDF, PPTX, ODT, DjVu |
| Editable copy | RTF, DOC(X), ODT |
| Formatted text | RTF, DOC(X), XLS(X), TXT, HTML, ODT, FB2, EPUB |
| Plain text | RTF, DOC(X), XLS(X), TXT, CSV, HTML, ODT, FB2, EPUB |
| Flexible layout | HTML |

In acelasi dropdown, sub lista de moduri, stau 3 bife: `Keep pictures`, `Keep headers and footers`, `Keep line breaks and hyphens`.

- **DOCX/RTF/ODT:** mod layout (Copie exacta = cadre/text box-uri pozitionate absolut; Copie editabila = paragrafe + coloane + tabele, aproape de original; Text formatat = fonturi, marimi, paragrafe, aliniat stanga (dreapta pentru RTL), text vertical devine orizontal; Text simplu = fara formatare); dimensiune hartie implicita; imagini (calitate: Cea mai buna/Echilibrat/Compact/Personalizat); pastreaza antete, subsoluri si numere de pagina (doar Copie editabila); pastreaza ruperi de rand si cratime; pastreaza ruperi de pagina; pastreaza numerele de linie (doar Copie editabila, in camp separat); pastreaza culorile textului si fundalului; pastreaza B/I/U in text simplu; evidentiaza caracterele nesigure (culoarea din setari); pastreaza metadatele (+ editare). Liste numerotate/marcate devin liste native Word; linkuri pastrate. Elementele de structura dezactivate se exporta ca text obisnuit.
- **XLSX/CSV:** fiecare tabel pe foaie separata sau toate pe una [DECIZIE: optiune]; ignora textul din afara tabelelor (optiune); numerele se convertesc in valori numerice (optiune); CSV: separator, codificare.
- **PPTX:** un slide per pagina; text in casete; imagini; pastreaza ruperi de rand.
- **PDF:** calitate imagine (Cea mai buna = rezolutia originala; Echilibrat; Compact = 300 dpi; Personalizat); PDF/A (versiuni) - incompatibil cu criptarea; PDF/UA (necesita OCR; poate arata putin diferit); parole si permisiuni (AES-128/256; criptare totala sau fara metadate); stergere obiecte (comentarii si marcaje, linkuri/media/actiuni/scripturi/date formular, semne de carte, atasamente); o singura dimensiune de hartie pentru toate paginile; MRC (doar PDF cautabil cu text sub imagine); netezire caractere (echivalent PreciseScan); mod PDF cautabil: Text si imagini doar | Text peste imaginea paginii | Text sub imaginea paginii; semne de carte din titluri; etichete PDF; fonturi: predefinite | Windows; incorporeaza fonturi (doar primele doua moduri); pastreaza metadatele.
- **HTML:** layout flexibil | text formatat | text simplu; codificare; culori; imparte in mai multe fisiere dupa marime; cuprins din titluri de nivel 1.
- **TXT:** text formatat | simplu; ruperi de rand; ruperi de pagina; codificare (detectie automata, UTF-8/UTF-16/ANSI); metadate.
- **EPUB/FB2:** cuprins din titluri, coperta din prima pagina (optiune), fonturi incorporate (EPUB), metadate.
- **DjVu:** calitate (Cea mai buna/Echilibrat/Compact), mod (strat text + imagine).
- **Imagini:** format, color/gri/alb-negru, rezolutie, compresie, multipagina.

### 8.7 Comparare - vezi 6.6. CLI identic cu sectiunea 9.

### 8.8 Automatizare
Runner unic pentru Automated Tasks, Hot Folder si CLI: executa o lista de pasi tipizati, cu context (proiect, fisiere, setari), jurnal structurat (JSON intern + export TXT), reluare la eroare per fisier (un fisier esuat nu opreste lotul; fisierele neprocesabile intra intr-un job separat). Hot Folder: scheduler persistent (APScheduler cu jobstore SQLite), watchdog pentru foldere locale, polling pentru retea/FTP/e-mail; blocare impotriva rularii duble; fisierele noi se considera stabile dupa 3 s fara modificari [DECIZIE].

### 8.9 Gestionarea erorilor
Ierarhie de exceptii (`DocError`, `OcrError`, `PdfPasswordRequired`, `UnsupportedFormat`, `ScannerError`, `ExportError`, `TaskError`); fiecare cu mesaj localizat pentru utilizator + detalii tehnice in jurnal (`%LOCALAPPDATA%\[Produs]\logs`, rotatie). Dialog de eroare cu "Copiaza detaliile". Nu se pierd date: salvare automata a proiectului OCR la fiecare 5 minute [DECIZIE] si fisier de recuperare.

---

## 9. Linie de comanda (compatibila ca semantica cu originalul)

```
dl-ocr.exe <fisiere...> | /scan [Scanner] [/lang L1 L2 ...] [/send MSWord|MSExcel|OpenOffice|Mail|Clipboard|WebBrowser|PDFViewer|PowerPoint] [/out Rezultat.ext] [/report raport.txt]
dl-compare.exe /compare /file1:A /file2:B [/lang:L] [/recMode:UseOnlyPdfText|AutoChoose|UseOnlyOCR] [/options:NoHeadersFooters,IgnorePunctDiff,IgnoreOneLetterDiff,UngroupDiff] [/saveFile:Out.ext /saveMode:PdfDocument1|PdfDocument2|Word]
```
- Limbi utilizator: prefix `@@` (ex. `@@LimbaMea`).
- Fara `/lang` se foloseste ultima limba folosita.
- Fara `/out` / `/saveFile`, rezultatul se deschide in aplicatia potrivita.
- Daca `/out` exista deja, fisierul se modifica (suprascrie) - cere confirmare doar in modul interactiv.
- Coduri de iesire: 0 succes, 1 eroare argumente, 2 fisier inexistent, 3 eroare OCR, 4 eroare export.
- Afiseaza o fereastra de progres (sau `--quiet` pentru consola).

Nume limbi CLI (selectie): English, Romanian, RomanianMoldavia, German, French, Italian, Spanish, Russian, Hungarian, Bulgarian, Ukrainian, SerbianLatin, SerbianCyrillic, Turkish, Greek, Polish, Czech, Slovak, ChinesePRC, ChineseTaiwan, Japanese, Korean, Arabic, Hebrew, Digits, Mathematical etc. Mapare interna la codurile Tesseract (`ron`, `eng`, ...).

---

## 10. Securitate

- Aplicatie offline: niciun apel de retea in afara de: FTP/e-mail configurate explicit de utilizator, server de timestamp la semnare (configurabil), verificare actualizari (oprita implicit).
- Credentialele FTP/e-mail criptate cu Windows DPAPI.
- JavaScript din PDF dezactivat implicit; rulare doar intr-un sandbox limitat [DECIZIE: suport limitat la actiuni de formular].
- Parsare PDF robusta la fisiere malformate (fuzzing cu un corpus de PDF-uri corupte; limite de memorie si timp per pagina).
- Redactarea elimina efectiv continutul (text, imagini, glife) din content stream, nu doar il acopera; test automat: textul redactat nu mai poate fi extras.
- "Elimina datele ascunse" sterge: metadate XMP si Info, comentarii, atasamente, JavaScript, actiuni, form data, semne de carte, straturi OCR ascunse, obiecte nefolosite.
- Validarea tuturor inputurilor (intervale de pagini, cai, nume de campuri, parametri CLI).
- Jurnal de audit local pentru operatiile Hot Folder si CLI.
- Backup inainte de suprascrierea unui fisier sursa (optiune).

---

## 11. Testare si criterii de acceptanta

**Planul complet e in `SPEC_06_plan_de_testare.md`, iar matricea cerinta → test in `SPEC_07_matrice_trasabilitate.csv`.** Acolo gasesti: cele 18 grupuri ale corpusului de test cu ce verifica fiecare, cele 19 praguri de calitate masurabile, procedurile celor 53 de teste de prioritate 1, cele 10 scenarii de acceptanta cronometrate si lista deschisa a ce nu acoperă planul.

Rezumatul obligatiilor:
- 1.501 de teste, unul per cerinta. `python3 -I genereaza_matrice_trasabilitate.py` regenereaza matricea si pica dacă o cerinta rămâne descoperita.
- Niciun build nu se livreaza cu un test de prioritate 1 picat (138 de cerinte).
- **Niciun test picat pe o cerinta marcata `D`.** O cerinta confirmata in documentatia oficiala care nu trece inseamna ca produsul se comporta altfel decat originalul.
- `python3 -I verifica_schema.py` ruleaza inainte de orice altceva: verifica 28 de reguli de business impuse direct in schema bazei de date.
- Corpusul de test are rezultatul asteptat scris de mana in fisiere `.expected`. Un test de OCR fara referinta scrisa de om nu verifica nimic.
- Pragurile cheie: acuratete pe caracter ≥ 98% pe scanari de 300 dpi; acuratete pe cuvant ≥ 96% pe documentele romanesti; confuzie ș/ş si ț/ţ ≤ 2 la 1.000 de caractere; structura de tabel ≥ 90% celule corecte; sub 4 s per pagina A4 in modul `thorough` pe 8 nuclee; interfata nu se blocheaza peste 200 ms.
- O scadere de peste 2% a oricarui indicator fata de build-ul anterior se trateaza ca regresie, chiar dacă valoarea rămâne peste prag.
- `Y-001` e un criteriu de livrare, nu o preferinta: toata suita de integrare trebuie sa treaca cu interfata de retea dezactivata.

---

## 12. Plan de dezvoltare pe etape

Fiecare etapa se termina cu: cod + teste verzi + demo documentat + actualizare `docs/`.

1. Analiza cerintelor - transforma aceasta specificatie in backlog (`docs/backlog.md`), cu ID per functie.
2. Arhitectura - schelet de pachete, interfete (`OcrEngine`, `Exporter`, `ImageTool`, `TaskStep`), CI (lint, mypy, pytest).
3. Baza de date - schemele `app.db` si `project.db`, migratii, teste de integritate.
4. Design system - tokeni, tema luminoasa/intunecata, componente comune (6.2) + galerie de componente.
5. Structura aplicatiei - cele 6 executabile, setari globale, dialogul Options complet.
6. (Nu exista autentificare - etapa inlocuita cu: licenta locala optionala si contor de pagini.)
7. (Nu exista roluri - etapa inlocuita cu: permisiuni PDF si autorul comentariilor.)
8. Module principale: OCR Editor (proiect, preprocesare, zone, OCR, verificare, export DOCX/PDF/TXT) -> PDF Editor (vizualizare, cautare, comentarii, organizare pagini, salvare) -> Lansator.
9. Module secundare: Edit Content, Securitate, Semnaturi, Formulare, restul exportorilor, Compare, Screenshot.
10. Automatizari: Automated Tasks, Hot Folder, CLI.
11. Integrari: Explorer, Office, scanare TWAIN/WIA, cloud prin foldere locale.
12. Rapoarte: jurnale Hot Folder, raport CLI, rapoarte Compare.
13. Testare completa (functional, UI, performanta, securitate, regresie).
14. Optimizare (paralelism, cache de randare, memorie).
15. Deployment: instalator Inno Setup cu Tesseract si modele incluse, semnare cod, instalare silentioasa (`/SILENT`).
16. Documentatie finala: manual utilizator (RO/EN), ghid administrator, `docs/decizii.md`, `docs/diferente.md`.

---

## 13. Reguli de business (obligatoriu de implementat si testat)

1. PDF cu strat text digital: mod implicit "Doar text din PDF"; scanat/cautabil/imagine: mereu OCR.
2. MRC doar pentru PDF cautabil cu "Text sub imaginea paginii".
3. Incorporarea fonturilor doar pentru "Text si imagini doar" sau "Text peste imagine".
4. "Pastreaza numerele de linie" si "Pastreaza antete/subsoluri" doar in "Copie editabila".
5. Elementele de structura dezactivate se exporta ca text simplu.
6. Stergerea pasului Analiza dintr-o sarcina sterge si OCR.
7. Paginile recunoscute nu se reproceseaza intr-o sarcina; cele analizate se recunosc.
8. Modificarea unei zone sau a setarilor OCR invalideaza textul paginii (status inapoi la `analyzed`).
9. Parola de permisiuni diferita de parola de deschidere.
10. Metadatele nu se editeaza la fisiere protejate cu parola (pana la deblocare).
11. "Imparte celule" doar pe celule unite anterior; zonele Tabel si Cod de bare nu accepta segmente.
12. Camp de formular obligatoriu = avertisment, nu blocare; nume camp unic, fara puncte la margini sau duble.
13. Imparte documentul: nu pastreaza semnele de carte; atasamentele in subfolder.
14. Diferentele ignorate nu apar in raportul Compare.
15. Doar campurile de semnatura goale se pot copia.
16. Hot Folder: "Modifica" doar pe sarcini oprite.
17. Separarea paginilor fata in fata conteaza ca 2 pagini in contorul de pagini [DECIZIE, preluata din FineReader Server].
18. Doar o instanta de Hot Folder ruleaza per utilizator [DECIZIE].
19. Codurile de bare: recunoastere oprita implicit; tip implicit "Autodetectare".
20. Antrenarea de patterns: oprita implicit; maxim 1000 caractere noi per pattern.
21. Stergerea unei zone de pe o pagina recunoscuta sterge si textul ei.
22. Zonele se numeroteaza automat stanga-dreapta la analiza, indiferent de directia textului.
23. Modul de layout limiteaza formatele de export (tabelul din 8.6). Formatele nepermise apar gri in dialogul de salvare.
24. Zonele nu se pot suprapune: o zona noua desenata peste alta fie o taie, fie e refuzata cu avertisment.
25. Zonele Text, Picture si Background Picture pot fi poligoane (add/cut area part); Table si Barcode nu.
26. Un stil cu rolul Heading (1-10) genereaza semn de carte la salvarea in PDF, daca e activ "Create bookmarks from headings".
27. Cand "Create PDF/UA" e bifat, "Create PDF tags" devine fortat si dezactivat.
28. Text editat in OCR Editor si salvat cu "Text under the page image" nu se vede pe pagina, dar exista in stratul de text.
29. O sarcina Hot Folder poate avea mai multi pasi de salvare si poate scoate simultan mai multe formate.
30. Cu cat sunt selectate mai multe limbi OCR, cu atat recunoasterea e mai lenta; afiseaza un avertisment peste 3 limbi.
31. La editarea unui PDF, fontul se potriveste din fonturile instalate local, nu se preia din fisier (vezi 8.5).

---

## 14. Livrabile finale ale tale

- Codul sursa complet, structurat ca in sectiunea 3.
- Instalator Windows.
- Suita de teste + raport de acoperire (>= 80% pe `core`).
- `docs/arhitectura.md`, `docs/decizii.md`, `docs/diferente.md`, `docs/manual_ro.md`, `docs/manual_en.md`, `CHANGELOG.md`.
- O lista de verificare cu fiecare ID din backlog, statusul si dovada (test sau captura).

Incepe cu etapa 1. La finalul fiecarei etape, raporteaza ce ai facut, ce teste ruleaza si ce urmeaza.
