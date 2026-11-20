# SPECIFICATIE 01 — Lansator si PDF Editor

Document 2 din livrabile, partea 1. **Versiunea 2, rescrisa dupa verificarea contra manualului oficial de 513 pagini.**

Fiecare rand e o cerinta implementabila si testabila. ID-ul se foloseste in cod (comentariu deasupra functiei), in commit-uri si in planul de testare.

**Legenda coloanelor**
- **ID** — identificator stabil, nu se reutilizeaza niciodata.
- **Unde** — unde se declanseaza in interfata.
- **Intrari** — ce primeste functia.
- **Reguli si validari** — ce verifica inainte si in timpul executiei.
- **Rezultat** — ce se schimba la final.
- **Erori** — ce se afiseaza cand nu merge.
- **Src** — de unde stim asta.

**Legenda surselor**
- **D** = confirmat in documentatia oficiala ABBYY. Se implementeaza exact asa.
- **V** = observat pe ecran in tutoriale video, neconfirmat in scris.
- **K** = din baza de cunostinte ABBYY.
- **N** = **adaugat de noi**, nu exista in original.
- **X** = **diferit deliberat** de original, cu motivul in nota.

**Legenda editiilor:** S = Standard, C = doar Corporate.

---

## A. LANSATOR (New Task)

### A.1 Structura ferestrei

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| A-001 | Deschiderea lansatorului la pornire | pornirea aplicatiei | setarea de ecran initial | **cele trei valori sunt: ecranul Lansatorului, OCR Editor cu proiect nou, OCR Editor cu ultimul proiect** | fereastra Lansator, tabul `Open` activ | ultimul proiect lipseste → proiect nou, notat in jurnal | D |
| A-002 | Revenire la Lansator | butonul din tabul `Document` al PDF Editor-ului; bara principala a OCR Editor-ului; `Ctrl+N` | — | **lansatorul se deschide si cand aplicatia e pornita prin clic dreapta pe un fisier in Explorer** | Lansatorul; modulul curent rămâne deschis | — | D |
| A-003 | Cele cinci sarcini din coloana stanga | clic pe sarcina | — | `Open`, `Scan`, `Compare`, `Recent`, `Mobile application` | panoul din dreapta se schimba | — | D |
| A-004 | Toate sarcinile folosesc setarile din Options | automat | — | `Tools > Options` | — | — | D |
| A-005 | Butonul `Options` | **stanga-jos a ecranului Lansatorului** | — | — | dialogul Options, tabul General | — | D |
| A-006 | Ajutor | `F1` | — | — | manualul local, la pagina contextuala | manual lipsa → mesaj cu calea asteptata | D |
| A-007 | Afisarea scenariilor la hover | hover peste o sarcina | cardul | intarziere 600 ms | pop-up cu scenarii tipice | — | N |

### A.2 Tabul Open — conversie rapida

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| A-010 | `PDF Document` | tab Open; `File > New PDF Document`; `File > Open PDF Document...` | fisier | PDF existent si citibil | PDF Editor cu documentul | fisier corupt → mesaj cu detalii copiabile | D |
| A-011 | Deschiderea unui PDF protejat | A-010 | parola | 3 incercari | documentul se deschide cu permisiunile din fisier | parola gresita → mesaj | D |
| A-012 | `OCR Editor` | tab Open; `Tools > OCR Editor`; `File > Open in OCR Editor...`; `Ctrl+R` | unul sau mai multe fisiere | formatele din tabelul de formate, coloana „intrare OCR Editor" | OCR Editor cu proiect nou | format nesuportat → fisierul se sare, se listeaza la final | D |
| A-013 | `Convert to PDF` | tab Open | lista de fisiere | minimum 1 fisier | panoul de conversie | — | D |
| A-014 | `Convert to Microsoft Word` | tab Open | lista de fisiere | idem | panou cu opțiuni DOCX | — | D |
| A-015 | `Convert to Microsoft Excel` | tab Open | lista de fisiere | idem | panou cu opțiuni XLSX | — | D |
| A-016 | `Convert to Other Formats` | tab Open | lista de fisiere | **formatele de ieșire: `.pptx`, `.odt`, `.html`, `.epub`, `.fb2`, `.rtf`, `.txt`, `.csv`, `.djvu`** | panou cu selector de format | — | D |
| A-017 | Recomandarea pentru documente complexe | panoul de conversie | — | **manualul recomanda conversia avansata (OCR Editor) pentru documente mari cu layout complex** | link catre OCR Editor | — | D |

### A.3 Panoul de conversie — comun

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| A-020 | Lista de fisiere | panou | fisiere | icon dupa tip, nume, dimensiune | lista reordonabila | — | D |
| A-021 | Adaugarea de fisiere | buton | fisiere noi | aceleasi formate | se adauga la sfarsitul listei | — | D |
| A-022 | Scoaterea unui fisier | buton | selectie | minimum 1 fisier ramas | fisierul dispare | — | D |
| A-023 | Mutare sus / jos | butoane; `Alt+Sus` / `Alt+Jos` | selectie | primul nu urca, ultimul nu coboara | ordinea se schimba; conteaza la combinare | — | D |
| A-024 | `Combine all files into one document` | bifa | — | activa cu minimum 2 fisiere | un singur fisier, in ordinea listei; apoi se cere numele si folderul | — | D |
| A-025 | `Remove` din lista | `Del` | selectie | — | — | — | D |
| A-026 | `Select all` | `Ctrl+A` | — | — | — | — | D |
| A-027 | Pornirea conversiei | butonul `Convert to <format>` | toate setarile | cel putin 1 fisier valid | dialog de progres, apoi alegerea folderului de destinatie | — | D |
| A-028 | Dialogul de progres | automat | — | se poate anula | bara, numarul de fisiere procesate, numele fisierului curent | la eroare pe un fisier, lotul continua; raport la final | V |
| A-029 | Revenirea la tabul Open | buton | — | avertisment dacă lista are fisiere | — | — | V |

### A.4 Panoul `Convert to PDF`

| ID | Setare | Valori | Reguli si validari | Src |
|---|---|---|---|---|
| A-035 | `Image quality` | `Best quality` / `Balanced` / `Compact size` / `Custom...` | `Best quality` pastreaza rezolutia originala; `Balanced` da fisier mai mic cu pierdere moderata; `Compact size` reduce calitatea imaginilor; `Custom...` deschide dialogul `Custom Settings`, confirmat cu `OK` | D |
| A-036 | `Full-text search` | **trei valori: `As in original document` / `Search inside text and images` / `Disable full-text search`** | prima recunoaste text numai dacă originalul are strat de text; a doua recunoaste si imaginile; **a treia produce un PDF doar-imagine** | D |
| A-037 | `Create PDF/A documents` | bifa | **se creeaza PDF/A-2b implicit**; `More options...` permite alegerea altei versiuni | D |
| A-038 | `Use MRC compression` | bifa | compresie Mixed Raster Content, reduce dimensiunea | D |
| A-039 | `OCR languages` | combo multiplu | minimum 1 | D |
| A-040 | `Image preprocessing settings...` | buton | deschide setarile de preprocesare | D |
| A-041 | `More options...` | buton | deschide tabul PDF din `Format Settings` | D |
| A-042 | Butonul final | `Convert to PDF` | — | D |

### A.5 Panoul `Convert to Microsoft Word`

| ID | Setare | Valori | Reguli si validari | Src |
|---|---|---|---|---|
| A-050 | `Keep formatting` | **patru valori: `Exact copy` / `Editable copy` / `Formatted text` / `Plain text`** | `Exact copy` e aproape identic cu originalul, dar greu de editat; `Editable copy` poate diferi usor, dar e usor de editat; `Formatted text` pastreaza fonturi, dimensiuni si paragrafe pe o singura coloana; `Plain text` pastreaza numai formatarea de paragraf, pe o coloana, cu un singur font | D |
| A-051 | `OCR languages` | combo multiplu | — | D |
| A-052 | `Keep pictures` | bifa | — | D |
| A-053 | `Keep headers, footers, and page numbers` | bifa | — | D |
| A-054 | `More options...` | buton | deschide tabul DOC(X)/RTF/ODT | D |
| A-055 | Butonul final | `Convert to Word` | — | D |

### A.6 Panoul `Convert to Microsoft Excel`

| ID | Setare | Valori | Reguli si validari | Src |
|---|---|---|---|---|
| A-060 | `Keep formatting` | **numai doua valori: `Formatted text` / `Plain text`** | — | D |
| A-061 | `OCR languages` | combo multiplu | — | D |
| A-062 | `Keep pictures` | bifa | **numai XLSX** | D |
| A-063 | `Create a separate sheet for each page` | bifa | **numai XLSX** | D |
| A-064 | `More options...` | buton | deschide tabul XLS(X) | D |
| A-065 | Butonul final | `Convert to Excel` | — | D |

### A.7 Panoul `Convert to Other Formats`

| ID | Setare | Valori | Src |
|---|---|---|---|
| A-070 | `Select output format` | `.pptx`, `.odt`, `.html`, `.epub`, `.fb2`, `.rtf`, `.txt`, `.csv`, `.djvu` | D |
| A-071 | `OCR languages` | combo multiplu | D |
| A-072 | `More options...` | deschide tabul formatului ales | D |
| A-073 | Butonul final | `Convert to <format>` | D |

### A.8 Tabul Scan

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| A-080 | Cele sase sarcini de scanare | tab Scan | — | `OCR Editor`, `PDF Document`, `Microsoft Word`, `Microsoft Excel`, `Image Files`, `Other Formats` | panoul sarcinii | — | D |
| A-081 | Pasii comuni | panou | dispozitiv, setari | se alege dispozitivul, apoi `Preview` (sau clic in imagine), apoi setarile formatului, apoi `Scan to <format>` | dialog de progres | niciun scaner → mesaj si buton catre Options | D |
| A-082 | **Dupa fiecare pagina** | automat | — | **se ofera `Scan Again` pentru a continua cu setarile curente, sau `Finish Scanning` pentru a inchide** | — | — | D |
| A-083 | `Scan to OCR Editor` | panou | `Automatically process page images as they are added` cu trei moduri: `Recognize page images`, `Analyze page images`, `Preprocess page images` | la `Analyze`, OCR-ul se porneste manual | paginile intra intr-un proiect OCR | — | D |
| A-084 | `Scan to PDF` | panou | `Image quality`, `Create PDF/A documents`, `Use MRC compression`, **`Recognize text on images`** | `Recognize text on images` porneste OCR-ul automat | **rezultatul se deschide in OCR Editor si se alege folderul de salvare** | — | D |
| A-085 | `Scan to Microsoft Word` | panou | `Preserve formatting` (4 valori), `OCR languages`, `Keep pictures`, `Keep headers, footers, and page numbers` | — | DOCX | — | D |
| A-086 | `Scan to Microsoft Excel` | panou | `Preserve formatting` (2 valori), `OCR languages`, `Keep pictures`, `Create a separate sheet for each page` | — | XLSX | — | D |
| A-087 | `Scan to Image Files` | panou | format de imagine, compresie | — | imagini | — | D |
| A-088 | Compresia TIFF | panou | **`PACKBITS` (fara pierderi, pentru scanari alb-negru); `JPEG (JFIF)` (cu pierderi, pentru fotografii gri si color, produce neclaritate si pierdere de culoare); `ZIP` (fara pierderi, pentru zone mari de o singura culoare); `LZW` (fara pierderi, pentru imagini vectoriale si gri)** | numai pentru TIFF | — | — | D |
| A-089 | `Scan to Other Formats` | panou | format, limbi | — | fisier | — | D |
| A-090 | `Image preprocessing settings...` in panourile de scanare | buton | — | — | — | — | D |

### A.9 Tabul Compare, Recent, Mobile application

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src | Editie |
|---|---|---|---|---|---|---|---|---|
| A-100 | Deschiderea modulului de comparare | tab Compare; `Tools > Compare Documents` | — | — | fereastra Compare, goala | — | D | C |
| A-101 | `Recent Comparisons` | tab Compare; `File > Recent Comparisons` in modulul de comparare | istoric | — | clic pe o pereche o redeschide | fisier lipsa → randul se marcheaza | D | C |
| A-102 | Lista de documente recente | tab Recent | istoric | **reia un PDF sau un proiect OCR salvat** | clic deschide documentul in modulul potrivit | fisier mutat → mesaj si opțiune de cautare | D |  |
| A-103 | `Find recent documents` | `Ctrl+F` in tab Recent | text | cautare in nume si in cale, fara diacritice | lista filtrata live | — | D |  |
| A-104 | Stergerea unei intrari din recente | meniu contextual | intrare | — | dispare din lista; fisierul nu se atinge | — | V |  |
| A-105 | Golirea listei de recente | meniu contextual | — | confirmare | lista goala | — | V |  |
| A-106 | Cerintele pentru aplicatia mobila | tab Mobile application | — | **aplicatia FineReader PDF pentru iOS plus clientul Google Drive pentru Windows** | — | — | D |  |
| A-107 | `Select folder` | tab Mobile application | folder | folderul local al clientului Google Drive, subfolderul FineReader | continutul se listeaza | folder sters → se cere din nou | D |  |
| A-108 | Sortarea documentelor mobile | automat | — | **dupa data creării, cel mai nou primul** | — | — | D |  |
| A-109 | Deschiderea unui element mobil | tab Mobile application | fisier sau folder | **un PDF se deschide in editor; un folder de imagini deschide un dialog de creare de PDF din JPG-uri; alte formate se convertesc in PDF** | — | — | D |  |
| A-110 | Sincronizarea inapoi | la salvare | — | modificarile urca pe server | — | — | D |  |
| A-111 | Empty state pe tab Recent | automat | — | — | mesaj si buton `Open` | — | V |  |

---

## B. PDF EDITOR — vizualizare si navigare

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| B-001 | Randarea paginii | centrul ferestrei | pagina, zoom | randare lenesa: paginile vizibile plus una inainte si una dupa | pagina afisata | pagina corupta → chenar gri cu mesaj | N |
| B-002 | `One-Page View` | bara jos; `View > View mode`; `Ctrl+5` | — | **o singura pagina** | — | — | D |
| B-003 | `One-Page Scrolling` | `Ctrl+6` | — | **paginile una dupa alta, cu derulare** | — | — | D |
| B-004 | `Two-Page View` | `Ctrl+7` | — | **doua pagini alaturate, impare in stanga si pare in dreapta** | — | — | D |
| B-005 | `Two-Page Scrolling` | `Ctrl+8` | — | perechi, cu derulare | — | — | D |
| B-006 | `Odd Pages on the Right` | `View > View mode` | — | **activ numai in modurile cu doua pagini** | paginile impare trec la dreapta | — | D |
| B-007 | Ecran complet | buton din bara de jos; `View > Full Screen`; `F11` | — | **se iese cu `F11` sau `Esc`** | pagina pe tot ecranul | — | D |
| B-008 | Bara de unelte in ecran complet | mouse la marginea de jos | — | — | bara cu moduri de vizualizare si camp de numar de pagina | — | D |
| B-009 | Meniu contextual in ecran complet | clic dreapta | — | **comentarii, puncte de inserare de text, semne de carte, editare de text si imagini** | — | — | D |
| B-010 | Zoom in / out | `Ctrl++` / `Ctrl+-`; bara jos | — | — | pagina se scaleaza | la limita, butonul se dezactiveaza | D |
| B-011 | `Best Fit` | `Ctrl+0` | — | **inaltimea paginii incape pe ecran** | — | — | D |
| B-012 | `Actual Size` | `Ctrl+1` | — | 100% din dimensiunea fizica | — | — | D |
| B-013 | `Fit to Width` | `Ctrl+2` | — | **latimea paginii incape pe ecran** | — | — | D |
| B-014 | Camp de numar de pagina | bara jos | numar + `Enter` | intre 1 si numarul de pagini | sare la pagina | in afara intervalului → camp rosu | D |
| B-015 | `Go to Page > Page Number...` | `Ctrl+G` | numar | idem | — | — | D |
| B-016 | Pagina urmatoare / anterioara | `Ctrl+Jos` / `Ctrl+Sus`; `View > Go to Page` | — | la capete, butoanele se dezactiveaza | — | — | D |
| B-017 | Prima / ultima pagina | `Home` / `End`; `View > Go to Page` | — | — | — | — | D |
| B-018 | Inapoi / inainte in istoricul de navigare | `Alt+Stanga` / `Alt+Dreapta` | — | istoric de 50 de pozitii | revine la pozitia anterioara, inclusiv zoom | — | V |
| B-019 | Panoul de navigare | `F5`; `View > Show Navigation Pane`; bara verticala | — | **cele sase panouri: `Pages`, `Bookmarks`, `Search`, `Comments`, `Attachments`, `Digital Signatures`** | panoul ales se deschide | — | D |
| B-020 | `Pages` | `Alt+Shift+1` | — | miniaturi generate lenes | lista de miniaturi | — | D |
| B-021 | `Bookmarks` | `Alt+Shift+2`; `View > Bookmarks` | — | arbore cu niveluri | semne de carte navigabile | document fara semne de carte → empty state | D |
| B-022 | `Search` | `Alt+Shift+3`; `View > Search` | — | — | panoul de cautare | — | D |
| B-023 | `Attachments` | `Alt+Shift+4`; `View > Attachments` | — | — | lista de atasamente | — | D |
| B-024 | `Digital Signatures` | `Alt+Shift+5` | — | validare la deschidere | lista de semnaturi cu stare | — | D |
| B-025 | `Comments` | `F7`; `View > Show Comments Pane` | — | — | lista de comentarii | — | D |
| B-026 | **Barele nu se ascund separat** | — | — | **bara de meniu, bara principala si bara de jos nu se pot ascunde individual; pentru asta se foloseste ecranul complet** | — | — | D |
| B-027 | Redimensionarea panourilor | tragerea marginii | — | latime intre 150 si 600 px | latimea se memoreaza | — | N |
| B-028 | Recunoasterea in fundal | automat la deschidere | document fara strat de text bun | **activa implicit; porneste automat la deschiderea unui PDF** | **strat de text temporar, cautabil si copiabil** | esec → cautarea rămâne pe textul existent, fara mesaj intruziv | D |
| B-029 | **Stratul temporar nu se pastreaza** | automat | — | **stratul de text din recunoasterea in fundal nu rămâne cand documentul e deschis in alta aplicatie** | — | — | D |
| B-030 | **Limitarea pe un singur nucleu** | automat | — | **recunoasterea in fundal nu poate rula pe procesoare cu un singur nucleu** | functia se dezactiveaza | — | D |
| B-031 | Depanarea recunoasterii in fundal | — | — | **cand cautarea sau copierea nu merge, prima verificare e setul de limbi OCR** | mesaj care sugereaza verificarea limbilor | — | D |
| B-032 | Salvarea permanenta a stratului de text | butonul din tabul `Document` > `Recognize Document...` | limbi, corectie de orientare, deskew | confirmare: fisierul se modifica | strat de text permanent | — | D |
| B-033 | Dezactivarea recunoasterii in fundal | `Options > Image Processing` | bifa | — | — | — | D |
| B-034 | **Confirmare inainte de deschiderea unui atasament** | automat | — | **se cere `Allow` sau `Cancel`** | — | — | D |
| B-035 | **Confirmare inainte de deschiderea unui link** | automat | — | idem | — | — | D |
| B-036 | **Confirmare inainte de trimiterea datelor unui formular** | automat | — | idem | — | — | D |
| B-037 | Banda de notificare pentru JavaScript | automat | — | **apare in partea de sus a ferestrei cand PDF-ul conține JavaScript** | — | — | D |
| B-038 | `Enable JavaScript for This Document Only` | banda de notificare | — | — | scriptul ruleaza doar pentru documentul curent | — | D |
| B-039 | `Enable JavaScript for All Documents` | banda de notificare | — | **deschide dialogul Options** | — | — | D |
| B-040 | JavaScript dezactivat implicit | `Options > Other > Enable JavaScript in PDF documents` | bifa | **dezactivat** | — | — | D |
| B-041 | Limita de timp pentru un script | automat | — | un script care depaseste 2 secunde se opreste si se noteaza | — | — | N |
| B-042 | Detectia automata a linkurilor | `Options > Other` | bifa | activ | URL si e-mail devin clicabile | — | D |
| B-043 | Tab-uri de documente | bara de sus | — | **originalul deschide ferestre separate** | mai multe documente in aceeasi fereastra | — | N |
| B-044 | Mod intunecat | `Options > Other` | — | **nu exista in original** | toata interfata comuta | — | N |

---

## C. PDF EDITOR — cautare, inlocuire, redactare, copiere

### C.1 Cautare

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| C-001 | Deschiderea panoului | tabul `Search` din bara verticala; `View > Search`; `Ctrl+F` | — | — | panou cu tab-urile `FIND`, `REPLACE`, `REDACT` | — | D |
| C-002 | Campul `Find what` | tab FIND | sir | minimum 1 caracter | **rezultatele se grupeaza pe sursa: text, comentarii, semne de carte**; aparitiile se evidentiaza in pagina | — | D |
| C-003 | `Exact Match` | sageata de lângă iconul de cautare | bifa | **numai cuvinte intregi** | filtreaza rezultatele | — | D |
| C-004 | `Match Case` | idem | bifa | respecta majusculele | filtreaza rezultatele | — | D |
| C-005 | Navigare intre rezultate | butoane; `F3` | — | — | rezultatul curent evidentiat; pagina sare | — | D |
| C-006 | Contorul de rezultate | bara de stare a panoului | — | — | numarul de rezultate sau mesaj de lipsa | — | V |
| C-007 | Marcarea rezultatelor cu `Highlight` | tab FIND | culoare | **se creeaza comentarii; textul PDF-ului nu se schimba** | adnotari de evidentiere | — | D |
| C-008 | Marcarea cu `Strikethrough` | idem | culoare | idem | adnotari de taiere | — | D |
| C-009 | Marcarea cu `Underline` | idem | culoare | idem | adnotari de subliniere | — | D |
| C-010 | Culoarea unui marcaj | sageata de lângă fiecare unealta | paleta | **implicit se folosesc culorile din bara `PDF Tools`** | — | — | D |
| C-011 | Selectia rezultatelor | rand / `Ctrl`+clic | — | mai multe deodata | selectia se foloseste la marcare, inlocuire si redactare | — | D |

### C.2 Inlocuire

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| C-015 | Tabul `REPLACE` | panoul de cautare | text cautat, `Replace with` | textul nou poate fi gol | se inlocuiesc rezultatele selectate | — | D |
| C-016 | **Rezultatul inlocuit dispare din lista** | automat | — | **un rezultat inlocuit se scoate din lista de rezultate** | — | — | D |
| C-017 | Salvarea dupa inlocuire | automat | — | **modificarile trebuie salvate explicit** | — | — | D |
| C-018 | Inlocuire in PDF scanat | tab REPLACE | idem | se foloseste stratul OCR; **PDF-ul imagine rămâne imagine** | textul vechi se acopera cu fundalul detectat, textul nou se deseneaza | fundal neuniform → avertisment inainte | V |

### C.3 Redactare dupa text

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| C-025 | Tabul `REDACT` | panoul de cautare | text sau lista de cuvinte | — | rezultatele marcate se pot redacta | — | D |
| C-026 | `Redact` | buton | selectie | **textul se sterge si zona se acopera** | — | — | D |
| C-027 | `Add Keyword to List` | combo al iconului | cuvant | adauga textul curent in lista | — | — | D |
| C-028 | `Find Using Keyword List` | combo al iconului | lista | caută cu o lista salvata | — | — | D |
| C-029 | `Edit Keyword List...` | combo al iconului | — | adauga, editeaza, sterge si salveaza cuvinte | — | — | D |
| C-030 | `Save and Find` | dialogul listei | — | salveaza modificarile si ruleaza cautarea | — | — | D |
| C-031 | Afisarea cuvintelor unei liste | hover pe numele listei | — | — | cuvintele apar in tooltip | — | D |
| C-032 | Inchiderea unei liste | iconul de lângă numele listei; debifarea `Find Using Keyword List` | — | — | — | — | D |

### C.4 Copierea continutului din PDF

**Modul care lipsea complet din versiunea 1 a specificatiei.**

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| C-040 | Marcarea unei zone de copiat | tragere peste pagina | dreptunghi | **zona trebuie sa rămână in interiorul unei singure pagini** | zona marcata, cu un mic toolbar lângă ea | zona care traverseaza pagini → nu se creeaza | D |
| C-041 | Accesul la opțiunile de copiere | iconul de lângă zona marcata; clic dreapta | — | — | meniu cu cele trei moduri | — | D |
| C-042 | `Copy as Image` | `Ctrl+C`; meniu contextual | zona | — | imaginea zonei in clipboard | — | D |
| C-043 | `Copy as Text` | `Ctrl+Shift+C`; meniu contextual | zona | — | textul zonei in clipboard | — | D |
| C-044 | `Copy Text` — a doua metoda | selectie directa de text, apoi `Ctrl+C` sau meniu contextual | selectie de text | **aceasta metoda poate traversa mai multe pagini**; cere strat de text, pe care recunoasterea in fundal il poate furniza | textul in clipboard | mouse-ul nu marcheaza text → se verifica recunoasterea in fundal | D |
| C-045 | `Copy as Table` | `Ctrl+Alt+C`; meniu contextual | zona | — | tabelul in clipboard, ca celule | — | D |
| C-046 | Editarea structurii tabelului inainte de copiere | toolbarul zonei | separatoare, celule | **se pot adauga separatoare verticale si orizontale, se pot sterge separatoare, se pot uni si separa celule** | structura modificata | — | D |
| C-047 | Copierea tabelului editat | iconul de tabel, din nou | — | **fisierul original nu se modifica** | tabelul editat in clipboard | — | D |
| C-048 | Editarea tabelului in fisierul sursa | — | — | **pentru asta se foloseste OCR Editor, nu PDF Editor** | — | — | D |
| C-049 | Depanare la diferente de continut | — | — | **cand datele copiate difera mult de imagine, se verifica limbile OCR sau se inlocuieste un strat de text slab, apoi se reia** | mesaj cu sugestia | — | D |

---

## D. PDF EDITOR — comentarii, marcaje, stampile

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| D-001 | `Note` | tabul `Document`; `Ctrl+M` | pozitie, culoare, text | textul poate fi gol | adnotare de nota, cu icon pe pagina | — | D |
| D-002 | Culoarea notei | bara de culori de deasupra documentului; meniu contextual | culoare | — | — | — | D |
| D-003 | **Marcajele cer strat de text** | automat | — | **marcarea textului functioneaza numai in documentele care au strat de text sau care au fost recunoscute in fundal** | — | fara strat de text → se pregateste textul, apoi se reia | D |
| D-004 | `Highlight` | `Ctrl+H` | selectie de text, culoare | vezi D-003 | adnotare de evidentiere | — | D |
| D-005 | `Underline` | `Ctrl+Shift+U` | idem | idem | adnotare de subliniere | — | D |
| D-006 | `Strikethrough` | `Ctrl+K` | idem | idem | adnotare de taiere | — | D |
| D-007 | `Insert Text` | `Ctrl+J` | punct de inserare, text | — | adnotare cu caret si text | — | D |
| D-008 | Adaugarea unui comentariu pe o adnotare | **dublu clic pe adnotare** | text | — | caseta de comentariu | — | D |
| D-009 | Forma `Ink` | combo de desenare din tabul `Document` | traseu liber | **uneltele de desenare trebuie dezactivate inainte de a tasta un comentariu. Pentru un comentariu pe un set de trasee, se tine `Shift` in timpul desenarii si se elibereaza abia la final** | adnotare de desen | — | D |
| D-010 | Forma `Line` | idem | doua puncte | **`Shift` fixeaza la vertical, orizontal sau 45 de grade** | — | — | D |
| D-011 | Forma `Arrow` | idem | doua puncte | idem | — | — | D |
| D-012 | Forma `Rectangle` | idem | doua colturi | **`Shift` face patrat** | — | — | D |
| D-013 | Forma `Oval` | idem | dreptunghi incadrator | **`Shift` face cerc** | — | — | D |
| D-014 | Forma `Polygon` | idem | puncte | **se inchide cu clic pe primul varf** | — | — | D |
| D-015 | Forma `Cloud` | idem | puncte | idem | contur ondulat | — | D |
| D-016 | Forma `Polyline` | idem | puncte | **se termina cu dublu clic** | — | — | D |
| D-017 | Forma `Text Box` | idem | dreptunghi, text | — | caseta cu text | — | D |
| D-018 | Setarile de desenare | meniu contextual al formei; bara `PDF Tools` **inainte de desenare** | culoare, grosime, fundal, transparenta | — | se aplica formei sau devin implicite | — | D |
| D-019 | Adnotarea `Text block` | combo din tabul `Document` | dreptunghi, text | **apare o bara de editare de text sub bara `PDF Tools`** | adnotare de tip bloc de text | — | D |
| D-020 | Opțiunile blocului de text | bara de editare | font, dimensiune, culoare de text; culoare si grosime de chenar; culoare de fundal; **`Detect background color`** | **fundalul e transparent implicit** | — | — | D |
| D-021 | **Blocul de text e adnotare, nu text de corp** | automat | — | — | — | — | D |
| D-022 | **Completarea formularelor fara campuri interactive** | unealta `Export` | text | **un formular fara campuri interactive se completeaza scriind peste el cu unealta `Export`** | text asezat peste formular | — | D |
| D-023 | Blocul de text creeaza un comentariu | automat | — | adaugarea unui bloc de text produce o intrare in panoul `Comments` | — | — | D |
| D-024 | Panoul `Comments` | butonul din toolbar; meniu contextual `Show Comments Pane`; `View`; `F7` | — | **arata toate adnotarile, comentariile, blocurile de text, stampilele si marcajele** | lista | — | D |
| D-025 | `Add Comment` | meniu contextual | text | — | — | — | D |
| D-026 | `Reply` | buton; `Ctrl+Enter` | text | — | raspuns imbricat, cu autor si data | — | D |
| D-027 | `Delete Reply` | meniu contextual al raspunsului | — | — | — | — | D |
| D-028 | Stergerea unei adnotari | `Del`; meniu contextual | selectie | **stergerea adnotarii sterge si comentariul ei; stergerea comentariului din panou sterge si raspunsurile** | — | — | D |
| D-029 | `Delete Comments and Markup...` | meniul `Document` | — | confirmare, cu numarul de adnotari | toate adnotarile dispar | — | D |
| D-030 | Bifa pe comentariu | caseta de pe rand; `Add Checkmark` | — | bifa e personala, nu se exporta ca status | — | — | D |
| D-031 | Status pe comentariu | submeniul `Status` din meniul contextual; butonul de status din caseta | `Accepted` / `Rejected` / `Cancelled` / `Completed` | — | statusul apare pe comentariu | — | D |
| D-032 | Proprietatile comentariului | meniu contextual `Properties...` | autor, subiect | **dialogul arata si istoricul statusurilor**; butonul `Set Default` memoreaza autorul pentru comentariile viitoare | — | — | D |
| D-033 | Butoane de navigare in panou | panoul `Comments` | — | — | se trece la comentariul urmator sau anterior | — | D |
| D-034 | Caseta de cautare in panou | panoul `Comments` | text | **caută in comentarii, in raspunsuri si in autori** | lista filtrata | — | D |
| D-035 | Sortarea | meniu de sortare | — | — | lista reordonata | — | D |
| D-036 | `Show All Comments` / `Hide Current Comments` | meniul de filtrare | — | — | — | — | D |
| D-037 | Filtrare dupa `Type` | meniul de filtrare | tipuri | — | — | — | D |
| D-038 | Filtrare dupa `Author` | idem | autori | — | — | — | D |
| D-039 | Filtrare dupa `Page` | idem | interval | — | — | — | D |
| D-040 | Filtrare dupa `Date` | idem | interval | — | — | — | D |
| D-041 | Filtrare dupa `Flag Status` | idem | bifat / nebifat | — | — | — | D |
| D-042 | Filtrare dupa `Status` | idem | cele patru statusuri | — | — | — | D |
| D-043 | `Reset` filtre | meniul de filtrare | — | — | toate filtrele se golesc | — | D |
| D-044 | Ascunderea textului comentariilor | comutator in panou | — | **rămân vizibili numai autorii si datele** | lista compactata | — | D |
| D-045 | Stampila predefinita | meniul `Stamp` din tabul `Document`; `Other stamp` pentru lista completa | una din setul livrat | — | stampila plasata pe pagina | — | D |
| D-046 | Stampilele primesc comentarii si statusuri | automat | — | **ca orice adnotare** | — | — | D |
| D-047 | `Create Stamp from Image...` | meniul `Stamp` | **`Name`; `Open` sau `Paste from Clipboard`; slider de dimensiune; `Save`** | — | stampila salvata in biblioteca | — | D |
| D-048 | `Create Text Stamp...` | meniul `Stamp` | **`Name`; `Stamp text`; combo `Add Date/Time`; grupul de font si chenar; `Add border`; previzualizare; `Save`** | **elementele se insereaza la pozitia cursorului din campul de text** | stampila salvata | — | D |
| D-049 | Etichetele de data si ora in stampile | campul `Stamp text` | `<d/>`, `<date/>`, `<t12/>`, `<t24/>`, `<time/>`, coduri de regiune, formate proprii | **vezi SPEC_03 secțiunea Z.1 pentru lista completa** | — | — | D |
| D-050 | `Manage Stamps...` | meniul `Stamp` | — | `Edit...` si `Use`; stergerea din lista cu `Delete...` | — | — | D |
| D-051 | Stergerea unei stampile din document | `Del`; meniu contextual `Delete...`; stergerea comentariului din panou | — | — | — | — | D |
| D-052 | Mutarea si redimensionarea stampilei | pe pagina | — | — | — | — | D |
| D-053 | Trimiterea documentului pe e-mail | butonul din tabul `Document`; `File > E-mail...` | nume, pagini | clientul de e-mail implicit; butonul `Create E-mail Message` | mesaj nou cu PDF-ul atasat | fara client → mesaj si opțiune de salvare locala | D |

---

## E. PDF EDITOR — Organize Pages

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| E-001 | Intrarea in modul Organize Pages | tab de ribbon | — | — | grila de miniaturi mari | — | D |
| E-002 | Selectia unei pagini | clic | — | — | pagina marcata | — | D |
| E-003 | Selectie multipla | `Ctrl`+clic, `Shift`+clic | — | — | — | — | D |
| E-004 | Selectie prin interval tastat | campul de selectie | **un numar, un interval de forma `2,3,5-7`, sau `Even Pages`, `Odd Pages`, `All Pages`** | spatiile se accepta; intervalele inversate se normalizeaza | selectia se aplica | numere in afara documentului → ignorate, cu avertisment | D |
| E-005 | Stergerea paginilor | `Del`; `Ctrl+Backspace`; buton; meniu contextual | selectie | nu se pot sterge toate paginile | paginile dispar; renumerotare | ultima pagina → mesaj | D |
| E-006 | `Rotate Right` | `Ctrl+Shift+>` | selectie | multiplu de 90 de grade | rotatia se scrie in pagina | — | D |
| E-007 | `Rotate Left` | `Ctrl+Shift+<` | selectie | idem | — | — | D |
| E-008 | `Correct Page Orientation` | `Ctrl+Shift+/` | selectie | detectie automata pe baza textului | paginile se rotesc corect | pagina fara text → se lasa neschimbata | D |
| E-009 | Mini-toolbar la hover | hover pe miniatura | — | — | sterge, roteste stanga, roteste dreapta | — | V |
| E-010 | `Crop Pages` | `Ctrl+Shift+X`; `Organize Pages > Crop Pages` | dreptunghi | **doua opțiuni: un cadru separat per pagina, sau un singur cadru pentru toate paginile selectate** | previzualizare live | — | D |
| E-011 | `Apply Crop` | buton; `Enter` | — | — | decuparea se aplica | — | D |
| E-012 | `Exit Crop` | buton; `Esc` | — | — | se iese fara modificari | — | D |
| E-013 | `Add Blank Page` | `Ctrl+Shift+B` | **se asaza cursorul intre pagini, apare butonul, se alege `Add Blank Page`, se alege dimensiunea paginii, se apasa `Add`** | — | pagina goala inserata | — | D |
| E-014 | `Add Pages from PDF...` | `Ctrl+Shift+P` | fisier, numere de pagini opționale, `Open` | **fisierele se adauga fara procesare de imagine** | paginile se insereaza | PDF protejat → se cere parola | D |
| E-015 | `Add Pages from File...` | `Ctrl+Shift+O` | fisier, pozitie, bifa `Split facing pages`, `Image Processing Settings`, `Add` | **mai lent decat adaugarea dintr-un PDF, pentru ca se face procesare de imagine** | paginile se insereaza | — | D |
| E-016 | Pozitia de inserare | dialog | **inainte de prima pagina / dupa ultima pagina / dupa pagina selectata** | — | — | — | D |
| E-017 | `Add Pages from Scanner...` | `Ctrl+Shift+K` | dispozitiv, parametri, pozitie, `Preview`, `Settings...`, `Scan` | — | paginile scanate se insereaza | — | D |
| E-018 | Reordonare prin tragere | drag and drop | — | indicator de inserare | ordinea se schimba | — | D |
| E-019 | `Move Pages` | `Ctrl+Shift+M` | selectie, pozitie: inainte de prima / dupa ultima / dupa o pagina specificata | — | — | — | D |
| E-020 | `Replace Pages...` | `Ctrl+Shift+E` | fisier sursa, interval sursa, interval tinta | intervalele trebuie sa aiba acelasi numar de pagini | paginile se inlocuiesc | lungimi diferite → mesaj explicit | D |
| E-021 | `Delete Blank Pages` | `Organize Pages`; `Ctrl+Alt+Backspace` | prag de continut | **se previzualizeaza cu `+` si `-`** | lista paginilor gasite | nicio pagina goala → mesaj | D |
| E-022 | Avertisment inainte de stergerea paginilor goale | automat | — | **se verifica intai dacă paginile conțin note de mana sau imagini** | — | — | D |
| E-023 | `Delete selected pages` | dialogul de pagini goale | bife | implicit toate bifate | se sterg doar bifatele | — | D |
| E-024 | `Split Document...` | `Organize Pages`; buton | metoda | **trei metode: `By file size`, `By page count`, `By bookmarks (first level only)`** | mai multe fisiere | — | D |
| E-025 | Split `By file size` | dialog | dimensiune maxima | **trebuie sa fie mai mica decat dimensiunea originalului. Rezultatul poate totusi depasi limita, in functie de continut: imagini, fonturi, formulare** | — | dimensiune prea mare → camp rosu | D |
| E-026 | Split `By page count` | dialog | numar maxim de pagini per document | — | — | — | D |
| E-027 | Split `By bookmarks` | dialog | — | **numai primul nivel; un document per semn de carte de nivel 1** | — | fara semne de carte → opțiunea e gri | D |
| E-028 | Numele fisierelor la split | dialog | **numerotare inainte sau dupa nume, cu numarul de cifre ales**; numele sursei e valoarea implicita | — | — | D |
| E-029 | Numele la split dupa semne de carte | dialog | **`Same as bookmark name` (cu `Add numeration` bifat implicit) sau `Use Custom name`** | debifarea `Add numeration` scoate numerotarea | — | D |
| E-030 | Folderul de ieșire la split | dialog | folderul sursei sau altul | folderul trebuie sa fie scriibil | — | fara drepturi → mesaj | D |
| E-031 | **Ce se pierde la split** | automat | — | **semnele de carte NU se pastreaza. Atasamentele merg intr-un folder numit `Attachments`** | — | — | D |
| E-032 | Dupa split | automat | — | **folderul de ieșire se deschide intr-o fereastra noua** | — | — | D |
| E-033 | `Recognize Selected Pages` | sageata de lângă butonul `Recognize`; `Recognize > Recognize Selected Pages` | selectie, limbi | — | strat de text pe paginile alese | — | D |
| E-034 | `Send Selected Pages to OCR Editor` | sageata; meniu contextual in panoul `Pages` | selectie | — | OCR Editor cu paginile alese | — | D |
| E-035 | `Enhance Images...` | `Organize Pages` | selectie, opțiuni | **dialogul are: `Correct page orientation`; `Deskew images and correct image resolution` (poate dura); `Apply ABBYY PreciseScan`**. Se aleg limbile OCR corecte | imaginile paginilor se imbunatatesc | — | D |
| E-036 | `Create PDF from Selected Pages` | meniu contextual din panoul `Pages` sau din tabul `Organize Pages` | selectie | — | **document nou, deschis intr-o fereastra noua de PDF Editor** | — | D |
| E-037 | `Save As` din Organize Pages | sageata din tab; meniu contextual in panoul `Pages` | selectie, format | — | doar paginile selectate | — | D |
| E-038 | `Image Processing Settings...` | sageata de lângă butonul relevant | `Image quality` (4 valori); bife `Recognize text on images`, `Use MRC compression` (cere limbi OCR), `Apply ABBYY PreciseScan` | — | — | — | D |
| E-039 | Slider de zoom pentru miniaturi | colt dreapta jos | — | — | grila se rearanjeaza | — | V |
| E-040 | Anularea operatiilor pe pagini | `Ctrl+Z` | — | istoric de minimum 50 de pasi | starea anterioara | — | N |

---

## F. PDF EDITOR — Edit Content

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| F-001 | Intrarea in modul de editare | tab `Edit Content`; `Ctrl+E` | — | **se iese comutand pe alt tab** | blocurile capata contur si manere | — | D |
| F-002 | **Ce documente se pot edita** | automat | — | **PDF-uri produse de alte aplicatii, documente scanate si PDF-uri cautabile. NU se pot edita PDF-urile al caror text e grafica vectoriala** | — | text vectorial → editarea nu e disponibila | D |
| F-003 | Indicatorul de pregatire a paginii | automat | — | apare cat timp pagina se pregateste | — | pagina care nu se poate pregati → mesaj, se rămâne in vizualizare | D |
| F-004 | Importanta limbilor | automat | — | **pentru scanari si PDF-uri cautabile, setul de limbi conteaza, mai ales cand recunoasterea in fundal e dezactivata** | — | — | D |
| F-005 | **Fontul in paranteze patrate** | automat | — | **un nume de font afisat in paranteze patrate inseamna font incorporat in PDF, dar neinstalat in sistem. Trebuie instalat inainte de a scrie cu el, altfel se foloseste un font implicit** | numele fontului se afiseaza in paranteze patrate | — | D |
| F-006 | Inlocuirea fontului la editare | automat | — | se alege cel mai apropiat font instalat, dupa metrici; alegerea se noteaza in jurnal | textul nou foloseste fontul potrivit | niciun font apropiat → font implicit, notat | V |
| F-007 | Uneltele de editare de text | `Ctrl+T` | — | — | bara de unelte de text | — | D |
| F-008 | Editarea textului | clic in text | caractere | textul face reflow in limitele blocului | textul se schimba | — | D |
| F-009 | Terminarea editarii unui bloc | clic in afara; `Esc` | — | — | modificarile raman | — | D |
| F-010 | Salvarea | `Ctrl+S` | — | — | — | — | D |
| F-011 | **Limita de dimensiune a unui bloc nou** | automat | — | **un bloc de text nou nu poate fi mai mare decat pagina. Textul nu trebuie sa treaca peste marginile paginii** | — | bloc prea mare → se refuza | D |
| F-012 | Stergerea unui bloc intreg | **`Ctrl`+clic pe bloc (sau selectie prin margine), apoi `Delete`** | — | — | blocul dispare; fundalul se completeaza | — | D |
| F-013 | Redimensionarea unui bloc | tragerea unui maner patrat | — | — | textul face reflow | — | D |
| F-014 | Mutarea unui bloc | `Ctrl`+tragere; tragerea marginii | — | ghidaje de aliniere | pozitia se schimba | — | D |
| F-015 | Fontul, dimensiunea, stilul | bara de unelte de text | font, dimensiune, bold, italic, underline | dimensiunea intre 1 si 1638 pt | se aplica selectiei | — | V |
| F-016 | Alinierea, spatierea, culoarea | bara de unelte de text | — | — | se aplica paragrafului | — | V |
| F-017 | `Correct Skew and Page Orientation` | buton in tabul `Edit Content` | pagina curenta sau tot documentul | **butonul apare numai pe paginile pe care s-a detectat inclinare** | pagina se indreapta | — | D |
| F-018 | `Text Layer > Recognize Page and Replace Existing Text Layer...` | buton in tabul `Edit Content` | — | **deschide dialogul `Recognize Document`, cu `Correct page orientation`, `Deskew images and correct image resolution` si butonul `Recognize`** | strat de text nou; cel vechi se pierde | — | D |
| F-019 | Editarea celulelor de tabel | clic intr-o celula detectata | text | structura tabelului rămâne | continutul celulei se schimba | — | V |
| F-020 | `Add Picture...` | bara `Edit Content`; `Edit Content > Add Picture...` | fisier imagine, `Open`, apoi plasare | — | imaginea se insereaza | — | D |
| F-021 | Mutarea, rotirea, redimensionarea imaginii | manerele | — | — | — | — | D |
| F-022 | `Bring Picture to Front` | meniu contextual | — | **pentru imagini suprapuse** | ordinea de desenare se schimba | — | D |
| F-023 | Stergerea unei imagini | meniu contextual `Delete` | — | **pentru PDF-uri produse de alte aplicatii** | — | — | D |
| F-024 | Unealta `Erase` | tabul `Security` | zona | **sterge continutul si completeaza fundalul automat**; continutul dispare si din stratul de text | — | — | D |
| F-025 | `Erase Text and Pictures` | `Ctrl+R` | zona | idem | — | — | D |
| F-026 | `Add Link...` | `Ctrl+L`; `Edit > Add Link...`; meniu contextual | zona, tinta | **dialogul `Link Editor` are doua tipuri: o pagina din documentul curent (cu `Select specific destination...`), sau alta resursa (adresa web, e-mail, fisier)** | link creat | — | D |
| F-027 | **Prefixele obligatorii pentru linkuri** | dialogul `Link Editor` | — | **adresa de e-mail cere prefixul `mailto:`; fisierul cere prefixul `file://`** | — | fara prefix → camp invalid | D |
| F-028 | `Edit Link...` | meniu contextual | — | — | se redeschide dialogul | — | D |
| F-029 | `Copy Link` | meniu contextual | — | — | adresa in clipboard | — | D |
| F-030 | `Remove Link` | meniu contextual | — | — | — | — | D |
| F-031 | Semne de carte — panoul | `View > Bookmarks`; butonul din bara verticala | — | — | arbore de semne de carte | — | D |
| F-032 | `Add Bookmark...` | `Document > Add Bookmark...`; `Ctrl+D` | nume | **un semn de carte nou trimite implicit la inceputul paginii curente** | semn de carte nou | — | D |
| F-033 | `Add Bookmark...` pe o selectie | meniu contextual pe text selectat | — | **tinta e selectia, iar textul selectat devine numele** | — | — | D |
| F-034 | `Set Destination` | meniu contextual | — | schimba tinta | — | — | D |
| F-035 | **Regula de imbricare** | automat | — | **imbricarea urmeaza semnul de carte selectat anterior. Primul semn de carte ajunge la nivelul radacina** | — | — | D |
| F-036 | Reordonarea semnelor de carte | tragere; `Move one level left` / `right` | — | **nu schimba aspectul documentului** | — | — | D |
| F-037 | Redenumirea | butonul din panou; meniu contextual | nume | nu poate fi gol | — | — | D |
| F-038 | Stergerea | butonul din panou; meniu contextual | selectie, `Ctrl` pentru mai multe | **stergerea unui parinte sterge si copiii** | — | — | D |
| F-039 | `Create Header and Footer...` | combo din bara `Edit Content` | pozitie, distanta de margine, unitati | **una din sase pozitii pe pagina, cu distanta exacta de margine si combo de unitati de masura** | antet sau subsol | — | D |
| F-040 | Elementele care se insereaza | dialog | **butoanele `Page Number`, `Bates Number` (cu `Start at` si opțiunea `Continue from`), `Date/Time`** | elementele se insereaza la pozitia cursorului din campul de text | — | — | D |
| F-041 | Fontul antetului | dialog, secțiunea `Font` | font, dimensiune, efecte, culoare | — | — | — | D |
| F-042 | Paginile pe care se aplica | dialog, secțiunea `Pages`, combo `Apply to` | **`All` / `Page range` / `Odd Pages` / `Even Pages`** | — | — | — | D |
| F-043 | `Save and Add` | dialog | nume | nume unic | sablonul se salveaza pentru refolosire | nume duplicat → se cere altul | D |
| F-044 | `Manage Headers and Footers...` | combo din bara | — | **`Copy...`, `Edit...`, `Save`, `Delete`** | — | — | D |
| F-045 | `Add Watermark...` | tabul `Security` | text, font, pozitie, offset | **noua pozitii, ajustabile prin offset** | filigran pe paginile alese | — | D |
| F-046 | Rotirea si transparenta | dialog | camp `Rotate` cu slider; camp `Transparency` cu slider | — | — | — | D |
| F-047 | Plasarea filigranului | dialog | **`Above page content` / `In the background beneath page content`** | — | — | — | D |
| F-048 | Paginile filigranului | dialog | **`All` / `Selected` / `Page range`** | — | — | — | D |
| F-049 | `Save and Add` filigran | dialog | — | **se pot adauga mai multe filigrane** | — | — | D |
| F-050 | `Delete Watermarks` | tabul `Security` | — | **sterge TOATE filigranele, nu doar cele adaugate de aplicatie** | — | — | D |
| F-051 | Atasamente — panoul | `View > Attachments`; butonul din bara verticala | — | — | lista de atasamente | — | D |
| F-052 | Operatii pe atasamente | toolbarul panoului; meniu contextual | — | **deschide, salveaza, redenumeste, sterge** | — | — | D |
| F-053 | Avertisment la atasamente executabile | automat | — | — | mesaj inainte de deschidere | — | N |
| F-054 | `Document Properties...` | `File > Document Properties...` | — | **editabile, dacă documentul nu e protejat prin parola: `Title`, `Author`, `Subject`, `Keywords`** | metadatele se scriu | fisier protejat → campurile sunt gri | D |
| F-055 | Proprietatile doar in citire | acelasi dialog | — | **`File name`, `Location`, `File size`, `Page size`, `Pages`, `PDF producer`, `Application`, `PDF version`, conformitate PDF/A sau PDF/UA, `Tagged PDF`, `Fast Web View`, `Created`, `Modified`** | — | — | D |
| F-056 | Pastrarea metadatelor la conversie | automat | — | **metadatele se pastreaza la conversie, dacă nu sunt sterse explicit sau suprascrise de opțiunile de export** | — | — | D |

---

## G. PDF EDITOR — securitate si semnaturi

### G.1 Parole si permisiuni

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| G-001 | Dialogul `Security Settings` | butonul din tabul `Security`; `Security > Password Security...` | — | — | dialogul de securitate | — | D |
| G-002 | `Restrict access with a Document Open password` | dialog | parola + confirmare | — | documentul se cripteaza | parolele nu coincid → mesaj | D |
| G-003 | `Hide characters` | dialog | bifa | **se poate dezactiva, ca sa se vada caracterele tastate** | — | — | D |
| G-004 | `Restrict printing and editing with a Permissions password` | dialog | parola + confirmare | **trebuie sa fie diferita de parola de deschidere** | restrictii active | identice → mesaj | D |
| G-005 | **Parola de permisiuni deschide si documentul** | automat | — | **parola de permisiuni poate fi folosita si pentru a deschide documentul protejat** | — | — | D |
| G-006 | Combo `Printing` | dialog | rezolutia de tiparire permisa | — | steag in PDF | — | D |
| G-007 | Combo `Editing` | dialog | operatiile de editare permise | — | steag in PDF | — | D |
| G-008 | `Allow copying text, images, and other content` | dialog | bifa | — | — | — | D |
| G-009 | `Allow screen readers to read text` | dialog | bifa | — | — | — | D |
| G-010 | Combo `Encrypt` | dialog | **`128-bit AES` / `256-bit AES`** | RC4 numai la citirea fisierelor vechi, niciodata la scriere | — | — | D |
| G-011 | Domeniul criptarii | dialog | **`All document contents` / `All document contents except metadata`** | — | — | — | D |
| G-012 | Confirmarea la `OK` | dialog | — | **se cer din nou ambele parole**, apoi se poate salva peste documentul deschis sau se creeaza unul nou | — | — | D |

### G.2 Redactare si curatare

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| G-020 | Unealta de redactare | tabul `Security` | zona, culoare | **sapte casete de culoare pe bara, o sageata pentru paleta si `More colors...` pentru restul** | textul si imaginile se sterg, iar aparitiile se acopera cu dreptunghiuri | — | D |
| G-021 | **Verificarea redactarii** | automat, dupa G-020 | — | se extrage textul si se verifica absenta | — | dacă textul mai apare, operatia se anuleaza si se raporteaza ca defect | N |
| G-022 | Stergerea datelor care nu sunt de corp | butonul din tabul `Security` | bife, apoi `Apply` | **comentarii, adnotari, semne de carte, atasamente, metadate** | obiectele alese dispar | — | D |
| G-023 | Lista din `Format Settings > PDF > Delete objects and data > Select...` | dialogul de setari de format | **patru elemente: `Comments and markup`; `Links, media, actions, scripts, and form data`; `Bookmarks`; `Attachments`** | obiectele selectate nu se salveaza | — | — | D |
| G-024 | Conversia in PDF imagine | — | — | **in original, stergerea textului si a obiectelor ascunse nu e listata ca opțiune a acestui dialog.** La noi: opțiune separata, cu avertisment explicit ca documentul devine PDF imagine | — | — | X |

### G.3 Semnaturi digitale

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| G-030 | `Add Digital Signature...` | tabul `Security` | zona sau clic pe o poziție | — | dialogul de semnare | — | D |
| G-031 | Combo `Sign as` | dialog | certificat | **certificatele care nu apar in lista trebuie instalate: Explorer > `Install Certificate`, prin `Certificate Import Wizard`** | — | fara certificat → mesaj cu instructiuni | D |
| G-032 | `Show Certificate...` | dialog | — | — | proprietatile certificatului | — | D |
| G-033 | Combo `Reason` | dialog | motiv predefinit sau text propriu | — | apare in semnatura | — | D |
| G-034 | Campurile `Location` si `Contact` | dialog | text | — | — | — | D |
| G-035 | Continutul afisat in semnatura | dialog | **bife pentru data si ora, informatia despre proprietar, numele si versiunea aplicatiei** | debifarea ascunde campul | aspectul semnaturii | — | D |
| G-036 | `Show labels` | dialog | bifa | **debifarea ascunde numele campurilor** | — | — | D |
| G-037 | `Set up Time Stamp Server` | dialog | **`Default` sau `Custom URL`, cu utilizator si parola dacă serverul le cere** | **credentialele se pastreaza in Windows Credential Manager** | marca temporala in semnatura | server inaccesibil → se intreaba dacă se semneaza fara | D |
| G-038 | `Borders and background` | dialog | bifa | — | — | — | D |
| G-039 | `Add custom image to digital signature` | dialog, `Select Image...` | fisier imagine | — | imaginea apare in dreptunghiul semnaturii | — | D |
| G-040 | `Save and sign` | dialog | — | **apoi documentul trebuie salvat** | semnatura aplicata | — | D |
| G-041 | Validarea automata | la deschidere | — | **semnaturile se valideaza automat si se listeaza in panoul `Digital Signatures`** | starea fiecarei semnaturi | certificat expirat → stare „valida, dar certificatul a expirat" | D |
| G-042 | `Show Signature Properties...` | dublu clic in panou; meniu contextual | — | — | detalii complete | — | D |
| G-043 | `Remove Signature` | meniu contextual | — | **cere certificatul potrivit** | semnatura dispare | fara certificat → mesaj | D |
| G-044 | Semnaturi multiple | automat | — | **se accepta mai multe semnaturi; semnaturile anterioare rămân valide cand se adauga una noua** | — | — | D |
| G-045 | Algoritmi de semnatura | setare | SHA-256, SHA-384, SHA-512 | MD5 numai la verificare | — | — | N |
| G-046 | Smartcard sau token | dialogul de certificat | PIN | **PIN-ul se cere de sistem, nu de aplicatie** | — | PIN greșit → mesaj de la driver | N |
| G-047 | LTV | automat | — | se incorporeaza lantul de certificate si raspunsurile OCSP sau CRL | semnatura verificabila pe termen lung | — | N |

### G.4 Semnaturi text si de imagine

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| G-050 | `Create Text Signature...` | tabul `Security`; `Other Signature > Create Text Signature...` | text, stil | se salveaza, apoi se plaseaza pe pagina | imagine de semnatura | — | D |
| G-051 | `Create Signature from Image...` | tabul `Security`; `Other Signature > Create Signature from Image...` | **`Open` pentru un fisier, sau `Paste from Clipboard`** | se poate redimensiona si face fundalul transparent, apoi `Save` | semnatura salvata | — | D |
| G-052 | Plasarea si transformarea | pe pagina | — | se poate redimensiona, roti si muta dupa plasare | — | — | D |
| G-053 | Numarul de semnaturi | automat | — | **un document poate conține oricate semnaturi** | — | — | D |
| G-054 | `Manage Signatures...` | `Other Signature` | — | **se selecteaza, `Edit...`, apoi `Save` si opțional `Use`** | — | — | D |
| G-055 | Stergerea unei semnaturi | `Delete`; meniu contextual `Delete...`; din lista prin `Manage Signatures` | — | **se pot sterge si semnaturile text si cele de imagine** | — | — | D |

---

## H. PDF EDITOR — formulare interactive

### H.1 Completarea formularelor

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| H-001 | Detectia formularului | automat la deschidere | — | **apare un mesaj cand se detecteaza un formular** | — | — | D |
| H-002 | `Highlight Fields` | mesajul de detectie; `Form Editor > Highlight Fields` | bifa | — | campurile capata fundal colorat | — | D |
| H-003 | `Load Form Data from File...` | meniul de date de formular | **FDF sau XFDF** | campurile trebuie sa corespunda | valorile se completeaza | campuri necunoscute → ignorate, cu raport | D |
| H-004 | `Save Form Data to File...` | idem | **FDF, XFDF sau HTML** | — | fisier cu valorile | — | D |
| H-005 | `Reset Form` | idem; meniu contextual | — | confirmare | **toate campurile se golesc**; elementul implicit al unei liste revine | — | D |
| H-006 | JavaScript pentru verificari de format | automat | — | **unele elemente, de exemplu verificarile de format al datelor, au nevoie de JavaScript, activat din `Options > Other > Enable JavaScript in PDF documents`** | — | JS dezactivat → verificarea nu ruleaza | D |
| H-007 | Completarea unui formular fara campuri | unealta `Export` | text | **cand nu se evidentiaza niciun camp, formularul se completeaza scriind peste el cu unealta `Export`** | — | — | D |

### H.2 Crearea si editarea campurilor

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| H-010 | Intrarea in `Form Editor` | tab de ribbon | — | **modul de editare a formularelor dezactiveaza uneltele principale de PDF** | campurile devin obiecte editabile | — | D |
| H-011 | `Show Field Names` | bifa din meniul contextual; `Form Editor > Show Field Names` | bifa | — | numele apare lângă fiecare camp | — | D |
| H-012 | Adaugarea unui camp | unealta din bara `Form Editor`, apoi clic sau tragere | pozitie sau dreptunghi | — | camp nou | — | D |
| H-013 | Adaugarea butoanelor radio | unealta `Radio Button` | clicuri succesive | **unealta adauga un buton la fiecare clic; `Esc` opreste adaugarea. Grupul e setul de butoane adaugate inainte de oprire. Se adauga minimum doua butoane per grup** | grup de butoane | un singur buton → avertisment | D |
| H-014 | Deschiderea proprietatilor | dublu clic; meniu contextual `Properties...` | — | — | dialogul de proprietati | — | D |
| H-015 | Copierea unui camp | `Ctrl+C` si `Ctrl+V`; meniu contextual | selectie | **copia pastreaza toate proprietatile, cu excepția numelui. Numai campurile de semnatura goale se pot copia** | camp nou | semnatura completata → mesaj | D |
| H-016 | `Create Linked Copy` | meniu contextual | — | **schimbarea numelui unei copii legate o transforma in copie independenta** | campuri legate | — | D |
| H-017 | Mutarea campurilor | tragere; `Ctrl`+clic pentru mai multe | — | **campurile se pot muta numai in interiorul paginii lor** | — | mutare in afara paginii → se refuza | D |
| H-018 | Ghidajele de aliniere | automat la mutare | — | **ghidaje mov; se tine `Ctrl` pentru a le ascunde** | — | — | D |
| H-019 | Coordonatele exacte | tabul `General` | `X`, `Y` | — | — | — | D |
| H-020 | Redimensionarea | tabul `General` sau manerele | `Width`, `Height` | **inaltimea nu poate fi 0** | — | — | D |
| H-021 | Stergerea campurilor | `Delete`; meniu contextual | selectie | — | — | — | D |
| H-022 | Campurile obligatorii | tabul `General` | bifa `Required` | **orice tip de camp, cu excepția butoanelor. Numele campurilor obligatorii se afiseaza cu rosu in modul de editare** | — | — | D |
| H-023 | **Comportamentul campului obligatoriu** | la completare | — | **`Required` NU blocheaza salvarea, trimiterea pe e-mail sau tiparirea cu campuri goale.** Doar avertizeaza | mesaj la trimitere | — | D |
| H-024 | Salvarea formularului | `File > Save As > PDF Document...` | — | **numai acest format pastreaza campurile. Alte formate, de exemplu Word, fac formularul needitabil** | PDF cu campuri | — | D |

### H.3 Proprietatile per tip de camp

| ID | Tip | Tab `General` | Tab `Appearance` | Alte tab-uri | Src |
|---|---|---|---|---|---|
| H-030 | `Text field` | `Field Name` (obligatoriu, unic; **nu poate incepe sau se termina cu punct, nici conține puncte consecutive**), `Tooltip`, `Max Number of Symbols` (opțional), `Required`, `Read-Only`, `Width`, `Height`, `X`, `Y`, `Units` (**centimetri, inci sau puncte**) | `Fill Color`, **`Stroke Color`**, `Thickness`, `Font Color`, `Font Name`, `Font Size`, `Set as Default Style` | **`Format`: combo cu `Text` (`Field Type`: `Single Line` sau `Multiline`) sau `Date` (caseta `View` fixeaza formatul final; utilizatorul poate tasta orice format, dar se reduce la formatul din `View` la completare)** | D |
| H-031 | `Drop-down list` | ca la `Text field`, **fara `Max Number of Symbols`** | la fel; **fonturile se aplica elementelor listei** | **`List Items`: `List Items`, `Add`, `Edit`, `Delete` (`Ctrl` pentru mai multe), `Set as Default`, **`Unset as Default`**, `Up`, `Down`, **`Allow non-list items`**. Elementul implicit revine cand toate campurile se golesc** | D |
| H-032 | `Check box` | `Field Name`, `Tooltip`, **`Enabled by Default`**, `Required`, `Read-Only`, dimensiuni | **`Checkmark Color`**, `Fill Color`, `Stroke Color`, `Thickness`, `Set as Default Style` | — | D |
| H-033 | `Radio button` | **`Radio Group Name`** (obligatoriu; nou sau ales dintre grupurile existente), **`Radio Group Tooltip`**, **`Radio Button Name`** (obligatoriu, unic), `Enabled by Default`, `Required`, `Read-Only`, dimensiuni | **`Dot Color`**, `Fill Color`, `Stroke Color`, `Thickness`, `Set as Default Style` | — | D |
| H-034 | `Button` | `Field Name`, `Tooltip`, **`Button Text`**, `Read-Only`, dimensiuni | `Fill Color`, `Stroke Color`, `Thickness`, `Font Color`, `Font Name`, `Font Size`, `Set as Default Style` | **`Actions`: lista de actiuni, `Create...`, `Edit...`, `Delete`** | D |
| H-035 | `Signature field` | `Field Name`, `Tooltip`, **`Required` inseamna ca semnatarul trebuie sa semneze**, `Read-Only`, dimensiuni | `Fill Color`, `Stroke Color`, `Thickness`, `Set as Default Style` | — | D |
| H-036 | `List box` | ca la `Drop-down list` | ca la `Drop-down list` | **`List Items`: aceleasi controale, plus `Allow multiple selection`** | D |

### H.4 Actiuni

| ID | Functie | Valori | Reguli si validari | Src |
|---|---|---|---|---|
| H-040 | Evenimentele declansatoare | **`Click`, `Drop`, `Mouse Over`, `Mouse Out`, `Focus`, `Focus Out`** | exact aceste sase | D |
| H-041 | Crearea unei actiuni | dialog cu `Trigger Event` si `Action`, apoi `Save` | — | D |
| H-042 | Modificarea unei actiuni | se schimba `Trigger Event` si `Action`, apoi `Save` si `OK` | — | D |
| H-043 | Actiuni de navigare | prima pagina, ultima pagina, pagina urmatoare, pagina anterioara, inapoi, inainte, **selecteaza o pagina** | D |
| H-044 | `Go to page` | caseta `Page Number` | in interval | D |
| H-045 | Actiuni de vizualizare | o pagina, doua pagini, derulare pe o pagina, derulare pe doua pagini, **zoom la 100%**, **potrivire pe latime**, **potrivire pe pagina**, ecran complet | D |
| H-046 | Actiuni de panouri | arata sau ascunde `Attachments`, `Bookmarks`, `Pages`, `Digital Signatures` | D |
| H-047 | `Open file` | caseta `File` | — | D |
| H-048 | `Follow link` | caseta `Link` | — | D |
| H-049 | `Send form` | caseta `Send to`; `File Format`: **PDF, FDF, XFDF sau HTML** | adresa valida | D |
| H-050 | `Reset form` | — | — | D |
| H-051 | `Save form as` | — | — | D |
| H-052 | `Print form` | — | — | D |
| H-053 | `Close document` | — | — | D |
| H-054 | `Exit application` | — | — | D |
| H-055 | `Search document` | — | — | D |
| H-056 | `Document properties` | — | — | D |
| H-057 | `Add pages from scanner` | — | — | D |
| H-058 | `Run JavaScript` | caseta `JavaScript` | **ruleaza numai dacă JavaScript e activat** | D |

---

## I. PDF EDITOR — salvare, export, tiparire

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| I-001 | `Save` | meniul `File`; butonul din tabul `Document`; `Ctrl+S` | — | fisier scriibil | modificarile se scriu; **versiunea PDF nu scade** | fisier blocat → mesaj | D |
| I-002 | `Save As > PDF Document...` | `Ctrl+Shift+S` | cale | **cu opțiunea de redenumire sau mutare** | copie noua | — | D |
| I-003 | `Save As > Searchable PDF Document` | `File > Save As` | opțiuni PDF | **textul devine selectabil si editabil** | strat de text adaugat | — | D |
| I-004 | `Save As > Image-Only PDF Document` | `File > Save As` | — | **fara strat de text** | PDF imagine | — | D |
| I-005 | Opțiunile de salvare | butonul `Options...` din dialogul de salvare, tabul PDF | — | — | — | — | D |
| I-006 | Salvarea unor pagini | selectie in panoul `Pages`, apoi `Save As` din meniul contextual; sau sageata din tabul `Organize Pages` | selectie | — | fisier doar cu paginile alese | — | D |
| I-007 | Salvarea pastreaza neatins ce nu s-a editat | automat | — | obiectele nemodificate se copiaza la nivel de octeti | fisier minim modificat | — | N |
| I-008 | `Create PDF/A` | `File > Save As > PDF Document...` + bifa + versiune din combo | versiune | — | PDF conform | nerespectarea standardului → raport cu motivele | D |
| I-009 | **Ce se include in PDF/A** | automat | — | **fonturi incorporate (cu excepția textului invizibil), numai fonturi care permit incorporarea, culori independente de dispozitiv, metadate conforme cu standardul** | — | — | D |
| I-010 | **Ce NU se suporta in PDF/A** | automat | — | **audio, video si obiecte 3D; scripturi; criptare; linkuri catre continut extern; continut cu drepturi, de exemplu compresia LZW** | — | PDF/A plus parola → eroare | D |
| I-011 | Versiunile PDF/A | combo | **PDF/A-1 (nivelurile B si A), bazat pe PDF 1.4; nivelul A adauga etichete de accesibilitate. PDF/A-2 (nivelurile B, A, U), bazat pe PDF 1.7; adauga Unicode (U), JPEG2000, transparenta, atasamente PDF/A si semnaturi digitale. PDF/A-3 (nivelurile B, A, U); adauga atasamente in orice format** | — | — | — | D |
| I-012 | `Create PDF/UA` | `Format Settings > PDF` | bifa | **cere OCR; aspectul poate diferi de original** | PDF accesibil | — | D |
| I-013 | `Save As` in alte formate | `File > Save As`; sageata din tabul `Document` | format, opțiuni | **Word, Excel, PowerPoint, HTML si formate de imagine** | fisier in formatul ales | — | D |
| I-014 | Combo `File options` la export | dialogul de salvare | **un fisier pentru toate paginile, sau un fisier separat per pagina** | — | — | — | D |
| I-015 | Conversia unor pagini | meniu contextual in panoul `Pages`; tabul `Organize Pages` | selectie | — | — | — | D |
| I-016 | `Reduce File Size...` | `File > Reduce File Size...` | **`Image quality`; `Use MRC compression (specify OCR languages below)`; `OCR languages`** | MRC se aplica paginilor recunoscute | **`Apply` deschide PDF-ul comprimat intr-o fereastra noua** | — | D |
| I-017 | `Recognize and Verify in OCR Editor` | combo din tabul `Document`; `Document > Recognize Document` | — | — | documentul se deschide in OCR Editor | — | D |
| I-018 | **Ce se pierde la trimiterea in OCR Editor** | automat | — | **atasamentele, semnele de carte, comentariile si adnotarile nu se transfera** | — | avertisment inainte | D |
| I-019 | Revenirea din OCR Editor | sageata de lângă buton > `Send to PDF Editor...`; `File > Send To > PDF Editor` | — | — | rezultatul revine in PDF Editor | — | D |
| I-020 | `E-mail...` | butonul din tabul `Document`; `File > E-mail...` | nume, pagini, `Create E-mail Message` | — | mesaj nou cu PDF-ul atasat | — | D |
| I-021 | `Print...` | butonul din tabul `Document`; `File > Print...`; `Ctrl+P` | — | **cere o imprimanta conectata, cu driver instalat** | dialogul de tiparire | fara imprimanta → mesaj | D |
| I-022 | Setarile de tiparire | dialog | **imprimanta; `Copies`; paginile de tiparit (toate, selectate sau un interval); dimensiunea si orientarea hartiei; scalarea si pozitia, cu pagini per foaie; comentariile si marcajele, cu `Show Comments...`; `Manually print on both sides`; `Black and white`** | — | — | — | D |
| I-023 | Avertisment la inchidere cu modificari | inchiderea documentului | — | — | Salveaza / Nu salva / Anuleaza | — | V |
| I-024 | Salvare automata de siguranta | la fiecare 5 minute | — | fisier separat, in folderul de recuperare | la repornire dupa o cadere, se ofera recuperarea | — | N |

---

## Tipuri de PDF — referinta care decide comportamentul

| ID | Tip | Definitie | Consecinta in produs | Src |
|---|---|---|---|---|
| I-030 | PDF doar-imagine | scanari fara strat de text | **recunoasterea in fundal creeaza un strat temporar, care se poate scrie in fisier** | D |
| I-031 | PDF cautabil | imagini de pagina plus un strat de text invizibil | **se obtine adaugand un strat de text sau folosind `Text under the page image` in setarile de PDF cautabil** | D |
| I-032 | PDF din formate editabile | numai text si imagini, fara imagini de pagina | **se obtine cu `Text and pictures only`. Rezultatul poate arata altfel decat originalul** | D |
| I-033 | Regula de recunoastere | — | **PDF-urile cautabile si cele doar-imagine folosesc intotdeauna OCR, indiferent de setarea de mod** | D |
