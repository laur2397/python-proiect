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

**Status:** 6b.1…6b.5, 6b.6a gata; urmeaza 6b.6b.

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
- **6b.3b — gata:** `dialogs.py`: `Verify Text` nemodal, `Ctrl+F7` (O-003…O-007,
  O-009 ca semnal pana la dialogul Options din 6b.5, O-010 CJK, O-109),
  `Mark Text as Verified`, `Ctrl+T` (O-011), `More Symbols...` cu `Subset` si
  `Character code` (O-008), dialogul `Hyperlink` (O-053…O-056); in panoul Text:
  tooltipul, `Ctrl`+clic si meniul contextual al legaturilor (O-050…O-052),
  `Add to Dictionary` din meniu (O-006), bara `Text Properties` pe trei coloane
  (O-106), descrierea selectiei mixte in combo-ul de stil (O-102).
  Teste: `tests/test_gui_dialogs.py`.

**INCOMPLET, marcat in cod:** `Style Editor`, spatierea (O-101), majusculele mici,
toate majusculele, culoarea de fundal si scalarea (O-106) nu au operatii in
nucleu si nici coloane in SPEC_04; butoanele lor sunt gri. `Options...` din
dialogul de verificare (O-009) se leaga de dialogul Options in 6b.5.

### 6b.4 — Image Editor

- L-001…L-004, L-100…L-108: antetul, panoul de unelte, parametrii, grila
  trapezului, histograma, peste uneltele din faza 2.

**Gata:** `image_editor.py`, in locul panoului Image (centru cu doua fete):
deschiderea din butonul panoului, din `Edit > Editeaza imaginile paginilor...`
si cu `Ctrl+I` (L-001), iesirea cu modificarile pastrate (L-002), `Selection`
in fiecare unealta (L-003), bifa paginii urmatoare (L-004, L-104), antetul
(L-100), cele 14 unelte in ordine, deschise inline (L-101, L-102), `Crop` cu
hartia, marimea, decalajul si unitatea, plus selectia trasa cu mouse-ul
(L-103, L-106), fundalul gri inchis (L-105), grila trapezului cu colturi
trase si `Correct` (L-107), histograma si cursoarele `Levels` (L-108), radiera
trasa cu mouse-ul. Teste: `tests/test_gui_image_editor.py`.
**INCOMPLET, marcat in cod:** operatiile ruleaza pe firul interfetei; firul de
lucru cu progres si anulare vine in 6b.6.

### 6b.5 — Dialogul Options

- Taburile si setarile X-*, cu regulile X-400…X-423; Y-025.

**Gata:** `options_dialog.py`: modal ~650x620 (X-400), taburi cu iconuri si
eticheta dedesubt, in ordinea X-402 (X-401); 129 din cele 131 de setari au
control generat din tipul lor (bool, enum, numar, culoare, cale, text, liste de
limbi), validat de nucleu; grupurile si dependentele X-403…X-423 (pornirea,
dispozitivul, interfata de scanare, linkurile de ajutor, preprocesarea pe trei
coloane cu `*` si comutator, cele trei moduri care pastreaza bifele, cele doua
`Also use built-in patterns`, incarcarea/salvarea sabloanelor .fbtx, lista
formatelor, PDF/UA forteaza tagurile, versiunea PDF/A gri). `Options...` din
dialogul de verificare deschide tabul `Zone si text` (O-009).
`error_dialog.py`: dialogul de eroare neasteptata cu urma stivei copiabila si
salvarea raportului; aplicatia continua (Y-025). Teste: `tests/test_gui_options.py`.
**INCOMPLET, marcat in cod:** `Select Device...` (X-404, X-407, faza 6d), mesajul
de vizualizator implicit si `Make Default...` (X-406, integrarea cu sistemul,
faza 16), `Pattern Editor...` si `Select Fonts...` (X-417, X-418: fara dialog;
`ocr.export_fonts` nu are inca control). Numele limbilor sunt traduse pentru
35 de limbi; celelalte apar prin cod.

### 6b.6 — Fluxurile

- Proiect nou, deschidere, salvare; adaugarea imaginilor; recunoasterea pe un
  fir de lucru cu progres si anulare; salvarea in formate (Q-100…Q-102, cu
  modurile de layout active dupa matrice); trimiterea si tiparirea
  (Q-040…Q-050).

**Impartit in doua (decizia 12):**

- **6b.6a — gata:** proiect nou, deschidere, salvare, salvare ca, inchidere, cu
  intrebarea pentru modificarile nesalvate (si la inchiderea ferestrei);
  adaugarea imaginilor si PDF-urilor (parola ceruta in dialog, fisierele
  refuzate raportate); recunoasterea tuturor paginilor sau a paginii curente,
  analiza, cu dialog de progres si `Cancel` (N-027, N-028; decizia 11);
  combo-ul de limbi din bara (J-401) cu limbile recente si `Mai multe limbi...`;
  titlul cu numarul proiectului fara titlu (J-030). Teste: `tests/test_gui_flows.py`.
- **6b.6b — urmeaza:** dialogul de salvare (Q-100…Q-102) cu formatele active dupa
  modul de layout, avertismentele (Q-051, Q-104), trimiterea, e-mailul,
  Kindle, clipboard, tiparirea (Q-040…Q-050), salvarea imaginilor paginilor.

**INCOMPLET, marcat in cod:** `Sarcina noua` (Lansatorul, faza 6c), `Scaneaza`
(faza 6d); pornirea cu ultimul proiect (X-001 `ocr_last_project`) cere lista
documentelor recente (A-052), care vine cu Lansatorul in 6c.

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
8. **[DECIZIE AUTONOMA] Cursorul de iesire din `Levels` (L-108)** este punctul
   alb de iesire (`out_white`); punctul negru de iesire ramane 0. SPEC_10 vorbeste
   de un singur cursor de iesire.
9. **[DECIZIE AUTONOMA] Bifa `Show next page...` (L-004)** se tine cat e deschis
   editorul; nu are setare in SPEC_04/X-*, deci nu se salveaza.

10. **[DECIZIE AUTONOMA] Unde se scriu setarile din Options.** Cele ale
    aplicatiei (`general.*`, `ui.*`, `app.*`, `ocr.max_threads`) in setarile
    globale; restul in setarile proiectului, care se salveaza cu proiectul (ca
    in original, unde optiunile tin de proiectul OCR). Fara proiect, toate in
    cele globale.
11. **[DECIZIE AUTONOMA] Operatiile lungi ruleaza pe firul interfetei**, cu
    dialog de progres care proceseaza evenimentele la fiecare raport si `Cancel`
    verificat intre pagini. Conexiunile SQLite ale proiectului sunt legate de
    firul care le-a deschis; OCR-ul are deja fondul lui de fire (N-027). Un fir
    separat ar cere conexiuni per fir in nucleu; se poate face mai tarziu, fara
    sa schimbe interfata.
12. **[DECIZIE AUTONOMA] 6b.6 in doi pasi**: 6b.6a proiectul si recunoasterea,
    6b.6b salvarea in formate, trimiterea si tiparirea.
