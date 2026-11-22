# Faza 12 — Compararea documentelor

**Cerinte:** `R-001`…`R-068` (SPEC_03), `R-300` (SPEC_09), `R-400`…`R-416` (SPEC_10).
**Status:** planul pasilor; urmeaza 12.1.

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

### 12.2 — Algoritmul (nucleu)

- Cuvinte → randuri → paragrafe (R-030), diferenta pe secvente de cuvinte cu
  ancore pe paragrafe identice (R-031), tipurile (R-032), diferentele minore
  ignorate mereu (R-033), punctuatia si diferentele de o litera la cerere (R-015,
  R-016), antetele si subsolurile gasite automat (R-022), cele trei grupuri
  (R-034), pe blocuri cu progres (R-036).
- Ignorarea unei diferente si a celor identice (R-048, R-049), comparatiile
  recente (R-006) si pastrarea comparatiei (SPEC_04).

### 12.3 — Salvarea rezultatelor (nucleu)

- `PDF with Comments` (R-063), `DOCX in Track Changes Mode` cate un fisier per
  document (R-061, avertismentul R-062), `Comparison Report` (R-064, R-414,
  R-415); numai `.pdf` si `.docx` (R-065); diferentele ignorate nu apar (R-067).

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
