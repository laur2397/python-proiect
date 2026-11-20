# SPECIFICATIE 09 — ANEXE DE REFERINTA

Tabelele complete care lipseau din specificatie. Fara ele, produsul nu se poate construi 1:1: un programator nu poate inventa 100 de scurtaturi, nu poate ghici ce formate se deschid unde, si nu poate decide singur ce intra in fiecare editie.

Aceleasi marcaje de sursa: **D** = documentatie oficiala, **V** = observat in video, **K** = baza de cunostinte, **N** = adaugat de noi, **X** = diferit deliberat.

---

## ANEXA A — SCURTATURILE DE TASTATURA, COMPLETE

Patru ferestre, fiecare cu propriul set. **Aceeasi combinatie poate insemna altceva in alta fereastra** (de exemplu `Ctrl+R` deschide in OCR Editor din Lansator, dar recunoaste pagina in OCR Editor si sterge text si imagini in PDF Editor).

| ID | Cerinta | Src |
|---|---|---|
| X-200 | Scurtaturile ferestrei Lansator se implementeaza exact ca in tabelul A.1 | D |
| X-201 | Scurtaturile PDF Editor se implementeaza exact ca in tabelul A.2 | D |
| X-202 | Scurtaturile OCR Editor se implementeaza exact ca in tabelul A.3 | D |
| X-203 | Scurtaturile modulului de comparare se implementeaza exact ca in tabelul A.4 | D |
| X-204 | **Reatribuirea scurtaturilor se face numai din OCR Editor**, prin `View > Toolbars > Customize...`, tabul `Keyboard Shortcuts` | D |
| X-205 | Fluxul de reatribuire: se alege o categorie in `Categories`, o comanda in `Commands`, se apasa combinatia in campul `Press new shortcut key`, apoi `Assign`; combinatia apare in `Current shortcut`; `OK` salveaza | D |
| X-206 | `Reset` readuce la valorile livrate scurtaturile categoriei selectate; `Reset All` pe toate | D |
| X-207 | O combinatie deja folosita nu se poate atribui din nou fara eliberare | N |

### A.1 Fereastra Lansator (New Task)

| Comanda | Scurtatura |
|---|---|
| New PDF Document | `Ctrl+N` |
| Open PDF Document... | `Ctrl+O` |
| Open in OCR Editor... | `Ctrl+R` |
| Scan to OCR Editor | `Ctrl+S` |
| New OCR Project | `Ctrl+Shift+N` |
| Open OCR Project... | `Ctrl+Shift+O` |
| Options... | `Ctrl+>` |
| Exit | `Ctrl+Q` |
| Move Up | `Alt+Sus` |
| Move Down | `Alt+Jos` |
| Remove | `Del` |
| Select All | `Ctrl+A` |
| Find Recent Documents | `Ctrl+F` |
| Help | `F1` |

### A.2 PDF Editor

**Meniul File**

| Comanda | Scurtatura |
|---|---|
| New Task... | `Ctrl+N` |
| Open... | `Ctrl+O` |
| Save | `Ctrl+S` |
| Save as PDF Document... | `Ctrl+Shift+S` |
| Close Document | `Ctrl+W` |
| Print... | `Ctrl+P` |
| Options... | `Ctrl+>` |
| **Exit** | **`Ctrl+Alt+W`** |

**Meniul Edit**

| Comanda | Scurtatura |
|---|---|
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Y` |
| Cut | `Ctrl+X` |
| Copy | `Ctrl+C` |
| Copy Area as Image | `Ctrl+C` |
| Copy Area as Text | `Ctrl+Shift+C` |
| Copy Area as Table | `Ctrl+Alt+C` |
| Paste | `Ctrl+V` |
| Delete | `Del` |
| Select All | `Ctrl+A` |

**Meniul Document**

| Comanda | Scurtatura |
|---|---|
| Add Note | `Ctrl+M` |
| Highlight | `Ctrl+H` |
| Underline | `Ctrl+Shift+U` |
| Strikethrough | `Ctrl+K` |
| Insert Text | `Ctrl+J` |
| Search and Mark Up | `Alt+Shift+3` |
| Recognize Document | `Ctrl+Shift+R` |
| Add Bookmark... | `Ctrl+D` |
| Find... | `Ctrl+F` |
| Find Next | `F3` |

**Meniul Organize Pages**

| Comanda | Scurtatura |
|---|---|
| Add Blank Page | `Ctrl+Shift+B` |
| Add Pages from PDF... | `Ctrl+Shift+P` |
| Add Pages from File... | `Ctrl+Shift+O` |
| Add Pages from Scanner... | `Ctrl+Shift+K` |
| Rotate Pages Right | `Ctrl+Shift+>` |
| Rotate Pages Left | `Ctrl+Shift+<` |
| Correct Page Orientation | `Ctrl+Shift+/` |
| Crop Pages | `Ctrl+Shift+X` |
| Replace Pages | `Ctrl+Shift+E` |
| Move Pages | `Ctrl+Shift+M` |
| Delete Pages | `Ctrl+Backspace` |

**Meniurile Edit Content si Security**

| Comanda | Scurtatura |
|---|---|
| Add Link... | `Ctrl+L` |
| Redaction Mode | `Ctrl+Shift+H` |
| Erase Text and Pictures | `Ctrl+R` |

**Meniul View**

| Comanda | Scurtatura |
|---|---|
| Show Navigation Pane | `F5` |
| Pages | `Alt+Shift+1` |
| Bookmarks | `Alt+Shift+2` |
| Search | `Alt+Shift+3` |
| Attachments | `Alt+Shift+4` |
| Digital Signatures | `Alt+Shift+5` |
| Show Comments Pane | `F7` |
| Zoom In | `Ctrl++` |
| Zoom Out | `Ctrl+-` |
| Best Fit | `Ctrl+0` |
| Actual Size | `Ctrl+1` |
| Fit to Width | `Ctrl+2` |
| Go to Page Number... | `Ctrl+G` |
| Next Page | `Ctrl+Jos` |
| Previous Page | `Ctrl+Sus` |
| First Page | `Home` |
| Last Page | `End` |
| Back | `Alt+Stanga` |
| Forward | `Alt+Dreapta` |
| One-Page View | `Ctrl+5` |
| One-Page Scrolling | `Ctrl+6` |
| Two-Page View | `Ctrl+7` |
| Two-Page Scrolling | `Ctrl+8` |
| Full Screen | `F11` |

**Generale**

| Comanda | Scurtatura |
|---|---|
| Save Selected Pages | `Ctrl+Alt+S` |
| Help | `F1` |

### A.3 OCR Editor

**Meniul File**

| Comanda | Scurtatura |
|---|---|
| New Task... | `Ctrl+N` |
| Open Image... | `Ctrl+O` |
| Scan Pages... | `Ctrl+K` |
| Save Page Images As... | `Ctrl+Alt+S` |
| Close | `Ctrl+W` |
| New OCR Project | `Ctrl+Shift+N` |
| Open OCR Project... | `Ctrl+Shift+O` |
| Save OCR Project... | `Ctrl+Shift+S` |
| E-mail document | `Ctrl+M` |
| E-mail images | `Ctrl+Alt+M` |
| Print text | `Ctrl+P` |
| Print image | `Ctrl+Alt+P` |
| Exit | `Ctrl+Q` |

**Meniul Edit**

| Comanda | Scurtatura |
|---|---|
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Y` |
| Cut | `Ctrl+X` |
| Recognize and Copy Text | `Ctrl+C` |
| Copy Area as Image | `Ctrl+Shift+C` |
| Paste | `Ctrl+V` |
| Delete | `Del` |
| Select All | `Ctrl+A` |
| **Cancel Selection** | **`Ctrl+Shift+A`** |
| Delete Pages... | `Ctrl+Backspace` |
| **Delete Areas and Text** | **`Ctrl+Del`** |
| **Delete Text** | **`Ctrl+Shift+Del`** |
| Rotate Pages Right | `Ctrl+Shift+>` |
| Rotate Pages Left | `Ctrl+Shift+<` |
| Edit Page Images... | `Ctrl+I` |
| Find... | `Ctrl+F` |
| Find Next | `F3` |
| Replace... | `Ctrl+H` |

**Meniul View**

| Comanda | Scurtatura |
|---|---|
| Show Navigation Pane | `F5` |
| Show Zoom Pane | `Ctrl+F5` |
| **Image Pane Only** | **`F6`** |
| **Image and Text Panes** | **`F7`** |
| **Text Pane Only** | **`F8`** |
| Next Pane | `Ctrl+Tab` |
| Previous Pane | `Ctrl+Shift+Tab` |
| Zoom In | `Ctrl++` |
| Zoom Out | `Ctrl+-` |
| Best Fit | `Ctrl+0` |
| Go to Page Number... | `Ctrl+G` |
| Go to Next Page | `Ctrl+Jos` |
| Go to Previous Page | `Ctrl+Sus` |
| **Go to First Page** | **`Ctrl+Home`** |
| **Go to Last Page** | **`Ctrl+End`** |
| **Close Page** | **`Ctrl+F4`** |

**Meniul Recognize**

| Comanda | Scurtatura |
|---|---|
| Recognize All Pages | `Ctrl+Shift+R` |
| Recognize Page | `Ctrl+R` |
| Analyze All Pages | `Ctrl+Shift+E` |
| Analyze Page | `Ctrl+E` |
| Verify Text... | `Ctrl+F7` |
| Next Error | `Alt+Jos` |
| Previous Error | `Alt+Sus` |
| Mark Text as Verified | `Ctrl+T` |

**Meniul Area**

| Comanda | Scurtatura |
|---|---|
| Recognize Area | `Ctrl+Shift+B` |
| Change Area Type to Recognition Area | `Ctrl+1` |
| Change Area Type to Text | `Ctrl+2` |
| Change Area Type to Table | `Ctrl+3` |
| Change Area Type to Picture | `Ctrl+4` |
| Change Area Type to Barcode | `Ctrl+5` |
| Change Area Type to Background Picture | `Ctrl+6` |

**Meniul Tools**

| Comanda | Scurtatura |
|---|---|
| View Dictionaries... | `Ctrl+Alt+D` |
| Redaction Mode | `Ctrl+Shift+H` |
| **Hot Folder** | **`Ctrl+Shift+F`** |
| Options... | `Ctrl+>` |

**Generale**

| Comanda | Scurtatura |
|---|---|
| Bold pe textul selectat | `Ctrl+B` |
| Italic pe textul selectat | `Ctrl+I` |
| Underline pe textul selectat | `Ctrl+U` |
| Navigare intre celulele de tabel | tastele cu sageti |
| Focus pe panoul Pages | `Alt+1` |
| Focus pe panoul Image | `Alt+2` |
| Focus pe panoul Text | `Alt+3` |
| Focus pe panoul Zoom | `Alt+4` |
| Help | `F1` |

### A.4 Compararea documentelor

| Comanda | Scurtatura |
|---|---|
| New Comparison | `Ctrl+N` |
| Open Document... | `Ctrl+O` |
| Close Document | `Ctrl+W` |
| Save... | `Ctrl+S` |
| Exit | `Ctrl+Q` |
| Undo | `Ctrl+Z` |
| Redo | `Ctrl+Y` |
| **Select All Differences** | **`Ctrl+A`** |
| Zoom In | `Ctrl++` |
| Zoom Out | `Ctrl+-` |
| **Fit to Width** | **`Ctrl+0`** |
| Next Page | `Ctrl+Jos` |
| Previous Page | `Ctrl+Sus` |
| Compare Documents | `Ctrl+R` |
| **Next Difference** | **`Ctrl+Dreapta`** |
| **Previous Difference** | **`Ctrl+Stanga`** |
| **Ignore Difference** | **`Del`** |
| Help | `F1` |

---

## ANEXA B — FORMATELE SUPORTATE, TABELUL COMPLET

| ID | Cerinta | Src |
|---|---|---|
| Y-100 | Formatele se implementeaza exact dupa tabelul B.1: fiecare format are trei capabilitati distincte, nu una | D |
| Y-101 | **Un format poate fi acceptat la intrare in PDF Editor dar nu in OCR Editor, si invers.** Produsul nu trebuie sa ofere un format intr-un modul care nu il accepta | D |
| Y-102 | **CSV, FB2 si EPUB sunt numai formate de ieșire** | D |
| Y-103 | **GIF, SVG, XPS, `.ppt`, `.ods`, `.odp`, `.vsd`, `.vsdx` sunt numai formate de intrare** | D |
| Y-104 | **SVG se deschide numai in PDF Editor**, nu in OCR Editor, si nu se poate salva | D |
| Y-105 | **Desenele Visio (`.vsd`, `.vsdx`) se deschid in PDF Editor dar NU in modulul de comparare** | D |
| Y-106 | **XPS cere Microsoft .NET Framework 4** in original. Produsul nostru trebuie sa citeasca XPS fara aceasta dependenta, sau sa spuna clar ca nu il suporta | X |
| Y-107 | **Pentru editarea textelor intr-un format editabil, originalul cere versiunea corespunzatoare de Microsoft Office sau LibreOffice instalata.** Produsul nostru trebuie sa o faca cu biblioteci proprii | X |
| Y-108 | PDF-ul acceptat la intrare e **versiunea 2.0 sau mai veche, inclusiv PDF/A si PDF/UA** | D |
| Y-109 | Comparatia salveaza numai `*.pdf` si `*.docx` | D |
| Y-110 | **Pentru vizualizarea PDF-urilor rezultate e nevoie de o aplicatie de citire PDF; lista de diferente se vede deschizand panoul `Comments`** | D |
| Y-111 | Conformitatea PDF/A sau PDF/UA, cand e in metadate, se afiseaza in fereastra `Document Properties` | D |
| Y-112 | Produsul declara explicit, in interfata si in `/listformats`, ce format merge in ce modul | N |

### B.1 Tabelul

| Format | Extensii | Intrare OCR Editor | Intrare PDF Editor si Compare | Salvare |
|---|---|---|---|---|
| PDF document | `.pdf` | da | da | da |
| **Formate de text editabil** | | | | |
| Microsoft Word Document | `.doc`, `.docx` | nu | da | da |
| Microsoft Excel 97-2003 Workbook | `.xls`, `.xlsx` | nu | da | da |
| Microsoft PowerPoint Presentation | `.pptx` | nu | da | da |
| PowerPoint vechi | `.ppt` | nu | da | **nu** |
| Microsoft Visio Drawing | `.vsd`, `.vsdx` | nu | **numai PDF Editor, nu Compare** | nu |
| HTML Document | `.htm`, `.html` | nu | da | da |
| Rich Text Format | `.rtf` | nu | da | da |
| Text Document | `.txt` | nu | da | da |
| Comma-Separated Values | `.csv` | nu | **nu** | da |
| OpenDocument Text | `.odt` | nu | da | da |
| OpenDocument Spreadsheet | `.ods` | nu | da | **nu** |
| OpenDocument Presentation | `.odp` | nu | da | **nu** |
| FB2 Document | `.fb2` | nu | **nu** | da |
| EPUB Document | `.epub` | nu | **nu** | da |
| **Formate needitabile** | | | | |
| XPS (cere .NET Framework 4) | `.xps` | da | da | **nu** |
| DjVu Document | `.djvu`, `.djv` | da | da | da |
| **Imagini** | | | | |
| JPEG | `.jpg`, `.jpeg` | da | da | da |
| JPEG 2000 | `.jp2`, `.j2k`, `.jpf`, `.jpx`, `.jpc` | da | da | da |
| PNG | `.png` | da | da | da |
| TIFF | `.tiff`, `.tif` | da | da | da |
| BMP | `.bmp`, `.dib`, `.rle` | da | da | da |
| GIF | `.gif` | da | da | **nu** |
| JBIG2 | `.jbig2`, `.jb2` | da | da | da |
| PCX | `.dcx`, `.pcx` | da | da | da |
| SVG | `.svg` | **nu** | **numai PDF Editor** | **nu** |

---

## ANEXA C — LIMBILE

Aici exista o **contradictie in sursele oficiale ale ABBYY**, si specificatia trebuie sa o spuna, nu sa aleaga una la intamplare.

| ID | Cerinta | Src |
|---|---|---|
| P-100 | **Manualul de utilizare spune 201 limbi OCR; pagina de specificatii a produsului spune 198.** Documentatia avertizeaza ca limbile suportate pot diferi intre versiuni. Produsul nostru declara propriul numar, nu il copiaza | D |
| P-101 | **Manualul spune 37 de limbi de comparare; pagina de specificatii listeaza 40.** Aceeasi regula: declaram ce acoperim | D |
| P-102 | **53 de limbi au suport de dictionar**, dupa pagina de specificatii | D |
| P-103 | In manual, limbile cu dictionar sunt marcate cu asterisc; dictionarul permite semnalarea caracterelor nesigure si a greselilor de scriere | D |
| P-104 | Cele patru limbi artificiale: **Ido, Interlingua, Occidental, Esperanto** | D |
| P-105 | Limbile formale din manual: **Basic, C/C++, COBOL, Fortran, Java, Pascal, formule matematice simple, numere** | D |
| P-106 | Pagina de specificatii listeaza doua in plus: **transcrieri fonetice engleze si formule chimice simple** | D |
| P-107 | Cele 22 de limbi de interfata: bulgara, chineza simplificata, chineza tradiționala, ceha, daneza, olandeza, engleza, franceza, germana, greaca, maghiara, italiana, japoneza, coreeana, poloneza, portugheza (Brazilia), slovaca, spaniola, suedeza, turca, ucraineana, vietnameza | D |
| P-108 | Interfata localizata cere suportul de limba corespunzator in sistemul de operare | D |
| P-109 | Limba romana apare ca `Romanian` si `RomanianMoldavia` | V |
| P-110 | **Produsul nostru declara ca obiectiv minim: romana (ambele variante de diacritice), engleza, franceza, germana, italiana, spaniola, maghiara, si cifrele.** Restul se adauga pe masura ce exista modele verificate | X |
| P-111 | Lista limbilor active se vede in produs, nu intr-o brosura | N |
| P-112 | Pentru fiecare limba se declara dacă are dictionar, pentru ca verificarea ortografica depinde de asta | N |

---

## ANEXA D — FONTURILE NECESARE PER SCRIERE

Tabelul complet din manual nu se reproduce aici, pentru ca site-ul ABBYY restrange reutilizarea continutului. Ce conteaza pentru implementare sunt **grupele** si regula de fond.

| ID | Cerinta | Src |
|---|---|---|
| P-120 | **`Arial Unicode MS` e fontul de baza, listat pentru fiecare limba cu scriere neeuropeana.** In original vine cu Microsoft Office 2000 sau mai nou | D |
| P-121 | Grupa „numai Arial Unicode MS": abhaza, araba, armeana (orientala, occidentala, grabar), vietnameza, gagauza, idis, mari, osetina, thailandeza, udmurta, hakasa, hanti, ciuvasa, iakuta | D |
| P-122 | Grupa „plus Lucida Sans Unicode": avara, agula, adige, altaica, darghina, zulu, ingusa, kabardina, koriaca, laka, lezghina, mansi, tabasarana, hausa, cecena, ciukcea | D |
| P-123 | Grupa „plus Palatino Linotype": basmira, rusa cu ortografie veche, tadjica | D |
| P-124 | Grupa ebraica: plus **Aharoni, David, Levenim MT, Miriam, Narkisim, Rod** | D |
| P-125 | Grupa CJK: chineza simplificata si tradiționala, coreeana (inclusiv hangul), japoneza, plus familia **SimSun** (SimSun Founder Extended, SimSun-18030, NSimSun) si **Simhei, YouYuan, PMingLiU, MingLiU, Ming for-ISO10646, STSong** | D |
| P-126 | **Produsul nostru nu poate presupune Microsoft Office instalat.** Pentru scrierile neeuropene se livreaza un font Unicode liber (Noto Sans sau DejaVu Sans) si se declara ce acopera | X |
| P-127 | Setarea `Font used to display plain text` din tabul `Areas and Text` rezolva afisarea cand caracterele apar ca `?` sau patrate | D |
| P-128 | **Cand un proiect OCR a fost recunoscut sau editat pe alt calculator, textul se poate afisa greșit; cauza e un font lipsa.** Produsul trebuie sa detecteze si sa spuna care font lipseste, nu doar sa afiseze patrate | D |

---

## ANEXA E — DIFERENTELE INTRE EDITII

| ID | Cerinta | Src |
|---|---|---|
| Y-130 | **Corporate = Standard plus trei lucruri: Hot Folder, sarcinile automatizate si compararea documentelor.** Nimic altceva nu difera functional | K |
| Y-131 | Standard **nu** are procesare automatizata de documente | K |
| Y-132 | Standard **nu** are compararea documentelor | K |
| Y-133 | Produsul nostru nu are editii. **Toate functiile sunt disponibile.** Marcajele `C` din specificatii arata doar ce era rezervat Corporate in original | X |
| Y-134 | Daca se introduc totusi editii, singura linie de separare care are sens e cea a originalului: automatizare si comparare | N |
| Y-135 | Varianta pentru Mac a originalului e un produs separat, mai mic, fara Hot Folder. **Nu e referinta pentru specificatia noastra** | D |
| Y-136 | Perioada de proba a originalului: functionalitate Corporate, **7 zile sau 100 de pagini salvate dupa OCR, inclusiv prin Hot Folder** | D |
| Y-137 | Produsul nostru nu are perioada de proba | X |
| Y-138 | FineReader PDF 16 a adaugat fata de 15: interfata in stil ribbon, unealta `Organize Pages`, aplicatie pe 64 de biti, OCR imbunatatit, si **preprocesare interna cu clasificare de documente** | D |
| Y-139 | **Clasificarea de documente** e o functie pe care specificatia nu o acoperea deloc. Daca se implementeaza, intra in pipeline-ul de preprocesare, inainte de analiza de layout | N |
| Y-140 | Imprimanta virtuala: originalul a livrat `PDF-XChange 5.0` pentru FineReader PDF 15, **eliminata in versiunea 16 Release 3**. Deci nu e „functie care nu exista in original", ci functie retrasa | V |

---

## ANEXA F — MENIURILE COMPLETE

| ID | Cerinta | Src |
|---|---|---|
| A-200 | Lansatorul are meniurile `File`, `Edit`, `Tools`, `Help` | V |
| B-200 | **PDF Editor nu are bara de meniu clasica: are un buton hamburger in stanga si cinci tab-uri de ribbon** — `Document`, `Organize Pages`, `Edit Content`, `Security`, `Form Editor` | V |
| B-201 | In dreapta sus a PDF Editor: rotita de setari, semnul intrebarii, si un buton care restrange ribbonul | V |
| B-202 | Pe randul al doilea, in dreapta: `Undo`, `Redo`, si butonul `Comments (N)` care comuta panoul de comentarii si arata numarul lor | V |
| J-300 | OCR Editor are bara de meniu clasica, cu `File`, `Edit`, `View`, `Recognize`, `Area`, `Tools`, `Help` | D |
| J-301 | In dreapta sus a OCR Editor: rotita de setari si semnul intrebarii | V |
| R-300 | Modulul de comparare are meniurile `File`, `Edit`, `View`, `Compare`, `Help` | D |
| J-302 | Meniul `Tools` din OCR Editor are exact aceasta structura, cu separatoare: `View Dictionaries...` (`Ctrl+Alt+D`), `Pattern Editor...`, `Style Editor...` — separator — `Redaction Mode` (`Ctrl+Shift+H`) — separator — `Automated Tasks`, `Hot Folder` (`Ctrl+Shift+F`), `Compare Documents`, `Screenshot Reader` — separator — `Options...` (`Ctrl+>`) | V |
| B-203 | Tabul `Document`: `New Task`, `Open`, `Save`, `Save As ▾`, `Print`, `E-mail`, `Note`, `Draw ▾`, `Highlight`, `Underline`, `Strikethrough`, `Insert Text`, `Add Stamp ▾`, `Recognize ▾`, `Compare`, **`Select`**, **`Hand`** | V |
| B-204 | Tabul `Organize Pages`: `Selected pages: [... ▾]`, cos de stergere, roteste stanga, roteste dreapta, corecteaza orientarea, `Crop`, `Add Pages ▾`, `Move`, `Replace`, `Split`, `Delete Blank Pages`, `Recognize ▾`, `Enhance`, `Save As ▾` | V |
| B-205 | Tabul `Edit Content`: `Header and Footer ▾`, `Picture`, `Add Text`, combo font, combo marime, `A+`, `A-`, `B`, `I`, `U`, patru alinieri, **directie text**, spatiere randuri, spatiere paragraf, culoare `A ▾` | V |
| B-206 | Tabul `Security`: `Signature ▾`, `Password Security`, `Watermark ▾`, `Erase`, `Redact`, `Delete Objects and Data...`, **`Select`**, **`Hand`** | V |
| B-207 | Tabul `Form Editor`: `Text Field`, `Check Box`, `Radio Button`, `Drop-down List`, `List Box`, `Button`, `Signature Field` | D |
| B-208 | Bara verticala din stanga PDF Editor, circa 30 px, cinci iconuri: `Pages`, `Bookmarks`, `Search`, `Attachments`, `Digital Signatures` | V |
| B-209 | Bara de jos a PDF Editor: sageata sus, sageata jos, `N / M`, combo de potrivire, comutator de mod de vizualizare, combo de zoom, `-`, `+` | V |

---

## ANEXA G — CE SE IA IN SEAMA INAINTE DE OCR

Secțiune de referinta din manual, pe care specificatia nu o avea. Fiecare rand e un factor care trebuie detectat si, cand e cazul, semnalat utilizatorului.

| ID | Factor | Ce trebuie sa faca produsul | Src |
|---|---|---|---|
| N-100 | Rezolutia imaginii | 300 dpi e tinta; **se semnaleaza sub 250 dpi, peste 600 dpi, si rezolutiile nestandard**; rezolutia orizontala si cea verticala trebuie sa coincida | D |
| N-101 | Tipul de tipar | se detecteaza automat in modul `Auto`; `Typewriter` pentru litere de latime egala; `Fax` pentru zgomot si distorsiune | D |
| N-102 | Calitatea tiparului | textul prea subtire sau prea gros se corecteaza din luminozitate sau prin trecerea pe gri | D |
| N-103 | Numarul de limbi | **cu cat mai multe limbi, cu atat recunoasterea e mai lenta.** Se semnaleaza peste trei limbi | D / V |
| N-104 | Modul de culoare | gri e cel mai bun pentru OCR; alb-negru nu se recomanda pentru fotografii, pagini de revista si texte CJK | D |
| N-105 | Orientarea paginii | se detecteaza si se corecteaza automat; o pagina fara text rămâne neschimbata | D |
| N-106 | Inclinarea | se detecteaza si se corecteaza; butonul de corectie apare numai pe paginile inclinate | D |
| N-107 | Pagini alaturate | se impart automat dacă opțiunea e activa; **paginile scanate invers nu se impart automat** | D |
| N-108 | Scriere complexa | araba, ebraica, idis, thailandeza, chineza, japoneza, coreeana cer fonturi si uneori suport de sistem | D |
| N-109 | Text amestecat CJK si european | se dezactiveaza corectarea orientarii si impartirea paginilor alaturate | D |
| N-110 | Scriere gotica | se foloseste numai limba gotica, nu in combinatie cu una moderna | D |

---

## ANEXA H — DEPANARE: CE SPUNE PRODUSUL CAND NU MERGE

Manualul are secțiuni de tipul „dacă nu merge X". Fiecare e, de fapt, o cerinta de comportament: produsul trebuie sa detecteze situația si sa spuna cauza, nu sa eșueze in silenta.

| ID | Simptom | Cauza si ce afiseaza produsul | Src |
|---|---|---|---|
| Y-200 | Cautarea sau copierea nu functioneaza intr-un PDF scanat | recunoasterea in fundal nu a rulat sau limbile OCR sunt greșite. **Mesajul trimite la setul de limbi** | D |
| Y-201 | Recunoasterea in fundal nu porneste deloc | procesor cu un singur nucleu. Functia se dezactiveaza cu mesaj, nu in silenta | D |
| Y-202 | Caracterele neeuropene apar ca `?` sau patrate in panoul `Text` | fontul de afisare nu conține caracterele. **Se sugereaza `Font used to display plain text`** | D |
| Y-203 | Textul unui proiect deschis pe alt calculator se afiseaza greșit | fonturi lipsa. Produsul **numeste fontul lipsa** | D |
| Y-204 | Fontul folosit in textul recunoscut e greșit | se schimba din stilul textului, **fara a relua recunoasterea** | D |
| Y-205 | Textul vertical sau inversat nu se recunoaste | se seteaza `Direction of CJK text` sau `Inversion` pe zona | D |
| Y-206 | Un scaner nu apare in lista de dispozitive | **„verificati dacă e conectat la calculator si pornit"** | D |
| Y-207 | O limba nu apare in lista | nu e suportata, sau a fost exclusa la instalarea personalizata | D |
| Y-208 | Structura unui tabel nu se detecteaza | se deseneaza manual zona de tabel si se apasa `Analyze table structure`; se pot adauga separatoare manual | D |
| Y-209 | Comenzile din meniul contextual al Explorer lipsesc | se reinstaleaza componenta din `Programs and Features > Change` | D |
| Y-210 | Add-in-ul de Office nu apare | se activeaza din `File > Options > Add-ins > COM Add-ins > Go...` | D |
| Y-211 | Un fisier din Hot Folder nu se proceseaza | e deja in evidenta fisierelor procesate, sau e inca in copiere, sau a depasit numarul de reincercari | D / N |
| Y-212 | O sarcina Hot Folder nu porneste | **calculatorul era oprit sau utilizatorul deconectat.** Produsul spune asta explicit in jurnal | D |
| Y-213 | Limita de pagini a Hot Folder atinsa | mesajul spune limita si cand se reseteaza | D |
| Y-214 | Editarea continutului nu e disponibila | textul paginii e grafica vectoriala | D |
| Y-215 | Un font apare in paranteze patrate | e incorporat in PDF dar neinstalat; trebuie instalat ca sa poata fi folosit la scriere | D |
| Y-216 | Textul exportat e neclar | **MRC si PreciseScan pot face textul neclar; dezactivarea lor rezolva** | V |
| Y-217 | Rezultatul copiat difera de imagine | limbile OCR sau un strat de text slab. Se inlocuieste stratul si se reia | D |
| Y-218 | Casetele nu se pot redimensiona in Word | modul `Exact copy` le fixeaza; pentru editare se foloseste `Editable copy` | V |
| Y-219 | Un fisier DOCX de comparare conține erori | **e o versiune recunoscuta; avertismentul e obligatoriu inainte de salvare** | D |
| Y-220 | Zonele nu se recunosc corect | zonele nu trebuie sa se suprapuna; pentru text peste imagine se foloseste tehnica cu `Background Picture` dedesubt si zone `Text` deasupra | V |

---

## Ce rămâne in afara anexelor

- **Lista nominala a celor 198 sau 201 de limbi** si tabelul de fonturi, rand cu rand, nu se reproduc aici: sunt continut al ABBYY, iar site-ul le restrange reutilizarea. Produsul trebuie sa isi declare propria lista.
- **Lista completa de functii pe editii** exista intr-o brosura ABBYY cu revizii periodice. Linia de separare functionala e in Anexa E; detaliile comerciale nu ne privesc.
- **Cifrele de limbi se contrazic intre manual si pagina de specificatii.** Nu am ales una: le-am notat pe amandoua, cu sursa.
