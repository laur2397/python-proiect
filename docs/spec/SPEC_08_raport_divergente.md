# SPECIFICATIE 08 — RAPORT DE DIVERGENTE

**De ce exista acest document.** Ai spus ca specificatia pare buna, dar nu se indeplineste unu la unu. Ai avut dreptate. Am citit manualul oficial ABBYY FineReader PDF integral (513 pagini, ediția engleza, `help.abbyy.com/assets/en-us/finereader/16/Users_Guide.pdf`), paginile de help pentru scurtaturi, Hot Folder si linia de comanda, si articolele relevante din baza de cunostinte ABBYY. Documentul de mai jos listeaza fiecare divergenta gasita si ce am facut cu ea.

## Bilantul

| | Versiunea 1 | Versiunea 2 |
|---|---|---|
| Cerinte numerotate | 789 | **1.124** |
| Confirmate din documentatia oficiala | nemarcate | **998** |
| Observate in video, neconfirmate in scris | nemarcate | 37 |
| Din baza de cunostinte ABBYY | nemarcate | 6 |
| Adaugate de noi, nu exista in original | nemarcate | **65** |
| Diferite deliberat de original, cu motiv | nemarcate | **15** |
| Cerinte de prioritate 1 in testare | 53 | **100** |

Cea mai importanta schimbare nu e numarul. E **coloana `Src`**: fiecare cerinta spune acum de unde stim ca e asa. In versiunea 1, o regula citita din manual si o regula inventata de mine arătau identic. Acum nu mai arata.

---

## 1. Divergente grave — specificasem greșit

Acestea nu erau lipsuri, erau afirmatii false. Fiecare ar fi dus la un produs care se comporta altfel decat originalul.

### 1.1 Linia de comanda era in mare parte inventata

**Ce scrisesem:** o linie de comanda unificata, cu `app /convert <intrare> /out <ieșire> /format pdf /layout exact /pages 1-5 /mrc /pdfa 2b /split pages:10 /threads 4 /json /recursive /quiet /config`. Treizeci de parametri, cu coduri de ieșire proprii.

**Ce spune documentatia:** **doua executabile separate, cu doua sintaxe diferite.**

```
FineReaderOCR.exe <surse> /lang <limbi> /send <aplicatie> /out <fisier> /report <fisier>
Comparator.exe /compare /file1:<cale> /file2:<cale> /lang:<limba> /recMode:<mod> /options:<lista> /saveFile:<cale> /saveMode:<mod>
```

Conversia foloseste parametri separati prin spatiu. Compararea foloseste sintaxa cu doua puncte. **Nu exista** `/format`, `/layout`, `/pages`, `/mrc`, `/pdfa`, `/dpi`, `/split`, `/merge`, `/threads`, `/json`, `/recursive`, `/quiet`, `/config`. **Exista** `/scan [NumeScaner]`, limbile proprii prefixate cu `@@`, si opt destinatii pentru `/send`: `MSWord`, `MSExcel`, `OpenOffice`, `Mail`, `Clipboard`, `WebBrowser`, `PDFViewer`, `PowerPoint`. Fara `/out`, rezultatul se deschide intr-o aplicatie si salvarea rămâne manuala. CLI-ul nu functioneaza in mod server.

**Ce am facut:** am rescris secțiunea U integral. Linia de comanda reala e in U-001…U-028, marcata `D`. Extinderile mele utile (procesarea unui folder, `/json`, coduri de ieșire) sunt acum intr-o secțiune separata, U-040…U-051, marcata `N`, cu nota ca nu fac parte din reproducerea 1:1.

### 1.2 Hot Folder nu poate rula ca serviciu

**Ce scrisesem:** „S-031 Pornirea ca serviciu — sarcinile ruleaza si cand niciun utilizator nu e conectat."

**Ce spune documentatia:** **sarcinile pornesc numai cat timp calculatorul e pornit si utilizatorul e conectat.** Baza de cunostinte ABBYY o spune explicit: nu exista posibilitatea de a rula Hot Folder ca serviciu cu niciun utilizator conectat.

In plus, limite reale pe care nu le aveam: **5.000 de pagini pe luna**, cu contorul resetat la 30 de zile, si **2 nuclee**, impuse de parametrul de licenta `Hot Folder Core Count`.

**Ce am facut:** S-005 spune acum limitarea ca regula fundamentala. S-006 si S-007 adauga limitele, marcate `K`.

### 1.3 Planificarea Hot Folder avea intervale inexistente

**Ce scrisesem:** „la fiecare N minute" si „la apariția unui fisier nou", cu un mecanism de stabilitate a fisierului de 3 secunde prezentat ca fiind al originalului.

**Ce spune documentatia:** doua moduri, `Run once` si `Recurring`, iar `Recurring` are exact patru intervale: **la fiecare minut, o data pe zi, o data pe saptamana, o data pe luna**. Efectul de urmarire se obtine prin verificarea la fiecare minut — de aici statusul `Watching...`. Evidenta fisierelor deja procesate se tine intr-un fisier `.ppi` lângă sarcina, nu prin data modificarii.

**Ce am facut:** S-032 descrie intervalele reale. S-009 descrie mecanismul `.ppi`, marcat `K`. Regula mea de stabilitate de 3 secunde rămâne, dar e acum S-073, marcata `N`, cu motivul.

### 1.4 Evenimentele butoanelor de formular erau numite greșit

**Ce scrisesem:** `Click`, `Drop`, `Mouse Enter`, `Mouse Exit`, `On Focus`, `On Blur`.

**Ce spune documentatia:** `Click`, `Drop`, **`Mouse Over`**, **`Mouse Out`**, **`Focus`**, **`Focus Out`**.

Patru din sase nume erau greșite. Un AI programator ar fi scris patru evenimente care nu exista in formatul PDF cu numele acela.

**Ce am facut:** H-040, marcata `D`.

### 1.5 `Delete Watermarks` sterge toate filigranele

**Ce scrisesem:** „F-041 se sterg doar filigranele adaugate de aplicatie".

**Ce spune documentatia:** comanda sterge **toate** filigranele.

**Ce am facut:** F-050.

### 1.6 `Best Fit` potriveste inaltimea, nu pagina intreaga

**Ce scrisesem:** „pagina incape intreaga".

**Ce spune documentatia:** `Fit to Width` potriveste latimea paginii pe ecran; **`Best Fit` potriveste inaltimea paginii.**

**Ce am facut:** B-011 si B-013.

### 1.7 Scurtaturile se configureaza din OCR Editor, nu din Options

**Ce scrisesem:** „X-085 Scurtaturi de tastatura — tabel editabil in `Options > Other`".

**Ce spune documentatia:** reatribuirea se face din OCR Editor, prin **`View > Toolbars > Customize... > Keyboard Shortcuts`**, cu `Categories`, campul `Press new shortcut key`, butoanele `Assign`, `Reset` si `Reset All`. Nu exista in dialogul Options.

**Ce am facut:** X-148.

### 1.8 `Timed Screen` are intarziere fixa

**Ce scrisesem:** „V-006 intarziere intre 1 si 60 de secunde".

**Ce spune documentatia:** **5 secunde, fixe.**

**Ce am facut:** V-006.

### 1.9 Salvarea rezultatelor de comparare avea alte opțiuni

**Ce scrisesem:** PDF cu comentarii, document Word cu doua coloane, raport de diferente.

**Ce spune documentatia:** trei variante, dintre care prima nu o aveam deloc: **`DOCX in Track Changes Mode`** pentru fiecare document, **`PDF with Comments`** pentru fiecare document, si **`Comparison Report`** ca tabel Word. Plus un avertisment obligatoriu: **fisierele DOCX salvate sunt versiuni recunoscute si pot conține erori de recunoastere.** Formatele de salvare sunt numai `.pdf` si `.docx`.

**Ce am facut:** R-060…R-066. R-062 e avertismentul, marcat prioritate 1.

### 1.10 Integrarile Office existau, iar eu le dadusem la o parte

**Ce scrisesem:** „W-005 in original exista add-in-uri de Office; alternativa le inlocuieste cu meniul contextual din Explorer, pentru a nu depinde de Office."

Prima parte e corecta, dar o decizie de proiectare a mea era prezentata ca si cum originalul n-ar avea mare lucru acolo. Are: add-in-uri in Word, Excel, PowerPoint si Outlook, cu butoane si setari proprii, plus integrare SharePoint cu check-out si check-in.

**Ce am facut:** secțiunea W rescrisa: W-030…W-041 pentru Word, W-050…W-060 pentru Excel, PowerPoint si Outlook, W-070…W-075 pentru SharePoint, toate `D`. Decizia noastra de a nu depinde de Office rămâne, dar e acum Y-007, marcata `X`, cu motivul.

---

## 2. Module care lipseau complet

### 2.1 Copierea continutului din PDF

Un modul intreg, cu trei moduri si reguli proprii, care nu exista nicaieri in versiunea 1. Acum C-040…C-049:

- zona de copiat trebuie sa rămână **in interiorul unei singure pagini**;
- `Copy as Image` (`Ctrl+C`), `Copy as Text` (`Ctrl+Shift+C`), `Copy as Table` (`Ctrl+Alt+C`);
- a doua metoda de copiere de text, prin selectie directa, **poate traversa mai multe pagini** si cere strat de text;
- inainte de copierea unui tabel se pot adauga si sterge separatoare si se pot uni sau separa celule; **fisierul original nu se modifica**;
- pentru editarea tabelului in fisierul sursa se foloseste OCR Editor.

### 2.2 Confirmarile de securitate din PDF Editor

Nu aveam nimic despre asta. Originalul cere confirmare `Allow` sau `Cancel` **inainte de deschiderea unui atasament, inainte de deschiderea unui link si inainte de trimiterea datelor unui formular.** Acum B-034, B-035, B-036, toate prioritate 1.

### 2.3 Lucrul in grup pe dictionare partajate

Acum J-080…J-085. Reguli pe care nu le-am fi ghicit:

- utilizatorii care partajeaza o limba pot adauga si sterge cuvinte, dar **nu pot schimba proprietatile limbii**;
- cat timp un utilizator editeaza un dictionar, ceilalti il pot folosi pentru recunoastere si verificare, dar **nu pot adauga sau sterge cuvinte**;
- **modificarile intra in efect dupa repornirea aplicatiei.**

### 2.4 Hyperlinkurile in OCR Editor

Nu aveam decat linkurile din PDF Editor. OCR Editor are dialogul `Edit Hyperlink` cu campul `Text to display` si trei tipuri de tinta. Acum O-050…O-056.

### 2.5 Etichetele de data si ora

Fara ele, stampilele si antetele nu se pot implementa corect. Acum Z-001…Z-013: `<d/>`, `<date/>`, `<t12/>`, `<t24/>`, `<time/>`, coduri de regiune de forma `<date=USA/>`, si formate proprii `%Y`, `%#m`, `%b`, `%B`, `%a`, `%A`, `%I`, `%p`, `%M`, `%S`, `%%`. Plus regula ca `%p` functioneaza numai pentru regiunile USA, ENG, HUN si CZ.

### 2.6 Expresiile regulate pentru limbi proprii

Dictionarul unei limbi proprii poate fi o expresie regulata. Acum Z-020…Z-030, cu simbolurile suportate si regula ca `@` e caracter rezervat.

### 2.7 Scrierea gotica

Sase limbi (Old English, Old French, Old German, Old Italian, Old Spanish, Latvian Gothic), trei familii de caractere (Textur/Textualis, Fraktur, Schwabacher), si o regula importanta: **se foloseste numai limba gotica, nu in combinatie cu una moderna.** Acum P-076…P-079.

### 2.8 Trimiterea la Kindle

`Send to Amazon Kindle...`, cu adresa contului, cele trei opțiuni de impartire si numele fisierului. Acum Q-045.

### 2.9 Tipurile de PDF, ca referinta

Trei tipuri cu definitii exacte, care decid comportamentul de recunoastere. Acum I-030…I-033, cu regula fixa: **PDF-urile cautabile si cele doar-imagine folosesc intotdeauna OCR, indiferent de setare.**

### 2.10 Cerintele de sistem si cifrele reale

Windows 11 si 10 pe 64 de biti, Server 2022 la 2012 R2; minim 1 GHz x64, 2 GB RAM plus 512 MB per procesor suplimentar, 1,6 GB pentru instalare plus 1,6 GB liberi; recomandat 1,5 GHz si 4 GB RAM; servere de terminal testate; TWAIN si WIA. **201 limbi OCR**, **37 de limbi de comparare**, **22 de limbi de interfata**. Acum Y-002…Y-008 si X-044…X-048.

---

## 3. Corectii de detaliu, grupate

### 3.1 Panoul de conversie din Lansator

| Ce scrisesem | Ce spune documentatia |
|---|---|
| `Full-text search` cu doua valori | **trei: `As in original document`, `Search inside text and images`, `Disable full-text search`** |
| `Create PDF/A` fara valoare implicita | **PDF/A-2b implicit** |
| panoul Word fara opțiuni de layout | **`Keep formatting` cu patru valori** |
| panoul Excel la fel ca cel Word | **numai doua valori de layout, plus `Create a separate sheet for each page`, numai XLSX** |
| nimic despre scanarea pagina cu pagina | **dupa fiecare pagina se ofera `Scan Again` sau `Finish Scanning`** |
| compresia TIFF nespecificata la scanare | **`PACKBITS`, `JPEG (JFIF)`, `ZIP`, `LZW`, cu domeniul de folosire al fiecareia** |

### 3.2 Recunoasterea in fundal

Trei reguli pe care nu le aveam: e **activa implicit**; **stratul temporar nu se pastreaza** cand documentul se deschide in alta aplicatie; **nu poate rula pe procesoare cu un singur nucleu**. Acum B-028, B-029, B-030.

### 3.3 Editarea continutului

| Ce lipsea | Ce spune documentatia |
|---|---|
| limitarea pe tip de document | **PDF-urile al caror text e grafica vectoriala nu se pot edita** |
| comportamentul fontului | **numele fontului se afiseaza in paranteze patrate cand e incorporat in PDF dar neinstalat; trebuie instalat, altfel se foloseste un font implicit** |
| limita blocului | **un bloc de text nou nu poate fi mai mare decat pagina** |
| cand apare butonul de indreptare | **numai pe paginile pe care s-a detectat inclinare** |
| validarea linkurilor | **e-mailul cere prefixul `mailto:`, fisierul cere `file://`** |

### 3.4 Organizarea paginilor

| Ce lipsea sau era aproximativ | Ce spune documentatia |
|---|---|
| split pe dimensiune | **limita trebuie sa fie sub dimensiunea originalului, dar rezultatul poate totusi depasi limita, in functie de imagini, fonturi si formulare** |
| numele la split dupa semne de carte | **`Same as bookmark name` cu `Add numeration` bifat implicit, sau `Use Custom name`** |
| ce se intampla dupa split | **folderul de ieșire se deschide intr-o fereastra noua** |
| diferenta dintre adaugarea din PDF si din fisier | **din PDF se adauga fara procesare de imagine; din fisier e mai lent, dar are `Split facing pages` si setari de procesare** |
| avertismentul la pagini goale | **se verifica intai dacă paginile conțin note de mana sau imagini** |

### 3.5 Formularele

Peste douazeci de corectii de etichete si reguli. Cele care conteaza cel mai mult:

- `Stroke Color`, nu „culoare de chenar"; `Thickness`; `Set as Default Style`;
- caseta de bifare are **`Enabled by Default`** si **`Checkmark Color`**;
- butonul radio are **`Radio Group Name`**, **`Radio Group Tooltip`** si **`Radio Button Name`**, plus **`Dot Color`**;
- butonul are camp **`Button Text`**;
- campul text are tabul `Format` cu `Text` (`Single Line` sau `Multiline`) sau `Date`, iar caseta **`View`** fixeaza formatul final: utilizatorul poate tasta orice format, dar se reduce la cel din `View`;
- lista derulanta are **`Unset as Default`** si **`Allow non-list items`**; elementul implicit revine cand toate campurile se golesc;
- **inaltimea nu poate fi 0**;
- **campurile se pot muta numai in interiorul paginii lor**;
- **schimbarea numelui unei copii legate o transforma in copie independenta**;
- salvarea care pastreaza campurile e numai `File > Save As > PDF Document...`; alte formate fac formularul needitabil;
- un formular fara campuri interactive se completeaza **scriind peste el cu unealta `Export`**.

### 3.6 Securitatea

- **parola de permisiuni poate deschide si documentul** — nu o aveam;
- `128-bit AES` si `256-bit AES`, cu domeniul `All document contents` sau `All document contents except metadata`;
- redactarea are **sapte casete de culoare, o sageata de paleta si `More colors...`**;
- `Delete objects and data` din setarile de format are exact patru elemente: `Comments and markup`; `Links, media, actions, scripts, and form data`; `Bookmarks`; `Attachments`;
- PDF/A **include** fonturi incorporate (cu excepția textului invizibil), numai fonturi care permit incorporarea, culori independente de dispozitiv si metadate conforme; **nu suporta** audio, video si 3D, scripturi, criptare, linkuri externe si continut cu drepturi, de exemplu compresia LZW;
- PDF/A-1 e bazat pe PDF 1.4, PDF/A-2 pe PDF 1.7 si adauga Unicode, JPEG2000, transparenta, atasamente si semnaturi digitale, PDF/A-3 adauga atasamente in orice format;
- credentialele serverului de marca temporala se pastreaza in **Windows Credential Manager**;
- certificatele care nu apar in lista se instaleaza prin **`Certificate Import Wizard`**;
- **semnaturile anterioare rămân valide** cand se adauga una noua.

### 3.7 OCR Editor

| Ce lipsea sau era greșit | Ce spune documentatia |
|---|---|
| scurtaturile de panouri | **`F5` Pages, `F6` numai Image, `F7` Image si Text, `F8` numai Text, `Ctrl+F5` Zoom** |
| personalizarea barelor | **bara principala NU e personalizabila; `Quick Access Bar` e ascunsa implicit si se personalizeaza din `View > Customize...`** |
| proiectele vechi | **conversia e ireversibila, cere salvare sub alt nume, iar textul recunoscut NU se transfera** |
| extensiile de fisier | **`*.fbt` si `*.fbtx` pentru sabloane si limbi; `*.blk` si `*.blkx` pentru sabloane de zone; `*.pmd`, `*.txt` si `*.dic` pentru import de dictionare; `*.hft` pentru sarcini Hot Folder** |
| reordonarea paginilor | **refacerea ordinii dupa duplex cere minimum trei pagini consecutive; `Swap book pages` cere minimum doua, din care cel putin doua alaturate** |
| parcurgerea zonelor | **tasta `Tab` trece de la o zona la urmatoarea** |
| dialogul de verificare | **butonul e `Skip`, nu `Ignore`. Exista combo `Subset` si camp `Character code`. Pentru CJK apar sugestii de caractere cu aspect asemanator** |
| opțiunile de verificare | **`ignora cuvintele cu cifre si caractere speciale`; `verifica cuvintele compuse care nu sunt in dictionar`; corectarea spatiilor in jurul punctuatiei** |
| editorul de stiluri | **se schimba numele, fontul, dimensiunea, spatierea intre caractere si scara** |
| uneltele de tabel din panoul Text | **ascunse implicit; se adauga din `View > Toolbars > Customize...`** |
| antrenarea sabloanelor | **nu e suportata pentru limbile asiatice; se pot antrena numai caractere din alfabet; pentru restul se folosesc combinatii de doua caractere sau `Insert Character`; sabloanele se aplica numai la acelasi font, dimensiune si rezolutie** |
| proprietatile limbii | **combo `Source language`; dictionar `None` / `Built-in` / `User` / `Regular expression`; importul dictionarului utilizator cere codificarea Windows-1252; exista un tabel de reguli de capitalizare** |

### 3.8 Codurile de bare

Autodetectarea acoperă **exact 11 tipuri**: Code 3 of 9, Code 93, Code 128, EAN 8, EAN 13, Postnet, UCC-128, UPC-E, PDF417, UPC-A, QR code. Celelalte se aleg manual din bara de proprietati a zonei. Fara activarea opțiunii, codurile se salveaza ca imagini. Versiunea 1 avea o lista de 11 tipuri, dar alta: includea Aztec, Data Matrix, Codabar si Interleaved 2 of 5, si nu avea Code 93, Postnet, UCC-128 si UPC-E.

### 3.9 Setarile de format

Versiunea 1 avea un rand per format. Acum sunt complete, cu toate bifele si dependentele lor, in SPEC_03 secțiunea X.5. Cele mai importante dependente, pe care nu le aveam:

- **`Keep line numbers` e disponibila numai cu `Editable copy`**;
- **`Keep bold, italic, and underlined text styles in plain text` e disponibila numai cu `Plain text`**;
- **`Use MRC compression` functioneaza numai pentru PDF cautabil cu `Text under the page image`**;
- **`Embed fonts` e disponibila numai pentru `Text and pictures only` si `Text over the page image`**;
- **HTML are trei moduri de layout, nu doua**: `Flexible layout`, `Formatted text`, `Plain text`;
- **stilurile de font se pastreaza numai in EPUB**, nu in FB2;
- `Use one paper size for all page images` e **dezactivata implicit**;
- `Preserve document metadata` e **activa implicit**;
- DjVu are `Multiple layers` cu trei valori, `Automatic` fiind implicita;
- HTML are `Book settings` cu trei moduri de impartire in fisiere;
- PPTX are `Shrink text on overflow`;
- CSV si TXT au `Insert page break character (#12)`.


### 3.10 Runda din 24.11.2026: notele Release 3 si pagina produsului

O analiza functionala a FineReader PDF 16 din documentatia publica (fara instalarea, decompilarea sau dezasamblarea produsului), facuta la auditul din 24.11.2026 (`docs/audit/AUDIT_2026-11-24.md`) si aprobata de utilizator. `support.abbyy.com` a raspuns cu 403, deci notele pe fiecare build nu s-au putut citi.

| Ce lipsea sau era greșit | Ce s-a schimbat | Sursa |
|---|---|---|
| **GlyphRecovery** (refacerea codificarii stricate a unui PDF) aparea numai in corpusul de test, legat de F-002 | cerinta noua **F-057**; corpusul `pdf_encoding_stricat/` trimite la F-057 | https://pdf.abbyy.com/blog/finereader-pdf-release-3-updates/ |
| **Pull&Recognize** era o adaugire `N` (N-012), iar corpusul `pdf_mixt/` trimitea la N-010 (`Use OCR`) | N-012 devine `D`; N-008, R-020 si X-060 spun ca modul automat ia textul digital chiar cu limba gresita si face OCR numai pe imagini; corpusul trimite la N-012 | aceeasi |
| X-141 nu avea valoare implicita si nici domeniu | implicit toate nucleele minus unul; limita se aplica si prelucrarii in fundal din PDF Editor | aceeasi |
| G-047 (LTV) era marcata `N` | `K`: originalul suporta LTV; la noi ramane sub E-508 (retea numai la cerere) | https://pdf.abbyy.com/how-to/digital-signature |
| E-102, X-414 si O-041 erau `V` | `D`, confirmate in notele Release 3; O-041 primeste rolul de titlu pe orice stil, pana la 10 niveluri | https://pdf.abbyy.com/blog/finereader-pdf-release-3-updates/ |
| P-005, X-044 (201 de limbi) si R-008, X-046, U-023 (37 de limbi de comparare) contraziceau P-100 si P-101 | fiecare trimite la P-100/P-101: pagina produsului spune 198 si 40, iar DocuLens declara propriul numar | https://pdf.abbyy.com/specifications/ |
| P-008 nu spunea ca `RomanianMoldavia` nu are dictionar in original | nota in P-008 si diferenta deliberata in secțiunea 4 | https://pdf.abbyy.com/specifications/ |

---

## 4. Ce rămâne diferit deliberat, si de ce

Cele 15 cerinte marcate `X`. Acestea nu sunt greseli: sunt locuri unde copierea originalului ar fi o greseala pentru produsul tau.

| ID | Originalul | La noi | Motivul |
|---|---|---|---|
| Y-001 | activare online, verificare de actualizari, telemetrie opționala | **nimic din acestea** | produsul e offline; asta e cerinta ta de la inceput |
| Y-012, Y-013 | activare in patru moduri, inregistrare opționala, mod de proba limitat | **fara activare si fara inregistrare** | nu vindem licente |
| V-002 | Screenshot Reader e beneficiu al inregistrarii | **mereu disponibil** | nu exista inregistrare |
| Y-007, Q-065 | cere Microsoft Office sau LibreOffice pentru formatele editabile | **biblioteci proprii** | un produs offline nu poate depinde de Office instalat |
| X-142, X-143, X-144 | verificare de actualizari, date de configurare, mesaje de marketing | **absente** | vezi Y-001 |
| U-011 | salvarea prin CLI cere licenta cu CLI extins | **mereu disponibila** | nu exista niveluri de licenta |
| Y-009 | instalator Windows | **plus AppImage si `.dmg`** | produsul tinteste si Linux si macOS |
| Y-020 | 22 de limbi de interfata | **romana si engleza obligatorii** | asta e piața reala |
| X-005 | comenzile din Explorer se instaleaza cu produsul | **setare care le poate dezactiva** | utilizatorul trebuie sa poata scoate produsul din meniul contextual |
| G-024 | stergerea textului ascuns nu e listata ca opțiune a dialogului | **opțiune separata, cu avertisment** | functia e utila, dar schimba documentul in PDF imagine si trebuie spus |
| S-072 | se bazeaza pe fisierul `.ppi` | **plus politica de 3 reincercari si folder `Errors`** | mai explicit si mai usor de depanat |

In plus, o diferenta fara cerinta `X` separata: **`RomanianMoldavia` foloseste dictionarul romanesc** (P-008). In original varianta Moldova nu are dictionar; la noi are, ca diacriticele nesigure si greselile de scriere sa fie semnalate si in documentele din Republica Moldova (P-103).

Celelalte 65 de cerinte marcate `N` sunt adaugiri: mod intunecat, tab-uri de documente, imprimanta virtuala, instalare fara drepturi de administrator, extinderile de linie de comanda, verificarea redactarii, pragul de incredere de 70, scalarea pe ecrane cu densitate mare, accesibilitatea, jurnalul de aplicatie, recuperarea dupa cadere. Fiecare e marcata, deci se poate si scoate.

---

## 5. Ce rămâne neverificabil

Spus deschis, ca sa nu para ca totul e acum 1:1.

1. **Algoritmii.** Documentatia spune ce face produsul, nu cum. Calitatea OCR-ului ABBYY, pragurile lui de incredere, euristica prin care decide intre stratul de text si OCR, algoritmul de compresie MRC — niciunul nu e public. Specificatia descrie comportamentul observabil si lasa implementarea deschisa. **Aici e cea mai mare diferenta posibila fata de original, si nu se poate inchide din documentatie.**
2. **Valorile implicite neafisate.** Documentatia da multe valori implicite, dar nu toate. Unde nu le da, am lasat marcajul `N` si valoarea noastra.
3. **Pozitiile exacte in interfata.** Manualul descrie dialogurile, nu pixelii. Aspectul vizual rămâne din capturile video si din descrieri.
4. **Lista completa a celor 201 de limbi** si tabelul fonturilor per limba exista in manual, dar nu sunt reproduse in specificatie. Produsul trebuie sa declare ce limbi acopera; nu se poate promite paritate fara modelele ABBYY.
5. **Formatele de fisier ale originalului** (`.hft`, `.fbtx`, `.blkx`, `.ppi`) sunt cunoscute doar ca nume si locatie. Compatibilitatea binara cu ele nu face parte din aceasta lucrare si ar cere inginerie inversa a formatului, pe care briefingul nu o cere si pe care nu am facut-o.
6. **Numerele de licenta** (limita de 5.000 de pagini, 2 nuclee) vin din baza de cunostinte, nu din manual, si se pot schimba.

---

## 6. Sursele folosite in aceasta runda

| Sursa | Ce a dat |
|---|---|
| `help.abbyy.com/assets/en-us/finereader/16/Users_Guide.pdf` — manualul oficial, 513 pagini, citit integral in sapte bucati | majoritatea celor 998 de cerinte marcate `D` |
| `help.abbyy.com/en-us/finereader/16/user_guide/hotkeys` | lista completa de scurtaturi, pe cele patru ferestre |
| `help.abbyy.com/en-us/finereader/16/user_guide/hotfolder` | statusurile, expertul si limitarile Hot Folder |
| `help.abbyy.com/en-us/finereader/16/user_guide/commandline_convert` | sintaxa reala de conversie |
| `help.abbyy.com/en-us/finereader/16/user_guide/commandline_compare` si `commandline_save` | sintaxa reala de comparare si de salvare |
| `help.abbyy.com/en-us/finereader/16/user_guide/sourceimage`, `cjkrecognition`, `newfeatures` | limbile, scrierile complexe, noutatile versiunii 16 |
| `support.abbyy.com` — articole despre nuclee, limita de pagini, locul sarcinilor Hot Folder, rularea cu utilizator deconectat | cele 6 cerinte marcate `K` |
| cele 22 de tutoriale video din runda a doua | cele 37 de cerinte marcate `V`, acolo unde documentatia nu spune nimic |

Manualul in engleza a fost citit cap la cap, nu doar cautat. De aceea raportul poate spune nu doar ce exista, ci si **ce nu exista** — de exemplu ca linia de comanda nu are parametru de format.
