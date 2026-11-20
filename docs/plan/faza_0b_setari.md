# Faza 0b — lista setarilor X-*, inainte de cod

Document de lucru pentru confirmare. Nu e specificatie: cand difera de
`docs/spec/`, decide `docs/spec/`, iar diferentele sunt listate la sfarsit
ca intrebari.

Surse citite: SPEC_03 capitolul X (X-001…X-169, 103 randuri), SPEC_09
(X-200…X-207), SPEC_10 (X-400…X-423), SPEC_05 sectiunea 4, SPEC_04 tabela
`setting`.

## Cum se stocheaza

- Un singur catalog in cod (`app/core/settings.py`) descrie fiecare cheie:
  tip, implicit, min/max sau valori permise, ID de cerinta. La deschiderea
  `app.db` randurile lipsa se adauga din catalog in tabela `setting`.
- Tipurile sunt cele permise de SPEC_04: `bool`, `int`, `float`, `string`,
  `enum`, `json`, `path`, `color`.
- `set()` arunca `ValueError` la valoare in afara intervalului sau a listei
  (SPEC_05). Cheie necunoscuta: tot `ValueError`.
- `reset_all()` readuce toate cheile la implicit (X-147).
- `with_overrides()` suprapune setarile proiectului peste cele globale (J-039).
- `export_to` / `import_from` raman pentru pasul 0c (Y-022), cum scrie in START.md.

Legenda coloanei **Cine citeste**: `core` = nucleul o foloseste;
`GUI` = valoarea se pastreaza acum, dar doar interfata o citeste.
Legenda **[P]**: specificatia nu da un implicit (`—`); valoarea e propunerea mea.

---

## 1. General

| Cheie | Tip | Implicit | Validare | ID | Cine citeste |
|---|---|---|---|---|---|
| `general.startup_screen` | enum | `new_task` | `new_task`, `ocr_new_project`, `ocr_last_project` | X-001 | GUI |
| `general.capture_device` | string | null = primul disponibil | — | X-002 | core (scanare) |
| `general.scan_interface` | enum | `app` | `app`, `driver` | X-003 | core (scanare) |
| `general.shell_integration` | bool | `true` [P] | — | X-005 | instalare / integrari |

Nu e setare: **X-004** (program implicit pentru PDF) e o actiune catre sistem,
starea se citeste din sistem → faza 15.

## 2. Image Processing

| Cheie | Tip | Implicit | Validare | ID | Cine citeste |
|---|---|---|---|---|---|
| `image.background_recognition_pdf` | bool | `true` | — | X-010 | core |
| `image.auto_process` | bool | `true` | — | X-011 | core |
| `image.auto_mode` | enum | `recognize` | `recognize`, `analyze`, `preprocess` | X-012 | core |
| `image.preprocess_mode` | enum | `auto` | `auto`, `manual`, `none` | X-014, X-015, X-031, X-413 | core |
| `image.split_facing_pages` | bool | `false` | — | X-016 | core |
| `image.correct_orientation` | bool | `true` | — | X-017 | core |
| `image.use_recommended` | bool | `true` | — | X-018 | core |
| `image.deskew` | bool | `true` | — | X-020 | core |
| `image.straighten_lines` | bool | `true` | — | X-021 | core |
| `image.correct_resolution` | bool | `true` | — | X-022 | core |
| `image.detect_page_edges` | bool | `true` | doar foto | X-023 | core |
| `image.whiten_background` | bool | `true` | doar foto | X-024 | core |
| `image.reduce_iso_noise` | bool | `true` | doar foto | X-025 | core |
| `image.remove_motion_blur` | bool | `false` | doar foto | X-026 | core |
| `image.correct_trapezoid` | bool | `true` [P] | doar foto | X-027 | core |
| `image.fix_inverted_colors` | bool | `true` | — | X-028 | core |
| `image.convert_to_bw` | bool | `false` | — | X-029 | core |
| `image.remove_color_marks` | bool | `false` | — | X-030 | core |

- **X-414** (bifele nu se pierd la schimbarea modului) iese din felul in care
  se stocheaza: modul si bifele sunt chei separate.
- **X-013** („se aplica doar imaginilor adaugate de acum inainte”) e regula
  de comportament pentru faza 2, nu cheie.
- Doar GUI: **X-019** (afiseaza / ascunde setarile avansate) e starea
  dialogului, nu se salveaza.

## 3. Languages

| Cheie | Tip | Implicit | Validare | ID | Cine citeste |
|---|---|---|---|---|---|
| `lang.mode` | enum | `auto` | `auto`, `manual` | X-040, X-042 | core |
| `lang.auto_candidates` | json (lista) | `["ron","eng"]` | minim o limba | X-041 | core |
| `lang.manual` | json (lista) | `["ron","eng"]` | minim o limba (P-001) | X-042 | core |

- **X-048** (limbile gotice nu se combina cu cele moderne) cere registrul de
  limbi → validarea se adauga in faza 4.
- Nu sunt setari: X-043 (buton „New…”), X-044…X-047, X-049 descriu limbile
  livrate → `LanguageRegistry`, faza 4.

## 4. OCR

| Cheie | Tip | Implicit | Validare | ID | Cine citeste |
|---|---|---|---|---|---|
| `ocr.pdf_mode` | enum | **vezi intrebarea 2** | `auto`, `ocr`, `text` | X-060 | core |
| `ocr.quality` | enum | `thorough` | `thorough`, `fast` | X-062, X-063 | core |
| `ocr.document_type` | enum | `auto` | `auto`, `typewriter`, `fax` | X-064 | core |
| `ocr.detect_headers_footers` | bool | `true` | — | X-065 | core |
| `ocr.detect_footnotes` | bool | `true` | — | X-065 | core |
| `ocr.detect_table_of_contents` | bool | `true` | — | X-065 | core |
| `ocr.detect_numbered_lists` | bool | `true` | — | X-065 | core |
| `ocr.barcodes_to_text` | bool | `false` | — | X-066 | core |
| `ocr.use_training` | bool | `false` | — | X-067 | core |
| `ocr.patterns` | enum | `builtin` | `builtin`, `user` | X-068 | core |
| `ocr.user_patterns_also_builtin` | bool | `false` | activa doar cu `user` | X-068, X-416 | core |
| `ocr.training_also_builtin` | bool | `false` | activa doar cu antrenare | X-416 | core |
| `ocr.export_fonts` | json (lista) | null = fonturile de sistem | — | X-071 | core (export) |
| `ocr.header_repeat_ratio` | float | `0.5` | 0 < x ≤ 1 | N-016 (in SPEC_05) | core |

- **X-061** (PDF-urile cautabile folosesc mereu OCR) e regula de
  comportament pentru faza 4, nu cheie.
- Doar GUI: X-069 (Pattern Editor), X-070 (salvare / incarcare `.fbt`).

## 5. Format Settings

### 5.1 PDF

| Cheie | Tip | Implicit | Validare | ID |
|---|---|---|---|---|
| `pdf.image_quality` | enum | `balanced` (din SPEC_05) | `best`, `balanced`, `compact`, `custom` | X-080 |
| `pdf.create_pdfa` | bool | `false` | — | X-081 |
| `pdf.pdfa_version` | enum | `2b` | cele 8 din `PdfAVersion` | X-081 |
| `pdf.create_pdfua` | bool | `false` | — | X-082 |
| `pdf.protect_with_password` | bool | `false` | — | X-083 |
| `pdf.delete_objects` | bool | `false` | — | X-084 |
| `pdf.delete_objects_items` | json (lista) | toate cele 4 [P] | `comments`, `links_media_forms`, `bookmarks`, `attachments` | X-084 |
| `pdf.single_paper_size` | bool | `false` | — | X-085 |
| `pdf.use_mrc` | bool | `false` | — | X-086 |
| `pdf.smooth_characters` | bool | `false` [P] | — | X-087 |
| `pdf.searchable_mode` | enum | `text_under` [P] | `text_and_pictures`, `text_over`, `text_under` | X-088 |
| `pdf.bookmarks_from_headings` | bool | `false` (din SPEC_05) | — | X-089 |
| `pdf.create_tags` | bool | `false` (din SPEC_05) | — | X-090 |
| `pdf.fonts` | enum | `predefined` [P] | `predefined`, `system` | X-091 |
| `pdf.embed_fonts` | bool | `true` [P] | — | X-092 |
| `pdf.preserve_metadata` | bool | `true` | — | X-093 |

- **Parolele nu se salveaza niciodata** in setari (CLAUDE.md §9). Se
  salveaza doar bifa X-083.
- Reguli intre chei, aplicate in nucleu:
  - X-421: PDF/UA bifat → `create_tags` e fortat la `true` in valoarea efectiva;
  - X-086: MRC doar cu `text_under`;
  - X-092: incorporarea fonturilor nu functioneaza cu `text_under`;
  - A-028: PDF/A + parola → `PdfAEncryptionConflictError`.

  Le verific la export (`ExportOptions.validate`, faza 6), nu la `set()`,
  ca utilizatorul sa poata bifa in orice ordine.
- `X-087` se numeste in original dupa o marca ABBYY; cheia noastra are nume generic.
- Doar GUI: X-094 (metadatele sunt per document, J-020, nu globale).

### 5.2 DOC(X) / RTF / ODT

| Cheie | Tip | Implicit | Validare | ID |
|---|---|---|---|---|
| `docx.layout` | enum | `editable` (din SPEC_05) | `exact`, `editable`, `formatted`, `plain` | X-100 |
| `docx.paper_size` | enum | `auto` [P] | `auto`, `a3`, `a4`, `a5`, `letter`, `legal` [P] | X-101 |
| `docx.keep_pictures` | bool | `true` (din SPEC_05) | — | X-102 |
| `docx.keep_headers_footers` | bool | `false` (din SPEC_05) | — | X-103 |
| `docx.keep_line_breaks` | bool | `false` (din SPEC_05) | — | X-104 |
| `docx.keep_page_breaks` | bool | `true` [P] | — | X-105 |
| `docx.keep_line_numbers` | bool | `false` [P] | doar cu `editable` | X-106 |
| `docx.keep_colors` | bool | `true` [P] | — | X-107 |
| `docx.keep_styles_in_plain` | bool | `true` [P] | doar cu `plain` | X-108 |
| `docx.highlight_low_confidence` | bool | `false` [P] | — | X-109 |

X-102 e in original un combo cu „Custom…”, cu valori nelistate. Pana in
faza 6 il pastrez ca bifa, cum e in SPEC_05.

### 5.3 Celelalte formate (X-120…X-127)

| Format | Chei (implicit) |
|---|---|
| XLSX (X-120) | `xlsx.layout` `formatted`/`plain` (`formatted` [P]); `xlsx.keep_pictures` (`true`); `xlsx.keep_headers_footers` (`false`); `xlsx.ignore_text_outside_tables` (`false` [P]); `xlsx.numbers_as_numbers` (`true` [P]); `xlsx.sheet_per_page` (`false` [P]) |
| PPTX (X-121) | `pptx.keep_pictures` (`true`); `pptx.keep_headers_footers` (`false`); `pptx.keep_line_breaks` (`true` [P]); `pptx.shrink_on_overflow` (`true` [P]) |
| CSV (X-122) | `csv.ignore_text_outside_tables` (`true` [P]); `csv.page_break_char` (`false` [P]); `csv.delimiter` `,` `;` `tab` (`;` [P], pentru Excel in romana); `csv.encoding` (`utf-8` [P]) |
| TXT (X-123) | `txt.layout` `formatted`/`plain` (`plain` [P]); `txt.keep_line_breaks` (`true` [P]); `txt.page_break_char` (`false` [P]); `txt.blank_line_paragraphs` (`false` [P]); `txt.keep_headers_footers` (`false`); `txt.encoding` (`utf-8` [P]) |
| HTML (X-124, X-125) | `html.layout` `flexible`/`formatted`/`plain` (`formatted` [P]); `html.keep_pictures` (`true`); `html.keep_line_breaks` (`false` [P]); `html.keep_colors` (`true` [P]); `html.keep_headers_footers` (`false`); `html.encoding` (`utf-8` [P]); `html.book_split` `none`/`auto`/`h1`/`h2` (`none` [P]) |
| EPUB / FB2 (X-126) | `epub.layout` `formatted`/`plain` (`formatted` [P]); `epub.retain_fonts` (`true` [P]); `epub.embed_fonts` (`false` [P]); `epub.first_page_cover` (`false` [P]); `epub.keep_pictures` (`true`); `epub.version` `2.0`/`3.0` (`3.0` [P]) |
| DjVu (X-127) | `djvu.save_mode` `text_under`/`image_only` (`text_under` [P]); `djvu.image_quality` ca la PDF (`balanced` [P]); `djvu.multiple_layers` `auto`/`on`/`off` (`auto`) |

`*.layout` accepta numai modurile permise pentru format (matricea Q din
`model.py`), deci validarea foloseste `ExportFormat.allowed_for`.

## 6. Other

| Cheie | Tip | Implicit | Validare | ID | Cine citeste |
|---|---|---|---|---|---|
| `ui.language` | enum | `ro` [P] | `ro`, `en` (CLAUDE.md §6.5) | X-140 | GUI (cere repornire) |
| `ocr.max_threads` | int | null = toate nucleele minus unul | ≥ 1 | X-141 | core |
| `pdf.enable_javascript` | bool | `false` | — | X-145 | core |
| `pdf.detect_urls` | bool | `true` | — | X-146 | core |
| `ui.dark_theme` | bool | `false` | — | X-149 (N) | GUI |
| `app.temp_folder` | path | null = folderul temporar al sistemului | — | X-150 | core (pasul 0c) |

- **X-142, X-143, X-144 nu exista** (Y-001). Un test verifica ca nicio cheie
  de actualizare, telemetrie sau marketing nu apare in catalog.
- X-147 (`Reset…`) = `reset_all()`.
- **Scurtaturile** (X-148, X-200…X-207) stau in tabela separata
  `keyboard_shortcut`, nu in `setting`, si au nevoie de catalogul de comenzi
  din SPEC_09 A.1…A.4 → **vezi intrebarea 5**.

## 7. Areas and Text

| Cheie | Tip | Implicit | Validare | ID | Cine citeste |
|---|---|---|---|---|---|
| `areas.check_uncertain` | bool | `true` | — | X-160 | GUI |
| `areas.uncertain_color` | color | `#FFB000` [P] | `#RRGGBB` | X-160, X-166, X-109 | GUI + export DOCX |
| `areas.ignore_words_with_digits` | bool | `true` [P] | — | X-161 | core (verificare) |
| `areas.check_compound_words` | bool | `true` [P] | — | X-161 | core (verificare) |
| `areas.fix_punctuation_spaces` | bool | `true` [P] | — | X-162 | core |
| `areas.user_dictionaries_folder` | path | null = `<date aplicatie>/dictionaries` (0c) | — | X-163 | core |
| `areas.plain_text_font` | string | null = fontul sistemului [P] | — | X-164 | GUI |
| `areas.color.<tip>` × 6 | color | paleta de mai jos [P] | `#RRGGBB` | X-165, M-100 | GUI |
| `areas.border_width.<tip>` × 6 | int | `2` [P] | 1…6 [P] | X-165 | GUI |
| `ocr.confidence_threshold` | float | `70` | 0…100 | X-167 | core |
| `areas.show_numbers` | bool | `true` | — | X-168 | GUI |
| `areas.show_nonprinting` | bool | `false` | — | X-169 | GUI |

Paleta propusa pentru zone. E diferita de ABBYY 16, unde textul e albastru,
imaginea roz-magenta si tabelul verde (M-100, CLAUDE.md §6.6):

| Tip | Culoare |
|---|---|
| `recognition` | `#6B7280` gri |
| `text` | `#0F9D8A` turcoaz |
| `table` | `#D97706` chihlimbar |
| `picture` | `#7C3AED` violet |
| `background_picture` | `#C084FC` violet deschis |
| `barcode` | `#DC2626` rosu |

## 8. Ce ramane pentru faza GUI (fara cheie acum)

- X-004, X-019, X-043, X-069, X-070, X-094: butoane, actiuni sau starea dialogului.
- X-400…X-423: aspectul dialogului Options (marime, ordinea tab-urilor,
  coloane, texte de ajutor, butoane). Doua dintre ele au si o regula in nucleu:
  - X-414 e acoperita de stocare;
  - X-421 e aplicata in valoarea efectiva PDF.

Total: 129 de chei, implementate in `app/core/settings.py` (`CATALOG`).
Codarile (`*.encoding`) accepta `utf-8`, `utf-16`, `windows-1250` si
`iso-8859-2` [P]; specificatia nu le listeaza.

**Status:** lista si cele 6 recomandari au fost confirmate de utilizator
pe 2026-11-20.

---

## Intrebari care cer decizia ta

1. **Preprocesarea nu se potriveste cu SPEC_05.**
   - `PreprocessSettings` nu are modul auto/manual/niciuna (X-413) si nici
     corectia de trapez (X-027).
   - `AutoProcessMode` are `read`, `analyze_and_read`, `preprocess_only` si
     `none`, iar X-012 are recunoastere, analiza si preprocesare.

   **Propunerea mea, fara sa modific contractul:** stochez modul ca cheie
   separata. `preprocess_settings()` intoarce atunci:
   - `none` → toate bifele `false`;
   - `auto` → valorile livrate;
   - `manual` → bifele salvate.

   Pentru X-012 folosesc maparea `recognize→READ`, `analyze→ANALYZE_AND_READ`,
   `preprocess→PREPROCESS_ONLY`, iar X-011 debifat → `NONE`. Trapezul se
   citeste deocamdata cu `get('image.correct_trapezoid')`, pana il adaugi in
   contract.
2. **`ocr.pdf_mode` implicit.** X-060 spune „Use Only Text from PDF” pentru
   PDF-urile cu strat de text. SPEC_05 spune `AUTO`. Propun `auto`: e cea mai
   apropiata de X-060 si de X-061 (OCR pentru cele doar-imagine).
3. **Doua bife „Also use built-in patterns”** (X-416). `OcrSettings` are un
   singur `also_use_builtin`. Propun doua chei, iar `also_use_builtin` din
   `ocr_settings()` sa fie bifa celui care e activ.
4. **Implicitele marcate [P]** (aproximativ 45). Accepti propunerile, sau vrei
   sa schimbi vreuna?
5. **Scurtaturile** (X-148, X-200…X-207). Propun un pas separat, dupa 0c:
   cere catalogul complet de comenzi din SPEC_09 si nu tine de tabela `setting`.
6. **Limba interfetei.** Originalul are 22 de limbi, fara romana. Propun
   deocamdata doar `ro` si `en`, cu implicit `ro`.

## Nepotriviri gasite (de stiut, nu cer decizie acum)

ID-urile din docstring-urile SPEC_05 sectiunea 4 sunt din numerotarea veche
(SPEC_08 confirma ca X-* au fost renumerotate). De exemplu:

| Camp in SPEC_05 | ID in SPEC_05 | ID real in SPEC_03 |
|---|---|---|
| `convert_to_bw` | X-022 | X-029 |
| `convert_barcodes_to_text` | X-044 | X-066 |
| `use_training` | X-046 | X-067 |
| `confidence_threshold` | X-102 | X-167 |
| `max_threads` | X-081 | X-141 |
| `create_bookmarks_from_headings` | X-060 | X-089 |

In cod si in teste folosesc ID-urile reale din SPEC_03.
