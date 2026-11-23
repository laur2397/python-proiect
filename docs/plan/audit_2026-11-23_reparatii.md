# Reparatiile dupa auditul din 23.11.2026

Raportul: `docs/audit/AUDIT_2026-11-23.md`. Defectele 2–7 sunt reparate, in
ordinea din raport, cu teste; defectul 1 (CI-ul) asteapta utilizatorul.

| # | Defect | Reparatia | Teste |
|---|---|---|---|
| 2 | N-026: limbile nu invalidau paginile | `OcrProject.check_ocr_settings`: amprenta setarilor OCR efective si a limbilor; la schimbare (limbile proiectului, setarile proiectului, setarile globale din Options) paginile `recognized`/`verified` revin la `analyzed`. Magazinele de setari anunta schimbarile (`add_listener`) | `tests/test_n026.py` (+ `test_areas.py`, T-N026.1) |
| 3 | Redactarea pierdea punctuatia | `redact._kept_words`: un caracter e pe randul cuvantului daca intervalele verticale se suprapun (punctuatia are dreptunghiul strans la linia de baza) | `test_pdf_redact.py::test_T_G020_3` |
| 4 | Chenarul tabelului citit ca randuri | `tables._frame`: prima si ultima linie care inchid toata cerneala sunt marginile grilei; celelalte linii sunt separatoare, oricat de aproape de chenar (coloana `Nr.`) | `test_tables.py::test_T_M040_2` |
| 5 | Cuprinsul dosarului | emitentul `OU, O` (`signatures._issuer_name`), data locala `09.08.2024 17:41` (`dossier.local_time`) | `test_pdf_dossier.py::test_T_E502_issuer_short_and_local_date` |
| 6 | DCX cu Pillow 12.3 | paginile DCX se citesc direct ca PCX din tabelul de pozitii (`loader._dcx_page`); verificat si cu Pillow 12.3 | `test_loader.py::test_dcx_multipage` |
| 7 | Trasabilitate | teste cu ID pentru N-013, N-025, N-103, P-102, I-018; **implementate**: I-032 (`text_and_pictures`) si X-204…X-207 (dialogul `Customize`, `ShortcutStore`) | `test_audit_trace.py`, `test_export_pdf.py::test_T_I032_1`, `test_x204.py` |

## Decizii

1. [DECIZIE AUTONOMA] **P-102 (`D`): DocuLens declara 120 de limbi cu dictionar,
   nu 53.** Originalul spune 53 (pagina de specificatii), dar lista lor nu e in
   specificatie, iar P-101 cere „declaram ce acoperim”. In DocuLens o limba are
   dictionar cand modelul Tesseract are lista de cuvinte (toate limbile naturale,
   plus Esperanto); limbile formale si cele artificiale fara model nu au
   (`languages.DICTIONARY_COUNT`). **Confirmat de utilizator pe 23.11.2026:
   raman 120.**
2. [DECIZIE AUTONOMA] **N-026**: la schimbarea setarilor, zonele si textul raman
   (se pot pastra corecturile), numai statusul revine la `analyzed`, iar exportul
   avertizeaza (Q-051). Numarul de fire (`ocr.max_threads`) nu invalideaza: schimba
   doar viteza. Amprenta de referinta e cea de la deschiderea proiectului; o
   setare globala schimbata cat proiectul era inchis nu se observa la redeschidere.
3. [DECIZIE AUTONOMA] **Chenarul tabelului**: o linie e chenar daca dincolo de ea
   nu mai e cerneala in zona. Un titlu deasupra tabelului, in aceeasi zona, face
   ca linia de sus sa fie separator, iar titlul un rand.
4. [DECIZIE AUTONOMA] **X-204**: dialogul `Customize` are numai tabul `Keyboard
   Shortcuts`; personalizarea barelor de instrumente nu e facuta (INCOMPLET).
   In `keyboard_shortcut.display_name` se pastreaza cheia de traducere a comenzii,
   nu textul (CLAUDE.md §6.5). Comenzile sunt cele din meniurile OCR Editor-ului.
5. [DECIZIE AUTONOMA] **I-032**: in `text_and_pictures` textul se scrie cu fontul de
   sistem cu diacritice, la locul si latimea fiecarui cuvant; liniile tabelelor si
   fundalul nu se deseneaza (cerinta spune ca rezultatul poate arata altfel).

## INCOMPLET

- Personalizarea barelor de instrumente din `Customize` (alte taburi decat
  `Keyboard Shortcuts`).
