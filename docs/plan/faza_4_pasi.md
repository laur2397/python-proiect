# Faza 4 — impartirea in pasi, inainte de cod

Document de lucru pentru confirmare. Faza 4 din CLAUDE.md §8: recunoasterea —
motor, limbi, incredere (`N-*`, `P-001`…`P-009`). Aici intra si ce a ramas
amanat din fazele anterioare: analiza automata a paginii (N-006, N-007),
orientarea (X-017), citirea codurilor de bare (M-057…M-060), textul in
istoricul de undo si la mutarea paginilor.

Surse citite: SPEC_02 N (N-001…N-028) si P-001…P-009, SPEC_05 sectiunea 7
(`RecognitionResult`, `OcrEngine`, `RecognitionService`, `LanguageRegistry`),
SPEC_06 capitolul 3 (pragurile de calitate), SETUP.md 1.4 (Tesseract).

Regula ramane: un pas = o sesiune = un commit cu CI verde.

**Status:** impartirea si cele 6 propuneri au fost confirmate de utilizator
pe 2026-11-20. Pasul 4a e implementat.

**Schimbare la decizia 2 (2026-11-21):** pe Mac-ul de dezvoltare (Intel,
macOS 15) Homebrew nu are Tesseract precompilat si cere Xcode 26. Produsul
ruleaza pe Windows, deci: CI-ul (Windows, Linux, macOS ARM) e referinta, iar
pe Mac Tesseract 5.5.4 vine de pe conda-forge, prin micromamba, in `.tools/`
(exclus din git).

**Constatare 4a, pentru 4e (P-001):** cu limbile implicite `ron+eng`,
Tesseract pierde diacriticele (Ștefan → Stefan); acuratetea pe cuvant scade
de la ~97% la ~92%. Doar cu `ron` pragul de 96% e atins. Alegerea automata
a limbii trebuie deci sa aleaga limba potrivita din lista, nu sa le foloseasca
pe toate deodata.

---

## Pragurile de calitate (SPEC_06, capitolul 3)

| Indicator | Prag |
|---|---|
| Acuratete pe caracter, scanari de 300 dpi | ≥ 98% |
| Acuratete pe caracter, scanari de 200 dpi | ≥ 94% |
| Acuratete pe cuvant, documente romanesti cu diacritice | ≥ 96% |
| Confuzia ș/ş si ț/ţ | ≤ 2 la 1.000 de caractere |
| Orientarea paginii | ≥ 99% |
| Viteza, A4 300 dpi, mod `thorough`, 8 nuclee | ≤ 4 s pe pagina |
| Coduri de bare | 100% pe cele 11 tipuri |

Corpusul real din SPEC_06 nu e in repo. In faza 4 le masor pe text romanesc
generat (pagini randate cu fonturi reale, cu diacritice) si marchez ca
INCOMPLET verificarea pe corpusul real.

---

## Pasii

### 4a — Motorul OCR: Tesseract

`app/core/ocr/engine.py`: `OcrEngine` din SPEC_05 si `TesseractEngine`.

- Recunoasterea unei zone (N-005): cuvinte cu pozitie si incredere,
  grupate in blocuri si randuri (`BlockData`, `LineData`, `WordData`).
- Salvarea textului in `text_block`, `text_line`, `word`.
- Limbile: codurile proiectului (`ron`, `eng`...), cu `LanguageModelMissingError`
  cand modelul lipseste (Y-004).
- Diacriticele romanesti: vezi decizia 4.
- Masurarea acuratetii (Levenshtein) pe pagini generate.
- **Tesseract instalat pe Mac si in CI** (decizia 2).

### 4b — Analiza automata a paginii si orientarea

`app/core/layout/analyzer.py`: `LayoutAnalyzer` din SPEC_05.

- `Analyze Page` / `Analyze All Pages` (N-006, N-007): zonele de text,
  imagine si tabel se gasesc automat, numerotate pe coloane (M-022). Zonele
  desenate de utilizator se pastreaza (SPEC_05).
- Orientarea paginii (X-017), cu modulul OSD din Tesseract.
- `Recognize Page` analizeaza intai daca e nevoie (N-004).

### 4c — Serviciul de recunoastere

`app/core/ocr/service.py`: `RecognitionService` din SPEC_05.

- `Recognize All Pages` (N-003): paginile deja recunoscute se sar.
- Progres si anulare dupa pagina curenta (N-022, N-028).
- Increderea si cuvintele nesigure, cu pragul 70 din setari (N-024, N-025).
- Avertismentele dupa recunoastere, de exemplu rezolutie prea mica (N-023).
- Paralelizarea pe nuclee (N-027).
- Recunoasterea automata la adaugare (N-001, J-051): preprocesare → analiza →
  recunoastere, dupa modul din setari (X-012).
- Moduri `thorough` / `fast` (N-013, N-014) si tipul de document (N-015…N-017).
- Textul intra in istoricul de undo si se muta odata cu paginile (marcat
  INCOMPLET din 1e).

### 4d — PDF-uri cu strat de text

- Evaluarea stratului de text existent (N-011) si alegerea modului (N-008,
  N-010). PDF-urile cautabile si cele doar-imagine folosesc mereu OCR (N-009).
- Documentele mixte: textul digital se extrage, imaginile se recunosc,
  rezultatele se combina (N-012).

### 4e — Elemente de structura, coduri de bare, limbi

- Antete si subsoluri (repetate pe pagini), note de subsol, cuprins, liste
  (N-018…N-021).
- Citirea codurilor de bare (M-057…M-060) cu zxing-cpp: cele 11 tipuri
  autodetectate; un cod ilizibil lasa zona imagine (M-060).
- Lista limbilor, alegerea automata dintr-o lista (P-001…P-004), limbile cu
  dictionar (P-006), romana si RomanianMoldavia (P-008), avertismentul peste
  3 limbi (P-009).

---

## Decizii care cer confirmarea ta

1. **Impartirea de mai sus**, in 5 pasi (4a…4e).
2. **Instalarea Tesseract.** Pe Mac: `brew install tesseract tesseract-lang`
   (Homebrew e deja instalat). In CI: pachetele sistemului pe Linux (apt),
   macOS (brew) si Windows (choco), cu limba romana. Pe Windows, instalarea
   poate adauga cateva minute la CI.
3. **Dependente noi:** pytesseract (Apache-2.0) in 4a, zxing-cpp (Apache-2.0)
   in 4e. **PaddleOCR nu**: e foarte mare (PaddlePaddle), iar tabelele le
   detecteaza deja `TableAnalyzer` din 3d. Revenim la el doar daca tabelele
   nu ating pragul de 90% din SPEC_06.
4. **Diacriticele:** textul recunoscut se normalizeaza implicit la forma
   corecta, cu virgula (ș, ț), oricum ar aparea in imagine (cu virgula sau cu
   sedila). Asa se elimina confuzia ș/ş masurata in SPEC_06. Forma cu sedila
   se poate pastra printr-o setare, pentru documente vechi.
5. **Tipul de document (N-016, N-017):** Tesseract nu are moduri „Typewriter”
   si „Fax”. Le aproximez prin setarile motorului si prin preprocesare, marcat
   ca atare.
6. **Pragurile de calitate** se verifica in 4a pe text generat. Verificarea pe
   corpusul real din SPEC_06 ramane marcata INCOMPLET pana exista corpusul.
