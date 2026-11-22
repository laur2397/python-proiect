# Faza 10 — Securitate, redactare, semnaturi

**Cerinte:** `G-001`…`G-055` (SPEC_01), `G-100`…`G-111` (SPEC_10).
**Status:** in lucru.

Contractul e in SPEC_05: `SecurityOptions`, `SecurityService`, `SignatureOptions`,
`SignatureService`. ID-urile din docstring-urile SPEC_05 sunt decalate fata de
SPEC_01; in cod se pun cele din SPEC_01. Redactarea dupa zone si dupa cuvinte,
cu verificarea G-021, exista din faza 7 (`app/core/pdf/security.py`).

---

## Pasii

### 10.1 — Parole, permisiuni, stergerea datelor (nucleu)

- `Password Security`: parola de deschidere, parola de permisiuni diferita de ea,
  care deschide si documentul (G-002…G-005), tiparirea, editarea, copierea,
  cititoarele de ecran (G-006…G-009), AES-128/256, metadatele necriptate la
  cerere (G-010, G-011); scoaterea protectiei.
- `Delete Objects and Data` (G-022…G-024, G-111): comentarii, linkuri si
  actiuni si scripturi si formulare, semne de carte, atasamente, metadate; textul
  si obiectele ascunse = conversia in PDF imagine, cu avertisment.
- Culorile redactarii, configurabile (G-020, G-100, G-101).
- **Gata.** `app/core/pdf/security.py` (`SecurityOptions`, `apply`,
  `remove_protection`, `delete_objects_and_data`), `cleanup.py`, protectia scrisa
  la salvare in `document.py`; testele in `tests/test_pdf_security.py`.

### 10.2 — Semnaturile digitale (nucleu)

- Certificatele (fisiere PKCS#12, cu calea si amprenta pastrate), detaliile lor
  (G-031, G-032); semnarea cu motiv, locatie, contact, aspect (G-033…G-039,
  G-104…G-107), algoritmi (G-045), semnaturi multiple (G-044), marca temporala
  (G-037); validarea la deschidere, cu certificatul expirat raportat separat
  (G-041), proprietatile (G-042), stergerea (G-043).
- Teste: `tests/test_pdf_signing.py`.

### 10.3 — Semnaturile text si imagine (nucleu)

- Biblioteca `saved_signature` (SPEC_04): semnatura text cu stil, din imagine
  (fisier sau clipboard, fundal transparent), editare, stergere (G-050…G-055);
  plasarea pe pagina, cu mutare, rotire, redimensionare (G-052).
- Teste: `tests/test_pdf_signature_images.py`.

### 10.4 — Interfata

- Tabul `Security`: dialogul de parole (cu confirmarea G-012), unealta de redactare
  cu bara de culori (G-100…G-103), `Delete Objects and Data` (G-111), butonul
  `Signature ▾` (G-110), dialogul de semnare cu previzualizare (G-105), panoul
  `Digital Signatures` cu proprietati si stergere (G-108), `Manage Signatures`.
- Teste: `tests/test_gui_pdf_security.py`.

---

## Decizii

1. [DECIZIE AUTONOMA] **Protectia** (G-001…G-012) se retine in document si se scrie
   la urmatoarea salvare (`Save` peste fisier sau `Save As`, G-012). Parola de
   permisiuni e parola de proprietar, deci deschide si documentul (G-005); fara
   parola de permisiuni nu exista restrictii. AES-128 = revizia 4, AES-256 =
   revizia 6; RC4 nu se scrie (G-010).
2. [DECIZIE AUTONOMA] **Scoaterea protectiei** cere parola de permisiuni (sau
   parola de proprietar a fisierului); parola de deschidere singura nu ajunge.
3. [DECIZIE AUTONOMA] **`Hidden text and objects`** (G-024) inlocuieste fiecare
   pagina cu imaginea ei la 200 dpi, asa cum se vede (cu rotatia aplicata);
   adnotarile raman, pentru ca au bifa lor in dialog (G-111).
4. [DECIZIE AUTONOMA] **Culorile redactarii** (G-100) sunt o setare
   (`pdf_editor.redaction_colors`, implicit cele opt din interfata originala), iar
   culoarea implicita (G-101) e negru (`pdf_editor.redaction_color`).

## INCOMPLET

(se completeaza pe parcurs)
