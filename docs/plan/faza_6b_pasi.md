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

**Status:** 6b.1, 6b.2, 6b.3a gata; urmeaza 6b.3b.

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

**Gata:** `app/gui/i18n` (ro/en, aceleasi chei, verificat de test), `MainWindow`
cu titlul J-400, bara in ordinea J-401, butonul de salvare cu formatele active
dupa modul de layout (Q-001), panourile mutabile stanga/dreapta (J-409),
indicatorul de avertismente (J-419), `Verify` gri fara cuvinte nesigure (J-420),
limba interfetei din setarea `ui.language` (X-140). Teste: `tests/test_gui_shell.py`.
**INCOMPLET, marcat in cod:** continutul panourilor (miniaturi, imaginea cu zone,
textul formatat) vine in 6b.2/6b.3; starea salvata a panourilor in 6b.6.

### 6b.2 — Paginile, imaginea, zonele

- Panoul Pages: miniaturi, selectie, ordine, stergere, starea paginii.
- Panoul Image: afisare, zoom, desenarea si editarea zonelor cu mouse-ul
  (M-009…M-011, M-015, M-029, M-100…M-111), culorile din setari.
- Panoul Zoom (J-*).

**Gata:** `pages_panel.py` (miniaturi cu insigna de stare si avertisment, tooltip,
stergere, rotiri; J-403…J-408), `image_panel.py` (toolbarul pe doua randuri,
unealta activa, banda PDF cu strat de text si modul X-060, proprietatile pe
doua taburi cu sageti M-029, zoom si potriviri, panoul Zoom independent;
J-410…J-418), `zones.py` (modificatorii M-009, Tab M-010, manere M-011/M-104,
orice directie M-106, Reorder M-111, culorile din setari M-100/M-101).
Desenarea, mutarea, redimensionarea, selectia cu Ctrl, adaugarea/taierea de
parti si schimbarea tipului trec prin `AreaEditor`; erorile lui se arata
traduse din cod (`error.*`, Y-013). Teste: `tests/test_gui_image.py`.
**INCOMPLET, marcat in cod:** `Edit Image` (6b.4); `Save Page`, `Recognize Page`,
`Analyze Page`, salvarea paginilor (6b.6); „Opened by” din tooltip (J-407) cere
lucrul in grup, care nu exista in nucleu; `copy` din M-108 nu are operatie in
nucleu.

### 6b.3 — Panoul Text

- Blocurile, celulele, evidentierea caracterelor nesigure (O-105), editarea,
  navigarea, sincronizarea cu imaginea (O-021), caracterele neimprimabile
  (O-028), fontul (O-029), barele (O-064, O-100, O-101, O-106), dialogul de
  verificare si simbolurile (O-003…O-012, O-109).

**Impartit in doua (decizia 5):**

- **6b.3a — gata:** `text_panel.py`: textul paginii editabil, cuvintele schimbate
  trec prin `TextEditor.set_word_text` (O-020); blocurile in cadre punctate
  (O-104); caracterele nesigure pe culoarea din setari, pe caracter (O-105:
  `word.char_confidences` se salveaza acum in proiect, coloana din SPEC_04);
  sincronizarea text ↔ imagine ↔ Zoom (O-021); neimprimabilele (O-028) si
  fontul textului simplu (O-029) din setari; toolbarul pe doua randuri (O-100,
  O-101) cu B/I/U, exponent, indice, alinierile si listele (nou in nucleu:
  `TextEditor.set_paragraph_format`, coloanele `alignment`, `list_level`),
  stilurile, redactarea; cautarea si inlocuirea (O-024, O-025); uneltele de
  tabel ascunse, din `View > Unelte de tabel` (O-064); zoom propriu (J-417).
  Teste: `tests/test_gui_text.py`.
- **6b.3b — urmeaza:** dialogul `Verify Text` (O-003…O-012, O-109), simbolurile
  (O-008), legaturile (O-050…O-056 in interfata), bara `Text Properties`
  (O-106), descrierea stilului la selectie mixta (O-102).

**INCOMPLET, marcat in cod:** `Style Editor` si spatierea (O-101) nu au operatii
in nucleu; schema nu are coloane pentru spatiere.

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
3. **[DECIZIE AUTONOMA] Bara de jos a panoului Image (J-416).** Cele „patru
   moduri de potrivire” sunt implementate ca trei potriviri (latime, inaltime,
   pagina) plus combo-ul de zoom; „lista” din J-416 nu e descrisa mai departe in
   specificatie si e tratata ca alegerea din combo.
4. **[DECIZIE AUTONOMA] Numarul zonei (M-103)** sta in colțul din stanga-sus
   (ca in versiunea 16) si nu se muta.
5. **[DECIZIE AUTONOMA] 6b.3 in doi pasi.** Panoul Text si dialogurile lui sunt
   prea mari pentru un singur pas verificabil: 6b.3a panoul, 6b.3b dialogurile
   (verificare, simboluri, legaturi) si bara de proprietati.
6. **[DECIZIE AUTONOMA] Liniile punctate dintre blocuri (O-104)** se deseneaza
   ca un cadru cu chenar punctat in jurul fiecarui bloc (Qt nu are linie
   orizontala punctata in documentele de text).
7. **[DECIZIE AUTONOMA] Dimensiunea panourilor.** La prima afisare, imaginea ia
   partea cea mai mare din fereastra; Pages ramane ingust (J-403), Text si Zoom
   in dreapta. Fara asta, docurile luau aproape toata latimea.
