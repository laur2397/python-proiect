# Faza 14 — linia de comanda

Cerinte: `U-001`…`U-013` (conversia), `U-020`…`U-028` (compararea), `U-040`…`U-051`
(extinderile proprii, `N`). 34 de cerinte. Codul: `app/cli/` (strat subtire peste
`app/core`, CLAUDE.md §4).

## Pasii

| Pas | Ce | Cerinte |
|---|---|---|
| 14.1 | Executabilul de conversie: sintaxa cu spatii, sursele (fisiere, `/scan`), `/lang` (si `@@limba proprie`), `/send` cu cele 8 destinatii, `/out`, `/report`, comportamentul fara `/out`; extinderile `/indir`, `/outdir`, `/pattern`, `/recursive`, `/pages`, `/layout`, `/pdfa`, `/mrc`, `/threads`, `/json`, `/quiet`, `/listlangs`, `/listformats`, `/version`, `/help`; codurile de iesire | U-001…U-013, U-040…U-051 |
| 14.2 | Executabilul de comparare: sintaxa cu doua puncte, `/compare`, `/file1:`, `/file2:`, `/lang:`, `/recMode:`, `/options:`, `/saveFile:`, `/saveMode:` | U-020…U-028, U-051 |
| 14.3 | Impachetarea: cele doua executabile in `dist\DocuLens` (consola), langa `DocuLens.exe` | U-001, U-020 |

## Decizii

1. [DECIZIE AUTONOMA] **Numele executabilelor:** `DocuLensOCR` (conversia) si
   `DocuLensCompare` (compararea), cu sintaxele din U-001 si U-020 neschimbate.
   `FineReaderOCR.exe` si `Comparator.exe` sunt numele produsului ABBYY, iar
   CLAUDE.md §6.6 interzice preluarea numelor. Din sursa: `python -m app.cli ocr …`
   si `python -m app.cli compare …`.
2. [DECIZIE AUTONOMA] **U-012 (`D`) si extinderile U-040…U-050 (`N`):** T-U012 cere ca
   parametrii care nu exista in original sa fie acceptati numai ca extindere proprie,
   grupata separat in `/help`. Asa se face: `/help` are doua liste („parametrii
   originalului” si „extinderi DocuLens”). Parametrii din U-012 care nu au o
   extindere definita (`/format`, `/dpi`, `/split`, `/merge`, `/config`) se refuza
   cu codul 1.
3. [DECIZIE AUTONOMA] **`/send` (U-006) fara Microsoft Office (CLAUDE.md §6.3):**
   rezultatul se scrie intr-un fisier temporar in formatul destinatiei si se
   deschide cu aplicatia implicita a sistemului: `MSWord` si `Mail` → DOCX,
   `MSExcel` → XLSX, `OpenOffice` → ODT, `PowerPoint` → PPTX, `WebBrowser` → HTML,
   `PDFViewer` → PDF, `Clipboard` → textul copiat in clipboard (`clip` pe Windows,
   `pbcopy` pe macOS, `wl-copy`/`xclip` pe Linux). `Mail` deschide clientul de
   e-mail si folderul cu documentul (atasarea automata nu are un mecanism standard,
   ca in faza 13, decizia 7). Fara `/send` si fara `/out` (U-009) rezultatul se
   deschide ca PDF in aplicatia implicita.
4. [DECIZIE AUTONOMA] **Numele limbilor (U-004, U-023):** se accepta numele englezesc
   (`German`, `Romanian`), numele romanesc si codul (`deu`, `ron`), fara diferenta de
   majuscule. „Ultima limba utilizata” (U-004) e `lang.manual` din setari; dupa o
   rulare cu `/lang`, limbile alese devin cele folosite ultima data.
5. [DECIZIE AUTONOMA] **Limbile proprii `@@Nume` (U-005):** in DocuLens limbile
   proprii sunt in `app.db` (faza 4b), nu in folderul proiectului; `@@Nume` cauta
   limba proprie cu acest nume. Numele cu caractere nealfanumerice se refuza (cod 1).
6. [DECIZIE AUTONOMA] **`/scan [SourceName]` (U-003):** scanerul cu acest nume
   (WIA); fara nume, `general.capture_device` („ultimul scaner utilizat”), apoi
   primul gasit. Setarile de scanare sunt cele implicite (300 dpi, gri).
7. [DECIZIE AUTONOMA] **`/password` (mentionat de U-045):** extindere pentru PDF-urile
   de intrare protejate; o parola gresita da codul 2. `/pdfa` impreuna cu `/password`
   se refuza cu codul 1.
8. [DECIZIE AUTONOMA] **U-013 (fara mod server):** pe Windows, rularea din sesiunea 0
   (servicii, niciun utilizator conectat) se refuza cu codul 1.
9. [DECIZIE AUTONOMA] **`/options:` la comparare (U-025):** fara `IgnorePunctDiff` si
   `IgnoreOneLetterDiff` se gasesc si diferentele de punctuatie si cele de o litera
   (numele optiunilor spun ca implicit nu se ignora); `NoheadersFooters` opreste
   detectarea antetelor si subsolurilor (R-022); `UngroupDiff` nu mai uneste
   diferentele apropiate (R-034).
10. [DECIZIE AUTONOMA] **Mesajele CLI-ului** vin din aceleasi fisiere de traducere
    ca interfata (CLAUDE.md §6.5); `app/cli` citeste numai `app/gui/i18n/*.json`,
    fara Qt.
