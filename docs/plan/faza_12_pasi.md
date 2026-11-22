# Faza 12 — Compararea documentelor

**Cerinte:** `R-001`…`R-068` (SPEC_03), `R-300` (SPEC_09), `R-400`…`R-416` (SPEC_10).
**Status:** 12.1…12.3 gata; urmeaza 12.4.

Contractul e in SPEC_05: `Difference`, `CompareOptions`, `DocumentComparer`, cu
`DiffType` si `NoTextFoundError`. ID-urile din docstring-urile SPEC_05 sunt
decalate fata de SPEC_03; in cod se pun cele din SPEC_03. Tabelele `comparison`,
`comparison_difference` si `recent_comparison` sunt in SPEC_04.

---

## Pasii

### 12.1 — Sursele: text cu pozitii (nucleu)

- `DocumentComparer.can_compare`, `extract_text`: PDF cu strat de text, PDF fara
  text si imagini prin OCR (R-007), modurile `Use Only Text from PDF` / automat /
  `Use OCR` (R-020, R-021), formatele editabile (R-002, R-005).
- Limbile de comparare, declarate separat ca subset al limbilor OCR (R-008, P-101).
- Cuvantul despartit la capat de rand se reunifica (R-035).
- **Gata.** `app/core/compare/sources.py` (`load_source`, `pdf_words`,
  `editable_blocks`, `blocks_to_pdf`, `rtf_text`, `COMPARE_LANGUAGES`).

### 12.2 — Algoritmul (nucleu)

- Cuvinte → randuri → paragrafe (R-030), diferenta pe secvente de cuvinte cu
  ancore pe paragrafe identice (R-031), tipurile (R-032), diferentele minore
  ignorate mereu (R-033), punctuatia si diferentele de o litera la cerere (R-015,
  R-016), antetele si subsolurile gasite automat (R-022), cele trei grupuri
  (R-034), pe blocuri cu progres (R-036).
- Ignorarea unei diferente si a celor identice (R-048, R-049), comparatiile
  recente (R-006).
- **Gata.** `app/core/compare/engine.py` (`DocumentComparer`, `compare_sources`,
  `ignore`, `ignore_identical`, `grouped`, `record_recent`, `recent_comparisons`);
  `Difference` si `CompareOptions` in `model.py`.

### 12.3 — Salvarea rezultatelor (nucleu)

- `PDF with Comments` (R-063), `DOCX in Track Changes Mode` cate un fisier per
  document (R-061, avertismentul R-062), `Comparison Report` (R-064, R-414,
  R-415); numai `.pdf` si `.docx` (R-065); diferentele ignorate nu apar (R-067).
- **Gata.** `app/core/compare/report.py` (`save_pdf_with_comments`,
  `save_track_changes`, `save_report`); testele pasilor 12.1…12.3 in
  `tests/test_compare.py`.

### 12.4 — Interfata

- Fereastra de comparare (R-001, R-040, R-300, R-400…R-416): doua zone cu bara de
  sus si de jos, panoul din dreapta cu `Compare` si `Differences (N)`, banda
  rosie, lista grupata, evidentierea, navigarea, derularea sincronizata, copierea,
  ignorarea, salvarea, tiparirea; scurtaturile din SPEC_09 A.4.
- Pornirea din Lansator, din PDF Editor (`Compare`) si din OCR Editor
  (`Tools > Compare Documents`), cu comparatiile recente.

---

## Decizii

1. [DECIZIE AUTONOMA] **Formatele editabile** (DOCX, XLSX, PPTX, ODT, ODS, ODP,
   RTF, HTML, TXT) se citesc cu biblioteci proprii sau din stiva (python-docx,
   openpyxl, python-pptx; ODF ca arhiva XML, fara dependenta noua), iar textul lor
   se aseaza intr-un PDF simplu (pagini A4, fontul de sistem cu diacritice), care
   e si ce se vede in zona de afisare. Asa toate sursele ajung la acelasi lucru:
   cuvinte cu pagina si pozitie (R-005).
2. [DECIZIE AUTONOMA] **Comparatia nu se pastreaza in baza de date**: tabelele
   `comparison` si `comparison_difference` sunt in partea `project.db` a SPEC_04,
   iar modulul de comparare nu are proiect. Se pastreaza perechea in
   `recent_comparison` (app.db, R-006), cu limbile si numarul de diferente.
3. [DECIZIE AUTONOMA] **Valorile implicite**: `Find differences in punctuation`
   (R-015) si `Find one-letter differences` (R-016) sunt debifate; o diferenta de
   o litera inseamna o singura litera schimbata, adaugata sau stearsa; cifrele nu
   sunt litere, deci o suma schimbata e mereu diferenta. Modul PDF implicit e
   `Use Only Text from PDF` (R-020, T-R020); paginile fara text trec totusi prin
   OCR (R-007). `Automatically Choose` recunoaste si paginile al caror text are
   peste 30% caractere neobisnuite.
4. [DECIZIE AUTONOMA] **Diferentele minore** (R-033) se ignora prin cheia de
   comparare: spatiile, randurile, fontul si formatarea nu intra deloc, iar ș/ş,
   ț/ţ, ghilimelele, liniutele si ligaturile se unifica (CLAUDE.md §6.4: cele doua
   variante ale diacriticelor sunt acelasi text). Nu se raporteaza diferente de
   tip `formatting`.
5. [DECIZIE AUTONOMA] **Antetele si subsolurile** (R-022): randurile din 12% de sus
   sau de jos ale paginii care, cu cifrele ignorate, apar pe cel putin jumatate din
   pagini (minimum doua). Se compara separat de corp si dau grupul `Headers and
   footers`; `Numbering` (R-034) primeste diferentele facute numai din marcaje de
   lista (`1.`, `a)`, `iv.`, `•`).
6. [DECIZIE AUTONOMA] **Paragrafele** (R-030): un spatiu vertical mai mare de
   jumatate de rand sau o pagina noua incepe un paragraf. O inlocuire care trece
   peste paragrafe se imparte; doua bucati sunt pereche numai daca stau la fel
   fata de textul identic vecin in ambele documente, altfel sunt `sters` si
   `inserat`. Diferentele apropiate (sub `group_distance_words` = 3 cuvinte) se
   unesc numai in acelasi paragraf.
7. [DECIZIE AUTONOMA] **`DOCX in Track Changes Mode`** (R-061): fiecare fisier are
   textul documentului lui, pe paragrafe; ce exista numai in el e marcat inserat
   (`w:ins`), ce exista numai in celalalt document e marcat sters (`w:del`), la
   locul diferentei. `PDF with Comments` (R-063): evidentiere pe textul propriu
   (verde adaugat, rosu sters, mov modificat), nota la locul textului care lipseste.

## INCOMPLET

- **Formatele vechi si cele inca necitite**: `.doc`, `.xls`, `.ppt`, XPS, DjVu,
  JBIG2 (SPEC_09 B.1 le accepta in Compare) dau mesaj de format nesuportat.
- **Formatele editabile se afiseaza ca text simplu**, asezat pe pagini A4, nu cu
  aspectul lor original; comparatia lucreaza pe text, deci rezultatul nu se schimba.
- **`ignore_tables`** (SPEC_05) nu are efect: tabelele se compara ca text.
