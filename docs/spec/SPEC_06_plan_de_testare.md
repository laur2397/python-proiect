# SPECIFICATIE 06 — PLAN DE TESTARE SI ACCEPTANTA

Documentul 10 din livrabile. Legat 1:1 de ID-urile cerintelor din SPEC_01, SPEC_02 si SPEC_03.

**1.487 de cerinte numerotate → 1.487 de teste.** Matricea completa e in `SPEC_07_matrice_trasabilitate.csv`, generata de `genereaza_matrice_trasabilitate.py` din fisierele de specificatie. Scriptul pica dacă o cerinta rămâne fara test sau dacă API-ul trimite la o cerinta inexistenta, deci matricea nu poate ieși din sincronizare pe nesimtite.

Matricea poarta si coloana `Src` din specificatii: **1.063 de cerinte sunt confirmate din documentatia oficiala**, 300 din tutoriale video analizate cadru cu cadru, 9 din baza de cunostinte ABBYY, 72 sunt adaugiri proprii si 25 sunt diferente deliberate. Un test care pica pe o cerinta marcata `D` e o abatere de la original. Un test care pica pe una marcata `N` e doar o functie proprie neterminata. Prioritizarea defectelor merge dupa aceasta coloana.

Regula de numerotare: cerinta `M-009` → testul `T-M009`. Un test, o cerinta. Cand un test are nevoie de mai multe cazuri, acestea se numeroteaza `T-M009.1`, `T-M009.2` si asa mai departe, dar toate raspund de aceeasi cerinta.

---

## 1. Nivelurile de testare

| Nivel | Cod | Ce acopera | Cum ruleaza | Numar de teste |
|---|---|---|---|---|
| Unitar | U | functii pure din `core`: preprocesare, zone, incredere, parsare | pytest, fara interfata, fara fisiere mari | 391 |
| Integrare | I | lanturi din `core`: deschide → analizeaza → recunoaste → exporta | pytest cu corpusul de fisiere de test | 736 |
| End-to-end | E | prin interfata, cu clicuri reale | pytest-qt, pe o sesiune grafica virtuala | 159 |
| Manual | M | scaner, imprimanta, smartcard, meniu contextual in Explorer | lista de verificare, inainte de fiecare lansare | 201 |

**Prioritatea 1** o au 138 de cerinte: cele care, dacă pica, fac produsul greșit, nu doar incomod. Niciun build nu se livreaza cu un test de prioritate 1 picat. Procedurile celor mai importante sunt scrise in capitolul 4; restul se citesc direct din cerinta, care conține deja validarile si erorile.

---

## 2. Corpusul de fisiere de test

Fara corpus, un plan de testare e doar o lista de intentii. Fisierele se tin in `tests/corpus/`, cu un `manifest.json` care spune pentru fiecare ce conține si ce trebuie sa produca.

| Grup | Fisiere | Ce verifica |
|---|---|---|
| `pdf_digital/` | 15 PDF-uri produse de Word, LaTeX, InDesign, Chrome, Excel | N-008, N-009: stratul de text e bun, nu trebuie OCR |
| `pdf_scanat/` | 20 de scanari la 150, 200, 300 si 600 dpi, alb-negru, gri si color | tot lantul de OCR |
| `pdf_mixt/` | 6 documente cu text digital si imagini scanate in acelasi fisier | N-012: Pull & Recognize |
| `pdf_encoding_stricat/` | 5 PDF-uri din care textul se copiaza ca mojibake | F-057: GlyphRecovery |
| `romanesti/` | 25 de documente in romana: contracte, facturi, hotarari, cereri de finantare, adeverinte | P-008: si varianta cu sedila (ş, ţ), si cea cu virgula (ș, ț) |
| `tabele/` | 18 pagini cu tabele: cu linii, fara linii, cu celule unite, pe doua pagini, cu subtotaluri | M-031..M-039 |
| `formulare/` | 10 PDF-uri cu formulare AcroForm, inclusiv unul cu XFA | H-001..H-052 |
| `semnate/` | 8 PDF-uri semnate: valid, expirat, certificat neincrezut, modificat dupa semnare, cu marca temporala, cu LTV | G-041 |
| `protejate/` | 6 PDF-uri: doar parola de deschidere, doar de permisiuni, ambele, AES-128, AES-256, RC4 vechi | G-002..G-009 |
| `pdfa/` | 8 fisiere conforme si 4 neconforme, pe mai multe versiuni | I-006 |
| `foto/` | 20 de fotografii de documente, facute cu telefonul: oblice, cu umbra, cu fundal, neclare | L-004, L-005, L-021..L-024 |
| `carti/` | 10 scanari de pagini duble, cu cotor curbat | L-003, L-007, J-016 |
| `coduri_bare/` | 1 pagina per tip, din cele 11 tipuri (N-021) | N-020, N-021 |
| `goale/` | 10 pagini: complet alba, alba cu praf de scaner, cu un singur numar de pagina, cu o linie | E-021: unde e pragul |
| `mari/` | 3 fisiere: 500 de pagini, 1.500 de pagini, o pagina A0 la 600 dpi | Y-016, Y-017, R-027 |
| `corupte/` | 8 fisiere: PDF trunchiat, antet greșit, xref stricat, JPEG trunchiat, TIFF cu pagina ilizibila | A-010, J-008 |
| `comparare/` | 12 perechi, cu numarul de diferente numarat manual | R-021, R-022, R-030 |
| `multilingv/` | 8 documente: romana+engleza, chirilic, greaca, arab, chineza, text vertical | P-001, M-030 |

**Regula pentru corpus:** fiecare fisier vine cu rezultatul asteptat scris de mana intr-un fisier `.expected` de lângă el — textul corect, numarul de pagini, numarul de tabele, numarul de celule. Fara rezultat scris de mana, un test de OCR nu verifica nimic: compara o ieșire cu ea insasi.

**Drepturi:** corpusul nu poate conține documente cu date personale reale si nici documente la care nu avem drepturi. Documentele romanesti de test se construiesc din formulare publice si din texte proprii, apoi se tipăresc si se scaneaza.

---

## 3. Pragurile de calitate

Un plan de testare pentru un produs de OCR are nevoie de numere, nu de „recunoaste bine".

| Indicator | Cum se masoara | Prag de acceptanta |
|---|---|---|
| Acuratete pe caracter, scanari bune de 300 dpi | 1 − (distanta Levenshtein / numarul de caractere din referinta) | **≥ 98%** |
| Acuratete pe caracter, scanari de 200 dpi | idem | ≥ 94% |
| Acuratete pe caracter, fotografii de telefon dupa preprocesare | idem | ≥ 90% |
| Acuratete pe cuvant, documente romanesti cu diacritice | cuvinte identice / cuvinte din referinta | **≥ 96%** |
| Confuzia ș/ş si ț/ţ | numarul de confuzii per 1.000 de caractere | ≤ 2 |
| Detectia corecta a structurii de tabel | celule corecte / celule din referinta | **≥ 90%** |
| Detectia orientarii paginii | pagini orientate corect / total | ≥ 99% |
| Deskew | eroarea unghiulara dupa corectie | ≤ 0,3 grade |
| Pagini goale | precizie si rapel pe grupul `goale/` | ≥ 95% ambele |
| Coduri de bare | coduri citite corect / coduri din corpus | 100% pe cele 11 tipuri declarate |
| Diferente la comparare | diferente gasite vs numarate manual | precizie ≥ 95%, rapel ≥ 95% |
| Viteza de recunoastere | pagina A4, 300 dpi, gri, text simplu, mod `thorough`, pe 8 nuclee | ≤ 4 s per pagina |
| Viteza de recunoastere, mod `fast` | idem | ≤ 1,5 s per pagina |
| Timp de deschidere a unui PDF de 500 de pagini | pana la afisarea primei pagini | ≤ 2 s |
| Memorie la un proiect de 500 de pagini | varf de memorie rezidenta | ≤ 2 GB |
| Interfata nu se blocheaza | niciun blocaj al firului de interfata | > 200 ms = test picat |
| Dimensiunea PDF-ului cu MRC | fata de PDF-ul imagine echivalent | ≤ 35% |

Pragurile se masoara automat, nu la ochi: `tests/benchmark/` ruleaza corpusul si scrie un raport comparabil intre build-uri. **Un build care scade un indicator cu peste 2% fata de build-ul anterior se trateaza ca regresie, chiar dacă rămâne peste prag.**

---

## 4. Procedurile testelor de prioritate 1

Cele mai importante dintre cele 138 de teste de prioritate 1 — cele care decid dacă produsul e corect. Fiecare are precondiție, pasi si criteriu de trecere masurabil. Restul cerintelor de prioritate 1 se testeaza direct din coloanele de validari si erori ale cerintei.

### 4.1 Regulile descoperite din tutoriale, care nu apar in documentatie

Acestea sunt cele mai usor de ratat la implementare, pentru ca nimeni nu le citeste intr-un manual.

| Test | Cerinta | Procedura | Criteriu de trecere |
|---|---|---|---|
| T-Q001 | Q-001 | Pentru fiecare dintre cele 5 moduri de layout, se cere exportul in fiecare dintre cele 18 formate: 90 de combinatii | Exact combinatiile din matricea Q-002..Q-006 reusesc; toate celelalte ridica `IncompatibleLayoutError`. Nicio combinatie in plus, niciuna in minus |
| T-Q002 | Q-002 | export in modul `exact` | reusesc RTF, DOCX, PDF, PPTX, ODT, DJVU; restul pica |
| T-Q003 | Q-003 | modul `editable` | reusesc RTF, DOCX, ODT; restul pica |
| T-Q004 | Q-004 | modul `formatted` | reusesc RTF, DOCX, XLSX, TXT, HTML, ODT, FB2, EPUB; **CSV pica** |
| T-Q005 | Q-005 | modul `plain` | reusesc aceleasi plus CSV |
| T-Q006 | Q-006 | modul `flexible` | reuseste **numai** HTML |
| T-F005 | F-005 | Se deschide un PDF cu un font care nu e instalat (de exemplu un font comercial), se intra in editare si se tasteaza un caracter | Textul nou se deseneaza cu un font instalat, raportat de `FontMatcher.match()` cu scor > 0; in jurnal apare fontul cerut si fontul ales. **Nu se accepta: text invizibil, dreptunghiuri, cadere** |
| T-N008 | N-008 | Se deschid 15 PDF-uri digitale si 20 de scanari, cu modul `AUTO` | Toate cele 15 digitale sunt tratate `TEXT_ONLY`; toate cele 20 de scanari sunt tratate `FORCE_OCR`. Zero clasificari greșite |
| T-N009 | N-009 | Se deschide un PDF digital cu strat de text stricat (din grupul `pdf_encoding_stricat/`) cu modul `AUTO` | `evaluate_text_layer()` intoarce sub prag si se trece pe OCR. Textul rezultat e corect, nu mojibake |
| T-N010 | N-010 | Cele 6 documente mixte, cu modul `AUTO` | Textul digital se extrage identic cu originalul (0 diferente), iar textul din imagini se recunoaste. Rezultatul le conține pe ambele, in ordinea corecta a paginii |
| T-O041 | O-041 | Se construiesc 3 stiluri cu `heading_level` 1, 2 si 3, se aplica pe un document de 20 de pagini, se exporta PDF cu `create_bookmarks_from_headings=True` | PDF-ul rezultat are exact atatea semne de carte cate fragmente cu stil de titlu exista, cu ierarhia corecta pe 3 niveluri |
| T-E031 | E-031 | Se imparte un PDF de 60 de pagini cu 12 semne de carte de nivel 1 si 3 atasamente, dupa semne de carte | 12 fisiere; **niciunul nu are semne de carte**; cele 3 atasamente se gasesc in subfolderul `Attachments`, cu suma de control identica |
| T-M022 | M-022 | Pagina cu 3 coloane, o pagina in ebraica si o pagina cu text vertical chinezesc | Numerele zonelor merg de la stanga la dreapta, apoi de sus in jos, **si in documentul in ebraica**, nu in ordinea de citire a textului |
| T-M032 | M-032 | Sablon salvat de pe o pagina A4 la 300 dpi, incarcat pe: aceeasi dimensiune, pe A4 la 600 dpi, pe Letter la 300 dpi | Pe prima reuseste; pe celelalte doua ridica `TemplateSizeMismatchError`; cu `scale=True` reuseste si zonele sunt scalate proportional, cu eroare sub 2 px |
| T-N026 | N-026 | Pagina recunoscuta. Se muta o zona, se schimba tipul unei zone, se roteste pagina, se schimba limbile. Cate un caz separat | In toate cele 4 cazuri statusul paginii revine la `analyzed`; la export apare avertismentul din Q-034 cu numarul paginii |
| T-X165 | X-165 | Se schimba culoarea si grosimea chenarului pentru fiecare dintre cele 6 tipuri de zona | Toate cele 6 se pot schimba si se pastreaza intre sesiuni. **Culorile nu sunt fixate in cod** — se verifica prin cautare in sursa: niciun literal de culoare de zona in fisierele de interfata |

### 4.2 Integritatea datelor

| Test | Cerinta | Procedura | Criteriu de trecere |
|---|---|---|---|
| T-G020 | G-020 | Se redacteaza un cuvant pe 5 pagini | Cuvantul nu apare la extragerea textului, nici la `pdftotext`, nici la o cautare binara in fisier |
| T-G021 | G-021 | Se forteaza artificial o redactare incompleta (test cu dublura care lasa textul) | `RedactionVerificationError` se ridica si documentul **nu** se salveaza |
| T-G022 | G-022 | `delete_objects_and_data(hidden_text_and_objects=True)` pe un PDF cautabil | Documentul devine PDF imagine; `has_text_layer()` intoarce False pe toate paginile |
| T-I001 | I-001 | Se deschid 15 PDF-uri de versiuni 1.4 … 2.0, se adauga un comentariu, se salveaza | Versiunea PDF din fisierul salvat e identica sau mai mare, niciodata mai mica |
| T-I007 | I-007 | Se deschide un PDF de 100 de pagini, se editeaza textul paginii 1, se salveaza | Fluxurile de continut ale paginilor 2-100 sunt identice la nivel de octeti cu originalul |
| T-C018 | C-018 | Se inlocuieste un cuvant intr-un PDF scanat | Textul nou apare vizual; **documentul rămâne PDF imagine**; pe fundal neuniform apelantul a primit avertismentul inainte de operatie |
| T-F024 | F-024 | Se sterge o zona cu unealta `Erase` | Continutul dispare din pagina **si** din stratul de text; cautarea nu il mai gaseste |
| T-E005 | E-005 | Se incearca stergerea tuturor paginilor | `LastPageError`; documentul rămâne cu o pagina |
| T-J055 | J-055 | Idem pe un proiect OCR | `LastPageError` |
| T-J034 | J-034 | Se salveaza un proiect cu 50 de pagini, zone, text editat si avertismente; se reincarca | Toate cele 4 categorii se regasesc identic: zone (poligoane cu precizie de 1 px), text editat cu `original_text`, statusuri, avertismente |
| T-J037 | J-037 | Se omoara procesul la mijlocul unei recunoasteri; se reporneste | Se ofera recuperarea; proiectul recuperat conține paginile procesate pana la ultima salvare automata |
| T-I024 | I-024 | Idem pe un PDF cu modificari nesalvate | Se ofera recuperarea; adnotarile adaugate inainte de ultima salvare automata sunt prezente |

### 4.3 Securitate

| Test | Cerinta | Procedura | Criteriu de trecere |
|---|---|---|---|
| T-G002 | G-002 | Se cripteaza cu parola de deschidere; se deschide cu parola corecta si cu 3 parole greșite | Cu parola corecta se deschide; cu cele greșite `WrongPasswordError`, fara sa dezvaluie nimic din continut |
| T-G004 | G-004 | Se cere aceeasi parola pentru deschidere si pentru permisiuni | `SamePasswordError`; nimic nu se scrie pe disc |
| T-G010 | G-010 | Se cripteaza AES-128 si AES-256; se deschide un fisier vechi cu RC4-40 | Scrierea foloseste numai AES; RC4 se citeste, dar nu se scrie niciodata |
| T-G030 | G-030 | Se semneaza cu un certificat de test | Semnatura e PAdES si se valideaza in Adobe Acrobat Reader, nu doar in aplicatia proprie |
| T-G037 | G-037 | Se semneaza cu un server de marca temporala inaccesibil | `TimestampUnavailableError`; cu `allow_without_timestamp=True` semnatura se face fara marca temporala si asta se vede in proprietati |
| T-G041 | G-041 | Cele 8 fisiere din `semnate/` | Fiecare primeste starea corecta. **Un certificat expirat da „valida, dar certificatul a expirat", nu „invalida"**; un fisier modificat dupa semnare da „invalida" |
| T-G043 | G-043 | Se incearca stergerea unei semnaturi fara certificatul potrivit | `CertificateNotOwnedError` |
| T-B040 | B-040 | Se deschide un PDF cu JavaScript | Scriptul **nu** ruleaza; apare notificarea; dupa activare explicita ruleaza; un script cu buclă infinita se opreste sub 2 secunde si se noteaza in jurnal |
| T-X145 | X-145 | Setarea de JavaScript la prima pornire | Valoarea implicita e dezactivat |
| T-Y001 | Y-001 | Se dezactiveaza toate interfetele de retea si se ruleaza toata suita de integrare | **Zero teste picate.** In paralel, un monitor de socket-uri la nivel de proces nu inregistreaza nicio incercare de conexiune in timpul rularii normale |

### 4.4 Corectitudinea recunoasterii

| Test | Cerinta | Procedura | Criteriu de trecere |
|---|---|---|---|
| T-N003 | N-003 | Recunoastere pe tot corpusul `pdf_scanat/` si `romanesti/` | Pragurile din capitolul 3 |
| T-N003 | N-003 | Proiect cu 10 pagini: 3 recunoscute, 4 analizate, 3 importate. `recognize_pages(skip_recognized=True)` | Cele 3 recunoscute nu se reproceseaza (se verifica prin `recognized_at` neschimbat); celelalte 7 se recunosc |
| T-N024 | N-024 | Document cu text clar si text degradat | Fiecare caracter are un scor 0..100; scorurile medii pe textul degradat sunt sub cele pe textul clar |
| T-N025 | N-025 | Se schimba pragul de la 70 la 50 si la 90 | Numarul de cuvinte marcate nesigure scade la 50 si creste la 90, monoton |
| T-P001 | P-001 | Se cere recunoastere cu zero limbi | `NoLanguageSelectedError`. Cu 4 limbi apare avertismentul de incetinire |
| T-P008 | P-008 | Cele 25 de documente din `romanesti/`, jumatate cu sedila, jumatate cu virgula | Pragul de confuzie ș/ş si ț/ţ: maximum 2 la 1.000 de caractere. **Acest test se ruleaza separat pentru fiecare dintre cele doua variante de diacritice** |

### 4.5 Formulare

| Test | Cerinta | Procedura | Criteriu de trecere |
|---|---|---|---|
| T-H013 | H-013 | Se creeaza un singur buton radio intr-un grup si se salveaza | `validate_document()` intoarce `OrphanRadioButtonError`; interfata avertizeaza inainte de salvare |
| T-H030 | H-030 | Nume de camp: gol, duplicat, `.nume`, `nume.`, `a..b`, `nume valid` | Primele 5 sunt refuzate cu excepția corecta; ultimul se accepta |
| T-H015 | H-015 | Se copiaza un camp de semnatura gol si unul semnat | Primul se copiaza, cu nume incrementat; al doilea ridica `SignedFieldCopyError` |
| T-H023 | H-023 | Formular cu 3 campuri obligatorii necompletate. Se salveaza, se tipareste, se trimite | **Toate trei reusesc**, cu avertisment. Niciuna nu e blocata |

### 4.6 Automatizare si linia de comanda

| Test | Cerinta | Procedura | Criteriu de trecere |
|---|---|---|---|
| T-S073 | S-073 | Se copiaza in folderul urmarit un fisier de 200 MB, cu copierea artificial incetinita la 10 secunde | Fisierul nu e preluat in timpul copierii; e preluat dupa 3 secunde de dimensiune stabila; rezultatul e complet, nu trunchiat |
| T-S072 | S-072 | Se pune un fisier corupt in folderul urmarit | Dupa 3 incercari fisierul ajunge in subfolderul `Errors` si nu mai e reprocesat; jurnalul conține cele 3 incercari |
| T-T018 | T-018 | Sarcina cu pasii: `get_images`, `save` in DOCX, fara `recognize` | `TaskValidationError` cu indexul pasului problematic si cu motivul |
| T-U006 | U-006 | Cate o rulare pentru fiecare dintre cele 8 valori ale `/send`: `MSWord`, `MSExcel`, `OpenOffice`, `Mail`, `Clipboard`, `WebBrowser`, `PDFViewer`, `PowerPoint` | Toate opt functioneaza; o a noua valoare e refuzata cu cod 1 |
| T-U051 | U-051 | Cate o rulare care produce fiecare dintre cele 6 coduri de ieșire | Codurile 0, 1, 2, 3, 4, 5 se obtin exact in situatiile declarate |

---

### 4.7 Regulile confirmate in runda de verificare

Aceste teste exista pentru ca versiunea 1 a specificatiei le avea greșit sau nu le avea deloc. Fiecare verifica o afirmatie din documentatia oficiala.

| Test | Cerinta | Procedura | Criteriu de trecere |
|---|---|---|---|
| T-U001 | U-001 | Se ruleaza sintaxa oficiala: `FineReaderOCR.exe <fisier> /lang Romanian /send MSWord` | Comanda se accepta exact in aceasta forma. Sursa, limbile si destinatia se interpreteaza corect |
| T-U012 | U-012 | Se ruleaza cate o comanda cu fiecare dintre parametrii inexistenti in original: `/format`, `/layout`, `/pages`, `/mrc`, `/pdfa`, `/split`, `/merge`, `/threads`, `/config` | **Fiecare e acceptat numai ca extindere proprie si apare ca atare in `/help`, grupat separat de parametrii originalului.** Daca produsul pretinde paritate 1:1 fara ei, comanda trebuie refuzata |
| T-U020 | U-020 | `Comparator.exe /compare /file1:a.pdf /file2:b.pdf /lang:Romanian /recMode:AutoChoose /options:IgnorePunctDiff,UngroupDiff /saveFile:out.docx /saveMode:Word` | Comanda se accepta cu sintaxa cu doua puncte. Sintaxa cu spatii, de la conversie, **nu** functioneaza aici |
| T-U024 | U-024 | `Comparator.exe /compare` fara `/recMode:` | Se foloseste `UseOnlyPdfText` |
| T-S005 | S-005 | Se creeaza o sarcina Hot Folder, se deconecteaza utilizatorul, se pune un fisier in folder | **Sarcina nu ruleaza.** Produsul nu pretinde ca ruleaza ca serviciu |
| T-S006 | S-006 | Se proceseaza 5.001 pagini intr-o luna calendaristica | La depasirea limitei procesarea se opreste si mesajul spune limita si cand se reseteaza |
| T-S009 | S-009 | Se lasa un fisier procesat in folderul urmarit si se ruleaza sarcina din nou | **Fisierul nu se reproceseaza.** Evidenta se tine intr-un fisier propriu, nu prin data modificarii |
| T-S032 | S-032 | Se creeaza cate o sarcina cu fiecare dintre cele patru intervale `Recurring` | Exista exact `la fiecare minut`, `o data pe zi`, `o data pe saptamana`, `o data pe luna`. Nu exista „la fiecare N minute" |
| T-S049 | S-049 | Folder urmarit cu trei subfoldere, cate doua fisiere in fiecare, mod de ieșire „un document per folder" | Trei fisiere de ieșire, cu ierarhia de foldere pastrata |
| T-B034 | B-034 | Se deschide un atasament dintr-un PDF | **Apare confirmarea `Allow` / `Cancel`. La `Cancel` atasamentul nu se deschide** |
| T-B035 | B-035 | Se apasa un link dintr-un PDF | Idem |
| T-B036 | B-036 | Se trimit datele unui formular | Idem |
| T-B030 | B-030 | Se ruleaza produsul pe o masina virtuala cu un singur nucleu | Recunoasterea in fundal se dezactiveaza curat, cu mesaj, fara cadere |
| T-C040 | C-040 | Se incearca marcarea unei zone de copiat care traverseaza doua pagini | Zona nu se creeaza |
| T-C044 | C-044 | Se selecteaza text care traverseaza trei pagini si se copiaza | **Textul se copiaza integral.** Aceasta metoda, spre deosebire de zona, traverseaza pagini |
| T-C047 | C-047 | Se marcheaza un tabel, se adauga doua separatoare, se unesc doua celule, se copiaza | Clipboard-ul conține structura editata; **fisierul original e neschimbat la nivel de octeti** |
| T-H015 | H-015 | Se copiaza un camp text si un camp de semnatura semnat | Copia campului text pastreaza toate proprietatile, cu excepția numelui. Copierea semnaturii semnate e refuzata |
| T-H017 | H-017 | Se incearca mutarea unui camp pe alta pagina | Mutarea e refuzata |
| T-H024 | H-024 | Se salveaza un formular ca PDF, apoi ca DOCX | PDF-ul pastreaza campurile interactive; DOCX-ul nu, si utilizatorul e avertizat |
| T-H030 | H-030 | Se completeaza un camp de tip `Date` cu un format diferit de cel din caseta `View` | **Valoarea se reduce la formatul din `View` la terminarea completarii** |
| T-F002 | F-002 | Se incearca editarea unui PDF al carui text e grafica vectoriala | Editarea nu e disponibila, cu mesaj explicit |
| T-F005 | F-005 | Se deschide un PDF cu un font incorporat si neinstalat | **Numele fontului se afiseaza in paranteze patrate.** La tastare se foloseste un font implicit si asta se noteaza |
| T-F027 | F-027 | Se creeaza un link de e-mail fara `mailto:` si un link de fisier fara `file://` | Ambele sunt refuzate pana se adauga prefixul |
| T-F050 | F-050 | Document cu trei filigrane, dintre care unul adaugat in alta aplicatie. Se apasa `Delete Watermarks` | **Toate trei dispar** |
| T-E025 | E-025 | Se imparte un PDF de 40 MB bogat in imagini, cu limita de 5 MB per fisier | Impartirea reuseste; **unele fisiere pot depasi 5 MB si produsul spune asta inainte, nu dupa** |
| T-M057 | M-057 | Cate o pagina pentru fiecare dintre cele 11 tipuri autodetectate, plus trei tipuri care nu se autodetecteaza | Cele 11 se citesc cu `Autodetect`; celelalte trei numai dupa selectie manuala a tipului |
| T-J032 | J-032 | Se deschide un proiect dintr-o versiune anterioara a produsului | Se avertizeaza ca conversia e ireversibila, se cere salvare sub alt nume, **textul recunoscut nu se transfera** |
| T-J083 | J-083 | Doi utilizatori, acelasi folder de dictionare partajat. Al doilea incearca sa schimbe proprietatile limbii | Adaugarea si stergerea de cuvinte reusesc; schimbarea proprietatilor limbii e refuzata |
| T-J084 | J-084 | Utilizatorul A editeaza dictionarul; utilizatorul B incearca sa adauge un cuvant | B poate folosi dictionarul pentru recunoastere si verificare, dar nu poate adauga sau sterge |
| T-J085 | J-085 | A adauga un cuvant; B caută cuvantul fara sa reporneasca | Cuvantul apare la B **numai dupa repornire**, si produsul spune asta |
| T-R008 | R-008 | Se incearca o comparare in cate o limba din cele 37 de comparare si in trei limbi OCR care nu sunt in setul de comparare | Cele 37 functioneaza; celelalte trei nu apar in combo |
| T-R033 | R-033 | Doua documente care difera numai prin font, spatii si tabulatori | **Zero diferente raportate** |
| T-R034 | R-034 | Document cu diferente in corp, in antet si in numerotare | Diferentele se grupeaza in exact `Body text`, `Headers and footers`, `Numbering`; gruparea se poate dezactiva |
| T-R061 | R-061 | Se salveaza rezultatul ca `DOCX in Track Changes Mode` | Se produce cate un fisier per document, cu modificarile marcate ca urmarite, deschizibile in Word |
| T-R062 | R-062 | Idem, pe o pereche de documente scanate | **Avertismentul ca fisierele sunt versiuni recunoscute si pot conține erori apare inainte de salvare, nu dupa** |
| T-R065 | R-065 | Se incearca salvarea rezultatului in TXT si in XLSX | Numai `.pdf` si `.docx` sunt oferite |
| T-I009 | I-009 | Se salveaza in PDF/A un document cu text invizibil si cu un font care nu permite incorporarea | Fonturile se incorporeaza, cu excepția celor din textul invizibil; fontul neincorporabil e raportat, nu incorporat in silenta |
| T-I010 | I-010 | Se incearca PDF/A cu parola, cu un script si cu un link extern | Fiecare caz e refuzat sau curatat, cu motivul spus |
| T-I018 | I-018 | PDF cu atasamente, semne de carte, comentarii si adnotari, trimis in OCR Editor | **Toate patru se pierd, si utilizatorul e avertizat inainte de transfer** |
| T-Q041 | Q-041 | Idem, in sens invers | Idem |
| T-G005 | G-005 | Document cu ambele parole. Se deschide folosind parola de permisiuni | **Documentul se deschide** |
| T-G030 | G-030 | Se semneaza si se verifica in Adobe Acrobat Reader | Semnatura e valida in Acrobat Reader, nu doar in produsul propriu |
| T-G037 | G-037 | Se configureaza un server de marca temporala cu utilizator si parola | Credentialele se pastreaza in magazinul de credentiale al sistemului, nu in fisierul de setari al aplicatiei |
| T-X165 | X-165 | Se schimba culoarea si grosimea chenarului pentru fiecare dintre cele 6 tipuri de zona | Toate se schimba si se pastreaza intre sesiuni; cautare in sursa: niciun literal de culoare de zona in fisierele de interfata |
| T-O041 | O-041 | Trei stiluri cu rol de titlu pe niveluri 1, 2 si 3, export PDF cu `Create bookmarks from headings` | Semnele de carte se genereaza cu ierarhia corecta |
| T-N013 | N-013 | Acelasi document in `Thorough` si in `Fast` | `Thorough` da acuratete mai buna pe layout complex si fundal colorat; `Fast` e mai rapid. Ambele peste pragul lor din capitolul 3 |
| T-T008 | T-008 | Sarcina automatizata rulata a doua oara pe acelasi folder, cu doua fisiere noi adaugate | **Se proceseaza numai cele doua fisiere noi** |
| T-T010 | T-010 | Se adauga pasul de recunoastere; apoi se sterge pasul de analiza | Adaugarea recunoasterii adauga automat analiza; stergerea analizei sterge si recunoasterea |
| T-I030 | I-030 | Cate un document din fiecare dintre cele trei tipuri de PDF | Fiecare e clasificat corect si tratat conform regulii I-033 |
| T-I033 | I-033 | PDF cautabil si PDF doar-imagine, cu modul setat pe `Use Only Text from PDF` | **Amandoua folosesc OCR, in ciuda setarii** |
| T-R020 | R-020 | Comparare pe o pereche de PDF-uri cu strat de text, fara a schimba setarile | Se foloseste `Use Only Text from PDF` |

---

### 4.8 Anexele de referinta si interfata recuperata

Teste adaugate la auditul al patrulea. Primele verifica tabelele de referinta, care nu existau; restul verifica elementele de interfata sterse la o rescriere anterioara.

| Test | Cerinta | Procedura | Criteriu de trecere |
|---|---|---|---|
| T-X204 | X-204 | Se caută in interfata locul in care se reconfigureaza scurtaturile | Exista **numai** in OCR Editor, la `View > Toolbars > Customize... > Keyboard Shortcuts`. Nu exista in dialogul Options |
| T-Y101 | Y-101 | Se incearca deschiderea fiecarui format din anexa B in fiecare dintre cele doua module | Un format acceptat doar in PDF Editor **nu apare** in dialogul de deschidere al OCR Editor-ului, si invers |
| T-Y102 | Y-102 | Se caută CSV, FB2 si EPUB in dialogurile de deschidere | Nu apar niciunde la intrare; apar numai la salvare |
| T-Y103 | Y-103 | Se caută GIF, SVG, XPS, `.ppt`, `.ods`, `.odp`, `.vsd` in dialogurile de salvare | Nu apar la salvare |
| T-Y104 | Y-104 | Se incearca deschiderea unui `.svg` in OCR Editor si in PDF Editor | Se deschide numai in PDF Editor |
| T-Y105 | Y-105 | Se incearca compararea a doua fisiere Visio | Refuzat; dar fisierul se deschide in PDF Editor |
| T-Y106 | Y-106 | Se deschide un `.xps` pe o masina fara .NET Framework 4 | **Produsul il citeste oricum, sau spune clar ca nu il suporta.** Nu eșuează in silenta |
| T-Y108 | Y-108 | Se deschid PDF-uri de versiuni 1.4 pana 2.0, plus PDF/A si PDF/UA | Toate se deschid |
| T-P100 | P-100 | Se compara numarul de limbi declarat de produs cu lista efectiv instalata | **Numarul declarat e cel real, verificabil din interfata.** Nu se copiaza un numar din brosura ABBYY |
| T-P102 | P-102 | Pentru fiecare limba instalata se verifica dacă are dictionar | Lista de limbi marcheaza corect care au dictionar; verificarea ortografica functioneaza exact pentru acelea |
| T-Y130 | Y-130 | Se compara setul de functii al editiilor, dacă exista editii | Singura linie de separare e automatizare si comparare. Daca nu exista editii, toate functiile sunt disponibile |
| T-N100 | N-100 | Imagini la 150, 200, 250, 300, 600 si 1200 dpi, plus una cu dpi orizontal diferit de vertical | Se avertizeaza sub 250, peste 600, la valori nestandard, si cand cele doua rezolutii difera |
| T-Y203 | Y-203 | Proiect recunoscut pe o masina cu un font exotic, deschis pe una fara el | **Mesajul numeste fontul lipsa**, nu afiseaza doar patrate |
| T-Y215 | Y-215 | PDF cu font incorporat si neinstalat, deschis in modul de editare | Numele fontului apare in paranteze patrate |
| T-B300 | B-300 | Se caută unealta de selectie in PDF Editor | Exista pe tabul `Document` si pe tabul `Security`, si e unealta implicita |
| T-B301 | B-301 | Se caută unealta de tragere a paginii | Exista pe aceleasi doua tab-uri si muta pagina prin tragere |
| T-A311 | A-311 | In dialogul de calitate personalizata se alege `Quality loss not allowed` | **Sliderul de calitate se dezactiveaza** |
| T-G104 | G-104 | Se deschide combo-ul de motiv al semnaturii | Conține cele cinci motive predefinite si accepta si text propriu |
| T-G111 | G-111 | Se deschid ambele dialoguri de stergere de obiecte | Cel din PDF Editor are sase bife, inclusiv textul ascuns si metadatele; cel din setarile de format are patru |
| T-J407 | J-407 | Hover pe o miniatura intr-un proiect deschis de pe o partajare | Tooltipul arata starea, utilizatorul, calculatorul si fisierul sursa |
| T-J413 | J-413 | Se deschide un PDF cu strat de text si unul fara | Banda cu `PDF recognition mode` apare **numai** la primul |
| T-M100 | M-100 | Cautare in sursa dupa literali de culoare de zona | Zero literali in fisierele de interfata; toate cele sase culori vin din setari |
| T-M110 | M-110 | Pagina cu text peste o fotografie: zona de fundal peste toata pagina, apoi zone de text deasupra | Textul se recunoaste, fundalul rămâne imagine, zonele nu se considera suprapuse |
| T-O102 | O-102 | Se selecteaza text cu formatare mixta | Combo-ul de stil arata o descriere compusa, nu un stil greșit |
| T-Q100 | Q-100 | Dialogul de salvare | Conține bifa de deschidere dupa salvare, butonul de opțiuni, si combo-ul de un fisier per pagina |
| T-R414 | R-414 | Se salveaza un raport de comparare | Tabel cu doua coloane, antet cu caile fisierelor, fiecare rand cu numarul paginii si textul, **celula goala unde textul lipseste** |
| T-S206 | S-206 | Se deschide dropdown-ul de salvare dintr-o sarcina Hot Folder | Patru opțiuni, inclusiv salvarea in SharePoint |
| T-S211 | S-211 | Se deschide combo-ul de tip de fisier al unei surse | Conține cele 15 valori din S-211, in aceeasi ordine |
| T-S214 | S-214 | Sarcina Hot Folder cu stergerea paginilor goale activa | **Paginile se sterg fara confirmare**, spre deosebire de modulele interactive |
| T-S216 | S-216 | Se construieste un sablon de nume cu toate cele cinci macrocomenzi | Fiecare insereaza valoarea corecta; exemplul de sub camp se actualizeaza live |
| T-T106 | T-106 | Sarcina automatizata cu analiza manuala | **Sarcina se opreste si asteapta utilizatorul**, nu continua cu zone detectate automat |
| T-X416 | X-416 | Tabul OCR din dialogul de setari | Doua bife separate de sabloane integrate, fiecare gri cand parintele ei nu e selectat |
| T-X421 | X-421 | Se bifeaza crearea de PDF/UA | Bifa de etichete devine gri si fortata |
| T-Y140 | Y-140 | Documentatia produsului despre imprimanta virtuala | Nu afirma ca originalul nu a avut una: a avut, si a fost retrasa |

---

## 5. Testele nefunctionale

| Test | Cerinta | Ce se face | Criteriu |
|---|---|---|---|
| T-Y016 | Y-016 | Proiect de 1.500 de pagini la 300 dpi | Varful de memorie sub 2 GB; nicio cadere; imaginile se proceseaza de pe disc, nu toate in memorie |
| T-Y017 | Y-017 | Se ruleaza fiecare operatie lunga si se masoara blocarea firului de interfata | Niciun blocaj peste 200 ms |
| T-Y018 | Y-018 | Interfata la 100%, 125%, 150% si 200% | Nicio eticheta tăiată, nicio suprapunere, niciun control in afara ferestrei. Verificare prin comparare de capturi |
| T-Y019 | Y-019 | Parcurgerea completa a interfetei doar cu tastatura | Fiecare functie din SPEC_01..SPEC_03 e accesibila fara mouse; fiecare control are nume accesibil |
| T-Y020 | Y-020 | Cautare in sursa dupa literali de text afisabil in fisierele de interfata | Zero texte afisabile in cod. Comutarea romana/engleza schimba tot |
| T-Y021 | Y-021 | Inventarul licentelor componentelor | Nicio componenta AGPL legata in proces; dacă una e necesara, ruleaza ca proces separat si asta e documentat |
| T-Y010 | Y-010 | Instalare si rulare fara drepturi de administrator | Aplicatia porneste si functioneaza; scrie doar in profilul utilizatorului |

---

## 6. Testele de regresie pe baza de date

Ruleaza `verifica_schema.py`, care executa `SPEC_04_schema_bd.sql` pe o baza de date in memorie si verifica 28 de reguli impuse la nivel de schema. Scriptul e deja scris si trece: e prima parte din suita care poate rula inainte sa existe o linie de cod de aplicatie.

Regulile verificate acolo acoperă: M-007, M-021, M-026, N-024, N-026, J-055, H-005, H-030, H-019, H-027, P-006, P-014, T-002, T-006, S-010, S-013, X-085, F-044, F-045, D-016, O-006, C-002, plus cele 5 vederi.

---

## 7. Ordinea de executie si automatizarea

```
la fiecare commit        testele unitare (195) + verifica_schema.py          < 2 minute
la fiecare pull request  + testele de integrare (451)                        < 15 minute
in fiecare noapte        + end-to-end (79) + benchmark pe tot corpusul       < 2 ore
inainte de lansare       + cele 64 de teste manuale, din lista de verificare  1 zi
```

Raportul de noapte compara indicatorii din capitolul 3 cu build-ul anterior si semnaleaza orice scadere peste 2%.

---

## 8. Criteriile de acceptanta a produsului

Produsul se considera livrabil cand, simultan:

1. Toate cele 138 de teste de prioritate 1 trec.
2. Peste 97% din cele 1.487 de teste trec; niciunul dintre cele picate nu e de prioritate 1, si fiecare are un defect deschis cu termen.
   Dintre cele picate, **niciunul nu poate fi pe o cerinta marcata `D`**: o cerinta confirmata in documentatia oficiala care nu trece inseamna ca produsul se comporta altfel decat originalul, iar asta contrazice scopul lucrarii.
3. Toti indicatorii din capitolul 3 sunt peste prag.
4. `Y-001` trece: suita de integrare ruleaza complet cu reteaua dezactivata.
5. Lista de verificare manuala e parcursa pe Windows 10 si Windows 11, pe un ecran la 100% si pe unul la 150%.
6. Pe cele 25 de documente romanesti de test, un om care le citeste nu gaseste nicio eroare de diacritice in textul exportat in Word.
7. Inventarul de licente e complet si nicio componenta nu impune o licenta incompatibila cu distribuirea produsului.
8. Cele 10 scenarii de acceptanta din capitolul urmator trec de la cap la coada, cronometrate.

---

## 9. Scenariile de acceptanta

Acestea nu testeaza functii, testeaza munca. Fiecare se cronometrează; timpul face parte din criteriu, pentru ca un produs corect, dar de doua ori mai lent decat originalul, nu inlocuieste originalul.

| Nr. | Scenariu | Criteriu |
|---|---|---|
| 1 | Un contract scanat de 14 pagini, in romana → DOCX editabil, cu antete, numerotare si tabele | Textul corect peste 96% pe cuvant; tabelele au structura corecta; sub 3 minute, inclusiv verificarea |
| 2 | 40 de facturi scanate → un XLSX cu datele din tabele, printr-o sarcina automatizata | Rulare fara interventie; sub 10 minute; toate cele 40 prezente in rezultat |
| 3 | Un dosar de finantare de 320 de pagini, mixt → PDF/A-2b cautabil, sub 20 MB | Conform PDF/A, validat extern; cautarea gaseste cuvintele din toate paginile |
| 4 | Doua versiuni ale unui ghid de finantare de 80 de pagini → raport de diferente | Toate diferentele numarate manual sunt gasite; sub 2 minute |
| 5 | Un formular PDF gol → formular interactiv cu 25 de campuri, salvat si completat in Acrobat Reader | Campurile functioneaza in Acrobat Reader, nu doar in aplicatia proprie |
| 6 | O cerere semnata olograf, fotografiata cu telefonul → PDF drept, curat, cautabil | Pagina dreapta sub 0,3 grade; fundal uniform; text corect peste 90% |
| 7 | Un document cu date personale → versiune publicabila, cu CNP-uri si adrese redactate | Zero aparitii ale datelor redactate la extragerea textului si la cautarea binara in fisier |
| 8 | Un folder urmarit: se pun 15 scanari peste noapte → PDF-uri cautabile intr-un alt folder, dimineata | Toate cele 15 procesate; jurnal complet; niciun fisier trunchiat |
| 9 | 500 de pagini de carte scanate ca pagini duble → EPUB cu cuprins | Paginile duble corect impartite; cuprinsul are capitolele corecte |
| 10 | Aceleasi 10 operatii, rulate din linia de comanda intr-un script | Aceleasi rezultate ca din interfata; coduri de ieșire corecte; `/json` parsabil |

---

## 10. Ce NU acopera acest plan

Spus deschis, ca sa nu para mai complet decat este:

- **Nu exista teste pentru add-in-uri de Office**, pentru ca alternativa nu le are (W-005): integrarea se face prin meniul contextual din Explorer.
- **Testele de scaner, imprimanta si smartcard rămân manuale.** Nu exista o cale rezonabila de a le automatiza fara hardware dedicat in integrarea continua.
- **Pragurile de acuratete sunt ale noastre, nu ale originalului.** ABBYY nu publica cifre de acuratete verificabile, deci nu se poate scrie „la fel de bun ca originalul" ca criteriu de test. Pragurile din capitolul 3 sunt alese ca sa fie utile in munca reala pe documente romanesti; dacă un motor de OCR nu le atinge, se schimba motorul, nu pragul.
- **Scrierile asiatice si arabe sunt acoperite superficial**, cu 8 documente. Un produs care tinteste serios acele piețe are nevoie de un corpus propriu si de oameni care citesc limbile respective.
- **Nu exista teste de compatibilitate cu fisierele de proiect ale originalului.** Formatul lor nu e public, iar reconstituirea lui prin inginerie inversa a formatului de fisier nu face parte din aceasta lucrare.
