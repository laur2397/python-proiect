# Faza 5 — impartirea in pasi

Faza 5 din CLAUDE.md §8: panoul de text, verificarea, stilurile (`O-*`).
Scrisa in modul autonom (CLAUDE.md §11); deciziile sunt marcate
`[DECIZIE AUTONOMA]` si se revad la oprirea de dupa faza 6d.

Surse citite: SPEC_02 O.1…O.8 (O-001…O-083), SPEC_10 (O-100…O-111), SPEC_05
(`TextEditor`, `StyleManager`, `TextStyle`), SPEC_04 (`word` cu formatarea
locala, `text_block.style_name`, `text_style` din app.db, `annotation`).

Nucleul e in `app/core/text/`. Ce tine numai de fereastra intra in faza 6b:
sincronizarea panourilor (O-021), caracterele neimprimabile (O-028), fontul de
afisare (O-029, partea din nucleu e in `app/core/fonts.py`, 4b.4), barele
de unelte (O-064, O-100, O-101, O-106), combo-ul de stil la selectie mixta
(O-102), panoul gol si separatoarele (O-103, O-104), culoarea de evidentiere
(O-105, setare existenta), afisarea celulelor (O-107), dialogul de simboluri
(O-008, O-109: nucleul insereaza caracterul).

**Status:** pasul 5.1 e implementat.

---

## Pasii

### 5.1 — Editarea si verificarea textului

`app/core/text/editor.py`: `TextEditor` din SPEC_05.

- Editarea directa a unui cuvant (O-020): se pastreaza textul original,
  cuvantul devine editat si neverificat, schimbarea ajunge la export.
- Cuvintele nesigure: urmatorul si anteriorul (O-001, O-002), pe toate paginile.
- Sesiunea de verificare (O-003…O-012): `Skip` scoate evidentierea fara sa
  schimbe textul (O-004), `Replace` (O-005), `Add to Dictionary` (O-006, in
  dictionarul limbii cuvantului), formatarea cuvantului (O-007), simbolurile
  (O-008), sugestiile (dictionarul utilizatorului; pentru CJK, caractere cu
  aspect asemanator, O-010), `Mark Text as Verified` (O-011), optiunile de
  verificare (O-012).
- Re-recunoasterea unei singure zone (O-108).

### 5.2 — Cautare, formatare, redactare, tabele, copiere

- Cautarea si inlocuirea (O-024…O-026), implicit fara diacritice (SPEC_05).
- Formatarea locala a cuvintelor (O-022, O-023): font, marime, bold, italic,
  subliniere, exponent, indice, culoare.
- Redactarea (O-070…O-072): cuvintele marcate, un singur pas de undo, la
  export puncte sau dreptunghi negru.
- Celulele de tabel (O-027, O-060…O-063): unirea si impartirea celulelor si
  randurilor pastreaza textul; `Delete` goleste celula, nu structura.
- Copierea (O-080…O-083): textul unei zone, imaginea unei zone (PNG), mai
  multe pagini.

### 5.3 — Stilurile

`app/core/text/styles.py`: `StyleManager` din SPEC_05, pe `text_style` (app.db).

- Aplicarea, editorul, ce se poate schimba, stil nou, unirea stilurilor,
  fragmentele (O-035…O-040, O-110).
- Rolul de titlu, `Heading 1`…`Heading 10` (O-041); titlurile detectate
  automat primesc stiluri `Heading N` (O-111).

### 5.4 — Legaturile

- Tooltip-ul cu adresa, deschiderea, stergerea, editarea (O-050…O-053).
- `Web page` (protocol plus adresa), `Local file` (`file://`), `E-mail
  address` (`mailto:`) (O-054…O-056, F-027).

---

## Decizii autonome

1. **[DECIZIE AUTONOMA] 5.4, unde stau legaturile.** Schema nu are un tabel de
   legaturi pentru textul OCR; tabelul `annotation` (project.db) are tipul
   `link`. O legatura e o adnotare `link` cu adresa in `content`, textul afisat
   in `subject` si cuvintele legate in `geometry` (`{"word_ids": [...]}`).
2. **[DECIZIE AUTONOMA] Modulul.** CLAUDE.md §4 nu numeste un modul pentru
   text; editarea, verificarea si stilurile stau in `app/core/text/`.
3. **[DECIZIE AUTONOMA] 5.1, `Skip` (O-004).** Cuvantul sarit primeste
   `is_verified = 1`: textul ramane, evidentierea dispare. Un cuvant editat de
   utilizator nu mai e nesigur.
4. **[DECIZIE AUTONOMA] 5.1, sugestiile CJK (O-010).** Lista grupurilor de
   caractere cu aspect asemanator e a noastra (`CJK_LOOKALIKES`); originalul
   nu o publica.
