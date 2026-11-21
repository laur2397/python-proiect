# Faza 6 — impartirea in pasi

Faza 6 din CLAUDE.md §8: exportul (`Q-*`, `I-008`…`I-016`, `I-030`…`I-033`).
Scrisa in modul autonom (CLAUDE.md §11); deciziile sunt marcate
`[DECIZIE AUTONOMA]` si se revad la oprirea de dupa faza 6d.

Surse citite: SPEC_02 Q (Q-001…Q-065, Q-100…Q-104), SPEC_01 I (I-008…I-016,
I-030…I-033), SPEC_05 (`LayoutMode`, `ExportFormat.allowed_for`,
`ExportOptions`, `Exporter`, `ExportService`), SPEC_06 (T-Q001: 90 de
combinatii, exact 29 valide), SPEC_03 X.5 (setarile per format).

Nucleul e in `app/core/export/` (CLAUDE.md §4: `base.py` + un exportator pe
format). Ce tine de fereastra (dialogul de salvare Q-100, bifa `Open document
after saving` Q-101, tiparirea Q-049/Q-050, trimiterea in alte programe
Q-040…Q-048) intra in faza 6b; nucleul pregateste fisierele.

**Status:** planul e scris; niciun pas implementat.

---

## Pasii

### 6.1 — Baza exportului si matricea modurilor

`app/core/export/base.py`: `LayoutMode`, `ExportFormat.allowed_for`,
`ExportOptions.validate`, `Exporter`, `ExportService` din SPEC_05.

- Matricea mod → formate (Q-001…Q-007): exact cele 29 de combinatii valide;
  restul ridica `IncompatibleLayoutError` (T-Q001, prioritate 1).
- Avertismentele inainte de export (Q-051: pagini invalidate; XLSX fara
  tabele), paginile alese (Q-023, I-015), optiunile (Q-024, Q-102).
- Documentul de exportat: paginile in ordinea zonelor, blocurile cu stilurile
  lor, redactarea (O-072), antetele dupa X-103, legaturile (5.4).
- Primul exportator: TXT (Q-018), cu modurile `formatted` si `plain`.

### 6.2 — PDF cautabil si PDF doar-imagine

`app/core/export/pdf.py` (pikepdf).

- PDF doar-imagine (Q-012, Q-033, I-030) si PDF cautabil (Q-011, I-031):
  imaginea paginii plus textul invizibil la pozitia cuvintelor, cu textul
  editat (O-020), fara textul redactat (dreptunghi negru, O-072).
- Regula de recunoastere (I-033): PDF-urile cautabile si cele doar-imagine
  folosesc intotdeauna OCR.
- Semnele de carte din titluri (O-041, X-060), legaturile (O-050…O-056),
  avertismentul MRC (Q-104).

### 6.3 — PDF/A, PDF/UA, reducerea dimensiunii

- PDF/A (I-008…I-011): versiunile, ce se include si ce nu (fara criptare,
  `PdfAEncryptionConflictError`).
- PDF/UA (I-012, Q-103): PDF etichetat, ordinea de citire, limba.
- `Reduce File Size...` (I-016), PDF din formate editabile (I-032).

### 6.4 — DOCX, RTF, ODT

- Word (Q-013, python-docx), RTF si ODT (Q-014, scrise de noi), in modurile
  `exact`, `editable`, `formatted`, `plain`: paragrafe, stiluri, tabele,
  imagini, antete si subsoluri, liste, note de subsol.

### 6.5 — XLSX, CSV, PPTX

- Excel (Q-015, openpyxl): tabelele, cate o foaie; CSV (Q-016, numai `plain`).
- PowerPoint (Q-017, python-pptx): numai `exact`.

### 6.6 — HTML, EPUB, FB2

- HTML (Q-019): `formatted`, `plain` si `flexible` (pozitiile aproape de
  original); EPUB (Q-020) si FB2 (Q-021), scrise de noi.

### 6.7 — DjVu si imaginile paginilor

- DjVu (Q-022), cu stratul de text ascuns.
- `Save As > Page Images...` (Q-030…Q-032): TIFF (multipagina, compresia),
  JPEG, PNG, JBIG2; PDF doar-imagine din imagini (Q-033).

### 6.8 — Trimiterea si tiparirea (partea din nucleu)

- Fisierele pentru `Send to` (Q-040…Q-048): PDF Editor, e-mail (impartirea
  pe dimensiune, Q-043), Kindle (EPUB), Word/Excel/PowerPoint, clipboard,
  browser; ce se pierde la trimitere (Q-041).
- Textul si imaginile pentru tiparire (Q-049, Q-050).
- Q-060…Q-065: alternativele libere la Office si diferenta noastra (fara
  Office, CLAUDE.md §6.3) — documentate, testate ca reguli.

---

## Decizii autonome

1. **[DECIZIE AUTONOMA] Dependente noi.** `pikepdf` (MPL-2.0, deja in stiva),
   `fontTools` (MIT: fontul fara glife pentru textul invizibil din PDF),
   `python-docx`, `openpyxl`, `python-pptx` (MIT, din stiva). Fiecare se
   adauga in `requirements.txt` la pasul care il foloseste.
2. **[DECIZIE AUTONOMA] Fara `ebooklib`.** Stiva il listeaza, dar e AGPL-3.0
   (CLAUDE.md §11: AGPL nu). EPUB se scrie de noi (ZIP cu XHTML, EPUB 3);
   RTF, ODT, FB2, HTML si TXT la fel.
3. **[DECIZIE AUTONOMA] DjVu.** Nu exista o biblioteca libera care sa scrie
   DjVu. Formatul se scrie de noi, cu blocurile standard `Smmr` (G4/MMR, prin
   Pillow) pentru paginile alb-negru si `BGjp` (JPEG) pentru cele color, in
   loc de JB2 si IW44: fisierele sunt valide, dar mai mari decat ale
   originalului. **INCOMPLET, marcat:** compresia JB2/IW44.
4. **[DECIZIE AUTONOMA] Textul invizibil din PDF.** Font Type0 (Identity-H)
   cu un font TrueType fara glife generat cu fontTools si ToUnicode, ca
   textul sa se caute si sa se copieze cu diacriticele romanesti corecte.
