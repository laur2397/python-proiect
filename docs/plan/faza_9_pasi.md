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
- Teste: `tests/test_pdf_bookmarks.py`, `tests/test_pdf_links.py`.

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
- Teste: `tests/test_pdf_headers.py`, `tests/test_pdf_watermarks.py`.

### 9.3 — Interfata pentru 9.1

- Panoul `Bookmarks` cu editare, `Link Editor`, operatiile din panoul
  `Attachments`, dialogul `Document Properties`.

### 9.4 — Interfata pentru 9.2

- Dialogurile de antet si subsol (cu `Save and Add`, `Manage...`), de filigran,
  `Delete Watermarks`, unealta `Erase`; previzualizarea (Z-013).

### 9.5 — Editarea continutului (nucleu)

- `PdfContentEditor`: blocurile de text ale paginii (din stratul existent sau din
  OCR pe o scanare), ce nu se poate edita (text vectorial, F-002), editarea cu
  reflow, blocuri noi in limitele paginii, stergere, mutare, redimensionare,
  fontul (F-005, F-006, F-008…F-016), indreptarea paginii si inlocuirea stratului
  de text (F-017, F-018), celulele de tabel (F-019), imaginile (F-020…F-023).

### 9.6 — Modul `Edit Content` (interfata)

- Intrarea si iesirea (F-001), pregatirea paginii (F-003), blocul activ si
  manerele, bara de text (F-007, F-100…F-110), imaginile.

---

## Decizii

(se completeaza pe parcurs, cu marcajul `[DECIZIE AUTONOMA]`)

## INCOMPLET

(se completeaza pe parcurs)
