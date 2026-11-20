# SPECIFICATIE 02 — OCR Editor

Document 2 din livrabile, partea 2. **Versiunea 2, rescrisa dupa verificarea contra manualului oficial.**

Aceleasi coloane si aceeasi legenda de surse ca in SPEC_01: **D** = documentatie oficiala, **V** = observat in video, **K** = baza de cunostinte, **N** = adaugat de noi, **X** = diferit deliberat.

OCR Editor e modulul cu cea mai mare densitate de reguli. El decide calitatea intregului produs.

---

## J. INTERFATA SI PROIECTUL OCR

### J.1 Pornirea si interfata

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| J-001 | Pornirea modulului | **5 cai: Lansator `Open > OCR Editor`; Lansator `Tools > OCR Editor`; Lansator `File > Open in OCR Editor...`; PDF Editor `Tools > OCR Editor`; meniul Start** | — | — | fereastra OCR Editor | — | D |
| J-002 | Ecranul de pornire | `Options > General` | `Open a new OCR project` / `Open the last used OCR project` | — | — | — | D |
| J-003 | Panourile | automat | — | **`Pages` (cu doua vederi: `Thumbnails` si `Details`), `Image`, `Text`, `Zoom` (cu controale de scara in partea de jos)** | — | — | D |
| J-004 | `Navigation pane` | `F5` | — | panoul `Pages` | — | — | D |
| J-005 | Numai panoul `Image` | `F6` | — | — | — | — | D |
| J-006 | Panourile `Image` si `Text` | `F7` | — | — | — | — | D |
| J-007 | Numai panoul `Text` | `F8` | — | — | — | — | D |
| J-008 | Panoul `Zoom` | `Ctrl+F5` | — | urmareste cursorul din panoul `Image` | randul marit | — | D |
| J-009 | Comutarea intre panouri | `Ctrl+Tab` / `Ctrl+Shift+Tab`; `Alt+1`…`Alt+4` | — | `Alt+1` Pages, `Alt+2` Image, `Alt+3` Text, `Alt+4` Zoom | — | — | D |
| J-010 | **Bara principala nu e personalizabila** | — | — | **`Main Toolbar` nu se poate modifica** | — | — | D |
| J-011 | `Quick Access Bar` | `View > Toolbars`; clic dreapta pe bara principala | — | **ascunsa implicit** | bara suplimentara | — | D |
| J-012 | Personalizarea `Quick Access Bar` | `View > Customize...`, tabul `Toolbars` | combo `Categories`, lista `Commands`, butoanele `>>` si `<<`, `OK`, `Reset All` | — | bara personalizata | — | D |
| J-013 | Panoul `Warnings` | `View > Show Warnings`; butonul din stanga-jos | — | **arata mesajele paginii selectate**, cu butoane de navigare si de stergere | lista de avertismente | — | D |
| J-014 | Redimensionarea panourilor | tragerea marginii | — | — | — | — | D |
| J-015 | Mutarea panourilor `Pages` si `Zoom` | `View`; meniul contextual al panoului | — | — | panoul se muta | — | D |
| J-016 | Bara de proprietati | meniu contextual | — | se poate ascunde si arata | — | — | D |
| J-017 | Deschiderea unei pagini | **dublu clic pe miniatura sau pe numarul paginii** | — | — | pagina in panoul `Image` | — | D |

### J.2 Proiectul

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| J-030 | Proiect nou | `Ctrl+Shift+N` | — | dacă proiectul curent are modificari, se intreaba | proiect gol | — | D |
| J-031 | `Open OCR Project...` | `Ctrl+Shift+O`; `File > Open OCR Project...` | folder de proiect | structura trebuie sa fie valida | proiectul se incarca | structura stricata → mesaj | D |
| J-032 | **Proiectele din versiuni mai vechi** | J-031 | — | **conversia e ireversibila; proiectul trebuie salvat sub alt nume; textul recunoscut NU se transfera si recunoasterea trebuie reluata** | proiect convertit | avertisment explicit inainte | D |
| J-033 | Deschiderea din Explorer | clic dreapta pe folderul proiectului > `Open OCR project in ABBYY FineReader PDF` | — | — | — | — | D |
| J-034 | `Save OCR Project...` | `Ctrl+Shift+S` | cale | — | **imagini, text, setari, sabloane si limbi, toate salvate** | fara drepturi de scriere → mesaj | D |
| J-035 | `Close` | `Ctrl+W`; `File > Close` | — | — | — | — | D |
| J-036 | Salvare automata | la fiecare 5 minute | — | doar dacă exista modificari | fisier de recuperare | — | N |
| J-037 | Recuperare dupa cadere | la pornire | — | se detecteaza un fisier de recuperare mai nou | se ofera recuperarea | — | N |
| J-038 | Metadatele proiectului | `Format Settings > Edit Metadata...` | **nume, autor, subiect, cuvinte cheie**, apoi `OK` | — | se scriu la export | — | D |
| J-039 | Setari de proiect | Options deschis din OCR Editor | — | suprascriu setarile globale pentru proiectul curent | — | — | V |
| J-040 | Indicatorul de modificari nesalvate | titlul ferestrei | — | — | asterisc langa nume | — | V |
| J-041 | Undo si redo | `Ctrl+Z` / `Ctrl+Y` | — | minimum 50 de pasi; operatiile pe imagine intra in acelasi istoric | starea anterioara | — | N |

### J.3 Paginile proiectului

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| J-050 | Adaugarea de imagini | `Ctrl+O`; `File > Open Image...` | fisiere, interval de pagini pentru fisiere multipagina | **copiile se salveaza in folderul proiectului**; paginile se adauga la un proiect deschis, sau se creeaza unul nou | paginile se adauga | format nesuportat → se sare, se raporteaza la final | D |
| J-051 | `Automatically process page images as they are added` | dialogul de deschidere | bifa + `Options...` | — | — | — | D |
| J-052 | PDF cu parola | J-050 | parola | se cere la deschidere | — | parola gresita → mesaj | D |
| J-053 | Adaugarea din Explorer | clic dreapta > `Convert with ABBYY FineReader PDF > Open in OCR Editor` | fisiere | **creeaza un proiect nou** | — | — | D |
| J-054 | Adaugarea prin tragere | drag and drop | fisiere | — | — | — | V |
| J-055 | Stergerea paginilor | butonul `Delete` din panoul `Pages`; `Edit > Delete Pages...`; meniu contextual `Delete...`; `Ctrl+Backspace` | selectie, multipla permisa | nu se poate goli complet proiectul | paginile si zonele lor dispar | ultima pagina → mesaj | D |
| J-056 | `Delete Blank Pages` | `Edit > Delete Blank Pages` | — | **toate paginile goale sunt preselectate; `+` si `-` navigheaza intre ele; butonul `Delete selected pages` sterge** | — | nicio pagina goala → mesaj | D |
| J-057 | Avertisment la pagini goale | automat | — | **se verifica intai dacă paginile conțin note de mana sau imagini** | — | — | D |
| J-058 | Rotirea paginilor | `Ctrl+Shift+>` / `Ctrl+Shift+<` | selectie | **rotirea invalideaza zonele si textul paginii** | status inapoi la `analyzed` | — | D |
| J-059 | `Reorder Pages...` | meniu contextual in panoul `Pages` | — | — | dialogul de reordonare | — | D |
| J-060 | `Reorder pages (cannot be undone)` | dialogul de reordonare | — | **operatia nu se poate anula** | ordinea se schimba | — | D |
| J-061 | `Restore original page order after duplex scanning` | acelasi dialog | ordine normala sau inversa pentru paginile pare | **cere minimum trei pagini consecutive selectate** | paginile se intercaleaza corect | mai puțin de trei → opțiunea e gri | D |
| J-062 | `Swap book pages` | acelasi dialog | — | **cere minimum doua pagini consecutive, din care cel putin doua alaturate** | paginile stanga si dreapta se inverseaza | — | D |
| J-063 | `Undo last operation` | acelasi dialog | — | anuleaza ultima reordonare | — | — | D |
| J-064 | Reordonare prin tragere | vederea `Thumbnails` | — | — | ordinea se schimba | — | D |
| J-065 | `Move Pages to New OCR Project...` | meniu contextual in panoul `Pages` | selectie | **dialogul are `Add OCR Project`, butoanele `Move` si `Return`, scurtaturile `Ctrl+Dreapta`, `Ctrl+Stanga` si `Delete`, si butoanele `Create` si `Create All`** | proiecte noi | — | D |
| J-066 | Numerotarea paginilor | automat | — | renumerotare la fiecare adaugare, stergere sau reordonare | — | — | V |
| J-067 | Tragerea paginilor intre doua instante | drag and drop intre ferestre | pagini | — | paginile se adauga la sfarsitul proiectului tinta | — | V |
| J-068 | `Close page` | `Ctrl+F4` | — | — | pagina se inchide din panoul `Image` | — | D |
| J-069 | Navigare intre pagini | `Ctrl+Jos` / `Ctrl+Sus`; `Ctrl+Home` / `Ctrl+End`; `Ctrl+G` | — | — | — | — | D |

### J.4 Lucrul in grup

**Modul care lipsea complet din versiunea 1.**

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| J-080 | Folder partajat de dictionare | `Options > Areas and Text > User Dictionaries... > Browse...` | **implicit, un folder per utilizator, sub `AppData\Roaming\ABBYY\FineReader\16`** | D |
| J-081 | Sabloane si limbi partajate | `Options > OCR > Save Patterns and Languages...` | fisier `*.fbtx` pe un folder partajat | D |
| J-082 | Drepturi necesare | — | **utilizatorii au nevoie de drepturi de citire si scriere pe folderele partajate** | D |
| J-083 | Limitare asupra limbilor | — | **utilizatorii care partajeaza o limba pot adauga si sterge cuvinte din dictionar, dar NU pot schimba proprietatile limbii** | D |
| J-084 | Limitare la editarea simultana | — | **cat timp un utilizator editeaza un dictionar, ceilalti il pot folosi pentru recunoastere si verificare ortografica, dar nu pot adauga sau sterge cuvinte** | D |
| J-085 | Momentul in care se vad modificarile | — | **modificarile intra in efect dupa repornirea aplicatiei** | D |

---

## K. ACHIZITIA IMAGINILOR

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| K-001 | `Open Image...` | butonul din bara principala; `File > Open Image...`; `Ctrl+O` | fisiere | vezi J-050 | paginile se adauga | — | D |
| K-002 | `Scan Pages...` | butonul din bara principala; `File > Scan Pages...`; `Ctrl+K` | dispozitiv, setari | **se alege dispozitivul, apoi `Preview` (sau clic in imagine), apoi `Settings...` pentru procesarea imaginii, apoi `Scan`** | paginile scanate se adauga | niciun scaner → mesaj | D |
| K-003 | Alegerea dispozitivului | `Options > General`; dialogul de scanare | TWAIN sau WIA | lista se reinterogheaza la fiecare deschidere | — | — | D |
| K-004 | Interfata de scanare | `Options > General` | a aplicatiei sau a driverului | — | — | driver incompatibil → se revine la interfata proprie | D |
| K-005 | Modul de culoare | dialogul de scanare | **color / gri / alb-negru** | **gri e cel mai bun pentru OCR**; alb-negru nu e recomandat pentru fotografii, pagini de revista si texte chinezesti, japoneze sau coreene | — | — | D |
| K-006 | Luminozitatea | dialog | 0-100 | **50% merge in majoritatea cazurilor; apare un avertisment cand e prea mica sau prea mare.** Se ajusteaza pentru caractere subtiri sau prea groase, sau se trece pe gri | — | — | D |
| K-007 | Rezolutia | dialog | dpi | **300 dpi e recomandarea. Rezolutia orizontala si cea verticala trebuie sa coincida. Peste 600 dpi incetineste OCR-ul fara castig real; sub 150 dpi degradeaza calitatea. Se ajusteaza dacă e sub 250, peste 600 sau nestandard** | — | avertisment in panoul `Warnings` | D |
| K-008 | `Crop Image` | dialog | dimensiuni predefinite sau zona manuala | — | — | — | D |
| K-009 | Scanare duplex | dialog | bifa | numai dacă scanerul o raporteaza | ambele fete | — | D |
| K-010 | Alimentator automat (ADF) | dialog | bifa | numai dacă scanerul il raporteaza | scanare in serie | hartie blocata → mesaj si oprire | D |
| K-011 | Pauza intre scanari | dialog | secunde | pentru scanere plate | scanare automata la interval | — | D |
| K-012 | `Preview` | buton; clic in fereastra de previzualizare | — | — | scanare rapida, la rezolutie mica | — | D |
| K-013 | Paginile alaturate la scanare | `Options > Image Processing > Split facing pages` | bifa | **paginile scanate invers nu se impart. Impartirea manuala se face din secțiunea `Split` a Image Editor-ului** | doua pagini | — | D |
| K-014 | Scanarea fotografiilor de documente | — | — | **recomandari din manual: circa 5 milioane de pixeli pentru A4; flash dezactivat; diafragma manuala; focalizare manuala; stabilizare sau trepied; zoom optic. Minim: 2 milioane de pixeli pentru A4** | — | — | D |
| K-015 | Iluminarea la fotografiere | — | — | **lumina puternica si uniforma, de preferat lumina naturala; doua surse pentru a evita umbrele; fara flash pe hartie lucioasa; la lumina slaba, de la circa 50 cm** | — | — | D |
| K-016 | Pozitionarea la fotografiere | — | — | **camera paralela cu pagina; distanta 50-60 cm; randurile inclinate cu maximum 20 de grade; focalizare in centru; stabilizare activa; declansare automata, chiar si pe trepied** | — | — | D |
| K-017 | Corectarea fotografiilor neclare | — | — | **unealta `Photo Correction` din Image Editor** | — | — | D |

---

## L. PREPROCESAREA IMAGINILOR

Fiecare unealta e o functie pura `apply(image, params) -> image`, inregistrata intr-un registru, apelabila si din Image Editor, si din pipeline-ul automat, si din Hot Folder.

### L.1 Image Editor

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| L-001 | Deschiderea | butonul din bara panoului `Image`; `Edit > Edit Page Images...`; `Ctrl+I` | — | D |
| L-002 | Iesirea | butonul `Exit Image Editor` | modificarile raman aplicate | D |
| L-003 | Combo `Selection` | fiecare unealta | **toate paginile impare, toate paginile pare, pagina curenta, paginile selectate** | D |
| L-004 | `Show next page after operation completes` | bifa | trece automat la pagina urmatoare | V |

### L.2 Uneltele

| ID | Unealta | Parametri | Reguli si note | Src |
|---|---|---|---|---|
| L-010 | `Recommended Preprocessing` | — | **corecteaza automat: zgomot, neclaritate, inversarea culorilor, inclinarea, indreptarea randurilor, distorsiunea trapezoidala si decuparea** | D |
| L-011 | `Deskew` | — | corecteaza inclinarea | D |
| L-012 | `Straighten Text Lines` | — | indreapta randuri curbate | D |
| L-013 | `Photo Correction` | — | **grup: indreptarea randurilor, eliminarea zgomotului si a neclaritatii, fundalul la alb** | D |
| L-014 | `Correct Trapezoid Distortion` | **grila albastra; se trag cele patru colturi; apoi butonul `Correct`** | liniile orizontale ale grilei trebuie sa fie paralele cu randurile | D |
| L-015 | `Rotate & Flip` | 90 stanga, 90 dreapta, 180, oglindire verticala si orizontala | fara pierdere de calitate | D |
| L-016 | `Split` | vertical, orizontal, pe o linie trasata manual | **pentru pagini de carte alaturate. O pagina devine doua, deci contorul creste** | D |
| L-017 | `Crop` | dimensiune de hartie, latime, inaltime, offset X si Y, inci sau milimetri, selectie de pagini | valorile nu pot depasi imaginea | D |
| L-018 | `Invert` | selectie de pagini | **pentru text deschis pe fundal inchis** | D |
| L-019 | `Resolution` | dpi tinta | intre 72 si 1200 | D |
| L-020 | `Brightness & Contrast` | doua slidere | — | D |
| L-021 | `Levels` | **slidere de intrare si de iesire; sliderul din mijloc ajusteaza luminozitatea** | punctul negru nu poate depasi punctul alb | D |
| L-022 | `Eraser` | traseu, dimensiune de pensula | zona se umple cu fundalul detectat | D |
| L-023 | `Remove Color Marks` | — | **numai pentru scanari cu fundal alb; nu pentru fotografii sau fundaluri colorate** | D |

### L.3 Preprocesarea automata

Setarile complete sunt in SPEC_03, secțiunea X.2. Aici sunt regulile de comportament.

| ID | Cerinta | Detaliu | Src |
|---|---|---|---|
| L-030 | Momentul aplicarii | **setarile de preprocesare se aplica numai imaginilor adaugate de acum inainte, nu celor deja din proiect** | D |
| L-031 | Modul implicit | corectarea automata a defectelor obisnuite de scanare si fotografie | D |
| L-032 | Opțiunile marcate cu asterisc | **se aplica numai fotografiilor digitale**: `Detect page edges`, `Whiten background`, `Reduce ISO noise`, `Remove motion blur`, `Correct trapezoid distortions` | D |
| L-033 | `Convert to black and white` | **conversia e ireversibila. Culorile nu se pot recupera.** Reduce dimensiunea proiectului si accelereaza procesarea, dar poate strica imaginile cu contrast slab | D |
| L-034 | `No preprocessing` | dezactiveaza tot. **Preprocesarea rămâne disponibila manual, din Image Editor** | D |
| L-035 | Detectia tipului de imagine | **fotografie contra scanare**, ca sa se decida dacă se aplica uneltele marcate cu asterisc. Estimata din absenta unui dpi declarat, din zgomot si din neuniformitatea fundalului | N |

---

## M. ZONELE (areas)

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| M-001 | Tipul `Recognition area` | unealta; `Ctrl+1` | — | zona in care se face analiza automata | — | — | D |
| M-002 | Tipul `Text` | unealta; `Ctrl+2` | — | continutul se recunoaste ca text | — | — | D |
| M-003 | Tipul `Table` | unealta; `Ctrl+3` | — | continutul se recunoaste ca tabel | — | — | D |
| M-004 | Tipul `Picture` | unealta; `Ctrl+4` | — | continutul nu se recunoaste | — | — | D |
| M-005 | Tipul `Barcode` | `Ctrl+5` | — | se recunoaste codul | — | — | D |
| M-006 | Tipul `Background picture` | unealta; `Ctrl+6` | — | **pentru text asezat peste o imagine**: imaginea devine fundal, textul de deasupra se recunoaste separat | — | — | D |
| M-007 | Culorile chenarelor | automat | — | **tipurile se deosebesc prin culoarea chenarului**, configurabila din `Options > Areas and Text` | — | — | D |
| M-008 | Desenarea unei zone | unealta din bara panoului `Image` + tragere | dreptunghi | latime si inaltime minime | zona noua | zona prea mica → nu se creeaza | D |
| M-009 | Scurtaturi de desenare fara unealta | tragere cu modificator | **`Ctrl+Shift` text, `Alt+Shift` imagine, `Ctrl+Alt` tabel, `Ctrl+Shift+Alt` imagine de fundal** | — | — | — | D |
| M-010 | **Parcurgerea zonelor cu tastatura** | tasta `Tab` | — | **`Tab` trece de la o zona la urmatoarea** | — | — | D |
| M-011 | Ajustarea marginilor | tragerea unei laturi sau a unui colt | — | — | zona se redimensioneaza | — | D |
| M-012 | Adaugarea unui maner | **`Ctrl+Shift`+clic pe chenar** | — | — | punct nou de control | — | D |
| M-013 | `Add area part` | unealta contextuala | dreptunghi | **numai pentru zonele de tip text, imagine si imagine de fundal** | zona devine poligon | pe tabel sau cod de bare → unealta e gri | D |
| M-014 | `Cut area part` | unealta contextuala | dreptunghi | idem | zona capata o scobitura | — | D |
| M-015 | Selectie multipla | `Ctrl`+clic | — | — | — | — | D |
| M-016 | Mutarea unei zone | `Ctrl`+tragere | — | nu poate iesi din imagine | — | — | D |
| M-017 | Schimbarea tipului | meniu contextual `Change Area Type To` | tip nou | **invalideaza textul paginii** | zona isi schimba culoarea | — | D |
| M-018 | Stergerea zonelor | `Delete`; meniu contextual `Delete`; unealta de stergere | selectie | **pe o pagina recunoscuta se sterge si textul zonei** | — | — | D |
| M-019 | `Delete Areas and Text` | meniu contextual; `Ctrl+Del` | — | confirmare | **toate zonele si tot textul paginii dispar** | — | D |
| M-020 | `Delete text` | `Ctrl+Shift+Del` | — | — | textul dispare, zonele rămân | — | D |
| M-021 | `Reorder Areas` | unealta; meniul `Area` | clicuri in ordine | — | numerele de ordine se recalculeaza | — | D |
| M-022 | Numerotarea automata | la analiza | — | **zonele se numeroteaza automat de la stanga la dreapta.** Numerele se vad in bara de proprietati a zonei sau cu unealta `Order Areas` | numere pe zone | — | D |
| M-023 | Proprietatea `Language` | bara de proprietati; meniu contextual `Properties` | limbi | poate fi diferita de limba documentului | zona se recunoaste cu limba ei | — | D |
| M-024 | Proprietatea `Function` | bara de proprietati | **`header`, `footer`, `footnote`** | **numai pentru zonele de tip text** | influenteaza exportul | — | D |
| M-025 | Proprietatea `Orientation` | bara de proprietati | 0, 90, 180, 270, auto | — | textul se recunoaste rotit | — | D |
| M-026 | Proprietatea `Print type` | bara de proprietati | auto, typewriter, fax | — | alege modelul de recunoastere | — | D |
| M-027 | Proprietatea `Inversion` | bara de proprietati | **combo cu valoarea `Inverted`** | pentru text deschis pe fundal inchis | — | — | D |
| M-028 | Proprietatea `Direction of CJK text` | bara de proprietati | orizontal, vertical | activa pentru limbile asiatice | — | — | D |
| M-029 | Navigarea in bara de proprietati | butoane cu sageti | — | **cand panoul e prea ingust, proprietatile se parcurg cu butoanele cu sageti** | — | — | D |
| M-030 | Limitare la limba pe zona | — | — | **limba se poate seta pe zona numai pentru zonele de acelasi tip** | — | — | D |
| M-031 | `Save Area Template...` | meniul `Area` | nume de fisier | **extensia `*.blk` sau `*.blkx`** | sablonul conține pozitiile si tipurile zonelor | — | D |
| M-032 | `Load Area Template...` | meniul `Area` | fisier, combo `Apply to` | **`Apply to`: `Selected pages` sau `All pages`. Scanarile trebuie sa aiba aceeasi rezolutie** | zonele se suprascriu | dimensiune diferita → avertisment cu opțiunea de scalare | D |
| M-033 | Re-recunoasterea dupa modificari | — | — | **dupa orice modificare de zone trebuie reluata recunoasterea** | — | — | D |
| M-034 | Interzicerea suprapunerii | la desenare si la mutare | — | o zona noua care intra peste alta fie o taie, fie e refuzata | — | mesaj | N |

### M.1 Tabelele

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| M-040 | `Analyze Table Structure` | meniu contextual; toolbarul care apare lângă zona; meniul `Area` | zona trebuie sa fie de tip tabel | D |
| M-041 | Transformarea unei zone in tabel | meniu contextual `Change Area Type To > Table` | — | D |
| M-042 | `Split Cells` | meniul `Area`; meniu contextual; toolbarul zonei | **numai celulele unite anterior se pot separa** | D |
| M-043 | `Merge Cells` | idem | — | D |
| M-044 | `Merge Rows` | idem | — | D |
| M-045 | Adaugarea unui separator orizontal | toolbarul zonei | clic pe pozitie | D |
| M-046 | Adaugarea unui separator vertical | toolbarul zonei | clic pe pozitie | D |
| M-047 | Stergerea separatoarelor | toolbarul zonei | randurile sau coloanele se unesc | D |
| M-048 | `Treat selected cells as picture` | bara de proprietati a zonei | **pentru celulele care conțin numai imagine** | D |
| M-049 | Structura nedetectabila | automat | o singura celula si un avertisment, nu o eroare | N |

### M.2 Codurile de bare

| ID | Functie | Reguli si validari | Src |
|---|---|---|---|
| M-055 | Starea implicita | **recunoasterea codurilor de bare e dezactivata implicit.** Se activeaza cu `Convert barcodes into strings` din `Options > OCR` | D |
| M-056 | Tipul implicit | **`Autodetect`** | D |
| M-057 | **Ce acopera autodetectarea** | **numai aceste 11 tipuri: Code 3 of 9, Code 93, Code 128, EAN 8, EAN 13, Postnet, UCC-128, UPC-E, PDF417, UPC-A, QR code** | D |
| M-058 | Celelalte tipuri | **se aleg manual din bara de proprietati a zonei.** Manualul listeaza si alte tipuri, care nu se autodetecteaza | D |
| M-059 | Comportamentul fara activare | **codurile de bare se salveaza ca imagini** | D |
| M-060 | Cod ilizibil | zona rămâne imagine | N |

---

## N. RECUNOASTEREA

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| N-001 | Recunoasterea automata | automat la adaugare | — | **activa implicit.** Se dezactiveaza din tabul `Image Processing` al dialogului Options | — | — | D |
| N-002 | **Cand trebuie pornita manual** | — | — | **dupa dezactivarea recunoasterii automate, dupa desenarea de zone, si dupa schimbarea limbii OCR, a opțiunilor OCR sau a fonturilor** | — | — | D |
| N-003 | `Recognize All Pages` | butonul din bara principala; `Recognize > Recognize All Pages`; `Ctrl+Shift+R` | toate paginile | **paginile deja recunoscute nu se reproceseaza; cele analizate se recunosc** | text in panoul `Text` | — | D |
| N-004 | `Recognize Page` | `Ctrl+R`; meniul `Recognize`; meniu contextual | pagina | dacă nu e analizata, se analizeaza intai | — | — | D |
| N-005 | `Recognize Area` | `Ctrl+Shift+B`; meniul `Area` | zona selectata | — | se recunoaste doar zona | — | D |
| N-006 | `Analyze Page` | `Ctrl+E` | pagina | — | zonele se detecteaza | — | D |
| N-007 | `Analyze All Pages` | `Ctrl+Shift+E` | toate paginile | — | — | — | D |
| N-008 | Modul de recunoastere PDF | `Options > OCR` | `Automatically Choose between OCR and Text from PDF` / `Use OCR` / `Use Only Text from PDF` | **`Use Only Text from PDF` e valoarea folosita pentru PDF-urile care au strat de text** | — | — | D |
| N-009 | **Regula fixa** | automat | — | **PDF-urile cautabile si cele doar-imagine folosesc intotdeauna OCR, indiferent de setare** | — | — | D |
| N-010 | `Use OCR` | `Options > OCR` | — | **mai lent, dar mai bun pentru straturi de text de proasta calitate** | — | — | D |
| N-011 | Evaluarea stratului de text existent | intern | — | calitatea se calculeaza din procentul de cuvinte din dictionar, din corectitudinea codificarii si din acoperirea paginii; sub prag se trece pe OCR | — | — | N |
| N-012 | Procesarea documentelor mixte | intern, in modul automat | — | textul digital se extrage, zonele care sunt imagini se recunosc, apoi rezultatele se combina | — | — | N |
| N-013 | `Thorough recognition` | `Options > OCR` | — | **pentru layout complex, fundaluri colorate si tabele cu linii albe sau colorate.** Mai lent | — | — | D |
| N-014 | `Fast recognition` | `Options > OCR` | — | **pentru documente mari si simple, cu imagini bune** | — | — | D |
| N-015 | `Document type: Auto` | `Options > OCR` | — | implicit; **autodetectarea tipului de tipar cere valoarea `Auto`** | — | — | D |
| N-016 | `Document type: Typewriter` | `Options > OCR` | — | **pentru litere de latime egala.** Dupa folosire se revine la `Auto` | — | — | D |
| N-017 | `Document type: Fax` | `Options > OCR` | — | **pentru zgomot si distorsiune** | — | — | D |
| N-018 | Detectia antetelor si subsolurilor | `Options > OCR`, bifa | — | **elementele detectate devin clicabile in fisierul salvat; dacă detectia e dezactivata, se salveaza ca text obisnuit** | — | — | D |
| N-019 | Detectia notelor de subsol | bifa | — | idem | — | — | D |
| N-020 | Detectia cuprinsului | bifa | — | idem | — | — | D |
| N-021 | Detectia listelor | bifa | — | idem | — | — | D |
| N-022 | Dialogul de progres | automat | — | se poate anula | progres si numarul de pagini procesate | — | V |
| N-023 | Avertismentele dupa recunoastere | panoul `Warnings` | — | mesaje per pagina | de exemplu cererea de rescanare la rezolutie mai mare | — | D |
| N-024 | Incredere pe caracter | intern | — | fiecare caracter primeste un scor; caracterele sub prag se marcheaza nesigure | — | — | D |
| N-025 | Pragul de incredere | `Options > Areas and Text` | valoare | **originalul nu publica un prag numeric. 70 e alegerea noastra** | — | — | N |
| N-026 | Invalidarea la modificare | automat | — | **modificarea zonelor sau a setarilor OCR duce statusul paginii inapoi la `analyzed`** | se cere re-recunoastere | avertisment inainte de export | D |
| N-027 | Paralelizarea | `Options > Other` | numar de nuclee | — | — | — | D |
| N-028 | Anularea unei recunoasteri | buton | — | se opreste dupa pagina curenta | paginile terminate rămân | — | N |

---

## O. VERIFICAREA SI EDITAREA TEXTULUI

### O.1 Verificarea

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| O-001 | Evidentierea caracterelor nesigure | panoul `Text` | — | culoarea se configureaza din `Options > Areas and Text` | fundal colorat | — | D |
| O-002 | Butoanele `Next` si `Previous` | panoul `Text`; `Alt+Jos` / `Alt+Sus` | — | — | cursorul sare la caracterul nesigur urmator sau anterior | la ultimul → mesaj | D |
| O-003 | Dialogul `Verify Text...` | `Recognize > Verify Text...`; butonul din bara principala; `Ctrl+F7` | — | parcurge cuvintele nesigure | dialogul de verificare | niciun cuvant nesigur → mesaj | D |
| O-004 | `Skip` | dialog | — | **scoate evidentierea fara sa schimbe textul** | trece mai departe | — | D |
| O-005 | `Replace` | dialog | sugestie sau text propriu | — | inlocuieste aparitia | — | D |
| O-006 | `Add to Dictionary` | dialog; meniu contextual in panoul `Text` | cuvant | se adauga in dictionarul limbii curente | cuvantul nu mai e semnalat | — | D |
| O-007 | Controale de font in dialog | dialog | font si efecte de font | — | se aplica cuvantului | — | D |
| O-008 | Caractere care nu sunt pe tastatura | butonul de simbol > `More Symbols...` | **combo `Subset` sau campul `Character code`** | — | simbolul se insereaza | — | D |
| O-009 | `Options...` din dialog | dialog | — | deschide setarile de verificare | — | — | D |
| O-010 | **Sugestii pentru CJK** | automat | — | **pentru textul chinezesc, japonez si coreean apar sugestii de caractere cu aspect asemanator** | — | — | D |
| O-011 | `Mark Text as Verified` | `Ctrl+T` | pagina | — | status `verified` | — | D |
| O-012 | Opțiunile de verificare | `Options > Areas and Text` | **`ignora cuvintele cu cifre si caractere speciale`; `verifica cuvintele compuse care nu sunt in dictionar`; corectarea spatiilor in jurul punctuatiei** | — | — | — | D |

### O.2 Editarea textului

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| O-020 | Editarea directa | clic si tastare in panoul `Text` | caractere | **modificarea se reflecta in export, inclusiv in stratul de text de sub imagine** | — | — | D |
| O-021 | Sincronizarea intre panouri | clic in text sau in imagine | — | — | pozitia se evidentiaza in celalalt panou si in `Zoom` | — | V |
| O-022 | Bara `Text Properties` | meniu contextual `Properties` | font, dimensiune, efecte, culoare, aliniere, spatiere, scara | — | se aplica selectiei | — | D |
| O-023 | Bold, italic, underline | `Ctrl+B`, `Ctrl+I`, `Ctrl+U` | — | — | — | — | D |
| O-024 | Cautare in text | `Ctrl+F` | sir | — | rezultatele se evidentiaza | — | D |
| O-025 | `Find next` | `F3` | — | — | — | — | D |
| O-026 | Inlocuire in text | `Ctrl+H` | cautat, nou | — | — | — | D |
| O-027 | Navigarea in celulele de tabel | tastele cu sageti | — | — | — | — | D |
| O-028 | Caractere neimprimabile | setare | bifa | arata marcajele de paragraf si tabulare | — | — | V |
| O-029 | Fontul de afisare a textului simplu | `Options > Areas and Text > Font used to display plain text` | font | **`Arial Unicode MS` pentru scrierile neeuropene** | — | caractere afisate ca `?` sau `□` → se schimba fontul | D |

### O.3 Stilurile

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| O-035 | Aplicarea unui stil | bara `Text Properties` | — | D |
| O-036 | `Style Editor...` | `Tools > Style Editor...` | — | D |
| O-037 | Ce se poate schimba | dialog | **numele, fontul, dimensiunea fontului, spatierea intre caractere si scara** | D |
| O-038 | `New` | dialog | stil nou | D |
| O-039 | `Merge...` | dialog | **deschide dialogul `Merge Styles`** | D |
| O-040 | `Previous Fragment` si `Next Fragment` | dialog | navigheaza la textul care foloseste stilul | D |
| O-041 | Rolul de titlu | coloana din tabelul de stiluri | **stilul cu rol de titlu genereaza semn de carte la salvarea in PDF, dacă opțiunea `Create bookmarks from headings` e activa** | V |

### O.4 Hyperlinkurile in OCR Editor

**Modul care lipsea din versiunea 1.**

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| O-050 | Vizualizarea adresei | hover peste link | adresa apare in tooltip | D |
| O-051 | Deschiderea | meniu contextual `Open Hyperlink`; `Ctrl`+clic | — | D |
| O-052 | `Remove Hyperlink` | meniu contextual | sterge linkul | D |
| O-053 | Dialogul `Edit Hyperlink` | meniu contextual `Hyperlink...` | **campul `Text to display`** | D |
| O-054 | `Link to > Web page` | dialog | **protocol plus adresa** | D |
| O-055 | `Link to > Local file` | dialog | **buton `Browse...`** | D |
| O-056 | `Link to > E-mail address` | dialog | **prefix `mailto`** | D |

### O.5 Tabelele in panoul Text

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| O-060 | `Merge Table Cells` | meniul `Area` | — | D |
| O-061 | `Split Table Cells` | meniul `Area` | **numai celulele unite anterior** | D |
| O-062 | `Merge Table Rows` | meniul `Area` | — | D |
| O-063 | Golirea unei celule | tasta `Delete` | **sterge continutul celulei, nu structura** | D |
| O-064 | **Uneltele de tabel sunt ascunse implicit** | — | **se adauga din `View > Toolbars > Customize...`** | D |

### O.6 Redactarea

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| O-070 | `Redaction Mode` | `Tools > Redaction Mode`; butonul din bara principala; `Ctrl+Shift+H` | se activeaza si se dezactiveaza cu acelasi element | D |
| O-071 | Marcarea textului | marker-ul | **`Ctrl+Z` sau butonul `Undo` anuleaza ultima redactare** | D |
| O-072 | Rezultatul la export | automat | **textul redactat apare ca puncte, sau ca dreptunghiuri negre in formatele care suporta culori** | D |

### O.7 Copierea continutului

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| O-080 | Uneltele de selectie | bara panoului `Image` | unelte separate pentru text, imagine si tabel | D |
| O-081 | `Recognize and Copy Text` | meniu contextual; butonul din toolbarul care apare; `Ctrl+C` | textul zonei in clipboard, fara export | D |
| O-082 | `Copy area as image` | `Ctrl+Shift+C` | imaginea in clipboard | D |
| O-083 | Copierea mai multor pagini | selectie in panoul `Pages`, apoi `Save As` sau `Send To` | — | D |

---

## P. LIMBI, DICTIONARE, SABLOANE DE CARACTERE

### P.1 Limbile

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| P-001 | `Automatically select OCR languages from the following list` | `Options > Languages` | radio + buton `Specify...` | **limbile se aleg automat dintr-o lista definita de utilizator** | — | — | D |
| P-002 | Dialogul `Languages` | butonul `Specify...` | lista cu bife, apoi `OK` | — | lista de lucru | — | D |
| P-003 | `Specify OCR languages manually` | `Options > Languages`; combo din bara principala > `More languages...` | lista cu bife | **se foloseste cand limba nu apare in lista scurta** | — | — | D |
| P-004 | Combo de limbi din bara principala | bara principala | limbi recente plus `More languages...` | — | — | — | D |
| P-005 | Numarul de limbi | — | — | **201 limbi OCR**, in trei categorii: naturale; artificiale (Ido, Interlingua, Occidental, Esperanto); formale (Basic, C/C++, COBOL, Fortran, Java, Pascal, formule matematice simple, numere) | — | — | D |
| P-006 | Limbile cu dictionar | lista | — | **marcate cu asterisc. Dictionarul permite detectarea caracterelor nesigure si a greselilor de scriere** | — | — | D |
| P-007 | Lista limbilor din licenta | `Help > About > License Info` | — | — | — | — | D |
| P-008 | Limba romana | lista | `Romanian`, `RomanianMoldavia` | produsul trebuie sa acopere si varianta cu sedila | — | — | V |
| P-009 | Avertisment la multe limbi | automat | — | peste 3 limbi, recunoasterea devine mai lenta | mesaj informativ | — | N |

### P.2 Limbi proprii si grupuri

| ID | Functie | Unde | Intrari | Reguli si validari | Src |
|---|---|---|---|---|---|
| P-020 | `New...` limba | `Options > Languages > New...` | **`Create a new language based on an existing one`**, apoi `OK` | — | D |
| P-021 | Dialogul `Language Properties` | din P-020 | **`Name`; combo `Source language`; `Alphabet` cu buton de editare** | — | D |
| P-022 | Dictionarul limbii | acelasi dialog | **`None` / `Built-in dictionary` / `User dictionary` (cu buton `Edit...`) / `Regular expression`** | — | D |
| P-023 | Importul in dictionarul utilizator | butonul `Edit...` | **fisiere text in codificarea Windows-1252** | — | D |
| P-024 | Regulile de litere mari si mici | acelasi dialog | **un tabel cu reguli de capitalizare a cuvintelor** | — | D |
| P-025 | Expresia regulata | acelasi dialog | expresie | **trebuie sa compileze. Simbolurile suportate sunt in SPEC_03 secțiunea Z.2; `@` e rezervat** | expresie invalida → mesajul erorii | D |
| P-026 | `Advanced...` | acelasi dialog | **caractere de inceput de cuvant, de sfarsit de cuvant, caractere care nu sunt litere, caractere ignorate in interiorul cuvantului, caractere interzise, si opțiunea care permite cifre arabe, cifre romane si abrevieri** | — | D |
| P-027 | `New...` grup de limbi | `Options > Languages > New...` | **`Create a new group of languages`** | — | D |
| P-028 | `Language Group Properties` | din P-027 | nume si limbi | minimum doua limbi | D |
| P-029 | `Advanced...` pentru grup | acelasi dialog | **campul `Prohibited characters`** | — | D |
| P-030 | **Unde se salveaza limbile proprii** | automat | **in folderul proiectului, implicit.** Pentru a le salva impreuna cu sabloanele se foloseste `Options > OCR > Save Patterns and Languages...` | — | D |

### P.3 Dictionarele

| ID | Functie | Unde | Intrari | Reguli si validari | Src |
|---|---|---|---|---|---|
| P-040 | `View Dictionaries...` | `Tools > View Dictionaries...`; `Ctrl+Alt+D` | limba, apoi `View...` | — | D |
| P-041 | `Add word` | dialogul de dictionar | cuvant | **un duplicat produce un avertisment** | D |
| P-042 | Stergerea unui cuvant | dialog | selectie, apoi `Delete` | — | D |
| P-043 | `Import...` | dialog | **fisiere `*.pmd`, `*.txt` sau `*.dic`** | — | D |
| P-044 | Importul dictionarelor din versiuni mai vechi | `Tools > View Dictionaries...` > limba > `View...` > `Import...` | **dictionare din FineReader 10, 11, 12 si 14** | — | D |
| P-045 | Folder partajat | `Options > Areas and Text > User Dictionaries... > Browse...` | cale | vezi J-080…J-085 | D |

### P.4 Sabloanele de caractere

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| P-050 | `Use built-in patterns` | `Options > OCR` | implicit | D |
| P-051 | `Use user patterns` | `Options > OCR` | cu `Also use built-in patterns` dedesubt | D |
| P-052 | `Use training to recognize new characters and ligatures` | `Options > OCR` | **dezactivat implicit. Util pentru simboluri speciale, text decorativ si volume mari de calitate slaba, peste 100 de pagini** | D |
| P-053 | `Pattern Editor...` | `Options > OCR`; `Tools` | lista de sabloane | D |
| P-054 | `New...` sablon | `Pattern Editor` | **dialogul `Create Pattern`, cu un nume, apoi `OK`** | D |
| P-055 | Butonul de antrenare | bara panoului `Image` | **deschide dialogul `Pattern Training`** | D |
| P-056 | Efectele in antrenare | dialogul de antrenare | **se pot inregistra bold, italic, exponent si indice** | D |
| P-057 | `Back` | dialogul de antrenare | **navigheaza la caracterul anterior din acelasi cuvant** | D |
| P-058 | **Limita de caractere** | automat | **maximum 1.000 de caractere noi per sablon** | D |
| P-059 | **Limbile asiatice** | automat | **antrenarea nu e suportata pentru limbile asiatice** | D |
| P-060 | **Ce se poate antrena** | automat | **numai caractere din alfabet. Pentru celelalte se folosesc combinatii de doua caractere sau butonul `Insert Character`** | D |
| P-061 | `Set Active` | `Tools > Pattern Editor...` | un singur sablon activ | D |
| P-062 | `Edit...` | `Pattern Editor` | **se selecteaza un caracter, apoi `Properties...`, cu campurile `Character` si `Effects`** | D |
| P-063 | `Delete` | `Pattern Editor` | sterge un caracter antrenat | D |
| P-064 | **Domeniul de aplicare al unui sablon** | automat | **sabloanele se aplica numai la acelasi font, aceeasi dimensiune si aceeasi rezolutie.** Se dezactiveaza revenind la `Use built-in patterns` | D |
| P-065 | `Save Patterns and Languages...` | `Options > OCR` | **fisier `*.fbt` sau `*.fbtx`** | D |
| P-066 | `Load Patterns and Languages...` | `Options > OCR` | **deschide dialogul `Load Options`** | D |

### P.5 Scrieri speciale

| ID | Functie | Reguli si validari | Src |
|---|---|---|---|
| P-070 | Limbile cu scriere complexa | **araba, ebraica, idis, thailandeza, chineza, japoneza, coreeana** | D |
| P-071 | Fonturile recomandate | **araba, ebraica, idis, thailandeza: `Arial Unicode MS`. Ebraica are si: Aharoni, David, Levenim mt, Miriam, Narkisim, Rod. Chineza simplificata si tradiționala, japoneza, coreeana: `Arial Unicode MS` sau fonturi din familia SimSun (SimHei, YouYuan, PMingLiU, MingLiU, STSong)** | D |
| P-072 | Dezactivarea procesarii automate pentru CJK | **pentru text CJK amestecat cu text european se debifeaza `Correct page orientation` si `Split facing pages`** | D |
| P-073 | Paginile alaturate la scrierile de la dreapta la stanga | **pentru araba, ebraica si idis se alege intai limba OCR, apoi `Split facing pages`. `Swap book pages` reface numerotarea** | D |
| P-074 | Recunoasterea amestecata | **`More languages...` din bara principala, apoi `Specify OCR languages manually` in `Language Editor`** | D |
| P-075 | Direcția textului | **butonul din bara panoului `Text` dupa recunoastere; combo `Direction of CJK text` din panoul `Image` inainte de recunoastere** | D |
| P-076 | Limbile gotice | **6 limbi: Old English, Old French, Old German, Old Italian, Old Spanish, Latvian Gothic** | D |
| P-077 | Caracterele gotice suportate | **Textur/Textualis, Fraktur, Schwabacher** | D |
| P-078 | Fara font gotic instalat | **rezultatul se afiseaza in Arial, Times sau Courier** | D |
| P-079 | **Regula pentru gotic** | **se foloseste numai limba gotica, nu in combinatie cu o limba moderna, altfel rezultatele sunt slabe** | D |

---

## Q. EXPORTUL DIN OCR EDITOR

### Q.1 Modurile de layout

| ID | Mod | Ce face | Formate permise | Src |
|---|---|---|---|---|
| Q-001 | Combo de mod | **sageata de lângă butonul `Save` din bara principala da cele cinci moduri** | **modul limiteaza formatele disponibile** | D |
| Q-002 | `Exact copy` | **cel mai apropiat de original; limiteaza editarea** | RTF, DOC(X), PDF, PPTX, ODT, DjVu | D / V |
| Q-003 | `Editable copy` | **usor de editat; poate diferi usor de original** | RTF, DOC(X), ODT | D / V |
| Q-004 | `Formatted text` | **pastreaza fonturile, dimensiunile si paragrafele, dar nu spatierea exacta a randurilor si nu pozitiile obiectelor. Textul e aliniat la stanga, iar la dreapta pentru scrierile de la dreapta la stanga. Textul vertical devine orizontal** | RTF, DOC(X), XLS(X), TXT, HTML, ODT, FB2, EPUB | D |
| Q-005 | `Plain text` | **fara formatare** | ca la `Formatted text`, plus CSV | D |
| Q-006 | `Flexible layout` | **pozitiile pe cat de aproape se poate de original** | HTML | D |
| Q-007 | Observatie despre matrice | — | **matricea mod → formate e confirmata in parte din documentatie (care spune ca `Flexible layout` e pentru HTML si ca modurile apar in setarile fiecarui format) si in parte citita din interfata.** Setarile per format din SPEC_03 X.5 confirma ce moduri accepta fiecare format | D / V |

### Q.2 Salvarea

| ID | Functie | Unde | Intrari | Reguli si validari | Rezultat | Erori | Src |
|---|---|---|---|---|---|---|---|
| Q-010 | Butonul de salvare | bara principala | — | iconul se schimba dupa formatul ales | salvare in formatul curent | — | D |
| Q-011 | `Searchable PDF Document` | sageata de lângă `Save As` | opțiuni PDF | — | PDF cu strat de text | — | D |
| Q-012 | `Image-Only PDF Document` | idem | — | — | PDF fara strat de text | — | D |
| Q-013 | `Microsoft Word Document` | idem | opțiuni DOC(X)/RTF/ODT | **stilurile existente se pot pastra** | DOCX | — | D |
| Q-014 | `RTF Document`, `ODT Document` | idem; `Save in Other Formats...` | idem | — | — | — | D |
| Q-015 | `Microsoft Excel Workbook` | idem | opțiuni XLS(X) | XLS sau XLSX | — | document fara tabele → avertisment | D |
| Q-016 | `CSV Document` | idem | opțiuni CSV | **CSV e numai format de ieșire** | — | — | D |
| Q-017 | `Microsoft PowerPoint Presentation` | idem | opțiuni PPTX | — | — | — | D |
| Q-018 | `TXT Document` | idem | opțiuni TXT | **in meniul contextual apare ca `Text Document`** | — | — | D |
| Q-019 | `HTML Document` | idem; `Save in Other Formats...`; `File > Save As > HTML Document` | opțiuni HTML | — | — | — | D |
| Q-020 | `EPUB Document` | idem | opțiuni EPUB/FB2 | **in meniul contextual: `Electronic Publication (EPUB)`.** EPUB e numai format de ieșire | — | — | D |
| Q-021 | `FB2 Document` | idem | idem | **in meniul contextual: `FictionBook (FB2)`.** Numai format de ieșire | — | — | D |
| Q-022 | `DjVu Document` | idem | opțiuni DjVu | — | — | — | D |
| Q-023 | Salvarea unor pagini | selectie in panoul `Pages`, apoi `Save As` din meniu contextual | selectie | — | fisier doar cu paginile alese | — | D |
| Q-024 | Opțiunile de salvare | butonul `Options...` din dialogul de salvare; `Tools > Options... > Format Settings` | — | **opțiunile sunt detaliate in SPEC_03 secțiunea X.5** | — | — | D |

### Q.3 Salvarea imaginilor

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| Q-030 | `Save As > Page Images...` | selectie in panoul `Pages`, apoi `File > Save As > Page Images...`; `Ctrl+Alt+S` | — | D |
| Q-031 | Fisier multipagina | dialog | **cere formatul TIFF si bifa `Create a single file for all pages`** | D |
| Q-032 | Compresia TIFF | dialog | **`ZIP` (fara pierderi; pentru zone mari de o singura culoare, capturi de ecran, alb-negru); `JPEG` (cu pierderi; pentru fotografii gri si color; produce contururi neclare si paleta mai slaba); `CCITT Group 4` (fara pierderi; obisnuit pentru alb-negru si scanari); `Packbits` (fara pierderi; pentru scanari alb-negru); `LZW` (fara pierderi; pentru grafica si imagini gri)** | D |
| Q-033 | PDF doar-imagine | dialog | **foloseste parametrii din `Format Settings > PDF`** | D |

### Q.4 Trimiterea rezultatelor

| ID | Functie | Unde | Reguli si validari | Src |
|---|---|---|---|---|
| Q-040 | `Send to PDF Editor...` | sageata de lângă buton; `File > Send To > PDF Editor...` | — | D |
| Q-041 | **Ce se pierde la trimitere** | automat | **atasamentele, semnele de carte, comentariile si adnotarile nu se transfera** | D |
| Q-042 | `E-mail > Document...` | `File > E-mail > Document...`; `Ctrl+M` | **toate formatele, cu excepția HTML** | D |
| Q-043 | Opțiunile de impartire la e-mail | dialog | **toate paginile intr-un fisier / fiecare pagina in fisier separat / impartire la paginile goale**, apoi `OK` | D |
| Q-044 | `E-mail > Images...` | `File > E-mail > Images...`; `Ctrl+Alt+M` | format, plus bifa `Send as multi-page image file` | D |
| Q-045 | `Send to Amazon Kindle...` | sageata de lângă `Save As` | **cere un cont Kindle.com. Campuri: adresa contului Kindle, aceleasi trei opțiuni de impartire, si numele fisierului. Se creeaza un e-mail cu atasamentul, care trebuie trimis** | D |
| Q-046 | Trimiterea in Word, Excel, PowerPoint | `File > Send To` | aplicatia trebuie instalata | V |
| Q-047 | Trimiterea in clipboard | `File > Send To` | — | V |
| Q-048 | Trimiterea in browser | `File > Send To` | — | V |
| Q-049 | `Print text` | `Ctrl+P` | — | D |
| Q-050 | `Print image` | `Ctrl+Alt+P` | — | D |
| Q-051 | Avertisment la export cu pagini invalidate | la salvare | paginile cu status `analyzed` dupa o modificare | N |

### Q.5 Aplicatiile cu care se interopereaza

| ID | Cerinta | Detaliu | Src |
|---|---|---|---|
| Q-060 | Versiunile de Office suportate de original | **Word, Excel, PowerPoint: 365, 2019, 2016 (16.0), 2013 (15.0); Office 2021 Professional Plus** | D |
| Q-061 | SharePoint | **Online, 2019, 2016, 2013** | D |
| Q-062 | Alternativele libere | **Apache OpenOffice Writer 4.1; LibreOffice Writer 6.2.5 si 6.3.0** | D |
| Q-063 | Stocare | **Microsoft Azure Storage Account** | D |
| Q-064 | Recomandarea | **se instaleaza ultimele actualizari ale aplicatiilor, pentru compatibilitate** | D |
| Q-065 | Diferenta noastra | **produsul nostru trebuie sa citeasca si sa scrie aceste formate cu biblioteci proprii, fara sa depinda de Office instalat** | X |
