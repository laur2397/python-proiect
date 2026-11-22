# Faza 9 — Editare de continut, antete, filigrane, semne de carte, stampile de data

**Cerinte:** `F-001`…`F-056` (SPEC_01), `F-100`…`F-110` (SPEC_10, bara de text),
`Z-001`…`Z-013` (SPEC_03, etichetele de data; facute in faza 7 pentru stampile,
aici se folosesc si in antete si subsoluri si li se completeaza testele).
**Status:** in lucru.

Contractul e in SPEC_05: `PdfDocument` (semne de carte, atasamente, linkuri) si
`PdfContentEditor` (editarea textului si a imaginilor, stergerea, antetele,
filigranele). ID-urile din docstring-urile SPEC_05 sunt decalate fata de SPEC_01;
in cod se pun cele din SPEC_01. Unde SPEC_05 contrazice o cerinta `D`, decide
cerinta: `remove_watermarks` sterge **toate** filigranele (F-050), nu doar cele
puse de aplicatie.

---

## Pasii

### 9.1 — Semne de carte, linkuri, atasamente, proprietati (nucleu)

- Semnele de carte: adaugare la pagina curenta sau pe o selectie (F-032, F-033),
  regula de imbricare (F-035), mutare si niveluri (F-036), redenumire (F-037),
  stergere cu copiii (F-038), `Set Destination` (F-034).
- Linkurile: catre o pagina (si destinatie precisa), adresa web, e-mail cu
  `mailto:`, fisier cu `file://` (F-026, F-027), editare, copiere, stergere
  (F-028…F-030).
- Atasamentele: adaugare, redenumire, stergere (F-052).
- Proprietatile documentului: cele editabile si cele doar in citire, gri pe un
  fisier protejat (F-054, F-055); metadatele raman la conversie (F-056).
- **Gata.** `app/core/pdf/outline.py` (semnele de carte), `navigation.py` (linkurile,
  atasamentele), `document.py` (metodele SPEC_05, `properties()`),
  `export/base.py` si `export/pdf.py` (metadatele la conversie); testele in
  `tests/test_pdf_bookmarks.py` si `tests/test_pdf_links.py`.

### 9.2 — Antete si subsoluri, filigrane, stergerea zonelor (nucleu)

- Antet si subsol: sase pozitii, distanta de margine cu unitati, numarul paginii,
  numerotarea Bates (`Start at`, `Continue from`), data si ora cu etichetele
  Z-001…Z-012, fontul, paginile (F-039…F-042); sabloanele in `app.db`
  (`header_footer_template`, F-043, F-044).
- Filigranul: text sau imagine, noua pozitii cu offset, rotire, transparenta,
  deasupra sau sub continut, paginile (F-045…F-049); `Delete Watermarks` sterge
  toate filigranele (F-050).
- `Erase`: continutul zonei dispare din pagina si din stratul de text, fundalul se
  completeaza (F-024, F-025).
- **Gata.** `app/core/pdf/decorate.py` (antetele, filigranele, sabloanele),
  `app/core/pdf/editor.py` (`PdfContentEditor`: `erase_region`, antet, filigran),
  fontul ales in `fonts.font_file`; testele in `tests/test_pdf_headers.py` si
  `tests/test_pdf_watermarks.py`.

### 9.3 — Interfata pentru 9.1

- Panoul `Bookmarks` cu editare, `Link Editor`, operatiile din panoul
  `Attachments`, dialogul `Document Properties`.
- **Gata.** `app/gui/pdf_content.py` (`Link Editor`, `Document Properties`, zona
  trasa pe pagina), `pdf_panels.py` (bara si meniul panourilor), `pdf_editor.py`;
  testele in `tests/test_gui_pdf_content.py`.

### 9.4 — Interfata pentru 9.2

- Dialogurile de antet si subsol (cu `Save and Add`, `Manage...`), de filigran,
  `Delete Watermarks`, unealta `Erase`; previzualizarea (Z-013).
- **Gata.** In acelasi modul si fisier de teste ca 9.3.

### 9.5 — Editarea continutului (nucleu)

- `PdfContentEditor`: blocurile de text ale paginii (din stratul existent sau din
  OCR pe o scanare), ce nu se poate edita (text vectorial, F-002), editarea cu
  reflow, blocuri noi in limitele paginii, stergere, mutare, redimensionare,
  fontul (F-005, F-006, F-008…F-016), indreptarea paginii si inlocuirea stratului
  de text (F-017, F-018), celulele de tabel (F-019), imaginile (F-020…F-023).
- **Gata.** `app/core/pdf/content.py` (blocurile, scrierea), `editor.py`
  (`PdfContentEditor`); testele in `tests/test_pdf_content_edit.py`.

### 9.6 — Modul `Edit Content` (interfata)

- Intrarea si iesirea (F-001), pregatirea paginii (F-003), blocul activ si
  manerele, bara de text (F-007, F-100…F-110), imaginile.

---

## Decizii

1. [DECIZIE AUTONOMA] **Imbricarea** (F-035): `add_bookmark` primeste, pe langa
   `parent_id` din SPEC_05, `after_id`: noul semn de carte vine imediat dupa cel
   selectat, la acelasi nivel; fara selectie ajunge la sfarsitul radacinii.
   `Move one level right/left` (F-036) sunt `outline.indent` / `outdent`.
2. [DECIZIE AUTONOMA] **Stergerea semnelor de carte** (F-038) accepta id-uri de pe
   orice nivel (SPEC_05 spune „doar la acelasi nivel”; F-038, cerinta `D`, nu
   are aceasta restrictie).
3. [DECIZIE AUTONOMA] **Linkurile catre fisiere** (F-027) se scriu ca actiune
   `Launch` cu calea de dupa `file://`; e-mailul si adresele web ca `URI`. Linkul
   catre o pagina fara pozitie aleasa foloseste `/Fit`.
4. [DECIZIE AUTONOMA] **Metadatele la conversie** (F-056): serviciul de export ia
   titlul, autorul, subiectul si cuvintele cheie din PDF-ul sursa, daca optiunile
   nu le dau deja; o valoare goala in optiuni inseamna „sters explicit”.
   Exportul din OCR Editor trimite si metadatele proiectului (J-038), care pana
   acum nu ajungeau in fisier.

5. [DECIZIE AUTONOMA] **Antetele, subsolurile si filigranele** se scriu in
   continutul paginii ca artefacte de paginare
   (`/Artifact <</Type /Pagination /Subtype /Header|Footer|Watermark>>`), cu
   fontul incorporat; pozitiile se masoara pe pagina vizibila, cu rotatia ei.
   Continutul antetului foloseste `{page}`, `{pages}`, `{bates}`, `{date}`,
   `{time}` si etichetele de data Z-001…Z-012.
6. [DECIZIE AUTONOMA] **`Delete Watermarks`** (F-050) recunoaste filigranele
   dupa marcajul `/Artifact ... /Watermark` (orice program), dupa formele cu
   `/PieceInfo` de filigran (Acrobat) si dupa adnotarile `/Watermark`. Un
   filigran desenat de alt program fara niciun marcaj nu se poate deosebi de
   restul paginii si ramane.
7. [DECIZIE AUTONOMA] **Fontul antetului** (F-041) se cauta printre fonturile
   TrueType instalate; bold si italic folosesc fisierul stilului daca exista,
   altfel se simuleaza (contur, inclinare). Fara fontul cerut se foloseste cel
   implicit, cu nota in jurnal (F-006). Efectele de text nu au coloane in
   `header_footer_template` (SPEC_04) si nu se salveaza in sablon.
8. [DECIZIE AUTONOMA] **`Erase`** (F-024, F-025) foloseste reconstruirea paginii
   de la redactare (faza 7, decizia 11), cu fondul detectat in jurul zonei;
   adnotarile raman, iar textul se cauta din nou in zona dupa stergere.
9. [DECIZIE AUTONOMA] **Distanta filigranului de margine**, la pozitiile de pe
   margine, e de 36 pt; offset-ul (F-045) e in puncte, spre dreapta si in jos.

10. [DECIZIE AUTONOMA] **Meniul unui link** (F-028…F-030) apare la clic dreapta
    pe link in pagina; `Copy Link` pune adresa in clipboard, iar pentru un link
    intern `#page=N`. `Add Link...` si `Erase` folosesc aceeasi unealta: se trage
    zona pe pagina, apoi dialogul (pentru link).
11. [DECIZIE AUTONOMA] **`Set Destination`** (F-034) muta tinta la inceputul
    paginii curente. `Add Bookmark...` pe selectie (F-033) e in meniul contextual
    al textului selectat.
12. [DECIZIE AUTONOMA] **`Continue from`** (F-040) foloseste numarul Bates de
    dupa ultimul antet aplicat, pastrat in setarea `pdf_editor.bates_next`.
    `Date/Time` insereaza eticheta `<d/>`; textul poate folosi orice eticheta
    Z-001…Z-012. Previzualizarea (Z-013) arata textul pentru prima pagina aleasa.
13. [DECIZIE AUTONOMA] **`Save and Add` la filigran** (F-049) aplica filigranul si
    redeschide dialogul pentru urmatorul; la antet (F-043) salveaza sablonul, cu
    nume unic cerut din nou daca e folosit.

14. [DECIZIE AUTONOMA] **Editarea reala a textului** (F-008…F-016): obiectele text
    din zona blocului se scot cu PDFium (`remove_obj`, `gen_content`), iar textul
    nou se scrie cu fontul incorporat (subset), cu reflow in latimea blocului.
    Restul paginii (vectori, imagini, fonturi) ramane neatins: pagina nu se mai
    transforma in imagine, cum facea inlocuirea din faza 7.
15. [DECIZIE AUTONOMA] **Pe o scanare** blocurile vin din stratul de text (sau din
    OCR facut atunci); textul vechi e in imagine, deci zona se acopera cu culoarea
    fondului detectata in jurul ei, iar stratul invizibil al zonei se scoate.
    Imaginea unei pagini scanate nu se poate sterge (F-023).
16. [DECIZIE AUTONOMA] **Formatarea** (F-015, F-016) se aplica pe tot blocul
    (fontul, marimea, aldin, cursiv, subliniat, culoarea, alinierea, spatierile,
    directia). Aldinul si cursivul folosesc fisierul de stil al fontului, daca
    exista, altfel se simuleaza. Directia de la dreapta la stanga aliniaza la
    dreapta; ordinea caracterelor ramane cea scrisa.
17. [DECIZIE AUTONOMA] **Celula de tabel** (F-019): SPEC_05 o identifica printr-o
    zona OCR (`area_id`); in PDF Editor tabelul e zona lui pe pagina, din care se
    detecteaza celulele (ca la copierea ca tabel, C-045). Liniile nu se ating.
18. [DECIZIE AUTONOMA] **`Bring Picture to Front`** (F-022) pune o copie a
    imaginii (aceeasi imagine, aceeasi pozitie) la sfarsitul paginii si scoate
    originalul, pentru ca PDFium nu reordoneaza obiectele; imaginea se pastreaza
    fara pierderi (necomprimata).
19. [DECIZIE AUTONOMA] **`Correct Skew and Page Orientation`** (F-017) apare cand
    inclinarea detectata trece de 0,3 grade; indreptarea foloseste `Enhance
    Images` (E-035) pe pagina. `Recognize Page and Replace Existing Text Layer`
    (F-018) scoate stratul invizibil vechi si scrie unul nou.

## INCOMPLET

(se completeaza pe parcurs)
