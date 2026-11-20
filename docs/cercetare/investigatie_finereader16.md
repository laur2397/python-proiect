# ABBYY FineReader PDF 16 - Investigatie si specificatie de reconstructie

Nov 19, 2026 · @Marius

## Cum se citeste documentul

Tinta reconstructiei este ABBYY FineReader PDF 16 pentru Windows, editia Corporate, ultima versiune publica verificata fiind build 16.0.14.7295. Alternativa se construieste in Python, desktop, offline. Documentul are 10 capitole, cate unul pentru fiecare livrabil cerut. Master Prompt-ul complet e intr-un fisier .md separat, gata de copiat.

**Baza de cercetare (revizia 2, 19 noiembrie 2026):** documentatia oficiala (help v16, ghidul utilizatorului in PDF, lista completa de functii din decembrie 2025, baza de cunostinte, release notes, blogul ABBYY) **plus 22 de tutoriale video analizate cadru cu cadru**: doua webinarii oficiale ABBYY de la A la Z (56 si 26 de minute), 12 tutoriale scurte oficiale, si 8 tutoriale independente, dintre care unul de 33 de minute care deschide pe rand toate tab-urile dialogului Options. Din ele am extras peste 60 de cadre oprite si marite, din care am citit textul exact al meniurilor, butoanelor si dialogurilor.

**Ce acopera asta:** fiecare fereastra, fiecare tab de ribbon, fiecare dialog important, fiecare optiune din Options, culorile zonelor, barele de proprietati si comportamentul la fiecare pas. Capitolul 3 nu mai e deductie din text, ci transcriere a ecranelor reale.

**Ce ramane neacoperit:** valorile HEX exacte si dimensiunile in pixeli (cadrele video sunt comprimate si redimensionate). Oricum nu trebuie copiate: alternativa are paleta, iconurile si numele ei proprii.

**Nume si marca:** alternativa trebuie sa aiba nume, logo si iconuri proprii. Se reproduc structura, fluxurile si comportamentul, nu marca ABBYY sau grafica originala.

**Legenda nivelurilor de incredere**

| Cod | Sens |
| --- | --- |
| A | Confirmata oficial (help, ghid, brosura ABBYY) |
| B | Confirmata din demonstratii: vazuta pe ecran intr-un tutorial |
| C | Confirmata din mai multe surse independente |
| D | Probabila: deductie logica, neconfirmata direct |
| E | Necunoscuta: informatii insuficiente |
| F | Contradictorie: sursele difera |

Daca un rand nu are cod, este A sau B.

**Acest document nu mai este singurul livrabil.** Dupa a treia runda de lucru, specificatia propriu-zisa a fost scoasa in sapte fisiere separate, pentru ca un capitol de sinteza nu e suficient ca sa se construiasca produsul. Documentul de aici ramane raportul de investigatie si harta; fisierele sunt specificatia executabila:

| Fisier | Ce contine |
| --- | --- |
| `SPEC_01_lansator_si_pdf_editor.md` | 409 cerinte, A-001 ... I-033 |
| `SPEC_02_ocr_editor.md` | 358 de cerinte, J-001 ... Q-065 |
| `SPEC_03_compare_automatizare_cli.md` | 357 de cerinte, R-001 ... Z-030 |
| `SPEC_04_schema_bd.sql` | 51 de tabele, 34 de indecsi, 23 de triggere, 5 vederi |
| `SPEC_05_api_core.py` | 124 de clase, 308 semnaturi, 42 de exceptii cu coduri |
| `SPEC_06_plan_de_testare.md` | corpus de test, 19 praguri masurabile, proceduri de test |
| `SPEC_07_matrice_trasabilitate.csv` | 1.124 de cerinte catre 1.124 de teste, 1:1 |
| `SPEC_08_raport_divergente.md` | fiecare divergenta gasita la verificarea contra manualului oficial |

**Total: 1.124 de cerinte numerotate**, fiecare cu intrari, validari, rezultat si erori.

**Runda a treia de verificare.** Manualul oficial ABBYY FineReader PDF, 513 pagini, a fost citit integral si confruntat cerinta cu cerinta. Rezultatul: 998 de cerinte sunt acum confirmate din documentatia oficiala, 37 din tutoriale video, 6 din baza de cunostinte ABBYY, 65 sunt adaugiri proprii si 15 sunt diferente deliberate, fiecare cu motivul scris. Fiecare cerinta poarta aceasta marca, deci se vede exact ce e reproducere si ce e invenție.

Verificarea a scos la iveala si erori in versiunea anterioara a specificatiei: linia de comanda era in mare parte inventata (in realitate sunt doua executabile cu doua sintaxe diferite), Hot Folder nu poate rula ca serviciu, evenimentele butoanelor de formular aveau patru nume din sase greșite, si lipseau module intregi, printre care copierea continutului din PDF, confirmarile de securitate si lucrul in grup pe dictionare partajate. Toate sunt listate in `SPEC_08_raport_divergente.md`.

**Runda a patra: audit.** Verificarea a aratat doua probleme. Prima: rescrierea de la runda a treia adusese corectiile din manual, dar stersese detaliu de interfata valid, cules din cele 22 de tutoriale analizate cadru cu cadru — uneltele de selectie si de tragere a paginii din PDF Editor, dialogul de calitate personalizata a imaginii, bara de proprietati de imagine din OCR Editor, macrocomenzile pentru numele fisierelor din Hot Folder, structura raportului de comparare. A doua: lipseau tabele de referinta intregi, fara de care produsul nu se poate construi.

Ambele sunt rezolvate in doua fisiere noi. `SPEC_09_anexe_referinta.md` adauga toate scurtaturile pe cele patru ferestre, tabelul de formate cu cele trei capabilitati separate pentru fiecare format, limbile, fonturile per scriere, diferentele intre editii, meniurile, factorii de luat in seama inainte de OCR si 21 de situatii de depanare. `SPEC_10_interfata_detaliata.md` pune inapoi interfata la nivel de element: fiecare bara, fiecare panou, fiecare dialog si fiecare mesaj de stare, cu ordinea exacta a controalelor.

Specificatia a ajuns la **1.487 de cerinte numerotate**, dintre care 1.063 confirmate din documentatia oficiala, 300 observate pe ecran, 9 din baza de cunostinte ABBYY, 72 adaugiri proprii si 25 diferente deliberate. Numarul cerintelor de prioritate 1 a crescut de la 100 la 138. Regula de lucru s-a schimbat si ea: de acum se adauga prin apendare, nu prin rescriere, ca sa nu se mai piarda nimic.

Auditul a scos la iveala si contradictii in sursele oficiale ale ABBYY: manualul spune 201 limbi de recunoastere si 37 de limbi de comparare, iar pagina de specificatii a produsului spune 198 de limbi si 53 cu dictionar. Specificatia le noteaza pe amandoua, cu sursa, in loc sa aleaga una.

## 1. Raport de investigatie

FineReader PDF 16 nu e o singura aplicatie, ci un pachet de 6 programe desktop care lucreaza impreuna: fereastra New Task (lansator), PDF Editor, OCR Editor, ABBYY Compare Documents, ABBYY Hot Folder si ABBYY Screenshot Reader. Toate folosesc acelasi motor OCR si acelasi dialog global Options. Produsul rezolva trei probleme: transforma scanari si PDF-uri imagine in documente editabile, editeaza orice PDF (inclusiv scanat) si automatizeaza conversiile in volum.

### 1.1 Versiuni si stare

| Element | Valoare | Sursa |
| --- | --- | --- |
| Versiune curenta | FineReader PDF 16, Release 3 Update 2, build 16.0.14.7295 | [Release notes](https://support.abbyy.com/hc/en-us/sections/9279032986387) |
| Prima lansare v16 | 26.09.2022, build 16.0.12.3977 | [Release 1 Update 2](https://support.abbyy.com/hc/en-us/articles/9928811814547-FineReader-PDF-16-Release-1-Update-2-build-16-0-12-3977) |
| Versiunea 15 | End of Support si End of Life la 1 octombrie 2025 | [Anunt EoL](https://support.abbyy.com/hc/en-us/articles/29214691204882) |
| Lista de functii | revizia din 16 decembrie 2025, tot pentru v16 | [Full feature list](https://portale.siva.it/files/doc/product/abbyy%20-%20finereader%20brochure.pdf.pdf) |
| Platforma | aplicatie nativa x64, Windows 10/11 64-bit si Windows Server 2012 R2-2022 | Ghid utilizator v16 |

Nu am gasit o versiune 17. Un site de download (FileHorse) listeaza imbunatatiri "2026" (selectie de pagini cu chenar in Organize Pages, controlul performantei proceselor de fundal, editare PDF in limba thai), dar nu da build sau data. Nivel: F, de verificat la ABBYY.

### 1.2 Editii si ce le deosebeste

Corporate = Standard + procesare automata (Hot Folder, Automated Tasks) + Compare Documents ([ABBYY Support](https://support.abbyy.com/hc/en-us/articles/4415642638355)). Hot Folder are limita de 5.000 de pagini pe luna, pe maxim 2 nuclee CPU. Linia de comanda extinsa (salvare automata in fisier) se cumpara separat si are limite de timp si de pagini.

| Editie | Pret indicativ | Ce aduce in plus |
| --- | --- | --- |
| Standard Windows | 16 $/luna sau \~99 EUR/an | OCR, editor PDF, conversie, formulare, securitate |
| Corporate Windows | 24 $/luna sau \~165 EUR/an | + Compare Documents, Hot Folder, Automated Tasks |
| Mac | \~69 $/an | OCR complet, dar mult mai putine functii PDF |

Preturile vin din [Capterra](https://www.capterra.com/p/65868/ABBYY-FineReader/) si [FileHorse](https://www.filehorse.com/download-abbyy-finereader-pdf/), nu din magazinul ABBYY (pagina de preturi nu s-a incarcat). Nivel: C.

### 1.3 Cifre cheie ale motorului OCR

- 198 de limbi OCR, dintre care 53 cu dictionar. Romana exista in doua variante: Romanian si RomanianMoldavia.
- Acuratete declarata de producator: pana la 99,8% (test intern ABBYY).
- Compare Documents lucreaza in aproximativ 40 de limbi, cu detectie automata.
- OCR-ul paralelizat pe mai multe nuclee, cu numarul de nuclee setabil.
- Tehnologia ADRT reconstruieste structura documentelor cu mai multe pagini: titluri, antete, subsoluri, note de subsol, numere de pagina.

### 1.4 Ce spun utilizatorii

Pe Capterra produsul are nota 4,7 din peste 420 de recenzii, iar pe G2 are 4,5 din 295. Laudati sunt OCR-ul si pastrarea aspectului paginii. Plangerile repetate sunt:

- Interfata are multe unelte, care ii coplesesc pe incepatori, iar unele comenzi nu sunt unde te-ai astepta.
- Nu exista tab-uri pentru documente: fiecare PDF se deschide in alta fereastra ([forum ABBYY](https://support.abbyy.com/hc/ja/community/posts/20867865196435-New-tabbed-user-interface-in-FineReader-PDF-16)).
- Nu exista mod intunecat pe Windows.
- Scanarea salveaza uneori PDF-uri cu pagini de marimi diferite.
- Exportul Exact copy in Word e greu de editat; traducatorii prefera Plain text sau Editable copy.
- Programul porneste greu si e lent la fisiere mari.

Acestea sunt oportunitati pentru alternativa: tab-uri de documente, mod intunecat si pornire rapida.

## 2. Inventar complet de functionalitati

Produsul are 9 module functionale si 3 integrari externe. Sursa principala este lista oficiala de functii si ghidul v16. Coloana Editie arata S (Standard) sau C (doar Corporate).

Capitolul de aici descrie modulele la nivel de ansamblu. **Inventarul complet, cerinta cu cerinta, e in `SPEC_01`, `SPEC_02` si `SPEC_03`**: 1.124 de functii numerotate, fiecare cu ce primeste, ce valideaza, ce rezulta si ce eroare da. Cine construieste produsul lucreaza din acelea, nu din listele de mai jos.

### 2.1 Modul New Task (lansator)

Fereastra de start are 5 tab-uri in stanga si sarcini in dreapta. La hover pe o sarcina apare un pop-up cu scenariile tipice.

| Tab | Sarcini | Editie |
| --- | --- | --- |
| Open | PDF Document (deschide in PDF Editor), OCR Editor, Convert to PDF, Convert to Microsoft Word, Convert to Microsoft Excel, Convert to Other Formats (PPTX, ODT, HTML, EPUB, FB2, RTF, TXT, CSV, DjVu) | S |
| Scan | Scan to OCR Editor, Scan to PDF, Scan to Word, Scan to Excel, Image Files, Other Formats | S |
| Compare | Open ABBYY Compare Documents, Recent Comparisons | C |
| Recent | Documente PDF si proiecte OCR recente, cu cautare (Ctrl+F) | S |
| Mobile App | Deschide folderul Google Drive unde aplicatia iOS exporta JPG sau PDF | S |

Sarcinile de conversie au optiuni in panou: limbi OCR, calitatea imaginii, tipul de PDF, combinare intr-un singur fisier si reordonare fisiere (Alt+Sus/Jos).

### 2.2 Modul PDF Editor

PDF Editor are 5 tab-uri (ribbon): Document, Organize Pages, Edit Content, Security, Form Editor.

**Vizualizare si navigare (S)**

- 4 moduri: One-Page View, One-Page Scrolling, Two-Page View, Two-Page Scrolling, plus Full Screen (F11).
- Optiune pagini impare la dreapta, zoom, Fit to Width, Actual Size, Best Fit.
- Panou de navigare cu Pages, Bookmarks, Search, Attachments, Digital Signatures, plus panou Comments (F7).
- Recunoastere in fundal: un strat text temporar pe PDF-urile scanate, ca sa poata fi cautate si copiate.
- Detectie automata a linkurilor si JavaScript activabil per document sau global.

**Cautare (S)**

- Cautare in text, comentarii, semne de carte si metadate, cu Exact match si Match case.
- Marcare rezultate dintr-un clic: Highlight, Strikeout, Underline, cu culoare la alegere.
- Search and Replace si Search and Redact, inclusiv dupa o lista de cuvinte cheie salvata.

**Copiere continut (S)**

- Copy Area as Image, as Text si as Table. La tabele poti muta, adauga sau sterge separatori si poti uni sau imparti celule inainte de copiere.

**Review si colaborare (S)**

- Note, Highlight, Underline, Strikethrough si Insert Text.
- Forme: Ink, Line, Arrow, Rectangle, Oval, Polygon, Cloud, Polyline si Text box. Shift constrange unghiul.
- Raspunsuri la comentarii (Ctrl+Enter) si bifa per comentariu.
- Statusuri: Accepted, Rejected, Cancelled, Completed, plus istoric.
- Sortare si filtrare dupa Tip, Autor, Pagina, Data, Bifa si Status.
- Stampile: predefinite, din imagine sau text cu data si ora, gestionate intr-un manager.
- SharePoint check-in si check-out, precum si trimitere PDF pe e-mail.

**Edit Content (S)**

- Editare text in PDF-uri digitale, scanate sau cautabile, cu reflow in paragraf. Ctrl+E intra in modul editare, Ctrl+T adauga text.
- Formatare: font, marime, stil, spatiere, aliniere, culoare si directie.
- Editare celule de tabel individuale.
- Blocuri de text si imagini: mutare, redimensionare, stergere, rotire si aducere in fata.
- Eraser cu detectia culorii fundalului si Add Image.
- Linkuri catre o pagina, o destinatie, un URL, un e-mail sau un fisier.
- Headers and Footers: 6 pozitii, cu text, numar de pagina, numar Bates sau data si ora.
- Bates numbering cu Start at si Continue from.
- Watermark: 9 pozitii, rotire, transparenta, deasupra sau in spatele continutului, cu scop pe toate paginile, pe selectie sau pe un interval.
- Text layer: recunoaste pagina si inlocuieste stratul existent. Corecteaza inclinarea si orientarea.
- Bookmarks: creare, imbricare prin drag, redenumire si stergere, plus creare automata din titluri.
- Atasamente (adaugare, deschidere, salvare, redenumire, stergere) si metadate (Title, Author, Subject, Keywords).

**Organize Pages (S)**

- Selectie de pagini: interval (2, 3, 5-7), pare, impare sau toate.
- Delete, Rotate (cu iconuri la hover), Correct Page Orientation si Crop (un singur cadru sau cate unul per pagina).
- Add Blank Page, Add Pages from PDF, from File sau from Scanner, cu pozitie inainte, dupa sau dupa selectie.
- Move Pages, Replace Pages si Remove Blank Pages, cu revizuire inainte de stergere.
- Split Document dupa marime, numar de pagini sau semne de carte de nivel 1.
- Recognize Selected Pages si Send to OCR Editor.
- Improve Images: auto, deskew si PreciseScan. Create PDF from Selected Pages.
- Image processing settings: calitate, MRC, PreciseScan si limbi.

**Security (S)**

- Parola de deschidere si parola de permisiuni pentru tiparire, editare, copiere si cititoare de ecran.
- Criptare RC4 40-bit, AES 128-bit sau AES 256-bit, cu sau fara metadate.
- Semnatura digitala: certificat, Reason, Location, Contact, server de timestamp, imagine proprie, LTV, smartcard, SHA-256/384/512 si validare la deschidere.
- Semnatura text si semnatura din imagine, cu manager de semnaturi.
- Redactare manuala cu 7 culori, plus redactare pentru metadate, comentarii, semne de carte si atasamente.
- Erase Text and Pictures si Remove hidden data intr-un clic.

**Form Editor (S)**

- 7 tipuri de campuri: Text field, Drop-down, Check box, Radio buttons, Button, Signature field, List box.
- Tab General: Name, Tooltip, Required, Read-only, X, Y, latime, inaltime, unitati.
- Tab Appearance: umplere, bordura, grosime, font si culoare.
- Tab Format: text sau data. Tab List Items: Add, Edit, Delete, Default, Up, Down.
- Butoane cu actiuni pe evenimente Click, Mouse Enter, Mouse Exit, Focus si Blur. Actiunile includ Submit form (PDF, FDF, XFDF, HTML), Reset, Go to page, Open file, Follow link si Execute JavaScript.
- Import si export date de formular (FDF, XFDF, HTML), Highlight fields si Show field names.
- Linked copy si ghidaje de aliniere.

**Salvare si export (S)**

- Save, Save As PDF, Searchable PDF, Image-only PDF si PDF/A (1a pana la 3u). PDF/UA si PDF etichetat.
- Export in Word, Excel, PowerPoint, HTML si imagini, cu Reduce File Size (MRC, calitate).
- Print cu sau fara comentarii, plus E-mail.

### 2.3 Modul OCR Editor

- **Proiect OCR:** imagini, text recunoscut si setari intr-un singur proiect, salvabil si redeschis. Poti adauga, reordona, roti si sterge pagini. Reorder pages are modurile restore duplex si book pages. Paginile se pot muta intr-un proiect nou.
- **Achizitie:** Open Image (PDF, imagini, XPS, DjVu), Scan Pages (TWAIN sau WIA, ADF, duplex) si drag-and-drop intre instante.
- **Procesare automata la adaugare:** Recognize, Analyze sau Preprocess only.
- **Preprocesare automata:** split facing pages, orientare, deskew, straighten lines, rezolutie, page edges, whiten background, ISO noise, motion blur, trapez, inversare, alb-negru si remove color marks.
- **Image Editor:** Recommended Preprocessing, Deskew, Straighten Text Lines, Photo Correction, Correct Trapezoid Distortion, Rotate and Flip, Split, Crop, Invert, Resolution, Brightness and Contrast, Levels, Eraser si Remove Color Marks. Se aplica pe toate paginile, pe cele impare, pe cele pare, pe pagina curenta sau pe selectie.
- **Zone (areas):** 6 tipuri: Recognition Area, Text, Table, Picture, Background Picture si Barcode. Se pot desena, redimensiona, adauga sau scoate segmente, muta (Ctrl+drag), reordona, schimba ca tip si sterge.
- **Proprietati zona:** Language, Function (header, footer, footnote), Orientation, Print type, Inversion si CJK direction.
- **Tabele:** Analyze table structure, adaugare si stergere separatori, Split cells, Merge cells, Merge rows si Treat cells as picture.
- **Area templates:** salvare si incarcare (.blk/.blkx) pe pagini selectate sau pe toate.
- **Recunoastere:** Recognize Page, Recognize All, Recognize Area si Analyze. Moduri Thorough sau Fast.
- **Tipul documentului:** Auto, Typewriter sau Fax.
- **Detectie structura:** antete si subsoluri, note de subsol, cuprins si liste. Coduri de bare 1D si 2D: Code 39, QR, Data Matrix, Aztec, Patch etc.
- **Verificare:** Text pane cu navigare intre caractere nesigure, Verify Text (Ignore, Replace, Add to Dictionary, simboluri), Next/Previous Error si Mark Text as Verified.
- **Personalizare:** dictionare utilizator (import .pmd/.txt/.dic), limbi utilizator (alfabet, dictionar sau regex, caractere interzise), grupuri de limbi si Pattern Training (maxim 1.000 de caractere noi).
- **Style Editor** si **Redaction Mode** in textul recunoscut.
- **Salvare:** 5 moduri de layout (Exact copy, Editable copy, Formatted text, Plain text, Flexible layout). Formate: PDF cautabil sau imagine, DOCX, RTF, ODT, XLSX, CSV, PPTX, TXT, HTML, EPUB, FB2 si DjVu.
- **Imagini de pagina:** TIFF multi-pagina cu compresie ZIP, JPEG, CCITT G4, Packbits sau LZW.
- **Trimitere:** Send to Word, Excel, PowerPoint, PDF Editor, clipboard, browser, e-mail sau Kindle.
- **Warnings pane:** avertismente per pagina, cu navigare si stergere.

### 2.4 Modul Compare Documents (C)

- Compara doua documente in formate diferite: Word, PDF digital, scan sau ODT.
- Gaseste diferente de tip Delete, Add si Change, grupate pe Body text, Headers and footers si Numbering.
- Optiuni: diferente de punctuatie, diferente de o litera, detectie automata a antetelor si subsolurilor, plus modul de recunoastere PDF.
- Scroll sincronizat si split orizontal. Ignore Difference si Ignore Identical Differences.
- Salvare ca DOCX cu Track Changes, ca PDF cu comentarii pentru documentul 1 sau 2, sau ca tabel Word cu diferentele.

### 2.5 Modul Hot Folder (C)

- Programare: Run once sau Recurring (la fiecare minut, zilnic, saptamanal sau lunar).
- Surse: folder local sau de retea, FTP (inclusiv anonim), Outlook sau proiect OCR. Originalele se pastreaza, se sterg sau se muta.
- Procesare: limbi, Recognize, Analyze sau Preprocess, area template si stergere pagini goale cu mutare in folder.
- Iesire: mai multi pasi de salvare. Un document per fisier, per folder (cu ierarhie) sau unul singur pentru tot.
- Statusuri: Running, Scheduled, Watching, Stopped, Completed si Error (see log).
- Log TXT cu setarile, erorile si statisticile. Notificare la final, import si export .hft.

### 2.6 Modul Automated Tasks (C)

Un constructor de pasi: sursa proiect, apoi Open sau Scan, Analyze (auto, manual sau template), OCR si pasi de iesire (Save, Send, E-mail document, Save images, E-mail images, Save OCR project). Sarcinile se pot exporta si importa. Paginile deja recunoscute nu se reproceseaza.

### 2.7 Linie de comanda (C)

- `FineReaderOCR.exe` cu fisiere sau `/scan`, `/lang`, `/send` (MSWord, MSExcel, OpenOffice, Mail, Clipboard, WebBrowser, PDFViewer, PowerPoint), `/out` si `/report`.
- `Comparator.exe /compare` cu `/file1`, `/file2`, `/lang`, `/recMode` (UseOnlyPdfText, AutoChoose, UseOnlyOCR), `/options` (NoHeadersFooters, IgnorePunctDiff, IgnoreOneLetterDiff, UngroupDiff), `/saveFile` si `/saveMode` (PdfDocument1, PdfDocument2, Word).

### 2.8 Screenshot Reader (bonus)

Captureaza o zona, o fereastra sau tot ecranul, inclusiv cu intarziere de 5 secunde. Trimite rezultatul ca text, tabel sau imagine in clipboard, Word, Excel, fisier, OCR Editor sau e-mail.

### 2.9 Integrari

- **Microsoft Office:** tab propriu in Word (Create PDF, Scan to Word, Convert to Word, Compare with), Excel, PowerPoint (speaker notes, slide-uri ascunse) si Outlook (PDF din mesaje, foldere si atasamente).
- **Windows Explorer:** meniu contextual cu Edit, Convert (cautabil, imagine, Word, Excel, altele), Open in OCR Editor, Compare with si Combine into one PDF. Previzualizare PDF in Explorer si Outlook.
- **Cloud:** OneDrive, Google Drive si Dropbox prin clientii locali de sincronizare, plus SharePoint check-in si check-out.

### 2.10 Administrare si licentiere

Activare online, prin site sau prin e-mail. Mod trial: 7 zile, 100 de pagini, maxim 3 pagini salvate o data (C, din FileHorse). Pentru organizatii: License Manager, licente concurente, instalare silentioasa (Active Directory, SCCM), Group Policy, terminal server si Azure. Nu e nevoie de toate pentru o versiune personala: in alternativa se pot reduce la o licenta locala simpla.

## 3. Documentatie UI/UX

Tot ce urmeaza e citit de pe ecran, din cadre oprite in tutoriale, nu dedus din text. Interfata e desktop Windows clasica: ribbon pe tab-uri in PDF Editor, bara de meniuri clasica in OCR Editor si Compare, panouri ancorate redimensionabile si dialoguri modale. Nu e aplicatie web, deci nu are versiune de telefon sau tableta.

### 3.1 Fereastra New Task (lansator)

- **Titlu fereastra:** "ABBYY FineReader PDF Corporate". Bara de meniuri: File, Edit, Tools, Help. Dreapta sus: rotita de setari si semnul intrebarii. Cand exista, si butonul "Rate This Product" (stea portocalie, cu chenar).
- **Stanga:** coloana de tab-uri verticale: **Open, Scan, Compare, Recent, Mobile App**. Tabul activ are fundal albastru deschis si o bara verticala albastra in stanga.
- **Dreapta:** carduri albe cu colturi rotunjite pe fundal gri-albastrui, grupate pe sectiuni cu titlu.
  - Tab Open, sectiunea **"Open and Edit"**: doua carduri mari cu ilustratie colorata: "PDF Document — View, search, and print" si "OCR Editor — Advanced conversion and verification". Sectiunea **"Convert to"**: patru carduri patrate: PDF, Microsoft Word, Microsoft Excel, Other Formats.
  - Tab Compare: cardul "Compare — Compares two versions of the same document" plus panoul "Recent Comparisons".
  - La hover pe un card apare un pop-up cu scenariile tipice.
- **Ecranul de conversie** (dupa ce alegi fisierele): buton "< Back" sus stanga; coloana stanga cu titlul mare al sarcinii si optiunile: "Image quality:", "Full-text search:", bife pentru PDF/A si MRC, "OCR languages:", linkurile "Image preprocessing settings..." si "More options...", apoi butonul albastru plin de actiune si butonul cu contur "Cancel". Dreapta: toolbar cu Add File, sterge, muta sus, muta jos, lista de fisiere cu icon de tip si bifa "Combine all files into one document".
- **Dialogul de progres:** titlu "Conversion", linia de stare ("Converting to searchable PDF..."), fisierul curent, bara verde si "2 of 3 files processed", buton Cancel.

### 3.2 Fereastra PDF Editor

Nu are bara de meniuri clasica, ci un buton hamburger si tab-uri de ribbon.

| Zona | Continut citit de pe ecran |
| --- | --- |
| Rand 1 | ≡ (hamburger) · icon document cu sageata · tab-urile **Document · Organize Pages · Edit Content · Security · Form Editor** (activul subliniat albastru). Dreapta: rotita, ?, ^ (restrange ribbon) |
| Rand 2 (ribbon) | butoanele tabului activ, cu icon 16 px si eticheta. Dreapta: undo, redo, butonul "Comments (N)" |
| Ribbon **Document** | New Task · Open · Save · Save As v · Print · E-mail · Note · Draw v · Highlight · Underline · Strikethrough · Insert Text · Add Stamp v · Recognize v · Compare · Select · Hand |
| Ribbon **Organize Pages** | "Selected pages: \[1 v\]" · cos · roteste stanga · roteste dreapta · auto-orientare · Crop · Add Pages v · Move · Replace · Split · Delete Blank Pages · Recognize v · Enhance · Save As v |
| Ribbon **Edit Content** | Header and Footer v · Picture · Add Text · font · marime · A+ A- · B I U · aliniere x4 · directie text · spatiere randuri · spatiere paragraf · culoare A v |
| Ribbon **Security** | Signature v · Password Security · Watermark v · Erase · Redact (toggle) · Delete Objects and Data... · Select · Hand |
| Ribbon **Form Editor** | Text Field · Check Box · Radio Button · Drop-down List · List Box · Button · Signature Field |
| Bara verticala stanga | \~30 px, 5 iconuri: Pages · Bookmarks · Search · Attachments · Digital Signatures. Jos un icon de cautare |
| Panou navigare | \~190 px, se deschide langa bara verticala (F5) |
| Centru | pagina pe fundal gri deschis |
| Panou Comments | dreapta (F7) |
| Bara de jos | sageata sus · sageata jos · "4 / 6" · icon potrivire v · icon mod vizualizare · zoom \[75% v\] · - · + |
| Benzi contextuale | banda galbena pentru formulare ("This document contains interactive form fields." + bifa "Highlight fields" + X) si banda de notificare JavaScript |

**Panoul Pages:** titlu "Pages" + X; toolbar cu roteste stanga, roteste dreapta, "..."; miniaturi cu chenar, numarul sub ele si o insigna albastra mica in coltul din stanga jos.

**Panoul Search** (cel mai detaliat citit): tab-uri cu majuscule **FIND | REPLACE | REDACT** (activul subliniat albastru) + X. Sub ele: "Find what:" cu rotita de setari si sageata; campul de cautare cu X de golire; "Replace with:" cu campul lui; butonul \[Replace\] aliniat dreapta, gri cat timp nu exista selectie; sagetile < > de navigare. Apoi arborele de rezultate: bifa plus nodul pliabil "Document Text (58)", iar sub el fiecare rezultat ca fragment de context cu potrivirea evidentiata galben si "Page 1" aliniat dreapta, fiecare cu bifa proprie. Bara de stare jos: "Found: 58" sau mesajul "No matches found". In pagina, toate aparitiile sunt evidentiate galben simultan.

**Panoul Comments:** titlu + X; camp "Comment text filter" cu lupa; rand cu < > navigare, "AZ v" sortare, palnie de filtrare si icon de optiuni. Fiecare comentariu: icon colorat de tip, "Today 19:02  Page 2", caseta de bifa in dreapta, campul "Enter your comment" si linkul "Add Reply". Comentariul selectat are fundal albastru deschis.

**Organize Pages** e un mod separat, nu un panou: grila de miniaturi mari (4-5 pe rand) pe fundal gri; pagina selectata are fundal albastru deschis rotunjit si numarul pe eticheta albastra; la hover apare un mini-toolbar vertical in coltul din dreapta sus al miniaturii, cu sterge, roteste stanga, roteste dreapta; se selecteaza si prin tragerea unui cadru peste miniaturi; jos-dreapta e un slider de zoom al miniaturilor.

**Campurile de formular** apar ca dreptunghiuri albastru deschis semitransparente, cu numele campului pe o eticheta neagra in coltul din dreapta sus ("TextField 3", "List Box 1"). Campul de semnatura are chenar punctat si eticheta portocalie "Sign". Campurile obligatorii au numele scris cu rosu in modul de editare. La aliniere apar ghidaje mov.

**In modul Redact** apare o bara de culori deasupra paginii, centrata: opt patrate (rosu, portocaliu, galben, verde, turcoaz, albastru, mov, negru) plus o sageata pentru mai multe culori. Textul redactat devine dreptunghi negru plin.

**In Edit Content** fiecare bloc capata un contur subtire cu manere mici la colturi si la mijloace; imaginea selectata are opt manere; la mutare, locul vechi ramane marcat punctat, iar textul face reflow.

### 3.3 Fereastra OCR Editor

Titlu: "Untitled project \[1\] - ABBYY FineReader OCR Editor". Bara de meniuri clasica: **File, Edit, View, Recognize, Area, Tools, Help**. Dreapta sus: rotita si semnul intrebarii.

**Main Toolbar** (un rand, nepersonalizabil), citit de pe ecran in ordine:

`+ New Task` | icon proiect nou, icon deschide proiect | `Open` | `Scan` | `[ 1 / 17 ]` cu sageti sus/jos | `Recognize` | combo limba `[English v]` | undo, redo | buton **Send/Save** cu icon care se schimba dupa format (PDF rosu, W albastru pentru Word) si sageata | combo mod de salvare `[Exact copy v]` | doua butoane toggle de layout al panourilor | `Verify` | doua iconuri (eroarea urmatoare/anterioara).

Exista si o **Quick Access Bar**, ascunsa implicit, personalizabila din View > Customize.

| Panou | Continut |
| --- | --- |
| **Pages** (F5) | \~95 px. Titlu "Pages" + X; toolbar: salveaza, sterge, roteste stanga, roteste dreapta, "...". Doua vizualizari: Thumbnails si Details. Miniaturi cu numarul sub ele si o insigna mica in coltul din stanga jos. Tooltip pe miniatura: "Recognized / Opened by: \<user> (DESKTOP-...) / Source: \<fisier>.pdf". Paginile cu avertismente au un triunghi galben in colt. Panoul se poate muta la dreapta |
| **Image** (F6) | Toolbar pe doua randuri. Rand 1: `Edit Image` · `Save Page` ‖ `Select` · `Hand Tool` · `Delete` · `Reorder`. Rand 2: `Recognize Page` · `Analyze Page` ‖ `Text` · `Picture` · `Table` · `Background Picture` · `Recognition Area` (unealta activa are fundal albastru deschis). Pentru PDF-uri cu strat text apare in dreapta textul "This PDF file contains a text layer" si butonul dropdown "PDF recognition mode ▾" |
| **Text** (F8) | Toolbar pe doua randuri. Rand 1: combo stil `[Body text v]` · font · marime · A+ A- · Ω (simbol) · link ‖ `Find`. Rand 2: `Style Editor` ‖ B I U x² x₂ ‖ aliniere x4 ‖ spatiere, liste ‖ `Redaction`. Cand pagina nu e recunoscuta, in mijloc scrie gri "Page not recognized" |
| **Zoom** (Ctrl+F5) | Randul marit al imaginii, pentru comparatie caracter cu caracter. Se inchide; toggle-ul "Zoom Pane" ramane in coltul din stanga jos |
| **Warnings** | Buton cu triunghi in coltul din stanga jos; mesaje per pagina, cu navigare si stergere |

**Barele de proprietati de jos** (una per panou) au tab-uri proprii:

- Sub Image: tab-urile **"Area Properties" | "Image Properties"**. Image Properties arata: `Width x height: 2550 x 3300 pixels` · `Resolution: [300] dpi` · `Color mode: Color` · formatul · `Source image: <cale completa>`.
- Sub Text: tabul **"Text Properties"**, cu campurile pe trei coloane: Style / Font / Size (plus B I U) ‖ Language / Font color / Effects ‖ Alignment / Background color / Scale / Spacing.

Sub fiecare panou mai e un rand cu iconuri de layout, fit width, fit height, best fit si un combo de zoom cu - si +.

**Zonele** se deseneaza ca dreptunghiuri sau poligoane, cu fundal semitransparent colorat si chenar de aceeasi culoare. Numarul de ordine apare intr-un patrat mic in colt (stanga sus in v16, dreapta sus in v15). Zona selectata are chenar mai gros si manere patrate la colturi si la mijloace. Cand zona e activa apare un **toolbar contextual plutitor** sub ea. Pentru tabele are noua iconuri: copiaza, adauga separator orizontal, adauga separator vertical, sterge separatoare, imparte celule, uneste celule, uneste randuri, selectie si analizeaza structura tabelului.

**Image Editor** (Ctrl+I) inlocuieste zona de lucru: antet cu "Image Editor" si butonul "< Exit Image Editor", imaginea pe fundal gri inchis si un panou in dreapta cu lista verticala a celor 14 unelte. Unealta aleasa se expandeaza inline, sub numele ei. Exemplu pentru Crop: `Paper size: [Custom v]` · `Size: [152,7] Width [240,9] Height` · `Offset: [32,6] X [50,9] Y` · radio `( ) Inches (o) Millimeters` · `Selection: [Current Page v]` · buton `[Crop]`. Jos de tot: bifa `[ ] Show next page after operation completes`.

### 3.4 Fereastra Compare Documents

Titlu: "\<fisier1> / \<fisier2> - ABBYY Compare Documents". Meniuri: File, Edit, View, Compare, Help.

- Doua zone de afisare, fiecare cu o bara sus (icon folder sau X, calea fisierului intr-un combo si o sageata) si o bara jos (sus, jos, "1 / 1", zoom -, fit width, +, icon de sincronizare). La incarcare apare un icon de rotite si textul "Loading the document. Please wait...".
- Panou dreapta (\~170 px) cu tab-urile **"Compare" | "Differences (N)"**.
  - Compare: `Document language:` combo (accepta si "Autoselect: English; French; German"), bifele `[x] Find differences in punctuation` si `[x] Find one-letter differences`, apoi butonul albastru plin **Compare** pe toata latimea.
  - Differences: toolbar cu `[W Save... v]` · jos · sus · cos (ignora) · icon de grupare. Grupuri pliabile: "Body text (16)", "Headers and footers (3)". Fiecare diferenta: icon cu sageata verde sau rosie, titlu ingrosat "Text added" / "Text deleted" / "Text edited" si "Pg. 1" aliniat dreapta; la "Text edited" apar ambele versiuni, una cu +, alta cu -.
- Deasupra zonelor de afisare, o **banda rosie**: "Differences found: 9".
- In documente, diferentele sunt evidentiate mov deschis, iar diferenta curenta are chenar albastru.
- **Raportul Word** e un tabel cu doua coloane; antetul contine caile celor doua fisiere, cu numele ingrosat; fiecare rand e o diferenta scrisa ca "\[page N\] \<text>" in coloana documentului care o contine; celula goala inseamna ca lipseste in acel document.

### 3.5 Fereastra Hot Folder

- **Fereastra principala:** toolbar cu New · import/export v · Start Now · Start on Schedule · Stop · Modify · Copy · Delete · toggle-uri · Log. Tabel cu coloanele **Name · Path · Status · Next Start Time · Log**. Exemplu de rand: icon de ceas, "Daily documents", calea, "Watching...", "19.10.2022, 14:45".
- **Bara de stare de jos:** "Pages remaining to recognize 4999 / the limit to be renewed in 21 days", cu un icon de informatie care explica limita de 5.000 de pagini la 30 de zile.
- **Dialogul "Task Settings"**: camp "Task name:" sus. Stanga, paleta de pasi grupati pe categorii, ca pastile albastru deschis: **Schedule** (Run once, Recurring) · **Open** (File from folder, File from FTP, File from Outlook, OCR project) · **Process** (Process document) · **Save** (Save results v, cu patru optiuni: Save document, Save to SharePoint, Save images, Save OCR project). Dreapta, initial mesajul "Select task steps", apoi pasii adaugati ca sectiuni pliabile cu antet "Step N: ..." si X de stergere. Jos: link "Help" | buton albastru plin "Create Task" | buton cu contur "Cancel".

### 3.6 Meniurile complete (din scurtaturile oficiale)

**OCR Editor**

| Meniu | Comenzi (scurtatura) |
| --- | --- |
| File | New Task (Ctrl+N), Open Image (Ctrl+O), Scan Pages (Ctrl+K), Save Page Images As (Ctrl+Alt+S), Close (Ctrl+W), New OCR Project (Ctrl+Shift+N), Open OCR Project (Ctrl+Shift+O), Save OCR Project (Ctrl+Shift+S), E-mail document (Ctrl+M), E-mail images (Ctrl+Alt+M), Print text (Ctrl+P), Print image (Ctrl+Alt+P), Exit (Ctrl+Q) |
| Edit | Undo, Redo, Cut, Recognize and Copy Text (Ctrl+C), Copy Area as Image (Ctrl+Shift+C), Paste, Delete, Select All, Cancel Selection (Ctrl+Shift+A), Delete Pages (Ctrl+Backspace), Delete Areas and Text (Ctrl+Del), Delete Text (Ctrl+Shift+Del), Rotate Right/Left (Ctrl+Shift+> / <), Edit Page Images (Ctrl+I), Find (Ctrl+F), Find Next (F3), Replace (Ctrl+H) |
| View | Navigation Pane (F5), Zoom Pane (Ctrl+F5), Image Only (F6), Image and Text (F7), Text Only (F8), Next/Previous Pane, Zoom In/Out, Best Fit (Ctrl+0), Go to Page (Ctrl+G), pagina urmatoare/anterioara/prima/ultima, Close Page (Ctrl+F4) |
| Recognize | Recognize All (Ctrl+Shift+R), Recognize Page (Ctrl+R), Analyze All (Ctrl+Shift+E), Analyze Page (Ctrl+E), Verify Text (Ctrl+F7), Next/Previous Error (Alt+Jos/Sus), Mark as Verified (Ctrl+T) |
| Area | Recognize Area (Ctrl+Shift+B), schimbare tip: Recognition (Ctrl+1), Text (Ctrl+2), Table (Ctrl+3), Picture (Ctrl+4), Barcode (Ctrl+5), Background (Ctrl+6), Reorder Areas, Save/Load Area Template, Analyze Table, Split/Merge Cells, Merge Rows |
| Tools | View Dictionaries (Ctrl+Alt+D), Redaction Mode (Ctrl+Shift+H), Hot Folder (Ctrl+Shift+F), Automated Tasks, Style Editor, Pattern Editor, Compare Documents, Screenshot Reader, Options (Ctrl+>) |

**PDF Editor**

| Meniu | Comenzi (scurtatura) |
| --- | --- |
| File | New Task (Ctrl+N), Open (Ctrl+O), Save (Ctrl+S), Save as PDF (Ctrl+Shift+S), Save As (alte formate), Reduce File Size, Document Properties, E-mail, Send To, Compare Documents, SharePoint, Close (Ctrl+W), Print (Ctrl+P), Exit (Ctrl+Alt+W) |
| Edit | Undo, Redo, Cut, Copy, Copy Area as Image/Text/Table (Ctrl+C / Ctrl+Shift+C / Ctrl+Alt+C), Paste, Delete, Select All, Add Link (Ctrl+L) |
| Document | Add Note (Ctrl+M), Highlight (Ctrl+H), Underline (Ctrl+Shift+U), Strikethrough (Ctrl+K), Insert Text (Ctrl+J), Search and Mark Up, Recognize Document (Ctrl+Shift+R), Add Bookmark (Ctrl+D), Find (Ctrl+F), Find Next (F3), Delete All Comments |
| Organize Pages | Add Blank Page (Ctrl+Shift+B), Add from PDF (Ctrl+Shift+P), from File (Ctrl+Shift+O), from Scanner (Ctrl+Shift+K), Rotate, Correct Orientation (Ctrl+Shift+/), Crop (Ctrl+Shift+X), Replace (Ctrl+Shift+E), Move (Ctrl+Shift+M), Delete (Ctrl+Backspace), Split |
| Security | Redaction Mode (Ctrl+Shift+H), Erase Text and Pictures (Ctrl+R), Password Security, semnaturi, Remove Hidden Data |
| View | Navigation Pane (F5), Pages/Bookmarks/Search/Attachments/Signatures (Alt+Shift+1..5), Comments Pane (F7), zoom, Actual Size (Ctrl+1), Fit to Width (Ctrl+2), Go to Page (Ctrl+G), Back/Forward (Alt+Stanga/Dreapta), moduri de vizualizare (Ctrl+5..8), Full Screen (F11) |

### 3.7 Dialogul Options, tab cu tab

Dialog modal, aproximativ 650 x 620 px, cu titlu "Options", ? si X. Tab-urile sunt **iconuri mari cu eticheta dedesubt**, pe un rand: General, Image Processing, Languages, OCR, Format Settings, "..." Other. Tabul activ are fundal albastru deschis si chenar. **Al saptelea tab, "Areas and Text", apare doar cand dialogul e deschis din OCR Editor** (confirmat: in New Task si PDF Editor sunt doar sase). Jos: OK | Cancel.

**General**

- "When OCR Editor starts": (o) Open a new OCR project / ( ) Open the last used OCR project
- "Select device for acquiring images": camp read-only cu numele dispozitivului + buton \[Select Device...\]
  - (o) Use FineReader's interface (scanners only) / ( ) Use scanner's interface + link "Which scanning interface to choose?"
- "\<Produs> is not currently your default PDF viewer" + buton \[Make Default...\]
- Dialogul \[Select Device\]: "Select a scanner or a camera:" + listbox cu dispozitive marcate "(TWAIN)" + textul de ajutor "If you can't see a device in the list above, check if it is attached to your computer and turned on."

**Image Processing**

- [x] "Enable background recognition in the PDF Editor" + paragraf explicativ + "OCR languages:" cu link catre limbi
- [x] "Automatically process page images as they are added to the OCR Editor", cu trei radio:
  - (o) Recognize page images (includes preprocessing and analysis)
  - ( ) Analyze page images (includes preprocessing)
  - ( ) Preprocess page images
  - (din Release 3 se adauga si "No preprocessing")

* "Image preprocessing settings", pe trei coloane:

| Coloana 1 | Coloana 2 (doar fotografii) | Coloana 3 |
| --- | --- | --- |
| Split facing pages | Detect page edges \* | Fix inverted colors on image |
| Correct page orientation | Whiten background \* | Convert to black and white |
| Deskew images | Reduce ISO noise \* | Remove color marks |
| Straighten text lines | Remove motion blur \* |  |
| Correct image resolution | Correct trapezoid distortions \* |  |

- Buton \[Hide Advanced Settings\] si nota "\* for photo images"

**Languages:** limbile OCR, limbile utilizator si grupurile de limbi, cu editorul de limbi.

**OCR** (tabul cel mai dens)

- "PDF recognition mode": combo \[Automatically choose between OCR and text from PDF v\] + link "Which PDF recognition mode to choose?"
- "Balance between OCR speed and accuracy": (o) Thorough recognition / ( ) Fast recognition
- "Document type": **(o) Auto / ( ) Fax / ( ) Typewriter**
- "Detection of structural elements", pe doua coloane: \[x\] Headers and footers, \[x\] Numbered lists, \[x\] Table of contents, \[x\] Footnotes
- "Barcodes": \[ \] Convert barcodes into strings
- Grup radio pentru sabloane:
  - (o) Use built-in patterns
  - ( ) Use user patterns, cu \[ \] Also use built-in patterns indentat dedesubt
  - ( ) Use training to recognize new characters and ligatures, cu aceeasi bifa indentata
  - link "How to use pattern training?"
  - butoane in coloana din dreapta: \[Pattern Editor...\] \[Load Patterns and Languages...\] \[Save Patterns and Languages...\]
- "Select fonts to be used in recognized text" + buton \[Select Fonts...\]

**Format Settings:** lista "Document type" in stanga (PDF, DOC(X)/RTF/ODT, XLS(X), PPTX, CSV, TXT, HTML, EPUB/FB2, DjVu) si setarile formatului in dreapta. Pentru PDF: Image quality cu \[Custom...\] si un sub-dialog cu rezolutie, control de culoare si calitate; Create PDF/A cu selector de versiune; Create PDF/UA (care forteaza si dezactiveaza "Create PDF tags"); protectie cu parole; stergere de obiecte si date; o singura dimensiune de hartie; MRC; PreciseScan; modul de PDF cautabil; semne de carte din titluri; etichete PDF; fonturi si incorporarea lor; pastrarea metadatelor cu buton \[Edit Metadata...\].

**Other:** limba interfetei, numarul de nuclee folosite pentru OCR (care din Release 3 limiteaza si procesele de fundal din PDF Editor; implicit toate nucleele minus unul), actualizari, date anonime, mesaje de marketing, JavaScript, detectie de URL si buton de Reset.

**Areas and Text** (doar in OCR Editor): verificarea caracterelor nesigure, verificarea cuvintelor din afara dictionarului, dictionarele utilizatorului, fontul pentru text simplu, culoarea si grosimea chenarului per tip de zona si culoarea de evidentiere.

### 3.8 Meniul Tools (OCR Editor), citit de pe ecran

| Comanda | Scurtatura |
| --- | --- |
| View Dictionaries... | Ctrl+Alt+D |
| Pattern Editor... |  |
| Style Editor... |  |
| Redaction Mode | Ctrl+Shift+H |
| Automated Tasks |  |
| Hot Folder | Ctrl+Shift+F |
| Compare Documents |  |
| Screenshot Reader |  |
| Options... | Ctrl+> |

Fiecare comanda are un icon mic in stanga; exista separatoare intre grupuri.

**Style Editor** e un dialog cu toolbar (New, Merge...) si un tabel cu coloanele: Style name, Font name, Font size, Scale, Spacing, B, I, Aa, **Heading**. Coloana Heading e un dropdown cu No si Heading 1 pana la Heading 10 — rolul care genereaza semnele de carte la salvarea in PDF. Jos: Previous Fragment | Next Fragment | OK | Cancel.

**ABBYY Screenshot Reader** e o fereastra mica flotanta: "Capture:" \[Area v\], "Language:" \[English v\], "Send:" \[Text to Clipboard v\], plus doua butoane mari cu iconuri in dreapta.

### 3.9 Dialoguri importante, citite de pe ecran

**Split Document:** "Split method:" cu trei radio (By file size / By page count / By bookmarks (first level only)); "Total files: 13" care se recalculeaza; "File name:" combo (Custom name / Same as bookmark name) + bifa "Add numeration" + numarul de cifre + linia "Example: 01\_Bookmark.pdf"; "Save to:" cu bifa "Same as source folder", camp de cale si \[Browse...\]; butoane \[Split\] \[Cancel\].

**Text Field Properties:** tab-uri General | Appearance | Format. General: "Field Name:", "Tooltip:", \[ \] Max Number of Symbols cu camp numeric gri pana la bifare, \[ \] Required, \[ \] Read-Only, Width si Height cu un lacat de proportii intre ele, X si Y, "Units:" \[Centimeters v\]. Toate numerele sunt spinbox-uri.

**Check Box Properties:** General | Appearance. In plus fata de campul de text: \[ \] Enabled by Default.

**Button Properties > Actions > New Action:** "Trigger Event:" \[Click v\], "Action:" \[Send form v\], "Send to:" camp de e-mail, "File Format:" \[PDF file v\] (plus HTML si XFDF), nota "All form fields will be sent.", butoane Save | Cancel.

**Add Digital Signature:** "Sign as" cu combo de certificate si \[Show Certificate...\]; grupul "Signature Details" cu Reason (combo editabil, cu motive predefinite: "I am the author of this document", "I approved this document" etc.), Location, Contact si linkul "Set up Time Stamp Server"; grupul "Signature Appearance" cu bife pentru Reason, Location, Contact, Date, Owner information, Application version, o previzualizare mare, bifele "Show labels" si "Borders and background", si "Add custom image to digital signature" cu \[Select Image...\]; butoane Help | Save and sign | Cancel.

**Delete Objects and Data:** "Select objects and data to delete:" cu bifele Hidden text and objects (cu avertismentul "The document will be converted to image-only PDF."), Comments and markup, Links/media/actions/scripts/form data, Bookmarks, Attachments, Metadata; butoane Apply | Cancel.

**Document Properties:** campuri editabile Title, Author, Subject, Keywords; campuri doar in citire: File name, Location (ca link), File size ("53.39 KB (54673 Bytes)"), Page size ("21.00 x 29.70 cm"), Pages, PDF producer, Application, PDF version, Tagged PDF, Fast Web View, Created, Modified.

**Task Settings (Automated Tasks):** stanga, panoul "Task steps" cu butoane grupate: eticheta "OCR project:" si cele trei optiuni (Create new OCR project, Select existing OCR project, Use current OCR project), apoi grupuri dezactivate pana la alegerea primului pas (Open image or PDF, Scan ‖ Analyze ‖ OCR ‖ Save/Send cu sageata). Dreapta: "Task name:" si mesajul centrat "Choose the first step". Jos: \[Help\] | \[Finish\] | \[Cancel\].

**Dialogul de progres la recunoastere:** titlu "Recognizing", "Process completed", "1 of 1 pages recognized", buton \[Close\] si zona de avertismente cu icon galben, de exemplu: "Page 1: Please rescan your document at a higher resolution. This will improve the OCR of the fragments printed in a small font size." Numarul paginii e link.

**Save document as** (dialogul Windows, extins): File name, "Save as type" cu formatele, bifa "Open document after saving", buton \[Options...\] si un combo \[Create a separate file v\] pentru un fisier per pagina sau unul singur.

### 3.10 Stari ale interfetei

| Element | Stari observate |
| --- | --- |
| Pagina in Pages | neprocesata, preprocesata, analizata, recunoscuta, verificata; insigna mica in coltul din stanga jos; triunghi galben la avertismente; nuanta colorata peste miniatura la paginile cu probleme |
| Zona | normala, activa (chenar gros, manere, toolbar contextual), selectata multiplu (Ctrl+clic), in curs de desenare (chenar punctat, cursor "+") |
| Caracter nesigur | evidentiat cu albastru deschis in Text pane; culoarea e configurabila |
| Unealta din toolbar | activa = fundal albastru deschis |
| Buton | normal, hover, apasat, dezactivat (gri), cu sageata de dropdown |
| Procese lungi | dialog modal cu bara de progres, numarul de fisiere procesate, sfaturi, avertismente si Cancel |
| Sarcina Hot Folder | Running, Scheduled, Watching, Stopped, Completed, Error (see log) |
| Camp de formular obligatoriu | numele scris cu rosu in modul de editare |
| Camp gol / lista goala | mesaj centrat gri ("Page not recognized", "No matches found", "Choose the first step", "Select task steps") |

### 3.11 Sistem vizual

**Culorile zonelor** difera intre versiuni si instalari, pentru ca sunt configurabile in Options > Areas and Text. Am observat trei seturi diferite:

| Tip zona | v14 | v15 | v16 |
| --- | --- | --- | --- |
| Text | verde | verde | albastru |
| Picture | - | roz/rosu | roz/magenta |
| Table | violet | albastru-violet | verde |
| Background Picture | - | roz inchis | - |

Concluzia pentru alternativa: culorile trebuie sa fie configurabile, cu un set implicit propriu.

**Restul sistemului vizual** ramane estimare (nivel D), pentru ca cadrele video sunt comprimate: font Segoe UI 9 pt; fundal alb; panouri gri deschis; accent albastru; ribbon de 90-100 px; bara verticala de navigare de aproximativ 30-40 px; panoul deschis de 190-260 px, redimensionabil. Doar tema luminoasa, fara mod intunecat (confirmat din recenzii, si o lipsa pe care alternativa o poate acoperi). Iconuri monocrome de 16 px in ribbon si in meniuri, 32 px pe cardurile din New Task.

## 4. Documentatie tehnica (arhitectura propusa)

Arhitectura interna ABBYY nu e publica. Ce urmeaza este o arhitectura echivalenta, in Python, dedusa din comportamentul documentat (nivel D). Principiul de baza: un singur motor (core) fara interfata, folosit de 5 aplicatii GUI si de linia de comanda, exact cum ABBYY imparte acelasi motor intre New Task, PDF Editor, OCR Editor, Compare si Hot Folder.

### 4.1 Straturi si tehnologii

| Strat | Rol | Biblioteci propuse (licenta) |
| --- | --- | --- |
| GUI | Ferestrele New Task, PDF Editor, OCR Editor, Compare, Hot Folder si Screenshot | PySide6 / Qt 6 (LGPL) |
| Randare PDF | Afisarea paginilor, miniaturi, selectie de text | pypdfium2 (Apache-2.0/BSD) sau PyMuPDF (AGPL sau comercial) |
| Structura PDF | Pagini, semne de carte, atasamente, metadate, criptare, formulare | pikepdf (MPL-2.0), PyMuPDF |
| Preprocesare imagine | Deskew, straighten, trapez, zgomot, binarizare, crop, levels, color marks | OpenCV, scikit-image, Pillow |
| Analiza de layout | Zone text, tabel, imagine, cod de bare, ordine de citire | PaddleOCR PP-Structure (Apache-2.0), cu euristici proprii |
| OCR | Recunoastere cu incredere pe caracter | Tesseract 5 LSTM (Apache-2.0) cu ron si eng; PaddleOCR ca al doilea motor |
| Coduri de bare | 1D si 2D | zxing-cpp (Apache-2.0) |
| PDF cautabil | Strat text sub imagine, PDF/A, optimizare | OCRmyPDF (MPL-2.0), Ghostscript pentru PDF/A, jbig2enc |
| Export | DOCX, XLSX, PPTX, ODT, RTF, HTML, TXT, CSV, EPUB, FB2, DjVu | python-docx, openpyxl, python-pptx, odfpy, ebooklib, djvulibre |
| Comparare | Diff pe cuvinte, grupare si raport | difflib, rapidfuzz |
| Semnaturi | PAdES, LTV, timestamp, smartcard | pyHanko (MIT) |
| Scanare | TWAIN si WIA | pytwain, comtypes (WIA) |
| Automatizare | Programare si urmarire foldere, FTP, e-mail | APScheduler, watchdog, ftplib, imaplib sau pywin32 (Outlook) |
| Stocare | Setari, istoric, sarcini, log-uri | SQLite (din biblioteca standard) |
| Ambalare | Instalator Windows | PyInstaller sau Nuitka, Inno Setup |

Atentie la licente: PyMuPDF si Ghostscript sunt AGPL. Pentru uz intern e in regula. Daca alternativa se vinde, fie cumperi licenta comerciala, fie folosesti pypdfium2 cu pikepdf.

### 4.2 Module de cod

1. `core/project` - modelul proiectului OCR, salvare si incarcare.
2. `core/imaging` - preprocesarea, cate o functie pura per unealta din Image Editor.
3. `core/layout` - detectia si editarea zonelor, sablonul de zone.
4. `core/ocr` - interfata comuna `OcrEngine` cu adaptoare Tesseract si Paddle, limbi, dictionare, patterns.
5. `core/pdf` - deschidere, randare, editare, organizare pagini, securitate, formulare, adnotari.
6. `core/export` - cate un exportor per format, fiecare cu cele 5 moduri de layout.
7. `core/compare` - extragere text (strat PDF sau OCR), aliniere, diff, grupare, rapoarte.
8. `core/automation` - pasi de sarcina, executie, programare, Hot Folder si log.
9. `core/settings` - echivalentul dialogului Options, profiluri si import/export.
10. `cli` - `ocr.exe` si `compare.exe`, cu aceiasi parametri ca originalul.
11. `gui/*` - cate un pachet per fereastra, plus componente comune (viewer de pagina, panouri, ribbon).

### 4.3 Modelul de date

Un proiect OCR se salveaza ca folder (sau arhiva .zip cu extensie proprie): `project.json` plus imaginile originale si procesate plus o baza `project.db` (SQLite). Setarile aplicatiei, sarcinile si istoricul stau intr-o baza globala `app.db`.

| Tabel | Campuri principale | Relatii si constrangeri |
| --- | --- | --- |
| project | id (UUID, PK), name, created\_at, modified\_at, settings\_json, languages | 1-N page |
| page | id (PK), project\_id (FK), order\_index, source\_file, source\_page\_no, image\_path, processed\_image\_path, width\_px, height\_px, dpi, rotation, status (new, preprocessed, analyzed, recognized, verified), has\_warnings | index (project\_id, order\_index), unic per proiect |
| area | id (PK), page\_id (FK), type (recognition, text, table, picture, background, barcode), polygon\_json, order\_index, language, function (body, header, footer, footnote), orientation, print\_type, inverted, cjk\_direction | 1-N text\_block; tip validat prin CHECK |
| table\_grid | area\_id (PK, FK), rows\_json, cols\_json, merges\_json | 1-1 cu area de tip table |
| text\_block | id (PK), area\_id (FK), paragraph\_index, style\_id (FK), text, chars\_json (bbox, conf, uncertain), verified | 1-N in zona |
| style | id (PK), project\_id (FK), name, font, size\_pt, spacing, scale, bold, italic | folosit de Style Editor |
| warning | id (PK), page\_id (FK), code, message, dismissed |  |
| area\_template | id (PK), name, page\_size, areas\_json | refolosibil intre proiecte |
| user\_language | id (PK), name, base\_language, alphabet, dictionary\_type, dictionary\_ref, regex, prohibited\_chars, word\_start\_chars, word\_end\_chars |  |
| user\_dictionary | id (PK), language, word | unic (language, word) |
| user\_pattern | id (PK), name, glyphs\_json (imagine plus caracter), max 1.000 de caractere |  |
| automated\_task | id (PK), name, steps\_json, created\_at | import/export JSON |
| hot\_folder\_task | id (PK), name, schedule\_type, schedule\_json, source\_type (folder, ftp, mail, project), source\_json, originals\_action, processing\_json, outputs\_json, status, next\_start\_at, last\_run\_at, log\_enabled, notify | 1-N task\_run |
| task\_run | id (PK), task\_id (FK), started\_at, ended\_at, pages, errors, warnings, uncertain\_chars, log\_path |  |
| comparison | id (PK), doc1\_path, doc2\_path, language, options\_json, created\_at | 1-N difference |
| difference | id (PK), comparison\_id (FK), kind (delete, add, change), group (body, header\_footer, numbering), text1, text2, page1, page2, bbox1, bbox2, ignored |  |
| recent\_item | id (PK), kind (pdf, project, comparison), path, opened\_at |  |
| stamp, signature\_appearance, redaction\_keyword\_list | resurse refolosibile in PDF Editor |  |
| usage\_counter | month, pages\_processed | pentru limita de 5.000 de pagini/luna, daca vrei sa o pastrezi |

Adnotarile, formularele, semnaturile si semnele de carte NU se tin in baza de date. Ele traiesc direct in fisierul PDF, ca in original.

### 4.4 Fluxul principal de recunoastere

1. Adaugi fisiere sau scanezi, iar paginile se creeaza cu statusul `new`.
2. Daca procesarea automata e activa, se aplica preprocesarea din setari si statusul devine `preprocessed`.
3. Analiza detecteaza zonele si ordinea lor, iar statusul devine `analyzed`. Daca exista un sablon de zone, se aplica sablonul in loc de detectie.
4. OCR ruleaza pe fiecare zona, cu limbile zonei sau ale documentului. Rezultatul are bounding box si incredere pe caracter. Caracterele sub prag sunt marcate `uncertain`. Statusul devine `recognized`.
5. Verificarea (manuala) marcheaza textul ca verificat. Cuvintele adaugate intra in dictionarul utilizatorului.
6. Exportul construieste documentul in formatul si modul de layout ales.

Schimbarea unei zone sau a setarilor OCR invalideaza textul paginii respective. Pagina trebuie recunoscuta din nou, exact ca in original.

### 4.5 Reguli de business confirmate

- **Modul de layout limiteaza formatele de export.** Regula, citita direct din dropdownul deschis: Exact copy da RTF, DOC(X), PDF, PPTX, ODT si DjVu; Editable copy da doar RTF, DOC(X) si ODT; Formatted text da RTF, DOC(X), XLS(X), TXT, HTML, ODT, FB2 si EPUB; Plain text la fel, plus CSV; Flexible layout da doar HTML. In acelasi dropdown stau si bifele Keep pictures, Keep headers and footers si Keep line breaks and hyphens.
- **La editarea unui PDF, fontul nu se pastreaza din original, ci se cauta cel mai apropiat font instalat pe calculator.** Confirmat explicit de ABBYY in webinar. Pentru alternativa inseamna un algoritm de potrivire a fonturilor dupa metrici, nu extragerea fontului incorporat.
- Text editat in OCR Editor si salvat cu "Text under the page image" nu se vede pe pagina, dar exista in stratul de text. Confirmat in demonstratie.
- PDF cu strat text digital: modul implicit este Use Only Text from PDF. PDF-urile scanate, cautabile sau imagine folosesc mereu OCR.
- Modul implicit "Automatically choose" foloseste din Release 3 algoritmul Pull&Recognize: pe documente mixte extrage textul digital si recunoaste separat textul din imagini.
- GlyphRecovery reconstruieste codificarea in PDF-urile cu encoding stricat, cele din care nu poti selecta textul desi se vede. Rezolva aproximativ doua din trei astfel de fisiere.
- MRC se poate activa doar pentru PDF cautabil cu "Text under the page image".
- Embed fonts merge doar cu "Text and pictures only" sau cu "Text over the page image".
- Cand e bifat "Create PDF/UA", optiunea "Create PDF tags" devine fortata si gri.
- MRC si PreciseScan pot inrautati claritatea textului la export; dezactivarea lor a rezolvat problema in demonstratie.
- "Keep line numbers" si "Keep headers and footers" sunt disponibile doar in modul Editable copy.
- Elementele de structura dezactivate se exporta ca text obisnuit.
- Un stil caruia i se atribuie rolul Heading (pana la 10 niveluri) genereaza semn de carte la salvarea in PDF, daca e activa optiunea "Create bookmarks from headings".
- **Zonele nu trebuie sa se suprapuna**; daca se suprapun, rezultatul e imprevizibil. Tehnica recomandata pentru pagini complicate: o zona Background Picture peste tot, apoi zone Text deasupra.
- Zonele pot fi poligoane, nu doar dreptunghiuri, prin "add area part" si "cut area part". Nu merge pe zonele de tip Table si Barcode.
- Zonele se numeroteaza automat de la stanga la dreapta la analiza, indiferent de directia textului; ordinea se schimba manual cu Reorder Areas.
- Modificarea unei zone sau a setarilor OCR invalideaza textul paginii; pagina trebuie recunoscuta din nou.
- Stergerea unei zone de pe o pagina recunoscuta sterge si textul ei din panoul Text. Asa se exclude continut din export fara a-l sterge din imagine.
- Nu se poate adauga text alternativ la imagini. Limitare reala a produsului, pe care alternativa o poate acoperi.
- Stergerea pasului Analyze dintr-o sarcina sterge si pasul OCR.
- Paginile deja recunoscute nu se reproceseaza intr-o sarcina; cele doar analizate se recunosc.
- Hot Folder ruleaza doar cu calculatorul pornit si utilizatorul logat. Paginile goale pot fi mutate intr-un folder separat.
- O sarcina Hot Folder poate avea mai multi pasi de salvare, deci poate scoate simultan Word pentru editare si PDF cautabil pentru arhiva.
- Parola de permisiuni trebuie sa fie diferita de parola de deschidere.
- Metadatele nu se pot edita la fisierele protejate cu parola.
- "Split cells" merge doar pe celule unite anterior.
- Un camp de formular obligatoriu doar avertizeaza, nu blocheaza salvarea. Numele campului trebuie sa fie unic, fara punct la inceput, la sfarsit sau dublat.
- Doar campurile de semnatura goale se pot copia.
- Split Document nu pastreaza semnele de carte; atasamentele merg intr-un subfolder.
- Diferentele ignorate in Compare nu apar in raport.
- Imaginile alb-negru fac proiecte mai mici si OCR mai rapid, dar nu se recomanda pentru fotografii sau pentru scrierile asiatice.
- Cu cat selectezi mai multe limbi OCR, cu atat recunoasterea e mai lenta.

### 4.6 Rezolutie si calitate recomandate

Regulile din ghidul oficial, de pus ca sfaturi in interfata:

- 300 dpi pentru text de minim 10 pt si 400-600 dpi pentru text mai mic.
- Grayscale e optim pentru OCR, iar luminozitatea implicita e 50%.
- Peste 600 dpi OCR-ul devine lent fara castig de calitate.

Pentru tipul documentului: Typewriter pentru fonturi cu latime fixa, Fax pentru faxuri, Auto in rest.

## 5. Catalog video

Am analizat **22 de videoclipuri**: le-am citit transcrierea completa si am oprit si marit peste 60 de cadre ca sa citesc textul din interfata. Durata totala vizionata e de aproximativ 4 ore si jumatate. Tabelul e ordonat dupa cat de mult a contribuit fiecare la specificatie.

### 5.1 Sursele principale

| Video | Canal | Durata | Data | Ce am extras |
| --- | --- | --- | --- | --- |
| [ABBYY FineReader — A smarter PDF solution](https://www.youtube.com/watch?v=h1oypuYx1W4) | Alfasoft + ABBYY (webinar oficial) | 56:39 | 28.10.2022 | **Demo complet de la A la Z.** Cele 4 module, editare PDF scanat, OCR Editor, Organize Pages, formular complet din Word, Hot Folder cu toti pasii, Compare cu raport. Prezentat de seful de vanzari ABBYY |
| [Abbyy Finereader 14 Pc Basic Tutorial](https://www.youtube.com/watch?v=kd_4VvUUSCY) | xandru tait | 33:43 | 105 K vizualizari | **Toate tab-urile din Options**, deschise pe rand: General, Image Processing, OCR, Format Settings. Meniul Tools complet cu scurtaturi. Task Settings. Screenshot Reader |
| [ABBYY FineReader PDF as a powerful Adobe Acrobat Alternative](https://www.youtube.com/watch?v=wOU5948ZHCw) | ABBYY (webinar oficial) | 26:36 | 24.11.2023 | **Image Editor cu toate cele 14 unelte** si parametrii lor. Cifre oficiale de produs. Pozitionare fata de Acrobat |
| [Abbyy Finereader 16 Quick 20 Min Tutorial](https://www.youtube.com/watch?v=kof1dSceV1U) | xandru tait | 22:27 | 23.09.2023 | Parcurgere completa v16: toate cele 5 tab-uri de ribbon, dialogul de scanare, Image Editor, Compare |
| [Using ABBYY FineReader 15 Video 1](https://www.youtube.com/watch?v=0z2HgNvDpSg) | david hardisty | 23:16 | 20.04.2021 | **Dropdownul modului de salvare, deschis**, cu formatele permise de fiecare mod. Reguli practice de zonare |
| [How to Handle Difficult Scans with Complex Layouts](https://www.youtube.com/watch?v=hrZZEdA0kbI) | The Accessibility Guy | 6:55 | 25.07.2025 | **Cel mai detaliat cadru al OCR Editor**: toolbar-ele pe doua randuri, barele de proprietati, zonele poligonale |
| [Abbyy Finereader 16: Overview of OCR Editor](https://www.youtube.com/watch?v=rv3oqLC5e6Q) | The Accessibility Guy | 11:37 | 10.02.2023 | Main toolbar, Options > General si Format Settings, sub-dialogul Custom image quality |
| [Convert an image to an editable document](https://www.youtube.com/watch?v=oqMNUSYzuW8) | The Accessibility Guy | 7:34 | 08.03.2023 | **Dialogul Options > Format Settings > PDF, complet.** Dialogul de progres cu avertismente. Zonarea unui tabel |
| [Abbyy FineReader PDF 15: Lecture and Demo](https://www.youtube.com/watch?v=2AkT35wH0f0) | The Accessibility Guy | 20:39 | 2021 | Barele de proprietati cu tab-uri. Toolbarul contextual de tabel, cu 9 iconuri |

### 5.2 Tutorialele scurte oficiale ABBYY

Toate publicate pe 28.09.2022, odata cu versiunea 16, fara voce, doar cu text pe ecran. Sunt cele mai utile pentru dialoguri, pentru ca arata interfata curata, in rezolutie mare.

| Video | Durata | Ce am extras |
| --- | --- | --- |
| [How to Find and Replace text in a PDF](https://www.youtube.com/watch?v=KrC7SOuVrrE) | 1:00 | **Panoul Search complet**: 3 tab-uri, arborele de rezultate, bara de stare |
| [How to Split a PDF](https://www.youtube.com/watch?v=EhiEN08-KlU) | 1:28 | **Dialogul Split Document complet** + toolbarul Organize Pages |
| [How to Create Fillable PDF Forms](https://www.youtube.com/watch?v=NIRJgxDIZcw) | 2:19 | Cele 7 tipuri de campuri, dialogurile de proprietati |
| [How to Protect and Redact a PDF File](https://www.youtube.com/watch?v=FAKe0OPx3qU) | 1:21 | Bara de culori de redactare, dialogul Delete Objects and Data |
| [How to Sign PDFs Digitally](https://www.youtube.com/watch?v=RlGiFd2RSsc) | 1:31 | Dialogul Add Digital Signature, Document Properties |
| [How to Organize Pages in a PDF](https://www.youtube.com/watch?v=uc9DSbrIUhk) | 1:30 | Grila de miniaturi, mini-toolbarul la hover, dialogul Add Pages |
| [How to Comment and Annotate in PDF](https://www.youtube.com/watch?v=FLlVhMoqVe8) | 1:12 | Ribbonul Document complet, panoul Comments |
| [How to Edit Any PDF](https://www.youtube.com/watch?v=qK0bcjuCUIM) | 1:04 | Ribbonul Edit Content, comportamentul blocurilor |
| [How to Extract Tables from PDF](https://www.youtube.com/watch?v=_zUafW3bfzM) | 1:23 | Editorul de separatori inainte de copiere |
| [How to Create and Merge PDF](https://www.youtube.com/watch?v=iQQ4QRxPxnc) | 0:51 | Ecranul de conversie din New Task |
| [How to Track Changes in PDF vs. Word](https://www.youtube.com/watch?v=YNU3iFK4hs4) | 1:08 | Fereastra Compare, tabul Differences |
| [How to Search in PDF](https://www.youtube.com/watch?v=VCD4N2JlHMQ) |  | Cautare si marcare |

### 5.3 Restul

[How to OCR over 100 pages](https://www.youtube.com/watch?v=whMN41a_wuU) (3:28), [ABBYY FineReader Overview 2025](https://www.youtube.com/watch?v=U1yp_aE1vvo) (4:46), [Mastering OCR Editing and Document Accessibility](https://www.youtube.com/watch?v=SEBFSNZwfM8) (6:10) si [Converting Scanned PDFs to Word](https://www.youtube.com/watch?v=OYoiI6XWBBA) (5:20), toate de la The Accessibility Guy. Din ele vin culorile zonelor, comportamentul ordinii de citire si limitarea ca nu se poate adauga text alternativ la imagini.

### 5.4 Ce ramane in afara

Tutorialele in alte limbi (turca, poloneza, spaniola) si webinariile despre alte produse ABBYY (FlexiCapture, Vantage) nu aduc nimic in plus despre FineReader desktop. Videoclipurile de tip "download si instalare" sunt in general reclame sau continut piratat, deci le-am ignorat.

## 6. Registrul surselor

Am consultat 34 de surse scrise si 22 de tutoriale video pe 19 noiembrie 2026. Videoclipurile sunt listate in capitolul 5, cu link si cu ce am extras din fiecare. Dintre sursele scrise, 21 au fost deschise efectiv, iar 13 au fost citite doar din fragmentele aratate de cautare (S19, S21-S23, S25-S30, S32-S34). Cele oficiale ABBYY au incredere A, recenziile au C.

| ID | Sursa | Tip | Ce am extras | Incredere |
| --- | --- | --- | --- | --- |
| S01 | [Full Feature List v16, rev. 16.12.2025](https://portale.siva.it/files/doc/product/abbyy%20-%20finereader%20brochure.pdf.pdf) | Brosura PDF oficiala | Toate functiile, pe editii | A |
| S02 | [Ghid utilizator v16 (FR)](https://help.abbyy.com/assets/fr-fr/finereader/16/Users_Guide.pdf) | Manual PDF oficial | UI, proceduri, CLI, formate, cerinte, licentiere (citit 0-650k din 886k caractere) | A |
| S03 | [OCR Editor interface](https://help.abbyy.com/en-us/finereader/16/user_guide/ocrwindow) | Help online | Panouri, toolbar-uri, layout | A |
| S04 | [Options dialog](https://help.abbyy.com/en-us/finereader/16/user_guide/options_window) | Help online | Cele 7 tab-uri | A |
| S05 | [Keyboard shortcuts](https://help.abbyy.com/en-us/finereader/16/user_guide/hotkeys) | Help online | Toate meniurile si scurtaturile | A |
| S06 | [Hot Folder](https://help.abbyy.com/en-us/finereader/16/user_guide/hotfolder) | Help online | Pasi, statusuri, log | A |
| S07 | [Automated tasks](https://help.abbyy.com/en-us/finereader/16/user_guide/taskmanager) | Help online | Tipuri de pasi | A |
| S08 | [PDF Editor overview](https://help.abbyy.com/en-us/finereader/16/user_guide/workwithpdf) | Help online | Structura capitolului | A |
| S09 | [Viewing modes](https://help.abbyy.com/en-us/finereader/16/user_guide/view_modes) | Help online | Moduri de vizualizare, panouri | A |
| S10 | [Viewing comparison results](https://help.abbyy.com/en-us/finereader/16/user_guide/differences) | Help online | Tipuri de diferente, grupare | A |
| S11 | [Command line save](https://help.abbyy.com/en-us/finereader/16/user_guide/commandline_save) | Help online | Parametri de export | A |
| S12 | [Image Editor](https://help.abbyy.com/en-us/finereader/16/user_guide/adjustimage) | Help online | Unelte de preprocesare | A |
| S13 | [Image processing options](https://help.abbyy.com/en-us/finereader/16/user_guide/scanoptions) | Help online | Setari de preprocesare | A |
| S14 | [Editing areas](https://help.abbyy.com/en-us/finereader/16/user_guide/editareas) | Help online | Unelte de zona | A |
| S15 | [Area properties](https://help.abbyy.com/en-us/finereader/16/user_guide/rectext) | Help online | Cele 6 proprietati | A |
| S16 | [OCR options](https://help.abbyy.com/en-us/finereader/16/user_guide/recoptions) | Help online | Moduri PDF, structura | A |
| S17 | [PDF settings](https://help.abbyy.com/en-us/finereader/16/user_guide/pdf_settings) | Help online | Optiuni de salvare PDF | A |
| S18 | [DOCX settings](https://help.abbyy.com/en-us/finereader/16/user_guide/docx_settings) | Help online | Moduri de layout | A |
| S19 | [Standard vs Corporate](https://support.abbyy.com/hc/en-us/articles/4415642638355) | Baza de cunostinte | Diferente de editie | A |
| S20 | [Release notes v16](https://support.abbyy.com/hc/en-us/sections/9279032986387) | Release notes | Build-uri | A |
| S21 | [Release 1 Update 2](https://support.abbyy.com/hc/en-us/articles/9928811814547-FineReader-PDF-16-Release-1-Update-2-build-16-0-12-3977) | Release notes (doar cautare) | Data lansarii | A |
| S22 | [EoL FineReader 15](https://support.abbyy.com/hc/en-us/articles/29214691204882) | Anunt oficial (doar cautare) | Sfarsitul v15 | A |
| S23 | [Hot Folder tasks location](https://support.abbyy.com/hc/en-us/articles/29218301003027-How-to-create-a-Hot-Folder-task-visible-for-both-the-Local-Administrator-and-the-Domain-User) | Baza de cunostinte | Fisiere .hft | A |
| S24 | [Tutoriale video oficiale](https://pdf.abbyy.com/how-to-videos/) | Pagina oficiala | Lista de 30 de videoclipuri | A |
| S25 | [Blog: Organize Pages](https://pdf.abbyy.com/blog/organize-pdf-pages/) | Blog oficial (doar cautare) | Lista de tab-uri | A |
| S26 | [Blog: Release 3](https://pdf.abbyy.com/blog/finereader-pdf-release-3-updates/) | Blog oficial | Cele 4 componente de baza | A |
| S27 | [Ce e nou in v16](https://pdf.abbyy.com/the-new-fr16/) | Pagina de produs | Noutati v16 | A |
| S28 | [Forum: tabbed UI](https://support.abbyy.com/hc/ja/community/posts/20867865196435-New-tabbed-user-interface-in-FineReader-PDF-16) | Forum oficial | Lipsa tab-urilor de documente | A |
| S29 | [Capterra](https://www.capterra.com/p/65868/ABBYY-FineReader/) | Recenzii | Preturi, plangeri | C |
| S30 | [G2](https://www.g2.com/products/finereader-pdf-15/reviews) | Recenzii | Note, plangeri | C |
| S31 | [FileHorse](https://www.filehorse.com/download-abbyy-finereader-pdf/) | Site de download | Pret in EUR, cerinte, "2026" | F |
| S32 | [Wikipedia](https://en.wikipedia.org/wiki/ABBYY_FineReader) | Enciclopedie | Ultimul build stabil | C |
| S33 | [Area types (Mac)](https://help.abbyy.com/en-us/finereader/15mac/user_guide/areatypes) | Help online Mac | Culorile zonelor | C |
| S34 | [Barcode recognition](https://help.abbyy.com/en-us/finereader/16/user_guide/recbarcode) | Help online | Tipuri de coduri de bare | A |

Documente care n-au putut fi deschise: ghidul in engleza de pe pdf.abbyy.com, din cauza unei erori de server (am folosit in schimb varianta franceza de pe help.abbyy.com, citita pe portiuni), si pagina de preturi ABBYY. In runda a doua, help.abbyy.com cerea acceptarea unor termeni de utilizare inainte de acces, asa ca am lucrat cu ce extrasesem deja si cu tutorialele video.

## 7. Gap analysis si acoperire

Dupa a doua runda de cercetare, pe video, acoperirea functionala si de interfata e practic completa. Raman doua goluri reale: valorile vizuale exacte in pixeli si HEX, si calitatea motorului OCR al ABBYY, care nu poate fi egalata identic cu biblioteci open-source.

### 7.1 Tabel de acoperire

| Domeniu | Investigat | Surse | Incredere | Ce lipseste |
| --- | --- | --- | --- | --- |
| Module si functii | Da | Lista completa de functii + help + 22 video | A | Nimic semnificativ |
| Meniuri si scurtaturi | Da | Help + meniul Tools citit de pe ecran | A | Ordinea exacta a catorva submeniuri rar folosite |
| Structura ferestrelor | Da | Peste 60 de cadre din video | A / B | Pozitii exacte in pixeli |
| Toolbar-e si ribbon-uri | Da | Cadre din toate cele 5 tab-uri | B | - |
| Dialoguri | Da | Cadre din 12 dialoguri majore | B | Dialogurile de verificare si de antrenare a sabloanelor |
| Optiuni (Options) | Da | Toate cele 7 tab-uri citite de pe ecran | A / B | Optiunile complete pentru XLSX, PPTX, HTML si EPUB |
| Culori, fonturi, dimensiuni | Partial | Cadre comprimate | D | HEX-uri exacte, spatieri, iconuri |
| Stari ale interfetei | Da | Observate in video | B | Semnificatia exacta a fiecarei insigne de pagina |
| Fluxuri de lucru | Da | Demonstrate integral in webinarii | A / B | - |
| Reguli de business | Da | Help + comportament observat | A / B | Pragurile interne de incredere OCR |
| Automatizari | Da | Hot Folder si Task Settings vazute pas cu pas | A / B | Formatul intern .hft (irelevant) |
| Linie de comanda | Da | Ghidul utilizatorului | A | - |
| Integrari | Da | Ghid + demonstratii Office si Explorer | A | - |
| Utilizatori si roluri | Da | Absenta confirmata | A | Nu exista roluri in aplicatie |
| Versiuni | Da | Release notes + diferente v14/v15/v16 observate direct | A | Ce contine actualizarea "2026" |
| Tutoriale video | Da | 22 analizate, transcrieri + cadre | B | Tutorialele in limbi pe care nu le-am parcurs |
| Arhitectura interna ABBYY | Nu (nepublica) | - | E | Inlocuita cu arhitectura proprie, capitolul 4 |
| Responsive | Nu se aplica | - | - | Aplicatie desktop; doar redimensionarea ferestrei si a panourilor |

### 7.2 Diferente inevitabile fata de original

- **Calitate OCR:** Tesseract si PaddleOCR sunt sub ABBYY pe scanari slabe, tabele complexe si stampile peste text. Diferenta estimata e de cateva puncte procentuale de acuratete pe documente dificile (D). Arhitectura cu interfata `OcrEngine` permite ulterior un motor comercial (de exemplu ABBYY FineReader Engine SDK), daca e nevoie.
- **Exact copy in Word:** reconstructia cu text box-uri pozitionate absolut e realizabila, dar fidelitatea va fi mai mica.
- **MRC si PreciseScan:** sunt algoritmi proprietari. Echivalentul se face prin separare text/fundal cu OpenCV, plus JBIG2 pentru masca si JPEG2000 pentru fundal. Factorul de comprimare de 20x nu e garantat.
- **Detectie automata de limba si clasificarea documentelor:** se implementeaza cu langdetect sau fastText si cu euristici proprii.
- **Dictionare pentru 53 de limbi:** se folosesc dictionare Hunspell, cu licente care trebuie verificate per limba.
- **Licentiere de firma** (License Manager, licente concurente, Azure): nu e necesara pentru uz propriu. Se poate amana.

### 7.3 Presupuneri necesare

- **Fara conturi de utilizator:** FineReader e o aplicatie desktop pentru o singura persoana, fara login. Matricea de permisiuni din cerinte se reduce la doua lucruri: permisiunile PDF (deschidere, tiparire, editare, copiere) si autorul comentariilor. Nivel A, din absenta oricarei mentiuni.
- **Limba interfetei:** alternativa porneste in romana si engleza.
- **Format proiect:** folder sau zip propriu, nu compatibil cu proiectele OCR ABBYY, al caror format e inchis.
- **Platforma:** Windows 10/11 x64, cu cod care poate rula si pe Linux, cu exceptia TWAIN, WIA si a integrarii Office.

## 8. Master Prompt pentru dezvoltare

Master Prompt-ul complet e in fisierul separat `MASTER_PROMPT_alternativa_FineReader.md`, livrat in conversatie. Il copiezi integral intr-o conversatie noua cu un AI programator. E autonom: nu are nevoie de acest document.

**Structura lui (14 sectiuni):**

1. Rolul AI-ului si cele 12 reguli obligatorii (fara butoane decorative, fara "Coming soon", fara copierea marcii ABBYY, decizii documentate separat).
2. Descrierea produsului si cele 7 executabile ale suitei.
3. Stack-ul tehnic obligatoriu (PySide6, pypdfium2, pikepdf, Tesseract, PaddleOCR, OpenCV, pyHanko etc.).
4. Arhitectura pe pachete, cu `core` separat de `gui`.
5. Modelul de date complet (proiect OCR si baza globala).
6. Setarile globale: cele 7 tab-uri ale dialogului Options, optiune cu optiune.
7. Specificatii UI/UX per fereastra: design system cu tokeni HEX proprii, mod intunecat, componente reutilizabile, toate meniurile, tab-urile, panourile si scurtaturile.
8. Formatele de intrare si iesire.
9. Backend: pipeline OCR, preprocesare, layout, moduri PDF, editare PDF, setarile fiecarui exportor, automatizare, erori.
10. Linia de comanda, compatibila ca semantica cu originalul.
11. Securitate: offline, DPAPI, redactare reala, eliminarea datelor ascunse, PDF-uri malformate.
12. Testare: corpus, metrici CER/WER, performanta.
13. Planul pe 16 etape.
14. Cele 22 de reguli de business de implementat si testat, plus livrabilele finale.

**Decizii proprii marcate \[DECIZIE\] in prompt:** pragul de incredere OCR (70), detectia antetelor (text repetat pe peste 50% din pagini), salvarea automata la 5 minute, stabilitatea fisierelor in Hot Folder (3 secunde), suport JavaScript limitat. Nu vin de la ABBYY si se pot schimba.

**Imbunatatiri fata de original incluse:** documente in tab-uri, mod intunecat, interfata in romana si OCR romanesc cu diacritice (inclusiv ş si ţ cu sedila, frecvente in documentele vechi).

## 9. Plan de implementare

Prima versiune utila e gata dupa faza 3: OCR Editor cu export in Word si PDF cautabil, adica exact ce iti trebuie la dosarele scanate. Restul se adauga pe module. Duratele sunt estimari pentru un dezvoltator lucrand cu un AI programator (D).

| Faza | Continut | Depinde de | Durata estimata | Gata cand |
| --- | --- | --- | --- | --- |
| 0. Fundatie | Backlog cu ID-uri, schelet de pachete, interfete, CI, schema bazelor de date, design system si componente comune | - | 2 saptamani | Testele CI trec; galeria de componente ruleaza |
| 1. Motor OCR | Proiect OCR, preprocesare (toate cele 14 unelte), detectie zone, Tesseract si Paddle, limbi, dictionare | 0 | 4 saptamani | CER sub 2% pe scanari curate in romana; toate uneltele au teste |
| 2. OCR Editor UI | Panourile Pages, Image, Text, Zoom si Warnings, Image Editor, editare zone si tabele, verificare, Options | 1 | 4 saptamani | Flux complet de la deschidere la verificare, din tastatura si mouse |
| 3. Export de baza | PDF cautabil (3 moduri), PDF/A, DOCX (4 moduri), TXT, XLSX, CSV | 1 | 3 saptamani | Fisierele se deschid fara erori in Word, Excel si Acrobat; PDF/A trece verificarea veraPDF |
| 4. PDF Editor | Vizualizare, navigare, cautare, comentarii, Organize Pages, Save si Print, recunoastere in fundal, tab-uri de documente | 0, 1 | 5 saptamani | PDF de 500 de pagini deschis in sub 3 secunde; adnotarile se vad in Acrobat |
| 5. Lansator | Cele 5 tab-uri de sarcini, conversii rapide, recente | 3, 4 | 1 saptamana | Fiecare card ruleaza conversia reala |
| 6. Editare avansata PDF | Edit Content, antete si subsoluri, Bates, filigran, linkuri, semne de carte, atasamente, metadate | 4 | 5 saptamani | Textul editat se pastreaza la redeschidere; restul paginii ramane neatins |
| 7. Securitate si formulare | Parole si criptare, redactare reala, eliminare date ascunse, semnaturi, Form Editor | 4 | 4 saptamani | Textul redactat nu se mai poate extrage; semnatura e valida in Acrobat |
| 8. Exportori ramasi | PPTX, ODT, RTF, HTML, EPUB, FB2, DjVu, imagini, plus Exact copy | 3 | 3 saptamani | Fiecare format se deschide in aplicatia lui |
| 9. Compare | Extragere, aliniere, grupare, UI cu doua panouri, cele 3 rapoarte | 1, 4 | 3 saptamani | Toate diferentele plantate in perechile de test sunt gasite |
| 10. Automatizare | Automated Tasks, Hot Folder (folder, FTP, e-mail), CLI, Screenshot | 3, 9 | 3 saptamani | O sarcina Hot Folder ruleaza 24 de ore fara eroare pe 1.000 de fisiere |
| 11. Integrari | Scanare TWAIN/WIA, meniul din Explorer, add-in Office | 4, 5 | 3 saptamani | Scanare cu ADF si duplex; comenzile apar in Explorer si Word |
| 12. Finalizare | Optimizare, testare completa, instalator, manuale RO/EN | toate | 2 saptamani | Testele de acceptanta din capitolul 10 trec |

Total estimat: circa 42 de saptamani pentru paritate completa cu editia Corporate.

**Ordine recomandata pentru uzul tau:** fazele 0, 1, 2, 3 si 10 (doar CLI si Hot Folder). Asa obtii in circa 16 saptamani un instrument OCR offline pentru dosarele de rambursare, care se poate lega de softul tau de verificare a dosarelor. PDF Editor-ul complet poate veni dupa.

## 10. Plan de testare si acceptanta

Alternativa e acceptata cand trec toate testele critice de mai jos, iar acoperirea cu teste automate a pachetului `core` e de cel putin 80%. Testele folosesc un corpus fix de 11 documente, descris in Master Prompt (sectiunea 11).

**Planul complet e in `SPEC_06_plan_de_testare.md`**, cu matricea cerinta catre test in `SPEC_07_matrice_trasabilitate.csv`: cele 18 grupuri ale corpusului de test, 19 praguri de calitate masurabile (acuratete pe caracter peste 98% la 300 dpi, pe cuvant peste 96% pe documente romanesti, confuzie s-sedila si t-sedila sub 2 la 1.000 de caractere), procedurile celor 53 de teste de prioritate 1, cele 10 scenarii de acceptanta cronometrate si lista deschisa a ce nu acopera planul. Scenariile de mai jos sunt subsetul de verificat manual.

### 10.1 Scenarii de testare

| ID | Modul | Scenariu si pasi | Rezultat asteptat (criteriu de acceptanta) |
| --- | --- | --- | --- |
| T01 | OCR | Deschizi o scanare in romana la 300 dpi, cu procesare automata, apoi Recognize All | CER sub 2%; diacriticele ă â î ș ț recunoscute; caracterele sub prag evidentiate |
| T02 | Preprocesare | Fotografie de telefon inclinata 7 grade, cu trapez | Deskew si Correct Trapezoid aduc liniile la orizontala cu toleranta de 0,5 grade |
| T03 | Preprocesare | Carte scanata cu doua pagini, Split facing pages | Rezulta 2 pagini in ordinea corecta |
| T04 | Zone | Desenezi o zona Table peste un tabel, apoi Analyze table structure, Merge cells si Recognize | Celulele unite se pastreaza in DOCX si XLSX |
| T05 | Zone | Schimbi tipul unei zone recunoscute | Statusul paginii revine la analyzed; apare avertismentul de re-recunoastere |
| T06 | Sablon | Salvezi un sablon de zone si il aplici pe 10 pagini | Zonele identice apar pe toate cele 10 pagini |
| T07 | Verificare | Verify Text, apoi Add to Dictionary pe un cuvant | Cuvantul nu mai e marcat la urmatoarea recunoastere |
| T08 | Export | Salvezi in cele 4 moduri DOCX | Exact copy foloseste cadre; Plain text nu are formatare; Keep line numbers disponibil doar in Editable copy |
| T09 | Export | PDF cautabil cu Text under the page image si MRC | Fisier mai mic decat originalul; textul se poate cauta; MRC indisponibil in celelalte moduri |
| T10 | Export | PDF/A-2b | Trece validarea veraPDF |
| T11 | PDF Editor | Deschizi un PDF de 500 de pagini | Prima pagina apare in sub 3 secunde |
| T12 | PDF Editor | PDF scanat fara strat text, apoi cautare | Recunoasterea in fundal gaseste cuvantul; fisierul ramane nemodificat pana la salvare |
| T13 | Cautare | Search and Replace pe 3 aparitii bifate din 5 | Se inlocuiesc doar cele 3 |
| T14 | Comentarii | Adaugi nota, highlight si forma, apoi status Accepted, filtru dupa autor si salvare | Adnotarile apar in Adobe Acrobat; filtrul ascunde corect |
| T15 | Organize Pages | Interval "2,3,5-7", Rotate, Move, Delete si Undo | Ordinea si rotatia sunt corecte; Undo revine complet |
| T16 | Split | Split dupa semne de carte de nivel 1 | Un fisier per semn de carte; atasamentele intr-un subfolder |
| T17 | Edit Content | Editezi un paragraf intr-un PDF digital si salvezi | Textul nou e in fisier; restul paginii ramane identic; versiunea PDF nu scade |
| T18 | Securitate | Parola de permisiuni egala cu parola de deschidere | Eroare de validare; nu se salveaza |
| T19 | Redactare | Redactezi un CNP fictiv, salvezi si extragi textul | CNP-ul lipseste complet din textul extras |
| T20 | Date ascunse | Remove hidden data | Nu mai raman metadate, comentarii, atasamente sau JavaScript |
| T21 | Semnatura | Semnatura digitala cu timestamp | Valida in Adobe Acrobat; LTV prezent |
| T22 | Formulare | Creezi 7 tipuri de campuri; Required pe unul; doua campuri cu acelasi nume | Numele duplicat e refuzat; Required doar avertizeaza; exportul FDF e corect |
| T23 | Compare | Word fata de scanarea lui, cu 10 diferente plantate | Toate cele 10 gasite si grupate; ignorate lipsesc din raport |
| T24 | Compare | Salvezi in cele 3 formate | Track Changes in Word; PDF cu comentarii; tabel Word |
| T25 | Automated Tasks | Stergi pasul Analyze | Pasul OCR dispare automat |
| T26 | Hot Folder | Sarcina la fiecare minut pe un folder, cu 1.000 de fisiere in 24 de ore | 0 fisiere pierdute; jurnal cu statistici; statusul trece prin Watching si Running |
| T27 | Hot Folder | Un fisier corupt in lot | Restul lotului se proceseaza; eroarea apare in jurnal |
| T28 | CLI | `dl-ocr.exe doc.pdf /lang Romanian /out rez.docx /report r.txt` | DOCX creat; raport scris; cod de iesire 0 |
| T29 | CLI | `dl-compare.exe` cu `/options:IgnorePunctDiff,UngroupDiff /saveMode:Word` | Tabel Word fara diferente de punctuatie si negrupat |
| T30 | Securitate | 50 de PDF-uri malformate (fuzzing) | Nicio blocare; mesaj de eroare clar pentru fiecare |
| T31 | UI | Navigare completa doar din tastatura, cu scurtaturile din capitolul 3.6 | Fiecare scurtatura face comanda documentata |
| T32 | UI | Mod intunecat si monitor 4K la 200% | Fara text taiat; contrast AA |
| T33 | Offline | Rulezi T01-T29 cu reteaua dezactivata | Toate trec |
| T34 | Instalare | Instalare silentioasa pe Windows 10 si 11 curate | Toate cele 7 executabile pornesc; Tesseract si modelele sunt incluse |

### 10.2 Tipuri de testare acoperite

- **Automate:** unitare (pytest), GUI (pytest-qt), API intern si CLI, baza de date (migratii si integritate), proprietati (hypothesis) si regresie la fiecare faza.
- **Performanta:** T11, T26, plus OCR pe o pagina A4 la 300 dpi in sub 4 secunde pe 4 nuclee.
- **Securitate:** T18-T20, T30 si testul offline T33.
- **Interfata si UX:** T31, T32, plus o revizuire manuala a fiecarei ferestre fata de capitolul 3.
- **Nu se aplica:** teste de autentificare si autorizare pe roluri (aplicatia nu are conturi) si teste responsive pe telefon (aplicatie desktop).
