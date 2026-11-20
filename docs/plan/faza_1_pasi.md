# Faza 1 — impartirea in pasi, inainte de cod

Document de lucru pentru confirmare. Faza 1 din CLAUDE.md §8: incarcare de
imagini si PDF, randare, proiect OCR (`J-*`, `K-001`, `B-001`).

Surse citite: SPEC_02 J.1…J.4 (J-001…J-085), J-300…J-420, K-001, SPEC_01
B-001, SPEC_05 sectiunile 5 (`LoadedImage`, `ImageLoader`) si 9 (`OcrProject`).

Regula ramane: un pas = o sesiune = un commit cu CI verde.

**Status:** impartirea si cele 4 propuneri au fost confirmate de utilizator
pe 2026-11-20. Pasii 1a si 1b sunt implementati.

---

## Ce intra in nucleu si ce ramane pentru interfata

Din cele 78 de cerinte J-*, aproape jumatate sunt de interfata. Ele raman
pentru faza GUI:

| Cerinte | De ce raman pentru GUI |
|---|---|
| J-001…J-017 | panouri, bare, zoom, bara de proprietati |
| J-300…J-420 | meniuri, toolbaruri, miniaturi, titlul ferestrei |
| J-054, J-064, J-067 | tragerea cu mouse-ul; nucleul da operatia (adaugare, reordonare) |
| J-059, J-063, J-065 | dialogurile; nucleul da operatia |
| J-068, J-069 | navigarea intre pagini |

Raman pentru alte faze:

- J-033, J-053 (Explorer) → faza 15;
- J-080…J-085 (dictionare si limbi partajate) → fazele 4–5;
- J-051 (prelucrarea automata la adaugare): in faza 1 parametrul exista,
  dar nu face nimic pana la faza 2, si e marcat ca atare.

---

## Pasii

### 1a — Incarcarea imaginilor raster

`app/core/images/loader.py`: `ImageLoader` si `LoadedImage` din SPEC_05.

- Formate: JPEG, PNG, TIFF (si multipagina), BMP, GIF, PCX, DCX, JPEG2000.
- Metadate: latime, inaltime, dpi, mod de culoare, numarul de pagini.
- `read_page_count`, `render_thumbnail` (PNG), interval de pagini.
- Erori: `UnsupportedFormatError`, `FileCorruptError`.
- Cerinte: K-001 (partea de nucleu), A-012, J-050 (partea de incarcare).
- **Dependenta noua: Pillow** — licenta HPND (de tip MIT).
- Teste: imagini generate in test, fara fisiere mari in git.

### 1b — PDF: incarcare si randare

Tot in `ImageLoader`, plus o functie de randare a unei pagini la o rezolutie data.

- Paginile PDF devin imagini la rezolutia ceruta.
- Parola prin `PasswordCallback` (J-052, A-011). Limita de 3 incercari e a apelantului.
- Partea de nucleu din B-001: randarea unei singure pagini, la cerere. O pagina
  stricata da `FileCorruptError` doar pentru ea, ca GUI-ul sa poata desena
  chenarul gri. Randarea „lenesa” (doar paginile vizibile) e treaba GUI-ului.
- Stratul de text existent (I-033, N-009) **nu** intra aici, ci in faza 4.
- **Dependenta noua: pypdfium2** — licenta Apache-2.0 sau BSD-3, cu PDFium (BSD-3).
  Nu PyMuPDF, care e AGPL (CLAUDE.md §5).

### 1c — Proiectul OCR: creare, deschidere, salvare, adaugare de pagini

`app/core/project.py`: `OcrProject` din SPEC_05, partea de baza.

- `create`, `open`, `save`, `close` (J-030, J-031, J-034, J-035).
- Proiectul e un folder: `project.db` (SPEC_04) + `images/`.
- `add_images`: copiaza imaginile in proiect si le numeroteaza (J-050, J-066).
  Fisierele nesuportate se sar si se raporteaza la final (J-050).
- Versiuni (J-032): proiect mai nou → `ProjectVersionError`. Conversia
  proiectelor mai vechi nu are inca ce converti (exista doar versiunea 1) si e
  marcata explicit.
- Metadate (J-038), setari de proiect peste cele globale (J-039), `is_modified` (J-040).
- Salvare automata si recuperare (J-036, J-037), peste `RecoveryRegistry` din 0c.

### 1d — Operatii pe pagini

- Stergere, cu `LastPageError` la ultima pagina (J-055).
- Rotire: invalideaza zonele si textul, statusul revine la `analyzed` (J-058).
- Reordonare (J-060), duplex (J-061), pagini de carte (J-062).
- Mutarea paginilor intr-un proiect nou (J-065), renumerotare (J-066).
- Paginile goale: gasirea candidatelor, fara stergere automata (J-056). Verificarea
  pentru note de mana si imagini (J-057) e o euristica simpla in 1d; varianta
  buna vine cu analiza de layout.

### 1e — Undo si redo

- Minimum 50 de pasi, salvati in `undo_entry` (SPEC_04, J-041).
- Toate operatiile din 1d se pot anula, inclusiv reordonarea (J-063).
- Exceptie: optiunea „Reorder pages (cannot be undone)” din J-060 nu intra in
  istoric, exact cum spune cerinta.

---

## Decizii care cer confirmarea ta

1. **Impartirea de mai sus**, in 5 pasi (1a…1e).
2. **Doua dependente noi:** Pillow (1a) si pypdfium2 (1b). Licentele le
   verific la instalare.
3. **Copie de lucru.** Propun ca un proiect deschis sa se editeze intr-o copie
   din folderul temporar al sesiunii, iar `save` sa o scrie inapoi in folderul
   proiectului. Avantaje:
   - „modificari nesalvate” (J-040) inseamna exact ce scrie: proiectul de pe
     disc nu se schimba pana la salvare;
   - o cadere nu strica proiectul salvat;
   - salvarea automata (J-036) si recuperarea (J-037) devin simple.

   Dezavantaj: la deschiderea unui proiect mare, imaginile se copiaza. Pentru
   500 de pagini inseamna cateva secunde.
4. **Trei formate amanate:** XPS, DjVu si JBIG2 apar in lista din SPEC_05, dar:
   - pentru XPS nu exista o biblioteca cu licenta permisiva;
   - DjVuLibre e GPL;
   - jbig2dec e AGPL.

   Toate trei ar trebui rulate ca proces separat (CLAUDE.md §5). Propun ca in
   faza 1 sa dea o eroare clara „format inca neimplementat”, iar decizia sa se
   ia separat.

## Nepotriviri gasite

ID-urile din docstring-urile `OcrProject` (SPEC_05) sunt din numerotarea veche:

| Metoda | SPEC_05 | Cerinta reala |
|---|---|---|
| `open` | J-003 | J-031 |
| `save` | J-004 | J-034 |
| `autosave` | J-005 | J-036 |
| `find_recovery` | J-006 | J-037 |
| `close` | J-007 | J-035 |
| `add_images` | J-008 | J-050 |
| `delete_pages` | J-012 | J-055 |
| `rotate_pages` | J-013 | J-058 |
| `interleave_duplex` | J-015 | J-061 |
| `swap_book_pages` | J-016 | J-062 |
| `move_pages_to` | J-017 | J-065 |

Testul `T-J003.1` din 0a („proiect invalid”) poarta ID-ul din SPEC_05. Il
redenumesc in `T-J031.1` la pasul 1c.
