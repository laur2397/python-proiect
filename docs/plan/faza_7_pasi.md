# Faza 7 — PDF Editor: vizualizare, cautare, copiere, comentarii, salvare, tiparire

**Cerinte:** `B-*` (vizualizare si navigare), `C-*` (cautare, inlocuire,
redactare dupa text, copiere), `D-*` (comentarii, marcaje, stampile),
`I-001`…`I-007`, `I-017`…`I-024` (salvare, trimitere, tiparire).
Circa 190 de cerinte, din SPEC_01 si SPEC_10.
**Status:** 7.1, 7.2a gata; urmeaza 7.2b.

Contractul e `PdfDocument` din SPEC_05 sectiunea 10. Din faza 1 exista partea de
citire (`open`, `render_page`, `page_size`); faza 7 adauga restul, pe pasi.

---

## Pasii

### 7.1 — Documentul: salvarea si textul (nucleu)

- `PdfDocument`: `save` (obiectele nemodificate raman, versiunea PDF nu scade,
  I-001, I-007), `save_as` (I-002), PDF cautabil si doar-imagine (I-003, I-004),
  salvarea unor pagini (I-006), `create_empty`, `from_images`,
  `extract_text`, `has_text_layer`, metadatele, `is_modified`, permisiunile,
  salvarea automata de siguranta si recuperarea (I-024).
- **Gata.** `app/core/pdf/document.py`, testele in `tests/test_pdf_document_save.py`.
  Ceasul de 5 minute al salvarii automate (`AUTOSAVE_INTERVAL_S`) il porneste
  fereastra, in 7.7.

### 7.2a — Cautarea, marcarea rezultatelor, listele de cuvinte cheie (nucleu)

- `search` cu `Exact Match`, `Match Case`, rezultatele in text, comentarii,
  semne de carte, metadate (C-002…C-006); marcarea rezultatelor cu adnotari
  (C-007…C-010); listele de cuvinte cheie in app.db si cautarea cu ele
  (C-027…C-032).
- **Gata.** `app/core/pdf/text.py`, `markup.py`, `keywords.py`; testele in
  `tests/test_pdf_search.py`.

### 7.2b — Inlocuirea si redactarea dupa text (nucleu)

- `replace_text` (C-015…C-018); redactarea rezultatelor si a listelor de
  cuvinte (C-025, C-026), cu verificarea dupa redactare (G-021, CLAUDE.md §6.7).

### 7.3 — Copierea (nucleu)

- Zona de copiat: ca imagine, ca text, ca tabel cu grila editabila
  (C-040…C-049), pe PDF-uri cu strat de text si pe scanari (OCR pe zona).

### 7.4 — Adnotarile (nucleu)

- Adnotari PDF standard, scrise cu pikepdf, cu aspect generat ca sa se vada si
  in alte programe: nota, marcaje pe text, forme, bloc de text, stampile
  (D-001…D-023, D-045…D-052); comentariile, raspunsurile, statusurile, filtrele,
  stergerea (D-024…D-044).

### 7.5 — Navigarea si siguranta (nucleu)

- Semnele de carte, atasamentele, semnaturile listate (B-019…B-025); JavaScript
  dezactivat implicit si confirmarile pentru atasamente, linkuri, formulare
  (B-034…B-041); detectia linkurilor (B-042).

### 7.6 — Recunoasterea in fundal (nucleu)

- Strat de text temporar, nesalvat, pe un singur nucleu, dezactivabil; salvarea
  lui permanenta la cerere (B-028…B-033).

### 7.7 — Fereastra PDF Editor

- Randarea, cele patru moduri de vizualizare, paginile impare in dreapta,
  ecranul complet, zoom-ul, navigarea, istoricul, panoul de navigare cu Pages,
  Bookmarks, Search, Attachments, Signatures, Comments (B-001…B-027,
  B-300…B-314), tab-uri de documente si modul intunecat (B-043, B-044).

### 7.8 — Panoul de cautare si copierea

- Tab-urile `FIND`, `REPLACE`, `REDACT`, arborele de rezultate, bifele,
  evidentierea, listele de cuvinte cheie (C-100…C-111); zona de copiat si
  toolbarul de tabel (C-112…C-115).

### 7.9 — Comentariile si uneltele de adnotare

- Panoul `Comments` cu filtre, sortare, raspunsuri, statusuri (D-100…D-105),
  uneltele de desenare, stampilele si dialogurile lor (D-106…D-110).

### 7.10 — Salvarea, trimiterea, tiparirea; legaturile

- Meniul `File` (I-001…I-006), trimiterea in OCR Editor si inapoi
  (I-017…I-019), e-mailul (I-020, D-053), tiparirea (I-021, I-022),
  avertismentul la inchidere (I-023); Lansatorul deschide PDF-urile in PDF
  Editor (A-010, A-011), nu in aplicatia sistemului.

---

## Decizii autonome

1. **[DECIZIE AUTONOMA] Doua biblioteci, doua roluri.** PDFium (pypdfium2)
   randeaza si citeste textul; pikepdf modifica si salveaza. Dupa fiecare
   modificare, PDFium reciteste documentul din memorie, ca imaginea sa arate
   exact ce se va salva.
2. **[DECIZIE AUTONOMA] Adnotarile sunt adnotari PDF standard** (`/Highlight`,
   `/Text`, `/Square`, `/FreeText`, `/Stamp`...), cu aspect (`/AP`) generat de
   noi, nu un format propriu: documentul arata la fel in orice cititor PDF.
3. **[DECIZIE AUTONOMA] CI-ul.** La 22.11.2026 GitHub nu a pornit joburile
   (problema de plata a contului, mesajul din adnotarile joburilor). Cat timp
   se intampla asta, verificarile ruleaza local inainte de fiecare commit, iar
   CI-ul se reia singur cand contul e in regula.
4. **[DECIZIE AUTONOMA] `save_as` primeste in plus `pages`, `context`, `engine`.**
   Semnatura din SPEC_05 (`save_as(path, *, options=None)`) ramane valabila;
   argumentele noi sunt optionale: `pages` pentru salvarea unor pagini (I-006),
   `context` pentru proiectul OCR temporar, `engine` pentru motorul OCR din teste.
   La fel `from_images(..., context, engine)`, plus `autosave`, `find_recovery`,
   `recover`, dupa modelul `OcrProject` (I-024 nu are metode in contract).
5. **[DECIZIE AUTONOMA] PDF cautabil si doar-imagine din PDF Editor** trec prin
   acelasi drum ca OCR Editor-ul: proiect temporar, recunoastere (numai pentru
   cautabil), exportul PDF din faza 6. Documentul deschis trece pe fisierul nou.
6. **[DECIZIE AUTONOMA] Salvarea minim modificatoare (I-007)** foloseste pikepdf
   cu fluxurile copiate octet cu octet si versiunea minima egala cu cea a
   fisierului. Nu e o actualizare incrementala (pikepdf rescrie structura), dar
   continutul obiectelor neatinse ramane identic. Un fisier criptat se
   recripteaza, deci acolo copierea octet cu octet nu se poate.
7. **[DECIZIE AUTONOMA] Metadatele pe un fisier protejat** (SPEC_05: „campurile
   sunt blocate”, fara exceptie numita) dau `NoWritePermissionError`.
8. **[DECIZIE AUTONOMA] Pasul 7.2 s-a impartit in 7.2a si 7.2b**, ca fiecare
   commit sa ramana mic: cautarea si marcajele intai, apoi inlocuirea si
   redactarea, care rescriu continutul paginii.
9. **[DECIZIE AUTONOMA] Rezultatele cautarii** sunt tupluri `(pagina,
   dreptunghi, context)`, ca in SPEC_05, de tipul `SearchHit`, care adauga
   sursa (C-002 cere gruparea pe sursa, iar tuplul din contract nu o spune),
   pozitia si dreptunghiurile pe randuri. Coordonatele: puncte, originea
   sus-stanga a MediaBox-ului. Cautarea trateaza ş/ș si ţ/ț ca aceeasi litera
   (CLAUDE.md §6.4).
10. **[DECIZIE AUTONOMA] Culorile implicite ale marcajelor** (C-010) sunt
    setarile `pdf_editor.markup_color.*`, cu paleta proprie; nu apar in
    dialogul Options al OCR Editor-ului, ci se schimba din bara PDF Editor-ului
    (pasul 7.9).
