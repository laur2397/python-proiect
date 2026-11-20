# SPECIFICATIE 10 — INTERFATA, LA NIVEL DE ELEMENT

**De ce exista acest fisier.** La runda a treia am rescris SPEC_01, SPEC_02 si SPEC_03 ca sa integrez corectiile din manualul oficial. Rescrierea a adus cerintele la zi, dar a si sters detaliu de interfata valid, cules in rundele anterioare din 22 de tutoriale video analizate cadru cu cadru. Fisierul de aici il pune inapoi si il completeaza.

**Regula pe care o aplic de acum:** se adauga prin apendare, nu prin rescriere. Un fisier nou nu poate sterge cerinte dintr-unul existent.

Marcaje de sursa ca in celelalte: **D** = documentatie oficiala, **V** = observat pe ecran in video, **K** = baza de cunostinte, **N** = adaugat de noi, **X** = diferit deliberat.

Cerintele de aici sunt **de nivel de interfata**: cum arata si cum se comporta elementele. Ele completeaza cerintele functionale din SPEC_01–03, nu le inlocuiesc.

---

## A. LANSATOR — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| A-300 | Lista de sarcini din stanga | elementul selectat are fundal albastru deschis **si o bara verticala albastra in marginea din stanga** | V |
| A-301 | Gruparea cardurilor pe tabul `Open` | doua secțiuni cu titlu: **`Open and Edit`** cu doua carduri mari (`PDF Document — View, search, and print` si `OCR Editor — Advanced conversion and verification`), si **`Convert to`** cu patru carduri patrate (PDF, Microsoft Word, Microsoft Excel, Other Formats) | V |
| A-302 | Aspectul cardurilor | carduri albe cu colturi rotunjite pe fundal gri-albastrui deschis; la hover apare chenar albastru | V |
| A-303 | Tabul `Compare` | secțiunea `Compare Documents` cu un card `Compare — Compares two versions of the same document`, si secțiunea `Recent Comparisons` ca panou alb mare | V |
| A-304 | Dialogul de alegere a fisierelor | dialog Windows standard, cu titlu de forma `Select Files to Convert to PDF` si filtru `All supported formats` | V |
| A-305 | Ecranul de conversie | buton `< Back` sus-stanga; coloana de setari in stanga, circa 190 px; lista de fisiere in dreapta | V |
| A-306 | Toolbarul listei de fisiere | patru butoane cu icon si eticheta dedesubt: `Add File`, `Remove`, `Move Up`, `Move Down`. **Gri cand nu e selectat nimic** | V |
| A-307 | Lista de fisiere | icon dupa tip de fisier plus numele; elementul selectat are fundal albastru deschis | V |
| A-308 | Dialogul `Custom Settings` pentru calitatea imaginii | **se deschide din `Image quality > Custom...`** | V |
| A-309 | Secțiunea `Resolution` din acel dialog | bifa `Reduce original resolution if required` cu trei valori radio: **300 dpi, 150 dpi, 96 dpi** | V |
| A-310 | Secțiunea `Color control` | combo cu valoarea `Do not change image color` | V |
| A-311 | Secțiunea `Quality` | combo cu `Quality loss allowed` sau **`Quality loss not allowed`**; cand e `not allowed`, **sliderul de calitate se dezactiveaza** | V |
| A-312 | Codecurile afisate in acel dialog | text informativ: pentru imagini gri si color **JPEG, ZIP, LZW, J2K**; pentru alb-negru **CCITT, JBIG2 (fara pierderi)** | V |
| A-313 | Sliderul de calitate | arata procentul curent, de forma `Quality (45%)` | V |
| A-314 | Butonul `Reset` din dialogul `Custom Settings` | readuce valorile livrate | V |
| A-315 | Dialogul de progres la conversie | titlu `Conversion`; linia de stare de forma `Converting to searchable PDF...`; linia de fisier de forma `Processing the file: <nume>`; bara de progres; contorul `N of M files processed`; buton `Cancel` | V |
| A-316 | Butonul `Rate This Product` | exista in original, in dreapta sus. **Nu se implementeaza** | X |

---

## B. PDF EDITOR — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| B-300 | **Unealta `Select`** | unealta implicita. Permite selectia de text si marcarea de zone. **Lipsea complet din specificatie** | V |
| B-301 | **Unealta `Hand`** | muta pagina prin tragere. Apare pe tabul `Document` si pe tabul `Security` | V |
| B-302 | Tragerea paginii cu tasta spatiu | tasta spatiu tinuta apasata comuta temporar pe `Hand` | N |
| B-303 | Butonul hamburger | in stanga tab-urilor; deschide meniul principal, pentru ca **PDF Editor nu are bara de meniu clasica** | V |
| B-304 | Butonul de restrangere a ribbonului | in dreapta sus, lângă rotita si semnul intrebarii | V |
| B-305 | Butonul `Comments (N)` | pe randul al doilea, in dreapta; **arata numarul de comentarii** si comuta panoul; evidentiat cand panoul e deschis | V |
| B-306 | Bara de jos | sageata sus, sageata jos, contorul `N / M`, combo de potrivire, comutator de mod de vizualizare, combo de zoom cu procent, `-`, `+` | V |
| B-307 | Panoul `Pages`, latime | circa 120 px | V |
| B-308 | Toolbarul panoului `Pages` | roteste stanga, roteste dreapta, si un buton `...` cu restul comenzilor | V |
| B-309 | Miniaturile din panoul `Pages` | chenar, numarul paginii dedesubt, **o insigna mica albastra in colțul din stanga-jos** care marcheaza existenta stratului de text; pagina curenta are fundal gri | V |
| B-310 | Meniul contextual al panoului `Pages` | conține toate operatiile de pagina din tabul `Organize Pages` | V |
| B-311 | Fundalul zonei de pagina | gri deschis, pagina centrata | V |
| B-312 | Blocurile in modul de editare | toate blocurile capata un contur subtire roz-mov; blocul activ capata manere | V |
| B-313 | Imaginea trasa in modul de editare | suprapunere albastra semitransparenta cu manere; **locul vechi rămâne marcat cu un dreptunghi punctat** | V |
| B-314 | Imaginea selectata | opt manere | V |

---

## C. CAUTARE SI COPIERE — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| C-100 | Panoul de cautare, latime | circa 190 px, sub bara verticala de iconuri | V |
| C-101 | Tab-urile panoului | text cu majuscule, `FIND | REPLACE | REDACT`, cel activ subliniat albastru, plus un `X` de inchidere in dreapta | V |
| C-102 | Campul `Find what:` | lângă el un icon de rotita cu sageata, care deschide opțiunile de potrivire; campul are un `X` de golire | V |
| C-103 | Butonul `Replace` | aliniat la dreapta, **gri pana exista rezultate selectate** | V |
| C-104 | Navigarea | sagetile `<` si `>`, aliniate la stanga | V |
| C-105 | Arborele de rezultate | nod pliabil cu numarul de rezultate, de forma `Document Text (58)`; fiecare rezultat e un fragment de context cu **potrivirea evidentiata galben**, cu numarul paginii aliniat la dreapta | V |
| C-106 | Bifa pe fiecare rezultat | fiecare rezultat are caseta proprie; bifa pe nodul parinte le bifeaza pe toate | V |
| C-107 | Rezultatul selectat | fundal albastru deschis | V |
| C-108 | Evidentierea in pagina | **toate aparitiile se evidentiaza galben simultan**, nu doar cea curenta | V |
| C-109 | Bara de stare a panoului | `Found: N`, iar cand nu exista rezultate mesajul centrat `No matches found` | V |
| C-110 | Dupa inlocuire | contorul devine `Found: 0` si apare mesajul de lipsa | V |
| C-111 | Combo-ul de cuvinte cheie din tabul `REDACT` | afiseaza numele listei ca un chip, cu sageata; textul initial e de forma `Type text or select Keyw...` | V |
| C-112 | Zona de copiat | dreptunghi punctat tras cu unealta `Select` | V |
| C-113 | Grila detectata la copierea unui tabel | linii albastru-mov; celula selectata evidentiata mov | V |
| C-114 | **Toolbarul plutitor de tabel, noua iconuri** | copiaza, adauga separator orizontal, adauga separator vertical, sterge separatoare, imparte celule, uneste celule, uneste randuri, selectie, si `Analyze table structure` cu sageata | V |
| C-115 | Poziția toolbarului de tabel | plutitor, sub zona selectata | V |

---

## D. COMENTARII SI STAMPILE — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| D-100 | Panoul `Comments`, latime | circa 150 px | V |
| D-101 | Antetul panoului | titlul `Comments` plus `X` de inchidere | V |
| D-102 | Campul de filtrare | `Comment text filter`, cu icon de lupa | V |
| D-103 | Randul de controale | `<` si `>` de navigare, `AZ ▾` de sortare, palnie de filtrare cu sageata, si un buton de opțiuni | V |
| D-104 | Fiecare comentariu in lista | icon colorat dupa tipul adnotarii, data si pagina de forma `Today 19:02  Page 2`, caseta de bifa in dreapta, campul de text cu text sugerat `Enter your comment`, si linkul `Add Reply` | V |
| D-105 | Comentariul selectat | fundal albastru deschis | V |
| D-106 | Culorile implicite de marcare | evidentierea apare portocalie sau galbena, taierea cu linie rosie; selecția capata chenar albastru | V |
| D-107 | Stampila text implicita | exemplul din original e `Final` cu data si ora completate automat | V |
| D-108 | Dialogul de stampila din imagine | campurile `Name`, butoanele `Open` si `Paste from Clipboard`, **un slider de dimensiune a stampilei**, si `Save` | D |
| D-109 | Dialogul de stampila text | `Name`, `Stamp text`, combo `Add Date/Time`, grupul de font si chenar, bifa `Add border`, previzualizare, `Save` | D |
| D-110 | Inserarea elementelor in stampila | la poziția cursorului din campul de text, nu la sfarsit | D |

---

## E. ORGANIZE PAGES — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| E-100 | Grila de miniaturi | patru sau cinci coloane de miniaturi mari, pe fundal gri | V |
| E-101 | Pagina selectata | fundal albastru deschis rotunjit, **cu numarul paginii pe o eticheta albastra** | V |
| E-102 | **Selectia prin cadru** | tragere peste miniaturi selecteaza tot ce atinge cadrul. **Lipsea din specificatie** | V |
| E-103 | Campul `Selected pages` | editabil, cu sageata de dropdown; se actualizeaza la selectia cu mouse-ul, de forma `2, 5` | V |
| E-104 | Mini-toolbarul la hover | plutitor vertical in colțul din dreapta-sus al miniaturii, **trei iconuri**: sterge, roteste stanga, roteste dreapta | V |
| E-105 | Pagina trasa in timpul reordonarii | semitransparenta | V |
| E-106 | Indicatorul de inserare | icon de pagina albastru, intre miniaturi | V |
| E-107 | **Sliderul de zoom al miniaturilor** | in dreapta jos, de forma `-  ---o---  +` | V |
| E-108 | Dialogul `Add Pages from File` | dialog Windows extins cu o zona proprie: bifa `Select pages (e.g. 2,3,5-7)` plus un camp de interval, si filtru de tip de fisier | V |
| E-109 | Dialogul `Blank Pages` | miniaturi cu chenar albastru pe cele selectate pentru stergere, numerele paginilor, zoom `-` si `+` in stanga jos, butoanele `Delete selected pages` si `Cancel` | V |
| E-110 | Dialogul `Split Document`, contorul | `Total files: N`, recalculat la fiecare schimbare de metoda | V |
| E-111 | Exemplul de nume in dialogul de impartire | de forma `Example: 01_Bookmark.pdf`, actualizat live | V |
| E-112 | Bifa `Same as source folder` | cand e pusa, **campul de cale se dezactiveaza** | V |

---

## F. EDIT CONTENT — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| F-100 | Blocul activ | chenar subtire cu manere, plus un cursor de mutare in colt | V |
| F-101 | Fontul detectat | se afiseaza in combo-ul de font imediat ce cursorul intra in bloc | V |
| F-102 | Combo-urile de font si marime | gri cand nu e selectat nimic | V |
| F-103 | Manerele blocurilor | mici, albastre, la colturi si la mijlocul laturilor | V |
| F-104 | Reflow-ul textului | textul se reaseaza in limitele blocului in timp ce se tasteaza | V |
| F-105 | Marimea fontului | intre 1 si 1638 pt | V |
| F-106 | Butoanele `A+` si `A-` | cresc si scad marimea cu un pas | V |
| F-107 | Cele patru alinieri | stanga, centru, dreapta, justify | V |
| F-108 | **Comutatorul de direcție a textului** | de la stanga la dreapta sau de la dreapta la stanga. **Lipsea din specificatie** | V |
| F-109 | Spatierea randurilor si a paragrafelor | doua controale separate in bara | V |
| F-110 | Butonul de culoare a textului | `A` cu sageata de paleta | V |

---

## G. SECURITATE — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| G-100 | Bara de culori in modul `Redact` | centrata deasupra paginii. **Manualul spune sapte casete de culoare; in interfata se vad opt** (rosu, portocaliu, galben, verde, turcoaz, albastru, mov, negru), plus o sageata pentru restul culorilor. Produsul trebuie sa fie configurabil, nu sa fixeze numarul | D / V |
| G-101 | Culoarea implicita de redactare | negru, selectat | V |
| G-102 | Textul redactat pe pagina | dreptunghiuri negre pline | V |
| G-103 | Butonul `Redact` ca comutator | activ = fundal albastru deschis | V |
| G-104 | **Motivele predefinite din combo-ul `Reason`** | cinci, editabile: „sunt autorul acestui document", „sunt de acord cu partile semnate ale acestui document", „am inspectat acest document", „am aprobat acest document", „am verificat integritatea acestui document". **Specificatia spunea doar „motiv predefinit"** | V |
| G-105 | Previzualizarea semnaturii | mare, in dialog, cu textul de forma `Digitally signed by <nume> / Reason / Date / Application version: <produs>` | V |
| G-106 | Bifele de aspect ale semnaturii | `Reason`, `Location`, `Contact`, `Date`, `Owner information`, `Application version` | V |
| G-107 | Semnatura pe pagina | dreptunghi albastru-gri cu textul semnaturii | V |
| G-108 | Panoul `Digital Signatures` | status in verde, de forma `Valid`, plus numele si data si ora | V |
| G-109 | Dialogul `Document Properties`, formatul valorilor | dimensiunea de forma `53.39 KB (54673 Bytes)`; dimensiunea paginii de forma `21.00 x 29.70 cm`; `Tagged PDF: No`; `Fast Web View: No` | V |
| G-110 | Butonul `Signature ▾` | dropdown cu semnatura digitala, text si imagine | V |
| G-111 | Dialogul `Delete Objects and Data` din PDF Editor | **sase bife**: `Hidden text and objects` (cu avertismentul `The document will be converted to image-only PDF.`), `Comments and markup`, `Links, media, actions, scripts, and form data`, `Bookmarks`, `Attachments`, `Metadata`; butoanele `Apply` si `Cancel`. **Dialogul din setarile de format are numai patru** | V |

---

## H. FORMULARE — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| H-100 | Banda de detectie a formularului | bara galbena sub ribbon, cu textul `This document contains interactive form fields.`, bifa `Highlight fields`, si `X` de inchidere in dreapta | V |
| H-101 | Randarea unui camp in modul de editare | dreptunghi albastru deschis semitransparent, **cu o eticheta neagra care arata numele campului in colțul din dreapta-sus** | V |
| H-102 | Randarea campului de semnatura | chenar punctat, **eticheta portocalie `Sign`**, si un simbol in mijloc | V |
| H-103 | Cursorul la desenarea unui camp | semnul `+` | V |
| H-104 | **Lacatul de proporții** | intre campurile `Width` si `Height`, in tabul `General`. **Lipsea din specificatie** | V |
| H-105 | Campurile numerice | spinbox cu sageti sus si jos | V |
| H-106 | Campul `Max Number of Symbols` | **gri pana se bifeaza caseta de activare**; valoarea sugerata in original e 250 | V |
| H-107 | Nota din dialogul de actiune `Send form` | textul `All form fields will be sent.` | V |
| H-108 | Formatele din `File Format` la `Send form` | `PDF file`, plus `HTML` si `XFDF` | V |
| H-109 | Numele generate automat | de forma `TextField 3`, `Checkbox 1`, `List Box 1`, `Button 1` | V |
| H-110 | Ghidajele de aliniere | linii mov; `Ctrl` tinut apasat le ascunde | V |

---

## J. OCR EDITOR — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| J-400 | Titlul ferestrei | de forma `<nume proiect> - <produs> OCR Editor`; pentru un proiect nou, `Untitled project [N]` | V |
| J-401 | **Ordinea exacta a barei principale** | `+ New Task`, doua iconuri de proiect (nou si deschide), `Open`, `Scan`, contorul `[ N / M ]` cu sageti sus si jos, `Recognize`, combo de limba, `Undo`, `Redo`, butonul de salvare cu sageata, combo de mod de layout, **doua butoane de comutare a aranjarii panourilor**, `Verify`, si doua iconuri de eroare urmatoare si anterioara | V |
| J-402 | **Butonul de salvare isi schimba iconul si eticheta dupa formatul ales** | PDF arata un icon rosu cu `Save`; Word un icon albastru `W` cu `Save`; trimiterea catre o aplicatie arata `Send` | V |
| J-403 | Panoul `Pages`, latime | circa 95 px | V |
| J-404 | **Toolbarul panoului `Pages`** | salveaza, sterge, roteste stanga, roteste dreapta, si `...` | V |
| J-405 | **Insigna de stare pe miniatura** | icon mic in colțul din stanga-jos, care arata starea paginii: neprocesata, analizata, recunoscuta, verificata | V |
| J-406 | **Triunghiul de avertisment pe miniatura** | in colțul din dreapta-jos, cand pagina are avertismente | V |
| J-407 | **Tooltipul miniaturii** | arata starea, utilizatorul care a deschis pagina si calculatorul lui, si fisierul sursa, de forma `Recognized / Opened by: <utilizator> (<calculator>) / Source: <fisier>`. **Util la lucrul in grup** | V |
| J-408 | Miniatura selectata | chenar albastru | V |
| J-409 | **Panourile `Pages` si `Zoom` se pot muta** | la stanga sau la dreapta; bara verticala de iconuri se muta cu ele | V |
| J-410 | **Toolbarul panoului `Image`, randul 1** | `Edit Image`, `Save Page`, separator, **`Select`**, **`Hand Tool`**, `Delete`, **`Reorder`** | V |
| J-411 | Toolbarul panoului `Image`, randul 2 | `Recognize Page`, `Analyze Page`, separator, `Text`, `Picture`, `Table`, `Background Picture`, `Recognition Area` | V |
| J-412 | Unealta de zona activa | fundal albastru deschis in toolbar | V |
| J-413 | **Banda pentru PDF cu strat de text** | in dreapta toolbarului panoului `Image` apar textul `This PDF file contains a text layer` si butonul `PDF recognition mode ▾`. **Apare numai pentru PDF-urile care au strat de text** | V |
| J-414 | **Bara de proprietati de sub panoul `Image`, cu doua tab-uri** | `Area Properties` si `Image Properties` | V |
| J-415 | **Continutul tabului `Image Properties`** | `Width x height: <N> x <N> pixels`, `Resolution: [<N>] dpi`, `Color mode: <mod>`, formatul fisierului, si `Source image: <cale completa>` | V |
| J-416 | Bara de jos a panoului `Image` | comutatorul `Zoom Pane`, iconuri de aranjare, **patru moduri de potrivire: lista, potrivire pe latime, potrivire pe inaltime, potrivire pe pagina**, combo de zoom cu procent, `-`, `+` | V |
| J-417 | Bara de jos a panoului `Text` | iconuri de aranjare plus combo de zoom propriu | V |
| J-418 | Panoul `Zoom` | are propriul procent de zoom, independent | V |
| J-419 | Indicatorul de avertismente | icon de triunghi galben in colțul din stanga-jos al ferestrei | V |
| J-420 | Butonul `Verify` | gri cand nu exista caractere nesigure | V |

---

## L. IMAGE EDITOR — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| L-100 | Antetul | textul `Image Editor` plus butonul `< Exit Image Editor` | V |
| L-101 | Panoul de unelte | lista verticala in dreapta, **cu cele 14 unelte in aceasta ordine**: `Recommended Preprocessing`, `Deskew`, `Straighten Text Lines`, `Photo Correction`, `Correct Trapezoid Distortion`, `Rotate & Flip`, `Split`, `Crop`, `Invert`, `Resolution`, `Brightness & Contrast`, `Levels`, `Eraser`, `Remove Color Marks` | V |
| L-102 | **Unealta aleasa se expandeaza inline**, sub numele ei | nu se deschide un dialog separat | V |
| L-103 | Parametrii inline ai uneltei `Crop` | `Paper size:` combo; `Size:` doua campuri, latime si inaltime; `Offset:` doua campuri, X si Y; radio `Inches` sau `Millimeters`; `Selection:` combo; butonul `Crop` | V |
| L-104 | Bifa din partea de jos | `Show next page after operation completes` | V |
| L-105 | Fundalul imaginii in editor | gri inchis | V |
| L-106 | Selecția in editor | chenar albastru cu manere; zona taiata rămâne marcata punctat | V |
| L-107 | Grila de corectare a trapezului | grila albastra cu patru colturi care se trag pe colturile paginii, plus butonul `Correct` | V |
| L-108 | Histograma uneltei `Levels` | cursoare de intrare pentru negru, gri si alb, plus un cursor de iesire | V |
| L-109 | Toate operatiile se pot anula | istoricul include operatiile pe imagine | V |

---

## M. ZONE — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| M-100 | **Culorile zonelor difera intre versiunile originalului** | in versiunea 14 textul e verde si tabelul mov; in 15 textul e verde, imaginea roz, tabelul albastru-violet; in 16 textul e albastru, imaginea roz-magenta, tabelul verde. **Concluzia: culorile sunt configurabile si produsul nu trebuie sa le fixeze in cod** | V |
| M-101 | Setul implicit propriu | produsul alege propriul set implicit, documentat, si il expune in `Options > Areas and Text` | X |
| M-102 | Randarea unei zone | fundal translucid in culoarea tipului, plus chenar in aceeasi culoare mai saturata | V |
| M-103 | Numarul de ordine al zonei | intr-un patrat mic, **in colțul din stanga-sus in versiunea 16, in dreapta-sus in versiunea 15**. Produsul alege o poziție si o pastreaza | V |
| M-104 | Zona selectata | chenar mai gros, plus manere patrate la colturi si la mijlocul laturilor | V |
| M-105 | Zona in curs de desenare | chenar punctat, cursor `+` | V |
| M-106 | Desenarea pe diagonala | de la stanga-sus la dreapta-jos e cea mai rapida; produsul accepta orice direcție | V |
| M-107 | Zonele de text pot fi poligoane | prin adaugarea si scoaterea de segmente | V |
| M-108 | Uneltele contextuale de zona | `copy`, `add area part` (plus), `cut area part` (minus), `select`, si combo de tip | V |
| M-109 | Zona de tabel | grila de randuri si coloane desenata in culoarea tipului; celula selectata evidentiata | V |
| M-110 | **Tehnica straturilor** | se deseneaza intai o zona `Background Picture` peste toata pagina, apoi zone `Text` deasupra: textul se recunoaste, fundalul rămâne imagine. **Flux de lucru documentat, de suportat explicit** | V |
| M-111 | Modul `Reorder` | se intra din buton; se face clic pe zone in ordinea dorita; numerele se recalculeaza la fiecare clic | V |
| M-112 | Stergerea unei zone de imagine | o scoate si din textul recunoscut | V |

---

## O. PANOUL TEXT — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| O-100 | **Toolbarul panoului `Text`, randul 1** | combo de stil, combo de font, combo de marime, `A+`, `A-`, **`Ω` pentru inserarea unui simbol**, **buton de link**, si `Find` | V |
| O-101 | **Toolbarul panoului `Text`, randul 2** | `Style Editor`, separator, `B`, `I`, `U`, **exponent**, **indice**, separator, cele patru alinieri, spatiere, **liste**, si `Redaction` | V |
| O-102 | **Combo-ul de stil la selectie mixta** | arata o descriere compusa, de forma `Other + 21 pt, Not Bold` | V |
| O-103 | Panoul `Text` gol | mesajul `Page not recognized`, gri, centrat | V |
| O-104 | Separarea blocurilor in panoul `Text` | linii punctate intre blocuri | V |
| O-105 | **Caracterele nesigure** | fundal albastru deschis in versiunea 16. Culoarea e configurabila | V |
| O-106 | **Bara `Text Properties`, pe trei coloane** | coloana 1: `Style`, `Font`, `Size` cu `B`, `I`, `U`; coloana 2: `Language`, `Font color`, `Effects` cu exponent, indice, majuscule mici si majuscule; coloana 3: `Alignment`, `Background color`, `Scale`, `Spacing` | V |
| O-107 | Celulele de tabel in panoul `Text` | reconstruite cu linii; navigarea intre ele cu tastele cu sageti | V |
| O-108 | Re-recunoasterea unei singure zone | se poate face separat, fara a relua pagina | V |
| O-109 | Dialogul de verificare, butonul de simbol | deschide `More Symbols...` cu combo `Subset` si camp `Character code` | D |
| O-110 | Tabelul editorului de stiluri | coloanele `Style name`, `Font name`, `Font size`, `Scale`, `Spacing`, `B`, `I`, `Aa`, si **`Heading`**; coloana `Heading` e un combo cu `No` si `Heading 1` pana `Heading 10` | V |
| O-111 | Stilurile detectate automat | originalul detecteaza titluri si le atribuie stiluri de tip `Heading #N`; stilurile se pastreaza la export | V |

---

## Q. SALVARE — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| Q-100 | Dialogul `Save document as` | dialog Windows extins, cu `File name`, combo `Save as type`, **bifa `Open document after saving`**, butonul `Options...`, si **combo `Create a separate file`** pentru un fisier per pagina sau un singur fisier | V |
| Q-101 | Bifa `Open document after saving` | cand e pusa, fisierul se deschide in aplicatia asociata | V |
| Q-102 | Butonul `Options...` din dialogul de salvare | deschide tabul de setari al formatului ales | V |
| Q-103 | Setul de setari recomandat pentru PDF accesibil | calitate personalizata fara reducere de rezolutie, `Do not change image color`, `Quality loss not allowed`, MRC si PreciseScan, `Text under the page image`, `Create bookmarks from headings`, `Create PDF tags`, `Use Windows fonts`. **Produsul poate oferi acest set ca presetare** | V |
| Q-104 | Avertisment despre MRC si PreciseScan | **pot face textul neclar la export.** Produsul spune asta cand ambele sunt active | V |

---

## R. COMPARARE — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| R-400 | Titlul ferestrei | de forma `<fisier 1> / <fisier 2> - <produs> Compare Documents` | V |
| R-401 | Bara de sus a fiecarei zone | icon de folder sau `X`, calea fisierului intr-un combo, si **o sageata de dropdown cu documentele recente** | V |
| R-402 | Mesajul de incarcare | icon rotativ plus textul `Loading the document. Please wait...` | V |
| R-403 | Bara de jos a fiecarei zone | sageata sus, sageata jos, contorul de pagina, `-`, potrivire pe latime, `+`, si un icon de sincronizare | V |
| R-404 | Panoul din dreapta, latime | circa 170 px | V |
| R-405 | Tab-urile panoului | `Compare` si `Differences (N)`, cu numarul de diferente in eticheta | V |
| R-406 | Butonul `Compare` | mare, albastru, pe toata latimea panoului | V |
| R-407 | **Banda roșie de rezultat** | deasupra documentelor, cu textul `Differences found: N` | V |
| R-408 | Toolbarul tabului `Differences` | icon de Word plus `Save... ▾`, navigare jos, navigare sus, cos de ignorare, si un icon de grupare | V |
| R-409 | Grupurile pliabile | cu numarul lor, de forma `Body text (16)` si `Headers and footers (3)` | V |
| R-410 | **Formatul unei diferente in lista** | icon cu sageata, verde pentru adaugare si roșie pentru stergere; titlu in bold, `Text added`, `Text deleted` sau `Text edited`; numarul paginii aliniat la dreapta, de forma `Pg. 1` | V |
| R-411 | Diferenta de tip modificare | arata ambele versiuni, cu valoarea veche si cea nouă marcate distinct | V |
| R-412 | Diferenta selectata in lista | fundal gri-albastru | V |
| R-413 | Evidentierea in documente | diferentele apar in mov deschis; **diferenta curenta e subliniata roșu**; textul adaugat capata chenar albastru | V |
| R-414 | **Structura raportului Word** | tabel cu doua coloane; antetul conține caile celor doua fisiere, cu numele in bold; fiecare rand e o diferenta, scrisa de forma `[page N] <text>` in coloana documentului careia aparține; **o celula goala inseamna ca textul lipseste in acel document** | V |
| R-415 | Numele implicit al raportului | `Differences` | V |
| R-416 | Dialogul de progres la comparare | arata sfaturi si avertismente in timpul rularii | V |

---

## S. HOT FOLDER — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| S-200 | **Toolbarul ferestrei principale** | `New`, meniul de import si export, **`Start Now`**, **`Start on Schedule`**, `Stop`, `Modify`, `Copy`, `Delete`, doua comutatoare, si `Log` cu vizualizarea jurnalului | V |
| S-201 | Randul unei sarcini | icon de ceas, numele, calea, statusul, si ora urmatoarei porniri | V |
| S-202 | **Bara de stare** | textul `Pages remaining to recognize <N> / the limit to be renewed in <N> days`, plus un icon de informatie cu explicatia limitei | V |
| S-203 | Contorul de pagini | se decrementeaza dupa fiecare pagina procesata | V |
| S-204 | Dialogul `Task Settings` | campul `Task name` sus; in stanga paleta de pasi, grupata pe categorii; in dreapta pasii adaugati | V |
| S-205 | **Categoriile paletei de pasi** | `Schedule` cu `Run once` si `Recurring`; `Open` cu `File from folder`, `File from FTP`, `File from Outlook` si `OCR project`; `Process` cu `Process document`; `Save` cu `Save results ▾` | V |
| S-206 | **Dropdown-ul `Save results`, patru opțiuni** | `Save document`, **`Save to SharePoint`**, `Save images`, `Save OCR project`. **`Save to SharePoint` lipsea din specificatie** | V |
| S-207 | Pasii adaugati | pastile cu fundal albastru deschis in paleta; in dreapta, panouri pliabile cu antet de forma `Step N: <nume>` si un `X` de stergere | V |
| S-208 | Mesajul initial din dreapta | `Select task steps` | V |
| S-209 | Pasul de planificare recurenta | radio `Every minute`, `Every day`, `Every week`, `Every month`, plus un camp de ora cu spinner | V |
| S-210 | Pasul de preluare din Outlook | `Mail folder` cu `Browse...`, bifa `Include all subfolders`, combo `File type`, grup `Original files` cu `Keep in` sau `Move to` si `Browse`, si bifa `Copy to local folder` cu `Browse` | V |
| S-211 | **Combo-ul `File type`, lista exacta** | `All files`, `All image and PDF files`, `Bitmap`, `DCX`, `DjVu`, `GIF`, `JBIG2`, `JPEG 2000`, `JPEG`, `PCX`, `PDF`, `PNG`, `TIFF`, `WDP`, `XPS` | V |
| S-212 | Pasul de analiza si recunoastere | `Document language` cu buton `Edit...`; grup `Document processing settings` cu cele trei moduri; butoanele `Recognition Options...` si `Preprocessing Options...`; grup `Document analysis settings` cu `Automatically analyze areas` sau `Use the following area template` plus `Browse...` | V |
| S-213 | Grupul de pagini goale din pasul de procesare | bifa `Automatically delete blank pages` si bifa `Move deleted blank pages to the following folder` cu `Browse` | V |
| S-214 | **In Hot Folder paginile goale se sterg fara confirmare** | spre deosebire de PDF Editor si OCR Editor, unde se revizuiesc intai | V |
| S-215 | Pasul de salvare | combo `Save as` cu `Options...`; radio `Recognize text on images` sau `Convert to image-only PDF`; `Folder`; pentru SharePoint si retea, `Login`, `Password` si bifa `Use current user login and password`; combo `Output`; campul `File name` | V |
| S-216 | **Macrocomenzile pentru numele fisierului** | butoane care insereaza: **`[F]` numele originalului, `[X]` extensia originala, `[D]` data, `[T]` ora, `[#]` contorul de fisiere**; sub camp apare un exemplu live, de forma `Example: Document.pdf`. **Lipseau complet din specificatie** | V |
| S-217 | Butoanele de jos ale dialogului | linkul `Help`, butonul plin `Create Task`, si butonul cu contur `Cancel`; `Create Task` e gri pana cand sarcina e valida | V |

---

## T. SARCINI AUTOMATIZATE — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| T-100 | Dialogul `Task Settings` | in stanga panoul `Task steps`, in dreapta `Task name` si zona de configurare | V |
| T-101 | Grupul de proiect din panoul de pasi | eticheta `OCR project:` si trei butoane: `Create new OCR project`, `Select existing OCR project`, `Use current OCR project`; cel selectat are chenar albastru | V |
| T-102 | Grupurile urmatoare | `Open image or PDF` si `Scan`; apoi `Analyze`; apoi `OCR`; apoi `Save/Send ▾` | V |
| T-103 | Grupurile dezactivate | **gri pana se alege primul pas** | V |
| T-104 | Mesajul initial din dreapta | `Choose the first step` | V |
| T-105 | Butoanele de jos | `Help`, `Finish`, `Cancel` | V |
| T-106 | Pasul de analiza manuala | **sarcina se opreste si asteapta utilizatorul sa deseneze zonele** | V |
| T-107 | Sablonul de zone la rulare | se poate fixa in sarcina sau se poate cere la fiecare pornire | V |

---

## V. SCREENSHOT READER — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| V-100 | Fereastra | mica, plutitoare, cu titlul produsului plus semnul intrebarii si `X` | V |
| V-101 | Cele trei combo-uri | `Capture:`, `Language:`, `Send:` | V |
| V-102 | Cele doua butoane mari | in dreapta, cu iconuri: unul porneste captura, celalalt trimite rezultatul | V |
| V-103 | **Trimiterea in OCR Editor** | se poate alege **proiectul curent sau un proiect nou** | V |
| V-104 | Opțiunile din meniul iconului din bara de sistem | `Always on Top`, `Run at Startup`, `Enable Sounds` | D |

---

## W. INTEGRARI — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| W-200 | Subiectul mesajului de e-mail generat | de forma `<nume fisier>.pdf (<produs>)` | V |
| W-201 | Tabul propriu in ribbonul Outlook | aplicatia adauga un tab cu numele produsului | V |
| W-202 | Tabul propriu in ribbonul Word | la fel; **cand sunt instalate doua versiuni ale produsului, apar doua tab-uri** | V |
| W-203 | Previzualizarea PDF in Explorer | originalul ofera previzualizare completa a documentului in Explorer si in Outlook | D |
| W-204 | Asocierile de fisiere | se stabilesc la instalare sau din `Options > General` | D |
| W-205 | Imprimanta virtuala | originalul a livrat una pentru versiunea 15, **retrasa in versiunea 16 Release 3**. La noi: opțională | X |

---

## X. OPTIONS — detaliu de interfata

| ID | Element | Comportament exact | Src |
|---|---|---|---|
| X-400 | Dialogul `Options` | modal, circa 650 x 620 px, cu titlu, semnul intrebarii si `X` | V |
| X-401 | Bara de tab-uri | **iconuri mari cu eticheta dedesubt**, orizontal; tabul selectat are fundal albastru deschis si chenar | V |
| X-402 | Ordinea tab-urilor | `General`, `Image Processing`, `Languages`, `OCR`, `Format Settings`, `Areas and Text` (numai din OCR Editor), `Other` | V |
| X-403 | Tabul `General`, grupul de pornire | eticheta `When OCR Editor starts` cu doua radio: `Open a new OCR project` si `Open the last used OCR project` | V |
| X-404 | Tabul `General`, grupul de dispozitiv | eticheta `Select device for acquiring images`, un camp read-only cu dispozitivul curent, si butonul `Select Device...` | V |
| X-405 | Radio-urile de interfata de scanare | `Use FineReader's interface (scanners only)` si `Use scanner's interface`, plus un link de ajutor de forma „care interfata de scanare sa aleg" | V |
| X-406 | **Mesajul de vizualizator implicit** | text in bold de forma `<produs> is not currently your default PDF viewer`, plus butonul `Make Default...`. **Mesajul dispare cand produsul e deja implicit** | V |
| X-407 | Dialogul `Select Device` | eticheta `Select a scanner or a camera:`, un listbox cu dispozitivele si tehnologia lor, si **textul de ajutor: „dacă nu vedeti un dispozitiv in lista, verificati dacă e conectat la calculator si pornit"** | V |
| X-408 | Tabul `Image Processing`, paragraful explicativ | sub bifa de recunoastere in fundal, un paragraf care spune ce face functia si ca fisierele rămân neschimbate, plus un link catre comanda de recunoastere permanenta | V |
| X-409 | Linkul de limbi OCR din acel tab | eticheta `OCR languages:` plus un link cu limbile curente | V |
| X-410 | **Setarile de preprocesare, pe trei coloane** | coloana 1: `Split facing pages`, `Correct page orientation`, `Deskew images`, `Straighten text lines`, `Correct image resolution`; coloana 2: `Detect page edges*`, `Whiten background*`, `Reduce ISO noise*`, `Remove motion blur*`, `Correct trapezoid distortions*`; coloana 3: `Fix inverted colors on image`, `Convert to black and white`, `Remove color marks` | V |
| X-411 | **Comutatorul de setari avansate** | buton care alterneaza intre `Show Custom Settings` si `Hide Custom Settings` | V |
| X-412 | Nota de sub coloane | `* for photo images` | V |
| X-413 | **Cele trei moduri de preprocesare** | radio `Use automatic settings`, `Specify settings manually`, `No preprocessing` | V |
| X-414 | **Setarile se pastreaza la comutarea modului** | trecerea pe `No preprocessing` si inapoi nu pierde bifele | V |
| X-415 | Tabul `OCR`, linkul de mod | lângă combo-ul de mod de recunoastere PDF, un link de forma „care mod de recunoastere sa aleg" | V |
| X-416 | **Cele doua bife `Also use built-in patterns`** | **una indentata sub `Use user patterns` si alta indentata sub `Use training to recognize new characters and ligatures`.** Fiecare e gri cand parintele ei nu e selectat. Specificatia avea doar una | V |
| X-417 | Butoanele din tabul `OCR` | `Pattern Editor...`, `Load Patterns and Languages...`, `Save Patterns and Languages...`, aliniate in coloana din dreapta | V |
| X-418 | Grupul de fonturi | eticheta `Select fonts to be used in recognized text` plus butonul `Select Fonts...` | V |
| X-419 | **Lista din stanga tabului `Format Settings`** | eticheta `Document type`, cu ordinea exacta: `PDF`, `DOC(X) / RTF / ODT`, `XLS(X)`, `PPTX`, `CSV`, `TXT`, `HTML`, `EPUB / FB2`, `DjVu` | V |
| X-420 | Elementul selectat in acea lista | fundal albastru | V |
| X-421 | Dependenta `Create PDF/UA` si `Create PDF tags` | **cand `Create PDF/UA` e bifata, `Create PDF tags` devine gri si fortata** | V |
| X-422 | Combo-ul de versiune PDF/A | gri pana se bifeaza `Create PDF/A` | V |
| X-423 | Butoanele de jos ale dialogului | `OK` si `Cancel`; `OK` e butonul plin | V |

---

## Y. MESAJE SI STARI

| ID | Mesaj sau stare | Unde apare | Src |
|---|---|---|---|
| Y-300 | `Page not recognized` | panoul `Text`, gri, centrat | V |
| Y-301 | `No matches found` | bara de stare a panoului de cautare | V |
| Y-302 | `Found: N` | idem | V |
| Y-303 | `Choose the first step` | dialogul de sarcina automatizata | V |
| Y-304 | `Select task steps` | dialogul Hot Folder | V |
| Y-305 | `Loading the document. Please wait...` | zonele modulului de comparare | V |
| Y-306 | `Differences found: N` | banda roșie din modulul de comparare | V |
| Y-307 | `Process completed` | dialogul de progres la recunoastere | V |
| Y-308 | `N of M pages recognized` | idem | V |
| Y-309 | `N of M files processed` | dialogul de conversie | V |
| Y-310 | Avertismentul de rezolutie | de forma `Page N: Please rescan your document at a higher resolution. This will improve the OCR of the fragments printed in a small font size.`, **cu numarul paginii ca link** | V |
| Y-311 | `Pages remaining to recognize N / the limit to be renewed in N days` | bara de stare Hot Folder | V |
| Y-312 | `This PDF file contains a text layer` | toolbarul panoului `Image` | V |
| Y-313 | `This document contains interactive form fields.` | banda galbena din PDF Editor | V |
| Y-314 | `The document will be converted to image-only PDF.` | dialogul de stergere de obiecte | V |
| Y-315 | `All form fields will be sent.` | dialogul de actiune de formular | V |
| Y-316 | **Toate mesajele stau in fisiere de traducere** | niciun text afisabil in cod | X |

---

## Observatii de implementare

1. **Cerintele marcate `V` descriu originalul cum arata pe ecran.** Produsul nostru nu trebuie sa copieze paleta de culori sau iconurile ABBYY — asta ar fi o problema de proprietate intelectuala. Ce se preia e **structura**: ce controale exista, in ce ordine, ce se dezactiveaza cand, si ce mesaj apare in fiecare stare.

2. **Textele de interfata in engleza, citate aici, sunt referinta functionala**, ca sa se stie exact ce comanda e descrisa. Produsul nostru are propriile texte, in romana si engleza, din fisierele de traducere.

3. **Unde manualul si interfata se contrazic** — numarul de casete de culoare la redactare, poziția numerelor de zona, culorile zonelor — specificatia noteaza ambele si cere ca produsul sa fie configurabil in loc sa aleaga arbitrar.
