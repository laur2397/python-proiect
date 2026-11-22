# DocuLens — instructiuni permanente pentru Claude Code

Citesti acest fisier la fiecare sesiune. Nu-l ignora.

---

## 1. Ce construim

O alternativa desktop, **complet offline**, la ABBYY FineReader PDF 16 Corporate: OCR, editor PDF, comparare de documente si automatizare. Python, interfata grafica proprie, fara dependenta de internet si fara dependenta de Microsoft Office.

Numele de lucru al produsului e **DocuLens**.

---

## 2. Specificatia e in `docs/spec/`. Ea decide, nu tu.

**1.501 de cerinte numerotate** (1.487 preluate din original, 14 extinderi proprii in `SPEC_11`). Fiecare are ID stabil, intrari, validari, rezultat si erori.

| Fisier | Ce conține |
|---|---|
| `SPEC_01_lansator_si_pdf_editor.md` | A-001 … I-033 — Lansator si PDF Editor |
| `SPEC_02_ocr_editor.md` | J-001 … Q-065 — OCR Editor |
| `SPEC_03_compare_automatizare_cli.md` | R-001 … Z-030 — comparare, Hot Folder, sarcini, CLI, setari |
| `SPEC_04_schema_bd.sql` | schema bazei de date, SQL executabil |
| `SPEC_05_api_core.py` | contractul nucleului: clase, semnaturi, excepții |
| `SPEC_06_plan_de_testare.md` | corpus de test, praguri masurabile, criterii de acceptanta |
| `SPEC_07_matrice_trasabilitate.csv` | cerinta → test, 1:1 |
| `SPEC_08_raport_divergente.md` | ce s-a corectat si de ce. Citeste-l o data, la inceput |
| `SPEC_09_anexe_referinta.md` | scurtaturi, formate, limbi, fonturi, editii, meniuri, depanare |
| `SPEC_10_interfata_detaliata.md` | interfata la nivel de element: bare, panouri, dialoguri, mesaje |
| `SPEC_11_extinderi.md` | functii cerute de utilizator care nu exista in original, toate `N`: E-500…E-513, unirea documentelor semnate electronic cu semnaturile pastrate valide |

`docs/MASTER_PROMPT.md` e harta de ansamblu: stiva, arhitectura, etapele de lucru.
`docs/prototip_ocr_editor.html` e un prototip clicabil al OCR Editor-ului. Deschide-l in browser cand nu e clar cum arata ceva.
`docs/cercetare/` contine investigatia completa si notele brute din care s-a scris specificatia. E context, nu cerinte: cand contrazice `docs/spec/`, decide `docs/spec/`.

### Coloana `Src` din fiecare cerinta

| Marcaj | Inteles | Ce faci |
|---|---|---|
| `D` | confirmat in documentatia oficiala ABBYY | **implementeaza exact asa.** O abatere e un defect |
| `V` | observat pe ecran in tutoriale | implementeaza asa; nu e confirmat in scris |
| `K` | din baza de cunostinte ABBYY | idem |
| `N` | adaugat de noi, nu exista in original | opțional |
| `X` | diferit deliberat de original | implementeaza versiunea noastra, cu motivul din nota |

---

## 3. Cum lucrezi — obligatoriu

1. **ID-ul cerintei e unitatea de munca.** Pui ID-ul in comentariul de deasupra fiecarei functii si in mesajul de commit.
2. **Nu incepi sa scrii cod inainte sa citesti cerintele vizate.** Daca ti se cere `L-011`, citesti randul `L-011` din `SPEC_02` si cerinta corespunzatoare din `SPEC_05_api_core.py`.
3. **`SPEC_05_api_core.py` e contractul.** Numele de clase, semnaturile si excepțiile se implementeaza asa cum sunt scrise. Nu le redenumesti „ca sa fie mai frumos".
4. **O cerinta nu e terminata fara testul ei.** Un commit care implementeaza `M-008` adauga si `tests/test_m008.py` sau echivalentul.
5. **Rulezi verificarile inainte si dupa fiecare modificare structurala:**
   ```
   python -I tools/verifica_schema.py
   python -I tools/genereaza_matrice_trasabilitate.py
   pytest -q
   ```
6. **Nu modifici fisierele din `docs/spec/`** decat daca ti se cere explicit. Specificatia e intrarea, nu ieșirea.
7. **Lucrezi pe o cerinta sau pe un grup de cerinte, nu pe tot modulul.** Daca ti se cere ceva prea mare, propui o impartire si asteapti.

---

## 4. Arhitectura — nenegociabil

```
app/
  core/            logica. NU importa niciodata din app/gui
    model.py       tipurile din SPEC_05
    errors.py      excepțiile din SPEC_05
    settings.py    SettingsStore
    project.py     OcrProject
    images/        loader.py preprocess.py scanner.py
    layout/        analyzer.py tables.py
    ocr/           engine.py languages.py patterns.py dictionary.py
    pdf/           document.py editor.py forms.py security.py signature.py organize.py
    export/        base.py + un exporter per format
    compare/       engine.py
    automation/    tasks.py hotfolder.py
    fonts.py       FontMatcher
  gui/             PySide6. Nu conține reguli de business
  cli/             main.py. Strat subtire peste core
```

**`core` nu importa `gui`. Niciodata.** Nucleul nu stie ca exista o interfata. Progresul se raporteaza prin callback, erorile prin excepții. Niciun dialog, niciun `print`, niciun `input` in `core`.

---

## 5. Stiva tehnica

| Nevoie | Ce folosim |
|---|---|
| Interfata | PySide6 (Qt 6) |
| Randare PDF | pypdfium2 |
| Manipulare PDF | pikepdf |
| OCR | Tesseract 5 prin pytesseract; tabelele cu analizorul propriu (`layout/tables.py`). PaddleOCR nu se foloseste (decizia din `docs/plan/faza_4_pasi.md`) |
| Imagini | scikit-image, SciPy, NumPy, Pillow (OpenCV nu e necesar) |
| Coduri de bare | zxing-cpp |
| Semnaturi PDF | pyHanko |
| Formulare, JavaScript | quickjs |
| Office | python-docx, openpyxl, python-pptx; ODT, RTF, EPUB, FB2, DjVu scrise de noi (`ebooklib` e AGPL) |
| Planificare | APScheduler, watchdog |
| Baza de date | SQLite (`sqlite3` din standard library) |
| Teste | pytest, pytest-qt |
| Impachetare | Nuitka sau PyInstaller, plus Inno Setup pe Windows |

**PyMuPDF e AGPL.** Nu il folosim legat in proces. Daca e nevoie de el, ruleaza ca proces separat si se documenteaza.

---

## 6. Reguli de produs care nu se incalca

1. **Offline total.** Nicio cerere de retea in functionarea normala. `Y-001` e criteriu de livrare: toata suita de integrare trebuie sa treaca cu interfata de retea dezactivata.
2. **Fara activare, fara inregistrare, fara telemetrie, fara verificare de actualizari.**
3. **Fara dependenta de Microsoft Office.** Citim si scriem formatele editabile cu biblioteci proprii.
4. **Diacriticele romanesti conteaza.** Produsul trebuie sa trateze corect si varianta cu virgula (ș, ț) si cea cu sedila (ş, ţ). Pragul din `SPEC_06`: maximum 2 confuzii la 1.000 de caractere.
5. **Niciun text afisabil in cod.** Toate textele de interfata in fisiere de traducere. Romana si engleza obligatorii.
6. **Nu copiem identitatea vizuala ABBYY.** Preluam structura interfetei, nu paleta, nu iconurile, nu numele. Culorile zonelor sunt setari, nu valori in cod (`M-100`, `X-165`).
7. **Redactarea trebuie verificata.** Dupa fiecare redactare se extrage textul si se verifica absenta. Daca textul mai apare, operatia se anuleaza (`G-021`).

---

## 7. Cele mai usor de ratat

Cerintele de prioritate 1 sunt 142 (138 din `SPEC_06`, plus 4 din `SPEC_11`). Acestea sunt cele care au fost greșite in versiunile anterioare ale specificatiei si care arata corect la o citire superficiala:

- **Modul de layout limiteaza formatele de export** (`Q-001`…`Q-006`). `Flexible layout` permite numai HTML. 90 de combinatii (5 moduri × 18 formate), exact 27 valide (6+3+8+9+1).
- **Linia de comanda are doua executabile, cu doua sintaxe.** Conversia cu spatii, compararea cu doua puncte. Nu exista `/format`, `/layout`, `/pages`, `/mrc`, `/split`, `/threads`, `/json` (`U-001`, `U-012`, `U-020`).
- **Hot Folder nu e serviciu de sistem** (`S-005`). Cere utilizator conectat.
- **PDF-urile cautabile si cele doar-imagine folosesc intotdeauna OCR**, indiferent de setarea de mod (`I-033`, `N-009`).
- **Evenimentele de formular**: `Click`, `Drop`, `Mouse Over`, `Mouse Out`, `Focus`, `Focus Out` (`H-040`).
- **Linkurile cer prefix**: `mailto:` si `file://` (`F-027`).
- **La impartirea unui PDF, semnele de carte se pierd** si atasamentele merg intr-un folder `Attachments` (`E-031`).
- **O modificare de zona invalideaza textul paginii** (`N-026`).
- **Fontul la editare**: numele in paranteze patrate = incorporat dar neinstalat (`F-005`).
- **`Delete Watermarks` sterge toate filigranele** (`F-050`).
- **Unirea fisierelor semnate nu modifica niciodata originalele** (`E-501`, `E-503`, `E-509`). Unirea clasica distruge semnaturile; se avertizeaza si se propune `E-500`.

---

## 8. Ordinea de construit

Nu sari peste pasi. Fiecare pas se termina cu teste care trec.

| Faza | Ce | Cerinte |
|---|---|---|
| 0 | schelet de proiect, baza de date, setari, jurnal | `SPEC_04`, `X-*`, `Y-022`…`Y-026` |
| 1 | incarcare de imagini si PDF, randare, proiect OCR | `J-*`, `K-001`, `B-001` |
| 2 | preprocesare: cele 14 unelte | `L-010`…`L-023`, `L-030`…`L-035`, `L-109` |
| 3 | zone: desenare, tipuri, proprietati, sabloane | `M-*` |
| 4 | recunoastere: motor, limbi, incredere | `N-*`, `P-001`…`P-009` |
| 4b | limbi proprii, dictionare, sabloane de caractere, expresii regulate | `P-020`…`P-128`, `Z-020`…`Z-030` |
| 5 | panoul de text, verificare, stiluri | `O-*` |
| 6 | export: PDF cautabil, DOCX, XLSX, si matricea de layout | `Q-*`, `I-008`…`I-016`, `I-030`…`I-033` |
| 6b | **interfata OCR Editor**: fereastra principala, panouri, Image Editor, zone cu mouse-ul, dialogul Options | partile de interfata din `J-*`, `L-001`…`L-004`, `L-100`…`L-108`, `M-*`, `O-*`, `X-*`, `Y-025`; lista exacta in `docs/plan/` la „faza GUI” |
| 6c | **Lansatorul**: conversie rapida, combinarea fisierelor intr-un PDF | `A-*` |
| 6d | scanare si fotografii de documente | `K-002`…`K-017` |
| 7 | PDF Editor: vizualizare, cautare, copiere, comentarii, salvare, tiparire | `B-*`, `C-*`, `D-*`, `I-001`…`I-007`, `I-017`…`I-024` |
| 8 | pagini: organizare, impartire, inserare | `E-*` |
| 9 | editare de continut, antete, filigrane, semne de carte, stampile de data | `F-*`, `Z-001`…`Z-013` |
| 10 | securitate, redactare, semnaturi | `G-*` |
| 11 | formulare | `H-*` |
| 12 | comparare | `R-*` |
| 13 | automatizare: sarcini, Hot Folder | `S-*`, `T-*` |
| 14 | linia de comanda | `U-*` |
| 15 | Screenshot Reader, integrari | `V-*`, `W-*` |
| 16 | impachetare, instalare, accesibilitate | `Y-*` |

**Interfata grafica.** Fazele 0–6 construiesc nucleul (`app/core`); fereastra OCR Editor-ului se construieste in faza 6b, peste nucleul gata. Din faza 7 inainte, fiecare faza livreaza nucleul **si** fereastra ei: o faza nu e terminata pana nu se poate folosi din interfata.

**Nicio cerinta fara faza.** `tools/verifica_faze.py` citeste tabelul de mai sus si pica daca vreun ID din `SPEC_07` nu e acoperit. Ruleaza in CI. Daca muti cerinte intre faze, actualizezi tabelul.

**Prioritatea reala pentru utilizator:** fazele 0–6d dau un produs folosibil pe dosare de finantare — scanare, OCR romanesc, export in Word si PDF cautabil, cu fereastra lui si cu combinarea fisierelor. Restul poate aștepta.

---

## 9. Ce nu faci

- Nu inventezi functii care nu sunt in specificatie. Daca crezi ca lipseste ceva, spui, nu adaugi.
- Nu scrii cod care „va fi completat mai tarziu" fara sa marchezi explicit ce lipseste.
- Nu raportezi o cerinta ca implementata daca testul ei nu trece.
- Nu schimbi schema bazei de date fara sa rulezi `tools/verifica_schema.py`.
- Nu adaugi dependente noi fara sa spui de ce si ce licenta au.
- Nu pui chei, parole sau token-uri in cod sau in fisiere urmarite de git.
- Nu refaci interfata ABBYY pixel cu pixel. Structura, da. Aspectul, nu.

---

## 10. Cand ceva nu e clar

Ordinea in care cauti raspunsul:

1. cerinta cu ID-ul respectiv, in `SPEC_01`…`SPEC_03`
2. `SPEC_05_api_core.py`, pentru semnatura si excepții
3. `SPEC_09_anexe_referinta.md`, pentru tabele si depanare
4. `SPEC_10_interfata_detaliata.md`, pentru cum arata
5. `SPEC_08_raport_divergente.md`, pentru ce s-a mai greșit deja
6. `docs/prototip_ocr_editor.html` — prototipul clicabil
7. `docs/cercetare/` — investigatia si notele brute, pentru context

Daca tot nu e clar, **intrebi**. Nu ghicesti si nu umpli golul cu o presupunere nemarcata.

---

## 11. Modul autonom — cand utilizatorul spune „continua singur”

In modul autonom lucrezi pas dupa pas, fara sa astepti confirmare intre pasi. Regulile din sectiunile 1–10 raman valabile; se schimba doar punctul 7 din sectiunea 3 si „asteapta confirmarea” din planuri.

**Sursa de adevar pentru unde ai ramas: `docs/plan/STARE.md`.** Il citesti la inceputul sesiunii si dupa fiecare compactare a contextului. Il actualizezi la sfarsitul fiecarui pas, in acelasi commit.

**Ciclul pentru fiecare pas:**
1. Iei urmatorul pas din `STARE.md`. La o faza noua, scrii intai `docs/plan/faza_N_pasi.md` (impartirea in pasi, ce ramane pentru interfata, deciziile) si il comiti.
2. Citesti cerintele pasului (sectiunea 3, punctul 2).
3. Implementezi, cu testele lor.
4. Rulezi toate verificarile: `verifica_schema.py`, `genereaza_matrice_trasabilitate.py`, `verifica_faze.py`, `ruff check app tools`, `pytest -q`. Toate trebuie sa treaca.
5. Commit cu ID-urile in mesaj, apoi push.
6. Daca `gh` e disponibil, astepti CI-ul. Daca pica, repari in pasul urmator, inainte de orice altceva. **Daca CI-ul nu porneste deloc** (cont, plata, minute), te opresti si scrii in `STARE.md`: fara CI nu exista verificare pe Windows.
7. Actualizezi `STARE.md` si treci la urmatorul pas.

**Deciziile pe care in mod normal le-ai fi intrebat:** alegi varianta cea mai apropiata de specificatie si de cerintele `D`, o scrii in planul fazei cu marcajul `[DECIZIE AUTONOMA]` si cu motivul, si mergi mai departe. Utilizatorul le revede la final.

**Te opresti si scrii in `STARE.md` de ce, numai daca:**
- acelasi test pica dupa doua incercari de reparare;
- doua cerinte `D` se contrazic sau o cerinta `D` nu se poate implementa cu stiva din sectiunea 5;
- ar trebui modificat ceva in `docs/spec/`;
- e nevoie de o dependenta noua cu licenta GPL sau AGPL, ori de un serviciu online;
- e nevoie de ceva ce numai utilizatorul are: documente reale, certificate, un scanner, acces la un portal;
- ai terminat **faza 6d**. Acolo e prima versiune folosibila, iar utilizatorul o verifica inainte de faza 7.

**Ce nu faci in modul autonom:** nu sari peste teste ca sa mergi mai repede, nu marchezi o cerinta ca facuta fara test, nu lasi CI-ul rosu ca sa treci la pasul urmator, nu stergi teste care pica.
