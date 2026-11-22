# Faza 8 — Pagini: organizare, impartire, inserare

**Cerinte:** `E-001`…`E-040` (SPEC_01), `E-100`…`E-112` (SPEC_10, interfata),
`E-500`…`E-512` (SPEC_11, unirea documentelor semnate).
**Status:** faza 8 gata (8.1…8.6), cu ce e marcat INCOMPLET mai jos.

Contractul e `PageOrganizer` din SPEC_05 (`app/core/pdf/organize.py`). ID-urile
din docstring-urile SPEC_05 sunt decalate fata de SPEC_01 (de exemplu `delete`
e scris `E-009`, cerinta reala e `E-005`); in cod se pun ID-urile din SPEC_01,
care decid (CLAUDE.md §2).

---

## Pasii

### 8.1 — `PageOrganizer`: operatiile pe pagini (nucleu)

- `parse_page_range` (E-004: numere, intervale, `Even/Odd/All Pages`,
  avertisment pentru numerele din afara documentului), `delete` (E-005,
  `LastPageError`), `rotate` (E-006, E-007), `correct_orientation` (E-008),
  `crop` (E-010, un cadru pentru toate sau unul per pagina), `add_blank`
  (E-013), `insert_from_pdf` (E-014, E-016, parola), `insert_from_file`
  (E-015, cu procesare de imagine prin proiectul OCR), `move` (E-018, E-019),
  `replace` (E-020), `find_blank` si verificarea continutului (E-021, E-022),
  `extract_to_new_document` (E-036), `enhance_images` (E-035, nucleul).
- **Gata.** `app/core/pdf/organize.py`; testele in `tests/test_pdf_organize.py`.

### 8.2 — Impartirea documentului (nucleu)

- `split` dupa marime, numar de pagini, semne de carte de nivel 1 (E-024…E-027);
  numele fisierelor (E-028, E-029); folderul scriibil (E-030); **fara semne de
  carte in rezultate, atasamentele in `Attachments`** (E-031); estimarea
  numarului de fisiere si a celor care pot depasi limita, inainte de impartire
  (E-025, E-110).
- **Gata.** `PageOrganizer.plan_split`, `split`, `SplitNaming` in
  `app/core/pdf/organize.py`; testele in `tests/test_pdf_split.py`.

### 8.3 — Modul `Organize Pages` in fereastra (interfata)

- Grila de miniaturi (E-001, E-100), selectia simpla, multipla si prin cadru
  (E-002, E-003, E-101, E-102), campul `Selected pages` (E-004, E-103),
  mini-toolbarul la hover (E-009, E-104), tragerea pentru reordonare (E-018,
  E-105, E-106), sliderul de zoom (E-039, E-107), comenzile de pe ribbon si
  scurtaturile (sterge, roteste, corecteaza orientarea, muta), anularea cu
  minimum 50 de pasi (E-040); meniul contextual al panoului `Pages` (E-034,
  E-036, E-037), `Recognize Selected Pages` (E-033).
- **Gata.** `app/gui/pdf_organize.py` (grila), `pdf_editor.py` (modul, comenzile,
  meniurile); testele in `tests/test_gui_pdf_organize.py`.

### 8.4 — Dialogurile din `Organize Pages` (interfata)

- Decuparea cu previzualizare, `Apply Crop`/`Exit Crop` (E-010…E-012);
  pagina goala si adaugarea din PDF, fisier, scaner, cu pozitia (E-013…E-017,
  E-108); `Move Pages` (E-019); `Replace Pages` (E-020); paginile goale
  (E-021…E-023, E-109); `Split Document` (E-024…E-032, E-110…E-112);
  `Enhance Images` (E-035); `Image Processing Settings` (E-038).
- **8.4a gata:** decuparea (`app/gui/pdf_crop.py`), pagina goala, adaugarea din
  PDF, fisier si scaner, butonul `+` dintre miniaturi, mutarea, inlocuirea,
  `Image Processing Settings` (`app/gui/pdf_organize_dialogs.py`); testele in
  `tests/test_gui_pdf_organize_dialogs.py`.
- **8.4b gata:** paginile goale (E-021…E-023, E-109), `Split Document` (E-024…E-032,
  E-110…E-112), `Enhance Images` (E-035), in acelasi modul si fisier de teste.

### 8.5 — Dosarul cu semnaturile pastrate (nucleu)

- Unirea pastrand semnaturile (E-500): originalele ca atasamente octet cu octet,
  verificate cu SHA-256 dupa salvare (E-501); pagina de cuprins cu raportul de
  semnaturi (E-502); copiile de citire etichetate, fara campuri de semnatura
  (E-503); semnele de carte (E-504); varianta portofoliu (E-505); verificarea
  offline (E-507); ASiC-E (E-510); extragerea verificata (E-511); detectarea
  dosarului (E-512); detectarea semnaturilor inainte de unirea clasica (E-509).
- Sigiliul dosarului cu un certificat PKCS#12 (E-506) si datele LTV (E-508).
- **Gata** (fara E-508, vezi INCOMPLET). `app/core/pdf/dossier.py`; semnaturile
  oricarui fisier (`signatures.validate_bytes`), cu emitentul; testele in
  `tests/test_pdf_dossier.py`, cu certificate de test generate in teste.

### 8.6 — Dosarul in interfata

- `Uneste pastrand semnaturile` in Lansator (langa A-024) si in `Organize
  Pages`; avertismentul E-509 la unirea clasica si la inserarile E-014, E-015,
  E-020; bara de informare E-512; `Save` verificat din panoul `Attachments`
  (E-511).
- **Gata.** `app/gui/dossier_dialog.py` (dialogul, avertismentul E-509, construirea),
  butonul din Lansator (`convert_screen.py`), comanda din meniul de adaugare a
  paginilor si bara de informare (`pdf_editor.py`); testele in
  `tests/test_gui_pdf_dossier.py`.

---

## Decizii

1. [DECIZIE AUTONOMA] **Pozitia de inserare** (`at`) e numarul paginii inaintea
   careia intra paginile noi, ca la `OcrProject.add_images`: 1 = inainte de
   prima, `n + 1` = dupa ultima; `insertion_point` traduce cele trei variante
   din dialog (E-016). `move(pages, to)` foloseste aceeasi conventie, cu `to`
   din numerotarea de dinainte de mutare.
2. [DECIZIE AUTONOMA] **Decuparea cu cadre separate** (E-010): SPEC_05 are un
   singur `rect`; cu `same_for_all=False`, `rect` e un dictionar pagina → cadru.
   Decuparea scrie `/CropBox`; MediaBox-ul ramane, deci continutul nu se pierde.
3. [DECIZIE AUTONOMA] **Semnele de carte catre pagini sterse** se scot (copiii
   lor urca un nivel), ca sa nu ramana semne de carte fara destinatie.
4. [DECIZIE AUTONOMA] **Avertismentul E-022:** „note de mana” = orice adnotare
   in afara de linkuri, campuri si popup-uri; „imagini” = cel putin doua imagini
   pe pagina (una singura e scanarea paginii, care exista pe orice PDF scanat si
   ar face avertismentul inutil).
5. [DECIZIE AUTONOMA] **Paginile goale** (E-021) se masoara ca in OCR Editor
   (`blank_score`, pragul 0,98), pe randarea fara adnotari.
6. [DECIZIE AUTONOMA] **Adaugarea din fisier si scaner** (E-015, E-017) si
   `Enhance Images` (E-035) trec prin proiectul OCR: preprocesarea recomandata,
   apoi exportul PDF. Fara alte setari, rezultatul e PDF doar-imagine;
   `Image Processing Settings` (E-038) aleg calitatea si recunoasterea.
7. [DECIZIE AUTONOMA] **Orientarea** (E-008) se detecteaza pe imaginea paginii
   cu OSD-ul Tesseract (ca X-017); o pagina fara text sau fara Tesseract ramane
   neschimbata.
8. [DECIZIE AUTONOMA] **Impartirea dupa marime** (E-025) estimeaza fiecare
   pagina salvata singura si grupeaza paginile cat suma ramane sub limita.
   Estimarea numara resursele comune (fonturi) pe fiecare pagina, deci
   fisierele ies de regula mai mici; un fisier semnalat inainte ca depasind
   limita e o pagina care singura e mai mare decat ea.
9. [DECIZIE AUTONOMA] **Impartirea dupa semne de carte** (E-027): paginile
   dinaintea primului semn de carte de nivel 1 intra in primul fisier; doua
   semne de carte catre aceeasi pagina dau un singur fisier, cu numele primului.
10. [DECIZIE AUTONOMA] **Fisierele existente** nu se suprascriu la impartire: se
    adauga ` (2)`, ` (3)`... Caracterele interzise in nume (`<>:"/\|?*`) devin `_`.

11. [DECIZIE AUTONOMA] **Grila din `Organize Pages`** e cate una pe document, in
    tabul documentului (vizualizarea si grila sunt intr-un `QStackedWidget`), ca
    tab-urile documentelor sa ramana vizibile. Mini-toolbarul (E-104) lucreaza pe
    pagina de sub mouse, nu pe selectie.
12. [DECIZIE AUTONOMA] **`Create PDF from Selected Pages`** (E-036) deschide o
    fereastra noua de PDF Editor, tinuta de fereastra din care s-a cerut si legata
    la aceleasi semnale (Lansator, Options, OCR Editor).
13. [DECIZIE AUTONOMA] **Undo** pastreaza 50 de pasi pe document (E-040), pentru
    toate operatiile din PDF Editor, nu doar cele pe pagini.

14. [DECIZIE AUTONOMA] **Cadrul de decupare** se masoara de la coltul zonei vizibile
    a paginii (CropBox-ul existent), exact ce arata vizualizarea; o pagina deja
    decupata se poate decupa din nou. Cu cadre separate, se decupeaza numai
    paginile pe care s-a tras un cadru.
15. [DECIZIE AUTONOMA] **Adaugarea de pagini** (E-013…E-017) e un meniu pe butonul
    `Add Blank Page` din ribbon si butonul `+` care apare intre miniaturi, langa
    marginea uneia (E-013); pozitia aleasa cu `+` se preia in dialog. Scanarea
    cere intai pozitia, apoi foloseste dialogul de scanare din OCR Editor.
16. [DECIZIE AUTONOMA] **`Apply ABBYY PreciseScan`** (E-035, E-038) apare ca
    „Netezeste marginile caracterelor”: numele din original nu se preia
    (CLAUDE.md §6.6).

17. [DECIZIE AUTONOMA] **Pragul de continut** pentru paginile goale (E-021) e un
    slider intre 0,80 si 1,00 in dialog; lista se recalculeaza la fiecare valoare.
    Marcajul paginilor bifate (E-109) e fundalul albastru al miniaturii.
18. [DECIZIE AUTONOMA] **`Enhance Images`** (E-035) aplica numai uneltele bifate:
    orientarea, apoi indreptarea impreuna cu corectarea rezolutiei; pagina devine
    imagine, cu strat de text daca `Recognize text on images` (E-038) e pus.
    `Schimba limbile...` deschide tabul de limbi din Options.

19. [DECIZIE AUTONOMA] **Recunoasterea dosarului** (E-512): `Root` poarta
    `/DocuLensDossier` cu numele, amprenta SHA-256 si paginile fiecarui original;
    extragerea (E-511) si sigilarea (E-506) verifica dupa el. Amprenta e scrisa si
    in descrierea atasamentului, ca sa se vada in orice cititor.
20. [DECIZIE AUTONOMA] **Copiile de citire** (E-503) se fac pentru PDF-uri si
    imagini; alte fisiere (Word, Excel...) sunt doar atasate si listate in cuprins
    („fara copie de citire”). Eticheta e o banda galbena sus pe fiecare pagina.
    Textele dosarului vin din fisierele de traducere (nucleul primeste `texts`).
21. [DECIZIE AUTONOMA] **Starea `nu se poate verifica offline`** (E-507): o
    semnatura intacta al carei emitent nu se poate verifica fara retea e
    `valida`, cu nota despre incredere; o validare care esueaza cerand revocare
    sau descarcare e `nu se poate verifica offline`, nu `invalida`.
22. [DECIZIE AUTONOMA] **ASiC-E** (E-510): containerul are `mimetype`,
    originalele si `META-INF/manifest.xml`; nu are o semnatura proprie a
    containerului (`META-INF/signatures*.xml`), pentru ca semnaturile sunt in
    originale.
23. [DECIZIE AUTONOMA] **Numele semnatarului** e numele comun din certificat
    (`Ana Popescu`), nu tot numele distins; se schimba si in panoul
    `Signatures` (B-024).

24. [DECIZIE AUTONOMA] **`Uneste pastrand semnaturile` in PDF Editor** e in
    meniul de adaugare a paginilor din `Organize Pages` (langa `Add Blank Page`),
    nu un buton nou pe ribbon; lista porneste cu documentul deschis. Avertismentul
    E-509 tine cont si de documentul deschis, nu doar de sursa: inserarea de
    pagini invalideaza si semnatura lui.
25. [DECIZIE AUTONOMA] **Meniul contextual din Explorer** (E-500, E-509, langa
    W-011) vine in faza 15, cu integrarile.

## INCOMPLET

- **Netezirea marginilor caracterelor** (PreciseScan, E-035, E-038): optiunea se
  pastreaza in setari, dar nu are efect; nucleul nu are inca o unealta de
  netezire a contururilor.
- **Datele LTV** (E-508, optional, `N`): cer retea (singura exceptie de la regula
  offline) si certificate calificate reale pentru verificare; nu sunt facute.
  Bifa nu apare in interfata pana atunci.
- **Acceptarea dosarului de portaluri** (MySMIS si altele) si comportamentul cu
  certificate calificate reale (STS, certSIGN, DigiSign, Trans Sped): le verifica
  utilizatorul cu un dosar real (SPEC_11, „Ce trebuie verificat”).
