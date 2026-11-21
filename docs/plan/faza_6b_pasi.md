# Faza 6b — impartirea in pasi

Faza 6b din CLAUDE.md §8: interfata OCR Editor-ului, peste nucleul gata
(fazele 0–6). Scrisa in modul autonom (CLAUDE.md §11); deciziile sunt marcate
`[DECIZIE AUTONOMA]` si se revad la oprirea de dupa faza 6d.

Cerintele de interfata ramase din fazele anterioare (notele „faza GUI”):
- J-001…J-017 (panouri, bare, zoom, bara de proprietati), J-* din faza 1;
- L-001…L-004, L-100…L-108 (Image Editor), din faza 2;
- M-009…M-011, M-015, M-029, M-100…M-111 (zonele cu mouse-ul), din faza 3;
- O-021, O-028, O-029, O-064, O-100…O-109 (panoul Text), din faza 5;
- X-004, X-019, X-043, X-069, X-070, X-094, X-400…X-423 (dialogul Options),
  Y-025, din faza 0b;
- Q-040…Q-050, Q-100…Q-102 (salvarea, trimiterea, tiparirea), din faza 6.

Surse: SPEC_10 (interfata la nivel de element), SPEC_09 (scurtaturi, meniuri),
`docs/prototip_ocr_editor.html`. Regula CLAUDE.md §6.6: structura interfetei,
nu identitatea vizuala ABBYY (fara paleta, iconuri, nume).

**Status:** planul e scris; niciun pas implementat.

---

## Pasii

### 6b.1 — Scheletul ferestrei si traducerile

- PySide6 (stiva, LGPL-3.0, legat dinamic) si pytest-qt (MIT) pentru teste,
  cu `QT_QPA_PLATFORM=offscreen` in CI (deja setat).
- `app/gui/i18n/`: traducerile romana si engleza (CLAUDE.md §6.5); niciun
  text afisabil in cod.
- Fereastra principala: meniurile si barele din SPEC_10/SPEC_09, panourile
  Pages, Image, Text, Zoom (J-001…J-017), aranjarea lor, starea salvata.
- Pornirea aplicatiei (`app/gui/main.py`) peste `AppContext`.

### 6b.2 — Paginile, imaginea, zonele

- Panoul Pages: miniaturi, selectie, ordine, stergere, starea paginii.
- Panoul Image: afisare, zoom, desenarea si editarea zonelor cu mouse-ul
  (M-009…M-011, M-015, M-029, M-100…M-111), culorile din setari.
- Panoul Zoom (J-*).

### 6b.3 — Panoul Text

- Blocurile, celulele, evidentierea caracterelor nesigure (O-105), editarea,
  navigarea, sincronizarea cu imaginea (O-021), caracterele neimprimabile
  (O-028), fontul (O-029), barele (O-064, O-100, O-101, O-106), dialogul de
  verificare si simbolurile (O-003…O-012, O-109).

### 6b.4 — Image Editor

- L-001…L-004, L-100…L-108: antetul, panoul de unelte, parametrii, grila
  trapezului, histograma, peste uneltele din faza 2.

### 6b.5 — Dialogul Options

- Taburile si setarile X-*, cu regulile X-400…X-423; Y-025.

### 6b.6 — Fluxurile

- Proiect nou, deschidere, salvare; adaugarea imaginilor; recunoasterea pe un
  fir de lucru cu progres si anulare; salvarea in formate (Q-100…Q-102, cu
  modurile de layout active dupa matrice); trimiterea si tiparirea
  (Q-040…Q-050).

---

## Decizii autonome

1. **[DECIZIE AUTONOMA] Traducerile.** Fisiere JSON proprii (`ro.json`,
   `en.json`, cheie → text), nu `.ts/.qm` ale Qt: nu cer uneltele Qt
   (`lrelease`) la construire si se verifica usor in teste (aceleasi chei in
   ambele limbi).
2. **[DECIZIE AUTONOMA] PySide6** e LGPL-3.0: se foloseste ca biblioteca
   dinamica, nemodificata (conditia LGPL), cum prevede stiva din CLAUDE.md §5.
