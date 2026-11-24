# SPECIFICATIE 03 — Comparare documente, automatizare, CLI, Screenshot, integrari, Options

Document 2 din livrabile, partea 3. **Versiunea 2, rescrisa integral dupa verificarea contra manualului oficial de 513 pagini si a paginilor de help.**

**Legenda surselor** (coloana `Src`, nou in aceasta versiune):
- **D** = confirmat in documentatia oficiala ABBYY (manual sau pagina de help). Se implementeaza exact asa.
- **V** = observat pe ecran in tutoriale video. Se implementeaza asa, dar nu e confirmat in scris.
- **K** = din baza de cunostinte ABBYY (support.abbyy.com).
- **N** = **adaugat de noi**, nu exista in original. Se implementeaza doar dacă vrem functia; nu e parte din „1:1".
- **X** = **diferit deliberat** de original, cu motivul in nota.

Aceleasi coloane ca in specificatiile 01 si 02.

---

## R. COMPARARE DOCUMENTE

### R.1 Pornirea si sursele

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| R-001 | Pornirea modulului | 4 cai: Lansator tab `Compare` sau `Tools > Compare Documents`; meniul Start; PDF Editor `File > Compare Documents`; Explorer `Compare with...` / `Compare documents...` | — | — | fereastra cu doua zone de afisare si tabul de diferente | — | D |
| R-002 | Alegerea documentului 1 | tragere peste zona; clic in zona; buton din toolbar; `File > Open Document...` | fisier | formatele din tabelul de formate (coloana „intrare PDF Editor si Compare") | documentul se afiseaza in zona 1 | format nesuportat → mesaj | D |
| R-003 | Alegerea documentului 2 | aceleasi 4 cai, in zona 2 | fisier | idem | — | — | D |
| R-004 | Comutarea intre zone | `Ctrl+Tab`, `Alt+1`, `Alt+2` | — | — | zona activa se schimba | — | D |
| R-005 | Compararea a doua formate diferite | automat | — | se accepta orice combinatie de formate acceptate la intrare | ambele se normalizeaza la text cu pozitii | — | D |
| R-006 | `Recent Comparisons` | `File > Recent Comparisons` | — | — | lista de perechi comparate recent | fisier lipsa → randul se marcheaza | D |
| R-007 | OCR automat pe surse fara strat de text | automat, inainte de comparare | limbi | **pe documentele scanate ruleaza OCR; vezi R-020 pentru modul** | textul se extrage | fara text → eroare `NO_TEXT_FOUND` | D |
| R-008 | Limba de comparare | combo pe tabul `Compare` | limbi | **ABBYY Compare Documents accepta 37 de limbi (pagina produsului: 40; vezi P-101 — DocuLens declara propriul numar), nu toate cele 201 de limbi OCR.** Lista de limbi de comparare e un subset si trebuie declarata separat in produs | influenteaza segmentarea in cuvinte | limba fara suport de comparare → nu apare in combo | D |
| R-009 | Inchiderea unui document | `File > Close Document`, `Ctrl+W` | — | — | zona se goleste | — | D |
| R-010 | Comparare noua | `File > New Comparison`, `Ctrl+N` | — | — | ambele zone se golesc | — | D |

### R.2 Opțiunile de comparare

| ID | Functie | Unde | Valori | Implicit | Rezultat | Src |
|---|---|---|---|---|---|---|
| R-015 | `Find differences in punctuation` | tabul `Compare` | bifa | — | diferentele de punctuatie intra sau nu in rezultat | D |
| R-016 | `Find one-letter differences` | tabul `Compare` | bifa | — | diferentele de o litera intra sau nu in rezultat | D |
| R-017 | Pornirea comparatiei | buton `Compare`; `Compare > Compare Documents`; `Ctrl+R` | — | — | lista de diferente | D |
| R-020 | Modul de recunoastere PDF | `Compare > Advanced` | `Use Only Text from PDF` / `Automatically Choose between OCR and Text from PDF` / `Use OCR` | **`Use Only Text from PDF` pentru PDF-urile care au strat de text.** Modul automat e Pull&Recognize (N-012): textul digital se ia chiar cu limba gresita, OCR numai pe imagini | decide dacă se face OCR | D |
| R-021 | `Use OCR` | acelasi dialog | — | **mai lent, dar mai sigur pe straturi de text de proasta calitate** | — | D |
| R-022 | `Find Headers and Footers Automatically` | `Compare > Advanced` | bifa | activ | se dezactiveaza cand documentele nu au antete | D |
| R-023 | `Reset Advanced Options` | acelasi dialog | buton | — | se revine la valorile livrate | D |

### R.3 Algoritmul de comparare

| ID | Cerinta | Detaliu | Src |
|---|---|---|---|
| R-030 | Normalizarea textului | extragere cu pozitii per cuvant; cuvintele se grupeaza in randuri, randurile in paragrafe | N |
| R-031 | Alinierea | diferenta pe secvente de cuvinte, cu ancore pe paragrafe identice pentru documente lungi | N |
| R-032 | Tipul diferentei | `inserted`, `deleted`, `replaced`, `formatting` | N |
| R-033 | **Diferentele minore se ignora** | **formatarea minora, fontul, spatiile si tabulatorii nu produc diferente.** Aceasta e o regula a originalului, nu o optiune: se implementeaza intotdeauna | D |
| R-034 | Gruparea diferentelor | **in trei grupuri fixe: `Body text`, `Headers and footers`, `Numbering`.** Gruparea se poate dezactiva dintr-un buton de pe tabul `Differences` | D |
| R-035 | Despartirea in silabe | cuvantul intrerupt la capat de rand se reunifica inainte de comparare | N |
| R-036 | Performanta | documentele mari se compara pe blocuri, cu progres afisat | N |

### R.4 Afisarea si navigarea

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| R-040 | Zonele de afisare | fereastra principala | — | doua zone, `Display Area 1` si `Display Area 2` | documentele alaturate | — | D |
| R-041 | `Split Document Pane Horizontally` | `View` | — | — | zonele se asaza una sub alta in loc de una lângă alta | — | D |
| R-042 | Zoom | `Ctrl+=`, `Ctrl+-`, `Ctrl+0` | — | — | — | — | D |
| R-043 | Lista de diferente | tabul `Differences` | — | numerotata, cu text vechi si text nou | lista navigabila | documente identice → lista goala | D |
| R-044 | Textul editat se arata in ambele versiuni | automat | — | **pentru o diferenta de tip inlocuire se listeaza si versiunea veche si cea noua** | — | — | D |
| R-045 | Navigare intre diferente | `Ctrl+Dreapta` / `Ctrl+Stanga`; butoanele din tabul `Differences`; `Compare > Next Difference` / `Previous Difference` | — | — | ambele zone sar la locul respectiv | — | D |
| R-046 | Derulare sincronizata | buton deasupra documentului; meniu contextual; `View > Fit to Width` apoi debifare `Synchronize Scrolling` | bifa | **activa implicit** | zonele se misca impreuna | — | D |
| R-047 | `Copy Difference` | meniu contextual; `Edit > Copy Difference` | diferenta | — | textul diferentei in clipboard | — | D |
| R-048 | `Ignore Difference` | buton din tabul `Differences`; `Del` | selectie, `Ctrl` pentru mai multe | — | diferenta nu intra in raport | — | D |
| R-049 | `Ignore Identical Differences` | tabul `Differences` | o diferenta | **ignora toate diferentele identice cu cea selectata, dintr-o singura comanda** | — | — | D |
| R-050 | `Select All Differences` | `Ctrl+A` | — | — | toate diferentele selectate | — | D |

### R.5 Salvarea rezultatelor

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| R-060 | Butonul `Save...` | tabul `Differences` | — | **formatul implicit e cel folosit ultima data** | dialog cu cele trei variante de mai jos | — | D |
| R-061 | `DOCX in Track Changes Mode` | dialogul de salvare | documentul 1 sau documentul 2 | **se salveaza cate un fisier per document, cu modificarile marcate ca urmarite** | DOCX cu track changes | — | D |
| R-062 | Avertisment la DOCX | automat la R-061 | — | **fisierele DOCX salvate sunt versiuni recunoscute si pot conține erori de recunoastere.** Avertismentul e obligatoriu, nu opțional | — | — | D |
| R-063 | `PDF with Comments` | dialogul de salvare | documentul 1 sau documentul 2 | fiecare diferenta devine o adnotare | PDF adnotat | — | D |
| R-064 | `Comparison Report` | dialogul de salvare | — | tabel Word cu diferentele | DOCX | — | D |
| R-065 | Formatele de salvare acceptate | — | `*.pdf`, `*.docx` | **doar acestea doua** | — | — | D |
| R-066 | Informatia de conformitate | fereastra `Document Properties` a fisierului rezultat | — | conformitatea PDF/A sau PDF/UA se vede acolo | — | — | D |
| R-067 | Diferentele ignorate nu apar in raport | automat | — | — | — | — | D |
| R-068 | Tiparirea rezultatelor | `Ctrl+P` | — | — | — | — | V |

---

## S. HOT FOLDER

Editia Corporate. **Corectie majora fata de versiunea 1 a acestei specificatii: Hot Folder NU poate rula ca serviciu de sistem.**

### S.1 Instalare, pornire, fereastra principala

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| S-001 | Componenta se instaleaza implicit | instalare | — | se poate scoate din instalarea personalizata si adauga ulterior din `Programs and Features > Change > Custom Setup > ABBYY Hot Folder` | — | — | D |
| S-002 | Pornirea | 3 cai: meniul Start; comanda `Hot Folder` din aplicatie (`Tools > Hot Folder`, `Ctrl+Shift+F`); **iconul din bara de sistem, care apare numai dupa ce exista cel putin o sarcina** | — | — | fereastra cu lista de sarcini | — | D |
| S-003 | Coloanele listei | automat | — | calea completa a folderului, statusul, `Next Start Time` | — | — | D |
| S-004 | Butoanele din toolbar | automat | — | `New`, `Modify`, `Copy`, `Delete`, pornire, `Log`, meniul `Import/Export`, comutator de jurnalizare, comutator de notificari | — | — | D |
| S-005 | **Limitarea fundamentala** | — | — | **sarcinile pornesc numai cat timp calculatorul e pornit si utilizatorul e conectat. Nu exista rulare ca serviciu cu niciun utilizator conectat** | — | — | D |
| S-006 | Limita de volum | — | — | **5.000 de pagini pe luna, contorul se reseteaza la fiecare 30 de zile** | la depasire, procesarea se opreste | mesaj care spune limita | K |
| S-007 | Limita de nuclee | — | — | **2 nuclee pentru Hot Folder in editia Corporate**, impuse de parametrul de licenta `Hot Folder Core Count` | — | — | K |
| S-008 | Locul in care se tin sarcinile | — | — | `%Userprofile%\AppData\Local\ABBYY\FineReader\16\HotFolder`, cate un fisier `.hft` per sarcina | — | — | K |
| S-009 | Evidenta fisierelor deja procesate | automat | — | **un fisier `<nume sarcina>.ppi` lângă sarcina tine minte ce s-a procesat, ca sa nu se reprocesese.** Aceasta e mecanica originalului; nu se foloseste doar data modificarii fisierului | — | — | K |

### S.2 Statusurile unei sarcini

| ID | Status | Inteles | Src |
|---|---|---|---|
| S-015 | `Running...` | imaginile din folder se proceseaza acum | D |
| S-016 | `Scheduled` | folderul se verifica **o singura data**, la ora din `Next Start Time` | D |
| S-017 | `Watching...` | folderul se verifica **repetat**; ora urmatoarei verificari apare in `Next Start Time` | D |
| S-018 | `Stopped` | utilizatorul a oprit procesarea | D |
| S-019 | `Completed` | procesarea s-a terminat | D |
| S-020 | `Error (see log)` | procesarea a eșuat; se selecteaza sarcina si se apasa `View Log` pentru eroarea completa | D |

### S.3 Expertul de creare a sarcinii

| ID | Pas / optiune | Valori | Reguli si validari | Src |
|---|---|---|---|---|
| S-030 | `Task name` | text | nume nevid, unic | D |
| S-031 | Planificare `Run once` | data si ora | in viitor | D |
| S-032 | Planificare `Recurring` | **la fiecare minut / o data pe zi / o data pe saptamana / o data pe luna**, la o ora specificata | **acestea sunt singurele intervale. Nu exista „la fiecare N minute" si nu exista declansare pe apariția unui fisier: verificarea repetata la fiecare minut e mecanismul prin care se obtine efectul de urmarire (statusul `Watching...`)** | D |
| S-033 | Sursa `File from folder` | cale locala sau de retea | folderul trebuie sa existe si sa fie citibil | D |
| S-034 | Sursa `File from FTP` | gazda, folder, `User name`, `Password`, bifa `Anonymous user` | se testeaza conexiunea; parola nu se tine in fisierul de sarcina | D |
| S-035 | Sursa `File from Outlook` | folder de e-mail | Outlook instalat | D |
| S-036 | Sursa `OCR project` | proiect OCR | **sursa poate fi un proiect OCR, nu doar un folder cu imagini** | D |
| S-037 | Procesarea subfolderelor | bifa | se poate dezactiva | K |
| S-038 | Ce se face cu originalul | pastreaza / sterge / muta in alt folder | la `muta`, folderul tinta e obligatoriu | D |
| S-039 | Limbile documentului | combo multiplu | minimum 1 | D |
| S-040 | `Document processing settings` | `recunoaste` / `analizeaza` / `preproceseaza` | — | D |
| S-041 | `Recognition Options...` | buton | deschide setarile de recunoastere | D |
| S-042 | `Preprocessing Options...` | buton | deschide setarile de preprocesare | D |
| S-043 | Detectia zonelor | automat / sablon de zone | sablonul trebuie sa existe | D |
| S-044 | `Automatically delete blank pages` | bifa | — | D |
| S-045 | `Move deleted blank pages to the following folder` | cale | activa doar cu S-044 bifat | D |
| S-046 | `Save as` | format + `Options...` | **pentru PDF se alege intre text cautabil si doar imagine** | D |
| S-047 | `Folder` de ieșire | cale | trebuie sa fie scriibil | D |
| S-048 | `Output` — un document per fisier | radio | — | D |
| S-049 | `Output` — un document per folder | radio | **pastreaza ierarhia de foldere** | D |
| S-050 | `Output` — un singur document pentru toate fisierele | radio | — | D |
| S-051 | `File name` | sablon de nume | — | D |
| S-052 | Mai multe pasi de salvare | buton de adaugare | **acelasi fisier sursa poate produce mai multe formate de ieșire** | D |
| S-053 | `Create Task` | buton | sarcina trebuie sa fie completa | D |

### S.4 Operatii pe sarcini

| ID | Functie | Unde | Reguli si validari | Rezultat | Src |
|---|---|---|---|---|---|
| S-060 | Pornirea unei sarcini | buton din toolbar | — | status `Running...` sau `Watching...` | D |
| S-061 | Oprirea | buton | se termina fisierul curent | status `Stopped` | D |
| S-062 | `Modify` | buton | **sarcina trebuie oprita intai**; la final se apasa din nou `Create Task` | — | D |
| S-063 | `Copy` | buton | — | sarcina duplicata | D |
| S-064 | `Delete` | buton | confirmare | — | D |
| S-065 | `Import/Export` | meniu din toolbar | sarcina se salveaza sub un nume, in folderul ales, si se poate incarca pe alt calculator | fisier `.hft` | D |
| S-066 | Notificari la final | comutator din toolbar | **un mesaj deasupra barei de activitati, la fiecare terminare de sarcina** | — | D |
| S-067 | Jurnalizarea | comutator din toolbar | — | se activeaza | D |
| S-068 | Locul jurnalului | automat | **fisier TXT, in acelasi folder cu rezultatele recunoasterii** — nu intr-un folder de jurnale separat | — | D |
| S-069 | Continutul jurnalului | automat | numele si setarile sarcinii, erorile si avertismentele, si statistici: **pagini procesate, numarul de erori, numarul de avertismente, numarul de caractere nesigure** | — | D |
| S-070 | `View Log` | buton; link din coloana `Log` | se selecteaza sarcina intai | jurnalul se deschide | D |
| S-071 | Dezactivarea pornirii automate | setare | se poate opri rularea la pornirea sistemului | — | K |
| S-072 | Tratarea fisierelor eșuate | automat | **dupa 3 incercari fisierul se muta intr-un subfolder `Errors` si nu se mai reproceseaza.** Originalul se bazeaza pe fisierul `.ppi` (S-009); aceasta e politica noastra, mai explicita | fisier mutat | X |
| S-073 | Stabilitatea fisierului inainte de preluare | automat | **un fisier se considera complet copiat dupa ce dimensiunea nu se mai schimba 3 secunde.** Originalul nu documenteaza acest detaliu; fara el, un fisier aflat in copiere se proceseaza trunchiat | — | N |

---

## T. SARCINI AUTOMATIZATE (Automated Tasks)

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| T-001 | Deschiderea managerului | `Tools > Automated Tasks` | — | — | lista de sarcini livrate si proprii | — | D |
| T-002 | Butoanele din toolbar | automat | — | creare, modificare, copiere, stergere, import, export | — | — | D |
| T-003 | Sarcinile livrate | automat | — | nu se modifica si nu se sterg; se pot duplica | — | — | V |
| T-004 | Lista sarcinilor livrate | — | — | Convert to PDF, Convert to searchable PDF, Convert to Word, Convert to Excel, Convert photo to Word, Scan to PDF, Scan to Word, Scan to Excel, Scan to images | — | — | V |
| T-005 | `New` sarcina | buton | nume | nume unic | editorul de sarcina | — | D |
| T-006 | Alegerea proiectului OCR | editor, primul pas | `Create new OCR project` / `Select existing OCR project` / `Use current OCR project` | — | — | — | D |
| T-007 | Sursa de imagini | editor | `Open image or PDF` (folder) sau `Scan` | obligatoriu | — | — | D |
| T-008 | **Ce se proceseaza** | automat | — | **se proceseaza numai imaginile nou adaugate. Paginile deja recunoscute nu se reproceseaza; paginile analizate se recunosc** | — | — | D |
| T-009 | Pasul de analiza | editor | `Analyze the layout automatically` / `Draw areas manually` / `Use an area template` | — | — | — | D |
| T-010 | **Dependenta analiza–recunoastere** | automat | — | **adaugarea pasului de recunoastere adauga automat pasul de analiza; stergerea pasului de analiza sterge si pasul de recunoastere** | — | — | D |
| T-011 | Pasul `Save document` | editor | format, folder, bifa `Create a timestamped subfolder` | — | — | — | D |
| T-012 | Pasul `Send document` | editor | aplicatie tinta | — | — | — | D |
| T-013 | Pasul `E-mail document` | editor | — | — | — | — | D |
| T-014 | Pasul `Save images` | editor | format, bifa `Save as one multi-page image file` | **fisierul multipagina e posibil numai pentru TIFF, PDF, JB2, JBIG2 si DCX** | — | — | D |
| T-015 | Pasul `E-mail images` | editor | — | — | — | — | D |
| T-016 | Pasul `Save OCR project` | editor | cale | — | — | — | D |
| T-017 | Stergerea unui pas | buton | — | nu se poate sterge primul pas | — | — | D |
| T-018 | `Finish` | buton | pasii trebuie sa fie coerenti | sarcina salvata | mesaj care spune ce pas lipseste | D |
| T-019 | Rularea unei sarcini | cardul din Lansator; `Tools > Automated Tasks > Run` | fisiere | — | progres, apoi rezultatul | — | V |
| T-020 | Scurtatura proprie pentru o sarcina | editor | combinatie | combinatia nu poate fi deja folosita | — | conflict → mesaj | N |
| T-021 | Export si import de sarcini | toolbar | fisier | versiune compatibila | — | — | D |

---

## U. LINIA DE COMANDA

**Aceasta sectiune a fost rescrisa integral.** Versiunea 1 descria o linie de comanda unificata, cu parametri inventati de mine. Originalul are **doua executabile separate, cu doua sintaxe diferite**.

### U.1 Conversia — `FineReaderOCR.exe`

| ID | Parametru | Valori | Reguli si validari | Src |
|---|---|---|---|---|
| U-001 | Sintaxa | `FineReaderOCR.exe <ImageSourceCommands> <RecognitionCommands> <ExportCommands>` | calea cu spatii se pune in ghilimele | D |
| U-002 | Sursa — fisiere | cai de imagini sau PDF-uri, separate prin spatiu | fiecare cale cu spatii se pune in ghilimele | D |
| U-003 | Sursa — `/scan [SourceName]` | numele scanerului, opțional | **fara `SourceName` se foloseste ultimul scaner utilizat**; numele cu spatii in ghilimele | D |
| U-004 | `/lang LangName` | una sau mai multe limbi, separate prin spatiu | **fara `/lang` se foloseste ultima limba utilizata** | D |
| U-005 | Limbi proprii in `/lang` | `@@NumeLimba` | **doua caractere `@` inaintea numelui; limba trebuie salvata in folderul proiectului OCR; numele nu poate conține caractere nealfanumerice** | D |
| U-006 | `/send Target` | `MSWord`, `MSExcel`, `OpenOffice`, `Mail`, `Clipboard`, `WebBrowser`, `PDFViewer`, `PowerPoint` | **exact aceste 8 valori**. `Mail` trimite rezultatul in format Word | D |
| U-007 | `/out Out.Ext` | cale de fisier | **un fisier existent se modifica, nu se refuza.** Extensia decide formatul | D |
| U-008 | `/report ReportFile` | cale de fisier | jurnal al conversiei | D |
| U-009 | Comportamentul fara `/out` | — | **rezultatul se deschide in aplicatia aleasa si salvarea rămâne manuala** | D |
| U-010 | Exemplu oficial | `"C:\Program Files\ABBYY FineReader 16\FineReaderOCR.exe" D:\Documents\Guide_German.pdf /lang German /send MSWord` | — | D |
| U-011 | Licenta pentru salvare | — | in original, salvarea prin linia de comanda cere o licenta cu CLI extins. **In produsul nostru nu exista niveluri de licenta, deci salvarea e mereu disponibila** | X |
| U-012 | **Ce NU exista in originalul CLI** | — | nu exista `/format`, `/layout`, `/pages`, `/mrc`, `/pdfa`, `/dpi`, `/split`, `/merge`, `/threads`, `/json`, `/recursive`, `/quiet`, `/config`. Cine implementeaza „1:1" nu le adauga | D |
| U-013 | Modul de rulare | — | **CLI-ul nu functioneaza in mod server: utilizatorul trebuie sa fie conectat, iar produsul instalat local pe fiecare calculator** | D |

### U.2 Compararea — `Comparator.exe`

| ID | Parametru | Valori | Reguli si validari | Src |
|---|---|---|---|---|
| U-020 | Sintaxa | `Comparator.exe /compare <ImageSourceCommands> <ComparisonCommands> <ExportCommands>` | **sintaxa cu doua puncte, diferita de cea a conversiei** | D |
| U-021 | `/file1:<cale>` | cale | obligatoriu | D |
| U-022 | `/file2:<cale>` | cale | obligatoriu | D |
| U-023 | `/lang:<limba>` | limba de comparare | din cele 37 de limbi de comparare (pagina produsului: 40; vezi P-101 — DocuLens declara propriul numar) | D |
| U-024 | `/recMode:` | `UseOnlyPdfText` / `AutoChoose` / `UseOnlyOCR` | **`UseOnlyPdfText` e valoarea folosita cand parametrul lipseste** | D |
| U-025 | `/options:` | `NoheadersFooters`, `IgnorePunctDiff`, `IgnoreOneLetterDiff`, `UngroupDiff` | mai multe, separate prin virgula, fara spatii | D |
| U-026 | `/saveFile:Out.Ext` | cale | extensia decide formatul: `.pdf` sau `.docx` | D |
| U-027 | `/saveMode:` | `PdfDocument1` / `PdfDocument2` / `Word` | `PdfDocument1` adauga comentariile in primul document, `PdfDocument2` in al doilea, `Word` produce tabelul de diferente | D |
| U-028 | Exemplu oficial | `"C:\Program Files\ABBYY FineReader 16\Comparator.exe" /compare /file1:D:\Documents\Document1.pdf /file2:D:\Documents\Document2.pdf /lang:French /recMode:AutoChoose /options:IgnorePunctDiff,UngroupDiff` | — | D |

### U.3 Extinderi proprii, clar marcate

Acestea **nu exista in original**. Se implementeaza pentru ca un produs offline folosit in munca pe loturi are nevoie de ele, dar ele nu fac parte din reproducerea 1:1.

| ID | Parametru | Valori | Motiv | Src |
|---|---|---|---|---|
| U-040 | `/indir <folder> /outdir <folder>` | cai | procesarea unui folder intreg fara Hot Folder | N |
| U-041 | `/pattern "*.pdf"` | masca | selectia fisierelor din folder | N |
| U-042 | `/recursive` | — | include subfolderele | N |
| U-043 | `/pages 1-5,8` | interval | procesarea partiala a unui fisier | N |
| U-044 | `/layout exact\|editable\|formatted\|plain\|flexible` | mod | se valideaza impotriva formatului cerut (matricea din Q-001) | N |
| U-045 | `/pdfa 1b\|2b\|...` | versiune | incompatibil cu `/password` | N |
| U-046 | `/mrc` | — | cere recunoastere | N |
| U-047 | `/threads N` | numar | intre 1 si numarul de nuclee | N |
| U-048 | `/json` | — | rezultat structurat la stdout, pentru integrare in scripturi | N |
| U-049 | `/quiet` | — | fara progres la stdout | N |
| U-050 | `/listlangs`, `/listformats`, `/version`, `/help` | — | descoperirea capabilitatilor | N |
| U-051 | Coduri de ieșire | `0` succes, `1` parametri greșiti, `2` eroare de fisier sau parola, `3` eroare de recunoastere, `4` eroare de scriere, `5` anulat | originalul nu documenteaza coduri de ieșire | N |

---

## V. SCREENSHOT READER

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| V-001 | Pornirea | 4 cai: iconul din bara de sistem; `Tools > Screenshot Reader` din Lansator, PDF Editor sau OCR Editor; meniul Start | — | ruleaza independent de aplicatia principala | fereastra mica | — | D |
| V-002 | Disponibilitate | — | — | **in original, utilitarul e un beneficiu al inregistrarii produsului.** In produsul nostru nu exista inregistrare, deci e mereu disponibil | — | — | X |
| V-003 | `Capture > Area` | combo | dreptunghi tras pe ecran | marginile si zona se pot trage, apoi se apasa `Capture` | zona capturata | — | D |
| V-004 | `Capture > Window` | combo | clic pe cadrul evidentiat | — | fereastra capturata | — | D |
| V-005 | `Capture > Screen` | combo | — | — | tot ecranul | — | D |
| V-006 | `Capture > Timed Screen` | combo | — | **intarziere fixa de 5 secunde, nu configurabila** | captura dupa 5 secunde | — | D |
| V-007 | Anularea capturii | `Esc` sau clic dreapta | — | — | — | — | D |
| V-008 | Anularea recunoasterii | butonul `Stop` sau `Esc` | — | — | — | — | D |
| V-009 | Combo `Language` | fereastra | limbi, inclusiv `More languages...` | **o limba lipsa inseamna ori ca nu e suportata, ori ca a fost dezactivata la instalarea personalizata** | — | — | D |
| V-010 | `Send > Text to Clipboard` | combo | — | — | textul in clipboard | — | D |
| V-011 | `Send > Table to Clipboard` | combo | — | — | tabelul in clipboard | — | D |
| V-012 | `Send > Image to Clipboard` | combo | — | — | imaginea in clipboard | — | D |
| V-013 | `Send > Text to Microsoft Word` | combo | — | Word instalat | document nou | — | D |
| V-014 | `Send > Table to Microsoft Excel` | combo | — | Excel instalat | foaie noua | — | D |
| V-015 | `Send > Text to File` | combo | cale, format | — | fisier | — | D |
| V-016 | `Send > Table to File` | combo | cale, format | — | fisier | — | D |
| V-017 | `Send > Image to File` | combo | cale, format | — | fisier | — | D |
| V-018 | `Send > Image to OCR Editor` | combo | — | **recomandat pentru zone cu text si imagini amestecate** | imaginea intra in OCR Editor | — | D |
| V-019 | `Send > Image to E-mail` | combo | — | **imaginea se atașează ca BMP** | mesaj nou | — | D |
| V-020 | Opțiunea `Always on Top` | clic dreapta pe iconul din bara de sistem > `Options` | bifa | — | — | — | D |
| V-021 | Opțiunea `Run at Startup` | idem | bifa | — | — | — | D |
| V-022 | Opțiunea `Enable Sounds` | idem | bifa | — | — | — | D |
| V-023 | Recomandare de utilizare | — | — | **se selecteaza text intr-o singura limba**; pentru text amestecat cu imagini se foloseste `Image to OCR Editor` | — | — | D |
| V-024 | Scurtatura globala | setare | combinatie | originalul nu documenteaza o scurtatura globala | utilitarul se activeaza | conflict → mesaj | N |
| V-025 | Ecran multiplu | automat | — | zona poate traversa monitoare | — | — | N |
| V-026 | `Repeat last capture` | buton | — | se refoloseste aceeasi zona | — | nicio captura anterioara → buton gri | N |

---

## W. INTEGRARI

**Sectiune rescrisa.** Versiunea 1 spunea ca integrarile Office se inlocuiesc cu meniul contextual din Explorer. Aceasta era o decizie de proiectare prezentata greșit ca „originalul nu are". Originalul **are** add-in-uri de Office cu functii proprii, detaliate mai jos.

### W.1 Meniul contextual din Windows Explorer

| ID | Comanda | Pe ce tip de fisier | Reguli si validari | Src |
|---|---|---|---|---|
| W-001 | `Edit with ABBYY FineReader PDF` | PDF | deschide in PDF Editor | D |
| W-002 | `Convert with ABBYY FineReader PDF` (submeniu) | PDF, imagini | conține comenzile W-003…W-007 | D |
| W-003 | `Convert to searchable PDF document` | PDF, imagini | — | D |
| W-004 | `Convert to image-only PDF document` | PDF, imagini | — | D |
| W-005 | `Convert to Microsoft Word document` | PDF, imagini | — | D |
| W-006 | `Convert to Microsoft Excel document` | PDF, imagini | — | D |
| W-007 | `Convert to another format` | PDF, imagini | — | D |
| W-008 | `Open in OCR Editor` | PDF, imagini | creeaza un proiect nou | D |
| W-009 | `Compare with...` | orice format acceptat | — | D |
| W-010 | `Compare documents...` | orice format acceptat | — | D |
| W-011 | `Combine into one PDF...` | orice format acceptat | — | D |
| W-012 | `Convert to PDF with ABBYY FineReader PDF...` | formate editabile (DOCX, XLSX, PPTX, RTF, TXT, ODT, HTML) | — | D |
| W-013 | `Convert to PDF and send...` | formate editabile | — | D |
| W-014 | Conversia Office pastreaza structura | automat | **conversiile din Word, Excel si PowerPoint pastreaza structura, semnele de carte si hyperlinkurile** | D |
| W-015 | Conversia mai multor fisiere | selectie multipla | **comanda `Convert` pe mai multe fisiere deschide fereastra Lansatorului**, nu proceseaza direct | D |
| W-016 | Comenzile depind de selectie | automat | **ce comenzi apar depinde de numarul si de formatul fisierelor selectate** | D |
| W-017 | Reinstalarea comenzilor | `Programs and Features > Change` | cand comenzile lipsesc din meniu | D |

### W.2 Add-in-ul de Microsoft Word

| ID | Functie | Intrari | Reguli si validari | Src |
|---|---|---|---|---|
| W-030 | Butonul `Create PDF` | nume, folder, bifa `Open document` | — | D |
| W-031 | Butonul `Create PDF and Send by E-mail` | — | atașează PDF-ul la un mesaj nou, gol | D |
| W-032 | Butonul `Scan to Word` | setari de scanare | — | D |
| W-033 | Butonul `Convert to Word` | `Document languages`, `Document layout`, `Options...` | `Options...` deschide setarile DOC(X)/RTF/ODT | D |
| W-034 | Butonul `Compare document with...` | al doilea document | deschide ABBYY Compare Documents | D |
| W-035 | Setarea `Create PDF/A` | versiune din combo | — | D |
| W-036 | Setarea `Create PDF/UA` | bifa | **aspectul poate diferi de original** | D |
| W-037 | Setarea `Password-protect documents` | buton `Settings...` | — | D |
| W-038 | Setarea `Create PDF tags` | bifa | — | D |
| W-039 | Setarea `Create bookmarks from headings` | bifa | — | D |
| W-040 | Setarea `Apply to pages` | `All` / `Ask to specify pages` | **`All` e valoarea implicita** | D |
| W-041 | Numele add-in-ului COM | — | se activeaza din `File > Options > Add-ins > COM Add-ins > Go...` | D |

### W.3 Add-in-urile de Excel, PowerPoint si Outlook

| ID | Functie | Aplicatie | Reguli si validari | Src |
|---|---|---|---|---|
| W-050 | `Create PDF`, `Create PDF and Send by E-mail`, `Preferences` | Excel | — | D |
| W-051 | `Apply to the following spreadsheets` | Excel | foaia activa / toate foile / zona selectata; `Ask to specify spreadsheets` intreaba la fiecare rulare | D |
| W-052 | `Create PDF`, `Preferences` | PowerPoint | — | D |
| W-053 | `Convert speaker notes` | PowerPoint | — | D |
| W-054 | `Include hidden slides` | PowerPoint | salveaza si slide-urile ascunse | D |
| W-055 | Conflict intre opțiuni | PowerPoint | **`Ask to specify slides` nu e disponibila cand `Convert speaker notes` e bifat** | D |
| W-056 | `Convert to PDF` | Outlook | creeaza PDF din corpul mesajelor selectate; se pot selecta mai multe | D |
| W-057 | `Create PDF from folder` | Outlook | din toolbar sau din meniul contextual al folderului | D |
| W-058 | `Create PDF from attachments` | Outlook | deschide fereastra de conversie de imagini | D |
| W-059 | Atasamentele in rezultat | Outlook | **atasamentele se salveaza ca atasamente ale PDF-ului rezultat** | D |
| W-060 | Versiunile de Office suportate | — | **Office 365 si 2019 pentru add-in; pentru conversie: 365, 2019, 2016 (16.0), 2013 (15.0)** | D |

### W.4 SharePoint

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| W-070 | `Check Out` | butonul din banda de mesaje sau `File > SharePoint® > Check Out` | dacă documentul e deja rezervat, se salveaza o copie locala | D |
| W-071 | `Check In...` | `File > SharePoint®` | — | D |
| W-072 | `Discard Check Out...` | `File > SharePoint®` | renunta la modificari | D |
| W-073 | Dialogul de check-in | automat | `Version type` (dacă e activ controlul de versiuni), un comentariu, bifa `Keep the document checked out after checking in the current version`, butonul `Check In` | D |
| W-074 | Limitare OneDrive | automat | **OneDrive nu permite rezervarea documentelor; ele se trateaza ca fisiere obisnuite** | D |
| W-075 | Versiunile SharePoint suportate | — | SharePoint Online, 2019, 2016, 2013 | D |

### W.5 Aplicatia mobila si stocarea in cloud

| ID | Functie | Reguli si validari | Src |
|---|---|---|---|
| W-080 | Cerinte | **aplicatia FineReader PDF pentru iOS plus clientul Google Drive pentru Windows**; nu exista integrare directa prin API | D |
| W-081 | Fluxul pe telefon | se creeaza documentul, apoi se exporta in Google Drive (folderul FineReader), cu autentificare Google; se alege JPG sau PDF si o dimensiune | D |
| W-082 | Fluxul pe calculator | tabul `Mobile application` > `Select folder` > folderul local FineReader, apoi se alege un document sau un folder | D |
| W-083 | Sortarea | **dupa data creării, cel mai nou primul** | D |
| W-084 | Deschiderea | un PDF se deschide in editor; un folder de imagini deschide un dialog de creare de PDF din JPG-uri; alte formate se convertesc in PDF | D |
| W-085 | Sincronizarea | modificarile urca pe server la salvare | D |
| W-086 | Stocare in cloud | OneDrive, Google Drive si Dropbox, **prin clientul lor de desktop**; folderul apare in Explorer; fisierele se descarca la deschidere si se sincronizeaza la salvare | D |
| W-087 | `Always keep on this device` | combo pe fisier, pentru disponibilitate offline | D |

### W.6 Alte integrari

| ID | Functie | Reguli si validari | Src |
|---|---|---|---|
| W-090 | Setarea ca vizualizator PDF implicit | `Options > General > Make FineReader the default program for opening PDF documents`; sau clic dreapta pe PDF > `Properties > General > Change` | D |
| W-091 | Tragerea fisierelor in fereastra | se deschid in modulul potrivit | V |
| W-092 | Argument de linie de comanda la pornirea interfetei | aplicatia porneste cu fisierul deschis | V |
| W-093 | Imprimanta virtuala | **nu exista in original.** Utila intr-un produs offline pentru a produce PDF din orice aplicatie | N |
| W-094 | O singura instanta | al doilea lansaj trimite fisierul primei instante | N |

---

## X. OPTIONS — toate setarile

Sapte tab-uri. Al saptelea, `Areas and Text`, **apare numai cand dialogul e deschis din OCR Editor**. Dialogul se deschide din butonul `Options` din stanga-jos a Lansatorului, sau din `Tools > Options...` in oricare modul, sau cu `Ctrl+>`.

### X.1 General

| ID | Setare | Valori | Implicit | Src |
|---|---|---|---|---|
| X-001 | Ecranul de pornire | `New Task screen` / OCR Editor cu proiect nou / OCR Editor cu ultimul proiect | `New Task screen` | D |
| X-002 | Dispozitivul de captura | lista de scanere | primul disponibil | D |
| X-003 | Interfata de scanare | a aplicatiei / a driverului | a aplicatiei | D |
| X-004 | `Make FineReader the default program for opening PDF documents` | bifa | — | D |
| X-005 | Integrarea in meniul contextual | — | **nu e o setare din acest tab in original; comenzile din Explorer se instaleaza cu produsul.** La noi rămâne o setare, ca sa poata fi dezactivata | X |

### X.2 Image Processing

| ID | Setare | Valori | Implicit | Note | Src |
|---|---|---|---|---|---|
| X-010 | `Enable background recognition in the PDF Editor` | bifa | activ | — | D |
| X-011 | `Automatically process page images as they are added to the OCR Editor` | bifa | activ | debifarea accelereaza deschiderea documentelor mari | D |
| X-012 | Modul automat | `Recognize page images (includes preprocessing and analysis)` / `Analyze page images (includes preprocessing)` / `Preprocess page images` | **recunoastere automata** | la `Analyze`, OCR-ul se porneste manual | D |
| X-013 | `Image preprocessing settings (apply to conversion and OCR)` | grup | — | **setarile se aplica numai imaginilor adaugate de acum inainte** | D |
| X-014 | Modul implicit de preprocesare | corectare automata a defectelor obisnuite | activ | — | D |
| X-015 | `Specify settings manually` | radio | — | deschide X-016…X-018 | D |
| X-016 | `Split facing pages` | bifa | dezactivat | **paginile scanate invers nu se impart** | D |
| X-017 | `Correct page orientation` | bifa | activ | — | D |
| X-018 | `Use recommended settings for better OCR` | bifa | activ | — | D |
| X-019 | `Show Custom Settings` / `Hide Custom Settings` | comutator | ascuns | deschide lista completa X-020…X-030 | D |
| X-020 | `Deskew images` | bifa | activ | — | D |
| X-021 | `Straighten text lines` | bifa | activ | — | D |
| X-022 | `Correct image resolution` | bifa | activ | — | D |
| X-023 | `Detect page edges` | bifa | activ | **doar fotografii digitale** | D |
| X-024 | `Whiten background` | bifa | activ | doar fotografii | D |
| X-025 | `Reduce ISO noise` | bifa | activ | doar fotografii | D |
| X-026 | `Remove motion blur` | bifa | dezactivat | doar fotografii | D |
| X-027 | `Correct trapezoid distortions` | bifa | — | **doar fotografii. Exista si ca setare automata, nu numai ca unealta manuala in Image Editor** | D |
| X-028 | `Fix inverted colors on image` | bifa | activ | — | D |
| X-029 | `Convert to black and white` | bifa | dezactivat | **conversia e ireversibila; culorile nu se pot recupera.** Nerecomandat pentru fotografii, pagini de revista si texte chinezesti, japoneze sau coreene | D |
| X-030 | `Remove color marks` | bifa | dezactivat | **nu pentru fotografii digitale sau fundaluri colorate** | D |
| X-031 | `No preprocessing` | radio | — | dezactiveaza tot; preprocesarea rămâne disponibila manual in Image Editor | D |

### X.3 Languages

| ID | Setare | Valori | Implicit | Src |
|---|---|---|---|---|
| X-040 | `Automatically select OCR languages from the following list` | radio + buton `Specify...` | activ | D |
| X-041 | Dialogul `Languages` | lista cu bife | limba interfetei + engleza | D |
| X-042 | `Specify OCR languages manually` | radio | — | D |
| X-043 | `New...` limba sau grup | buton | — | D |
| X-044 | Numarul de limbi OCR | **201** (pagina produsului: 198; vezi P-100 — DocuLens declara propriul numar), in trei categorii: naturale; artificiale (Ido, Interlingua, Occidental, Esperanto); formale (Basic, C/C++, COBOL, Fortran, Java, Pascal, formule matematice simple, numere) | — | D |
| X-045 | Limbile cu dictionar | marcate cu asterisc in lista; dictionarul permite detectarea caracterelor nesigure si a greselilor de scriere | — | D |
| X-046 | Limbile de comparare | **37** (pagina produsului: 40; vezi P-101 — DocuLens declara propriul numar) | — | D |
| X-047 | Lista completa a limbilor din licenta | `Help > About > License Info` | — | D |
| X-048 | Limbile gotice | **6: Old English, Old French, Old German, Old Italian, Old Spanish, Latvian Gothic.** Caractere suportate: Textur/Textualis, Fraktur, Schwabacher. **Se foloseste numai limba gotica, nu in combinatie cu o limba moderna** | — | D |
| X-049 | Limba romana | `Romanian` si `RomanianMoldavia`; produsul trebuie sa acopere si varianta cu sedila, frecventa in documentele vechi | — | V |

### X.4 OCR

| ID | Setare | Valori | Implicit | Src |
|---|---|---|---|---|
| X-060 | Modul de recunoastere PDF | `Automatically Choose between OCR and Text from PDF` / `Use OCR` / `Use Only Text from PDF` | **`Use Only Text from PDF` pentru PDF-urile care au strat de text.** Modul automat e Pull&Recognize (N-012): textul digital se ia chiar cu limba gresita, OCR numai pe imagini | D |
| X-061 | Comportamentul fix | — | **PDF-urile cautabile si cele doar-imagine folosesc intotdeauna `Use OCR`, indiferent de setare** | D |
| X-062 | `Thorough recognition` | radio | activ | **pentru layout complex, fundaluri colorate si tabele cu linii albe sau colorate** | D |
| X-063 | `Fast recognition` | radio | — | pentru documente mari, simple, cu imagini bune | D |
| X-064 | `Document type` | `Auto` / `Typewriter` / `Fax` | `Auto` | **`Typewriter` pentru litere de latime egala; `Fax` pentru zgomot si distorsiune. Dupa folosire se revine la `Auto`** | D |
| X-065 | `Detect structural elements` | bife: antete si subsoluri, note de subsol, cuprins, liste | toate active | **elementele detectate devin clicabile in fisierul salvat; dacă detectia e dezactivata, se salveaza ca text obisnuit** | D |
| X-066 | `Convert barcodes into strings` | bifa | **dezactivat** | altfel codurile se salveaza ca imagini | D |
| X-067 | `Use training to recognize new characters and ligatures` | bifa | **dezactivat** | pentru simboluri speciale, text decorativ si volume mari de calitate slaba (peste 100 de pagini) | D |
| X-068 | Sabloane | `Use built-in patterns` / `Use user patterns` + `Also use built-in patterns` | built-in | D |
| X-069 | `Pattern Editor...` | buton | — | D |
| X-070 | `Save Patterns and Languages...` / `Load...` | butoane | fisier `*.fbt` sau `*.fbtx` | D |
| X-071 | `Select Fonts...` | buton + lista | fonturile folosite in textul exportat | D |

### X.5 Format Settings

Un sub-tab per format. Toate valorile de mai jos sunt confirmate din manual.

#### X.5.1 PDF

| ID | Setare | Valori | Implicit | Note | Src |
|---|---|---|---|---|---|
| X-080 | `Image quality` | `Best quality` / `Balanced` / `Compact size` / `Custom...` | — | `Best quality` pastreaza rezolutia originala; **`Compact size` reduce imaginile si paginile la 300 dpi** | D |
| X-081 | `Create PDF/A` | bifa + versiune | **PDF/A-2b cand se bifeaza din Lansator** | — | D |
| X-082 | `Create PDF/UA (requires OCR)` | bifa | dezactivat | **aspectul poate diferi de original** | D |
| X-083 | `Protect documents with passwords` | bifa + `Settings...` | dezactivat | — | D |
| X-084 | `Delete objects and data` | bifa + `Select...` | dezactivat | patru elemente: `Comments and markup`; `Links, media, actions, scripts, and form data`; `Bookmarks`; `Attachments` | D |
| X-085 | `Use one paper size for all page images` | bifa | **dezactivat**; dimensiunile originale se pastreaza | — | D |
| X-086 | `Use MRC compression (requires OCR)` | bifa | dezactivat | **functioneaza numai pentru PDF cautabil cu `Text under the page image`** | D |
| X-087 | `Apply ABBYY PreciseScan to smooth characters on page images` | bifa | — | — | D |
| X-088 | Modul de PDF cautabil | `Text and pictures only` / `Text over the page image` / `Text under the page image` | — | `Text and pictures only` da cel mai mic fisier, dar poate diferi de original | D |
| X-089 | `Create bookmarks from headings` | bifa | — | — | D |
| X-090 | `Create PDF tags` | bifa | — | permite recurgerea textului pe ecrane de alta dimensiune | D |
| X-091 | `Fonts` | `Use predefined fonts` (Adobe) / `Use Windows fonts` | — | — | D |
| X-092 | `Embed fonts` | bifa | — | **disponibila numai pentru `Text and pictures only` si `Text over the page image`** | D |
| X-093 | `Preserve document metadata, such as authors and keywords` | bifa | **activ** | — | D |
| X-094 | `Edit Metadata...` | buton | — | nume, autor, subiect, cuvinte cheie | D |

#### X.5.2 DOC(X)/RTF/ODT

| ID | Setare | Valori | Note | Src |
|---|---|---|---|---|
| X-100 | `Document layout` | `Exact copy` / `Editable copy` / `Formatted text` / `Plain text` | — | D |
| X-101 | `Default paper size` | combo | pentru RTF, DOC, DOCX, ODT | D |
| X-102 | `Keep pictures` | combo + `Custom...` | — | D |
| X-103 | `Keep headers, footers, and page numbers` | bifa | — | D |
| X-104 | `Keep line breaks and hyphens` | bifa | — | D |
| X-105 | `Keep page breaks` | bifa | pastreaza aranjarea pe pagini | D |
| X-106 | `Keep line numbers` | bifa | **disponibila numai cu `Editable copy`**; numerotarea sta intr-un camp separat, care nu se schimba la editarea textului | D |
| X-107 | `Keep text and background colors` | bifa | — | D |
| X-108 | `Keep bold, italic, and underlined text styles in plain text` | bifa | **disponibila numai cu `Plain text`** | D |
| X-109 | `Highlight low-confidence characters` | bifa | **pentru editarea in Microsoft Word, nu pentru panoul Text al OCR Editor-ului.** Culoarea se schimba din tabul `Areas and Text` | D |

#### X.5.3 Celelalte formate

| ID | Format | Setari confirmate | Src |
|---|---|---|---|
| X-120 | XLS(X) | layout `Formatted text` sau `Plain text`; `Keep pictures` (doar XLSX); `Keep headers and footers`; `Ignore text outside tables`; `Convert numeric values to numbers`; `Create separate sheet for each page` (doar XLSX) | D |
| X-121 | PPTX | `Keep pictures` + `Custom...`; `Keep headers and footers`; `Keep line breaks` (fara ea, tot textul devine un rand); **`Shrink text on overflow`** | D |
| X-122 | CSV | `Ignore text outside tables`; **`Insert page break character (#12) as page separator`**; `Delimiter`; `Encoding` (detectata automat). **CSV e format numai de ieșire** | D |
| X-123 | TXT | layout `Formatted text` sau `Plain text`; `Keep line breaks`; `Insert page break character (#12) as page break`; **`Use blank line as paragraph separator`**; `Keep headers and footers`; `Encoding` | D |
| X-124 | HTML | layout **`Flexible layout` / `Formatted text` / `Plain text`** (trei, nu doua); `Keep pictures`; `Keep line breaks`; `Keep text and background colors`; `Keep headers and footers`; `Encoding` | D |
| X-125 | HTML — `Book settings` | `Generate a table of contents and use it to divide the document into files`, cu trei variante: `Automatically create files based on headings` (imparte in parti aproximativ egale), `Create files based on level 1 headings`, `Create files based on level 2 headings` | D |
| X-126 | EPUB/FB2 | layout `Formatted text` sau `Plain text`; **stilurile de font se pastreaza numai in EPUB**; `Retain fonts and font sizes (EPUB only)` + `Embed fonts` (unele dispozitive nu afiseaza fonturi incorporate); `Use the first page as the e-book cover`; `Keep pictures`; `EPUB Settings` cu versiunea EPUB. **FB2 si EPUB sunt formate numai de ieșire** | D |
| X-127 | DjVu | `Save mode`: `Text under the page image` sau `Page image only`; `Image quality` + `Custom...`; **`Multiple layers`: `Automatic` (implicit), `Always on`, `Always off`** | D |

### X.6 Other

| ID | Setare | Valori | Implicit | Note | Src |
|---|---|---|---|---|---|
| X-140 | `Interface language` | 22 de limbi: English, Bulgarian, Hungarian, Vietnamese, Dutch, Greek, Danish, Spanish, Italian, Chinese Traditional, Chinese Simplified, Korean, German, Polish, Portuguese (Brazilian), Slovak, Turkish, Ukrainian, French, Czech, Swedish, Japanese | limba aleasa la instalare | **schimbarea cere repornirea aplicatiei** | D |
| X-141 | Nucleele folosite la OCR | 1…N | **implicit: toate nucleele minus unul.** Din Release 3, limita se aplica si prelucrarii in fundal din PDF Editor (https://pdf.abbyy.com/blog/finereader-pdf-release-3-updates/) | — | D |
| X-142 | Verificarea automata a actualizarilor | bifa | activ in original | **la noi: absent. Produsul e offline (Y-001)** | X |
| X-143 | Trimiterea de date de configurare anonimizate | bifa | — | **la noi: absent** | X |
| X-144 | Mesaje de marketing | bifa | — | **la noi: absent** | X |
| X-145 | `Enable JavaScript in PDF documents` | bifa | **dezactivat** | — | D |
| X-146 | Detectia automata a adreselor web | bifa | activ | — | D |
| X-147 | `Reset...` | buton | — | readuce toate setarile la valorile livrate | D |
| X-148 | Scurtaturi reatribuibile | — | — | **in original NU se configureaza din acest tab. Se configureaza din OCR Editor: `View > Toolbars > Customize... > Keyboard Shortcuts`, cu `Categories`, `Press new shortcut key`, `Assign`, `Reset`, `Reset All`** | D |
| X-149 | Tema intunecata | — | — | **nu exista in original** | N |
| X-150 | Folderul de fisiere temporare | cale | folderul temporar al sistemului | originalul nu expune aceasta setare | N |

### X.7 Areas and Text (numai din OCR Editor)

| ID | Setare | Valori | Implicit | Src |
|---|---|---|---|---|
| X-160 | Verificarea caracterelor nesigure | bifa + culoare de evidentiere | activ | D |
| X-161 | Cuvintele din afara dictionarului | **`ignora cuvintele cu cifre si caractere speciale`; `verifica cuvintele compuse care nu sunt in dictionar`** | — | D |
| X-162 | Corectarea spatiilor in jurul punctuatiei | bifa | — | D |
| X-163 | `User Dictionaries...` + `Browse...` | cale de folder | folderul utilizatorului, sub `AppData\Roaming\ABBYY\FineReader\16` | D |
| X-164 | `Font used to display plain text` | combo | — | **Arial Unicode MS pentru scrieri neeuropene** | D |
| X-165 | Culoarea si grosimea chenarului per tip de zona | 6 tipuri | valori livrate | **obligatoriu configurabila** | D |
| X-166 | Culoarea de evidentiere a caracterelor nesigure | culoare | — | aceeasi culoare se foloseste si la `Highlight low-confidence characters` in Word (X-109) | D |
| X-167 | Pragul de incredere | 0-100 | **70** | **originalul nu publica un prag. 70 e alegerea noastra** | N |
| X-168 | `Show area numbers` | bifa | activ | D |
| X-169 | Caracterele neimprimabile | bifa | dezactivat | V |

---

## Y. INFRASTRUCTURA SI CERINTE DE SISTEM

| ID | Cerinta | Detaliu | Src |
|---|---|---|---|
| Y-001 | Functionare complet offline | **nicio cerere de retea in functionarea normala.** Originalul are activare online, verificare de actualizari si telemetrie opționala; produsul nostru nu are niciuna. Se testeaza cu interfata de retea dezactivata | X |
| Y-002 | Sisteme de operare suportate de original | Windows 11 si Windows 10 (64 de biti); Windows Server 2022, 2019, 2016, 2012 R2. **Sistemul trebuie sa suporte limba de interfata aleasa** | D |
| Y-003 | Cerinte minime ale originalului | procesor x64 de 1 GHz; 2 GB RAM, plus 512 MB per procesor suplimentar pe sisteme multiprocesor; 1,6 GB pentru instalare plus 1,6 GB liberi pentru functionare; ecran 1024x768; tastatura si mouse | D |
| Y-004 | Cerinte recomandate | 1,5 GHz Intel sau AMD x64; 4 GB RAM | D |
| Y-005 | Servere de terminal testate | Windows Server RDS, RemoteApp, RD Web Access; Citrix Workspace App 1808; Citrix Virtual Apps and Desktops | D |
| Y-006 | Scanere | **TWAIN si WIA**, scanere si multifunctionale | D |
| Y-007 | Dependenta de Office | **originalul cere Microsoft Office sau LibreOffice pentru formatele editabile, conversiile rapide, comparari si adaugarea de pagini in PDF.** Produsul nostru trebuie sa citeasca si sa scrie aceste formate cu biblioteci proprii, ca sa nu depinda de Office | X |
| Y-008 | Versiuni suportate pentru interoperare | Word, Excel, PowerPoint 365, 2019, 2016 (16.0), 2013 (15.0); Office 2021 Professional Plus; Apache OpenOffice Writer 4.1; LibreOffice Writer 6.2.5 si 6.3.0 | D |
| Y-009 | Instalare | originalul: `Setup.exe` plus expert. La noi: Windows prin Inno Setup; Linux prin AppImage; macOS prin `.dmg` | X |
| Y-010 | Instalare fara drepturi de administrator | **nu exista in original.** La noi: varianta portabila care scrie doar in profilul utilizatorului | N |
| Y-011 | Desfasurare in retea | originalul suporta Active Directory, SCCM, linie de comanda si instalare manuala, descrise in ghidul administratorului | D |
| Y-012 | Activare | **patru metode in original: prin internet, prin site, prin e-mail, prin e-mail de pe alt calculator.** Fara activare, numarul de pagini salvate e limitat si programul se opreste dupa o perioada. **Produsul nostru nu are activare** | X |
| Y-013 | Inregistrare | opționala in original; aduce suport tehnic, ABBYY Screenshot Reader si recuperarea numarului de serie. **Nu exista la noi** | X |
| Y-014 | Raport de sistem pentru suport | `Help > About > System Info... > Save...` | D |
| Y-015 | Numarul de build | `Help > About` | D |
| Y-016 | Limita de memorie | documentele mari se proceseaza pagina cu pagina, cu imaginile pe disc | N |
| Y-017 | Interfata nu se blocheaza | operatiile lungi pe fire separate, cu progres si anulare | N |
| Y-018 | Scalarea pe ecrane cu densitate mare | corect la 100%, 125%, 150%, 200% | N |
| Y-019 | Accesibilitate | navigare completa cu tastatura, nume accesibile pe controale | N |
| Y-020 | Localizare | romana si engleza obligatorii; niciun text afisabil in cod | X |
| Y-021 | Licente ale componentelor | fisier cu licentele tuturor componentelor; componentele AGPL se evita sau se izoleaza ca proces separat | N |
| Y-022 | Setarile per utilizator | fisier in profilul utilizatorului, exportabil si importabil | N |
| Y-023 | Curatarea fisierelor temporare | la inchidere normala si la pornire, pentru resturile de la o cadere | N |
| Y-024 | Jurnal de aplicatie | fisier rotativ, cu niveluri; folderul se deschide dintr-un buton din Options | N |
| Y-025 | Raportarea unei erori neasteptate | dialog cu mesajul, urma stivei copiabila si salvarea jurnalului; aplicatia nu se inchide dacă starea documentului se poate salva | N |
| Y-026 | Recuperarea dupa o cadere | la pornire se ofera recuperarea fisierelor de siguranta | N |

---

## Z. ETICHETE DE DATA SI ORA, EXPRESII REGULATE

Doua referinte din manual care nu existau in versiunea 1 a specificatiei si fara care doua functii nu se pot implementa corect.

### Z.1 Etichete de data si ora (stampile, antete, subsoluri, numerotare Bates)

| ID | Eticheta | Rezultat | Src |
|---|---|---|---|
| Z-001 | `<d/>` | data scurta, de exemplu `07.02.2013` | D |
| Z-002 | `<date/>` | data lunga, de exemplu `7 February 2013` | D |
| Z-003 | `<t12/>` | ora in format de 12 ore | D |
| Z-004 | `<t24/>` | ora in format de 24 de ore | D |
| Z-005 | `<time/>` | `HH:MM:SS` | D |
| Z-006 | Cod de regiune | `<d=RUS/>`, `<date=USA/>`, `<time=ENG/>`. **Fara cod, se foloseste formatul regional din Windows** | D |
| Z-007 | Formate proprii pentru an | `%y`, `%#y`, `%Y`, `%#Y` | D |
| Z-008 | Formate proprii pentru luna | `%b`, `%B`, `%m`, `%#m` | D |
| Z-009 | Formate proprii pentru zi | `%d`, `%#d`, `%a`, `%A` | D |
| Z-010 | Formate proprii pentru ora | `%H`, `%#H`, `%I`, `%#I`, `%p` | **`%p` (AM/PM) functioneaza numai pentru regiunile USA, ENG, HUN si CZ** | D |
| Z-011 | Minute si secunde | `%M`, `%#M`, `%S`, `%#S` | D |
| Z-012 | Procent literal | `%%` | D |
| Z-013 | Previzualizare | **dialogul de stampile si cel de numerotare Bates arata rezultatul inainte de aplicare** | D |

### Z.2 Expresii regulate pentru limbi proprii

| ID | Simbol | Inteles | Src |
|---|---|---|---|
| Z-020 | `.` | orice caracter | D |
| Z-021 | `[ ]` | un caracter din grup | D |
| Z-022 | `[^ ]` | un caracter care nu e din grup | D |
| Z-023 | `\|` | sau | D |
| Z-024 | `*` | zero sau mai multe repetari | D |
| Z-025 | `+` | una sau mai multe repetari | D |
| Z-026 | Clase de litere si cifre | clase predefinite pentru litere si cifre | D |
| Z-027 | Intervale latine si chirilice | majuscule si minuscule, separat | D |
| Z-028 | `@` | **caracter rezervat; nu se poate folosi ca literal** | D |
| Z-029 | Evadarea | caracterele speciale se scriu cu backslash inainte | D |
| Z-030 | Utilizare | expresia se foloseste ca dictionar al unei limbi proprii, pentru campuri de tip data sau adresa de e-mail; trebuie sa compileze, altfel se refuza cu mesajul erorii | D |

---

## Ce rămâne neacoperit, spus deschis

- **Lista completa a celor 201 de limbi OCR si a celor 37 de limbi de comparare** nu e reprodusa aici. Produsul trebuie sa declare explicit ce limbi acopera; nu se poate promite paritate cu originalul fara modelele lui.
- **Tabelul fonturilor necesare per limba** exista in manual si trebuie consultat la implementarea afisarii scrierilor neeuropene. Regula de baza: `Arial Unicode MS` acopera majoritatea; ebraica are fonturi proprii (Aharoni, David, Levenim mt, Miriam, Narkisim, Rod); chineza, japoneza si coreeana cer fonturi din familia SimSun (SimHei, YouYuan, PMingLiU, MingLiU, STSong).
- **Numerele exacte de licenta** (limita de pagini a Hot Folder, numarul de nuclee) vin din baza de cunostinte, nu din manual, si se pot schimba.
- **Formatul fisierelor originalului** (`.hft`, `.fbtx`, `.blkx`, `.ppi`) e cunoscut doar ca nume si locatie. Compatibilitatea binara cu ele nu face parte din aceasta lucrare.
