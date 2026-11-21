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
pe 2026-11-20. Pasii 4.1 (commit „Faza 4a”), 4.2, 4.3 si 4.4 sunt implementati.
Pasul 4.5 e impartit in 4.5.1 (alegerea automata a limbii, P-001, P-009; implementat),
4.5.2 (tabelele pe celule, mutarea paginilor cu text; implementat), 4.5.3 (structura,
N-018…N-021; implementat) si 4.5.4 (coduri de bare, zxing-cpp).

**Mutat din 4.3 in 4.5:** recunoasterea tabelelor pe celule si mutarea
paginilor intre proiecte impreuna cu textul lor.

**Numerotarea pasilor (2026-11-21):** pasii fazei 4 se numesc 4.1…4.5 (initial
4a…4e). Literele sunt folosite in CLAUDE.md pentru faze (4b, 6b, 6c, 6d), deci
de acum pasii oricarei faze se numeroteaza cu punct: 6.1, 6.2... Pasii deja
facuti (1a…3d) si commit-ul „Faza 4a” raman cu numele lor.

**Faza 4b (CLAUDE.md §8) e alta decat pasul 4.2:** limbi proprii, dictionare,
sabloane de caractere, expresii regulate (P-020…P-128, Z-020…Z-030). Vine
dupa faza 4 si are propriul plan. Faza 4 acopera N-* si P-001…P-009.

**Schimbare la decizia 2 (2026-11-21):** pe Mac-ul de dezvoltare (Intel,
macOS 15) Homebrew nu are Tesseract precompilat si cere Xcode 26. Produsul
ruleaza pe Windows, deci: CI-ul (Windows, Linux, macOS ARM) e referinta, iar
pe Mac Tesseract 5.5.4 vine de pe conda-forge, prin micromamba, in `.tools/`
(exclus din git).

**Constatare 4.1, pentru 4.5 (P-001):** cu limbile implicite `ron+eng`,
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

### 4.1 — Motorul OCR: Tesseract

`app/core/ocr/engine.py`: `OcrEngine` din SPEC_05 si `TesseractEngine`.

- Recunoasterea unei zone (N-005): cuvinte cu pozitie si incredere,
  grupate in blocuri si randuri (`BlockData`, `LineData`, `WordData`).
- Salvarea textului in `text_block`, `text_line`, `word`.
- Limbile: codurile proiectului (`ron`, `eng`...), cu `LanguageModelMissingError`
  cand modelul lipseste (Y-004).
- Diacriticele romanesti: vezi decizia 4.
- Masurarea acuratetii (Levenshtein) pe pagini generate.
- **Tesseract instalat pe Mac si in CI** (decizia 2).

### 4.2 — Analiza automata a paginii si orientarea

`app/core/layout/analyzer.py`: `LayoutAnalyzer` din SPEC_05.

- `Analyze Page` / `Analyze All Pages` (N-006, N-007): zonele de text,
  imagine si tabel se gasesc automat, numerotate pe coloane (M-022). Zonele
  desenate de utilizator se pastreaza (SPEC_05).
- Orientarea paginii (X-017), cu modulul OSD din Tesseract.
- `Recognize Page` analizeaza intai daca e nevoie (N-004).

### 4.3 — Serviciul de recunoastere

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

### 4.4 — PDF-uri cu strat de text

- Evaluarea stratului de text existent (N-011) si alegerea modului (N-008,
  N-010). PDF-urile cautabile si cele doar-imagine folosesc mereu OCR (N-009).
- Documentele mixte: textul digital se extrage, imaginile se recunosc,
  rezultatele se combina (N-012).

### 4.5 — Elemente de structura, coduri de bare, limbi

- Antete si subsoluri (repetate pe pagini), note de subsol, cuprins, liste
  (N-018…N-021).
- Citirea codurilor de bare (M-057…M-060) cu zxing-cpp: cele 11 tipuri
  autodetectate; un cod ilizibil lasa zona imagine (M-060).
- Lista limbilor, alegerea automata dintr-o lista (P-001…P-004), limbile cu
  dictionar (P-006), romana si RomanianMoldavia (P-008), avertismentul peste
  3 limbi (P-009).

---

## Decizii care cer confirmarea ta

1. **Impartirea de mai sus**, in 5 pasi (4.1…4.5).
2. **Instalarea Tesseract.** Pe Mac: `brew install tesseract tesseract-lang`
   (Homebrew e deja instalat). In CI: pachetele sistemului pe Linux (apt),
   macOS (brew) si Windows (choco), cu limba romana. Pe Windows, instalarea
   poate adauga cateva minute la CI.
3. **Dependente noi:** pytesseract (Apache-2.0) in 4.1, zxing-cpp (Apache-2.0)
   in 4.5. **PaddleOCR nu**: e foarte mare (PaddlePaddle), iar tabelele le
   detecteaza deja `TableAnalyzer` din 3d. Revenim la el doar daca tabelele
   nu ating pragul de 90% din SPEC_06.
4. **Diacriticele:** textul recunoscut se normalizeaza implicit la forma
   corecta, cu virgula (ș, ț), oricum ar aparea in imagine (cu virgula sau cu
   sedila). Asa se elimina confuzia ș/ş masurata in SPEC_06. Forma cu sedila
   se poate pastra printr-o setare, pentru documente vechi.
5. **Tipul de document (N-016, N-017):** Tesseract nu are moduri „Typewriter”
   si „Fax”. Le aproximez prin setarile motorului si prin preprocesare, marcat
   ca atare.
6. **Pragurile de calitate** se verifica in 4.1 pe text generat. Verificarea pe
   corpusul real din SPEC_06 ramane marcata INCOMPLET pana exista corpusul.

---

## Decizii autonome (CLAUDE.md sectiunea 11)

- **[DECIZIE AUTONOMA] 4.5.3, cuprinsul (N-020):** SPEC_04 nu are un tip de bloc
  pentru cuprins. Intrarile primesc `text_block.style_name = "TOC"`; exportul
  (faza 6) le transforma in legaturi. Motiv: nu se modifica `docs/spec/`.
- **[DECIZIE AUTONOMA] 4.5.3, benzile:** antetul sta in primele 12% din pagina,
  subsolul in ultimele 12%; nota de subsol sub 70%, cu randul sub 90% din
  inaltimea obisnuita si cu un marcaj (cifra, exponent, asterisc).
- **[DECIZIE AUTONOMA] 4.5.3, numarul de pagina „1”:** Tesseract il citeste des
  „l” sau „I”; singur in banda de antet/subsol, conteaza ca numar de pagina.
- **[DECIZIE AUTONOMA] 4.5.3, motorul:** zona trimisa la Tesseract primeste o
  margine alba de 10 px; o zona mica (sub 5% din pagina) gasita goala in modul
  pagina se reincearca in modul „un rand” (psm 7).
