# Faza 11 — Formulare

**Cerinte:** `H-001`…`H-058` (SPEC_01), `H-100`…`H-110` (SPEC_10).
**Status:** 11.1 si 11.2 gata; urmeaza 11.3.

Contractul e in SPEC_05: `FormFieldData`, `FormFieldType`, `FormEditor` si erorile
`DuplicateFieldNameError`, `InvalidFieldNameError`, `SignedFieldCopyError`,
`OrphanRadioButtonError`. ID-urile din docstring-urile SPEC_05 sunt decalate fata
de SPEC_01 (ca la faza 10); in cod se pun cele din SPEC_01.

Motorul JavaScript (B-038, H-006, H-058) e **QuickJS** (MIT), ales de utilizator
la inceputul fazei.

---

## Pasii

### 11.1 — Citirea si completarea formularului (nucleu)

- `FormEditor` peste `PdfDocument`: campurile din `/AcroForm` ca `FormFieldData`
  (toate cele sapte tipuri), detectia formularului (H-001).
- Completarea: `set_value` cu `Read-Only` si `Max Number of Symbols`, data redusa
  la formatul din `View` (H-030), bife, butoane radio, liste cu elemente proprii
  (H-031, H-036); aspectul campului regenerat la fiecare valoare, cu diacritice.
- `Reset Form` (H-005): golire, elementul implicit al listei revine.
- `Load Form Data from File...` (FDF, XFDF; campurile necunoscute ignorate si
  raportate, H-003), `Save Form Data to File...` (FDF, XFDF, HTML, H-004).
- Campurile obligatorii necompletate, numai pentru avertisment (H-022, H-023);
  `Save As > PDF` pastreaza campurile (H-024).
- **Gata.** `app/core/pdf/forms.py` (`FormEditor`: `fields`, `has_fields`,
  `set_value`, `value`, `reset`, `incomplete_required`, `load_data`, `save_data`,
  `format_date`), `FormFieldData` in `model.py`; campurile se deseneaza acum in
  PDF Editor (`new_pdfium` in `document.py`, decizia 5); testele in
  `tests/test_pdf_forms.py`.

### 11.2 — Crearea si editarea campurilor (nucleu)

- Validarea numelui (H-030), numele generate (H-109), crearea celor sapte tipuri
  cu proprietatile din H-030…H-036 si aspectul lor, unitatile (cm, in, pt).
- Modificarea proprietatilor, stergerea (H-021), copierea fara nume si refuzul
  pentru semnatura completata (H-015), copia legata si dezlegarea la redenumire
  (H-016), mutarea numai in pagina (H-017), ghidajele (H-018), redimensionarea cu
  inaltime nenula (H-020), grupurile radio cu minimum doua butoane (H-013),
  `Set as Default Style`.
- **Gata.** `FormEditor`: `validate_field_name`, `next_name`, `create_field`,
  `update_field`, `default_on`, `delete_fields`, `delete_widgets`, `copy_field`,
  `create_linked_copy`, `move_field`, `resize_field`, `alignment_guides`,
  `validate_document`; `style_of`/`with_style`, `to_units`/`from_units`; testele
  in `tests/test_pdf_form_editing.py`.

### 11.3 — Actiuni si JavaScript (nucleu)

- Actiunile butoanelor si campurilor (H-034, H-040…H-058): cele sase evenimente,
  scrise ca actiuni PDF standard (`/AA`), citite inapoi in `FormFieldData.actions`.
- Executia actiunilor in PDF Editor printr-un dispecer care intoarce comanda
  pentru fereastra (navigare, vizualizare, panouri, fisier, link, trimitere,
  resetare, salvare, tiparire, inchidere, cautare, proprietati, scanare).
- Motorul QuickJS: un subset al obiectelor Acrobat (`this.getField`, `event`,
  `app.alert`, `AFNumber_*`, `AFDate_*`, `AFSpecial_*`, `AFPercent_*`), cu
  verificarile de format la completare (H-006), `Run JavaScript` (H-058),
  limita de 2 secunde (B-041) si regula de activare (B-038…B-040).

### 11.4 — Interfata: completarea

- Banda galbena de detectie cu `Highlight fields` si `X` (H-100, H-002); campurile
  completate direct pe pagina (text, liste, bife, butoane radio, butoane cu
  actiuni); meniul de date de formular (H-003…H-005); avertismentul pentru
  campurile obligatorii la salvare, trimitere, tiparire (H-023).

### 11.5 — Interfata: `Form Editor`

- Tabul `Form Editor` (H-010), care dezactiveaza uneltele principale; uneltele
  pentru cele sapte tipuri, cu cursorul `+` (H-103); randarea campurilor (H-101,
  H-102), `Show Field Names` (H-011), obligatoriile cu rosu (H-022).
- Selectia, mutarea cu ghidaje mov si `Ctrl` (H-017, H-018, H-110), manerele,
  `Delete`, `Ctrl+C`/`Ctrl+V`, `Create Linked Copy`, meniul contextual.
- Dialogul de proprietati pe tipuri (H-030…H-036, H-104…H-106), dialogul de
  actiune (H-041, H-042, H-107, H-108).

---

## Decizii

1. [DECIZIE AUTONOMA] **Formularul se pastreaza in PDF** (`/AcroForm`, prin
   pikepdf), ca semnele de carte si linkurile din fazele 7–9. Tabelele
   `form_field*` din SPEC_04 apartin proiectului OCR si nu se folosesc in PDF
   Editor.
2. [DECIZIE AUTONOMA] **Aspectul campurilor** (`/AP`) il scrie DocuLens la fiecare
   modificare, cu fontul de sistem incorporat (subset, cu ș si ț), ca orice
   cititor sa arate valoarea; `/DA` foloseste Helvetica, ca alte programe sa
   poata regenera aspectul.
3. [DECIZIE AUTONOMA] **QuickJS ruleaza fara apeluri inapoi in Python**: limita
   de timp a motorului nu se poate combina cu functii Python. Valorile
   campurilor intra in script ca date JSON; schimbarile, mesajele si `event.rc`
   ies tot ca JSON si le aplica nucleul. Limita de 2 secunde (B-041) e cea a
   motorului.
4. [DECIZIE AUTONOMA] **`FormFieldData.value`** (contractul SPEC_05 nu are campuri
   separate) poarta, la creare si modificare: textul butonului (`Button Text`,
   H-034) pentru butoane si `Enabled by Default` pentru bife si butoane radio
   (H-032, H-033), adica valoarea implicita (`/DV`). La citire, bifele si
   butoanele radio au in `value` starea curenta; starea implicita o da
   `FormEditor.default_on`.
5. [DECIZIE AUTONOMA] **Randarea campurilor:** PDFium deseneaza widgeturile numai
   cu mediul de formular pornit, deci fiecare document PDFium deschis de
   `PdfDocument` porneste `init_forms()` (`new_pdfium`). Pana acum campurile
   altor programe nu se vedeau in PDF Editor.
6. [DECIZIE AUTONOMA] **Numele campurilor cu punct** (`persoana.nume`) fac arbore
   in `/AcroForm`, ca in standard: `persoana` devine parinte si nu mai poate fi
   nume de camp. Copiile legate (H-016) sunt widgeturi ale aceluiasi camp;
   redenumirea unei copii o scoate din camp, cu valoarea si proprietatile lui.
7. [DECIZIE AUTONOMA] **Numele generate** (H-109) sunt in engleza, ca in original
   (`TextField 1`, `Checkbox 1`, `Radio Button 1`, `Drop-down List 1`,
   `List Box 1`, `Button 1`, `Signature 1`, grupurile `Radio Group 1`): sunt date
   scrise in PDF, nu text de interfata. Datele de formular (H-003) se citesc si din
   campuri doar-citire; valorile care nu se potrivesc (element lipsa din lista,
   text prea lung) se raporteaza ca ignorate.

## INCOMPLET

- **Numele lunilor in formatele de data** (`mmm`, `mmmm`, H-030): formatele din
  `View` sunt numerice (`dd.mm.yyyy`, `mm/dd/yy`, `yyyy-mm-dd`...).
