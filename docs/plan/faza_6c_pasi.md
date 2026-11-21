# Faza 6c — Lansatorul

**Cerinte:** `A-*` din SPEC_01 (A-001…A-111) si SPEC_10 (A-300…A-316).
**Status:** planul e scris; niciun pas implementat.

Lansatorul e ecranul de pornire: sarcinile din stanga (Open, Scan, Compare,
Recent, Mobile application), cardurile din dreapta, conversia rapida a
fisierelor (cu combinarea lor intr-un singur document, prioritatea pentru
dosarele de finantare) si documentele recente.

---

## Pasii

### 6c.1 — Nucleul: conversia rapida si documentele recente

- `app/core/convert.py`: `ConvertJob` — lista de fisiere, formatul tinta
  (PDF, DOCX, XLSX si celelalte din A-016/A-070), modul de layout (A-050,
  A-060), limbile (A-039), pastrarea imaginilor si a antetelor (A-052, A-053,
  A-062), o foaie pe pagina (A-063), calitatea imaginii (A-035), cautarea in
  text (A-036), PDF/A (A-037), MRC (A-038), combinarea intr-un singur document
  in ordinea listei (A-024). Fiecare fisier trece printr-un proiect OCR
  temporar: adaugare, recunoastere (stratul de text al PDF-urilor se foloseste
  dupa N-009), export. Eroarea unui fisier nu opreste lotul; raport la final
  (A-028). Progres pe fisiere si anulare.
- `app/core/recent.py`: documentele recente in `recent_document` (SPEC_04):
  adaugare, lista (cel mai recent primul), cautare fara diacritice (A-103),
  stergerea unei intrari (A-104), golirea (A-105), fisierele lipsa marcate
  (A-102).

### 6c.2 — Fereastra Lansatorului

- Sarcinile din stanga cu selectia marcata (A-003, A-300), butonul `Options`
  stanga-jos (A-005), `F1` cu manualul local (A-006), scenariile la hover
  (A-007, `N`, ca tooltip).
- Tabul `Open`: grupurile `Open and Edit` si `Convert to`, cardurile (A-301,
  A-302); `OCR Editor` (A-012, `Ctrl+R`), `PDF Document` (A-010, A-011).
- Tabul `Compare` (A-100, A-101, A-303), tabul `Recent` (A-102…A-105, A-111),
  tabul `Mobile application` (A-106…A-110).

### 6c.3 — Ecranul de conversie

- `< Back` (A-029, A-305), coloana de setari, lista de fisiere cu toolbarul
  ei (A-020…A-026, A-306, A-307), setarile pe format (A-035…A-073), dialogul
  `Custom Settings` (A-308…A-314), dialogul de progres (A-027, A-028, A-315),
  recomandarea pentru documente complexe (A-017).

### 6c.4 — Pornirea si legaturile

- Ecranul de pornire dupa `general.startup_screen` (A-001, X-001), inclusiv
  ultimul proiect OCR din documentele recente; revenirea la Lansator din OCR
  Editor (`Ctrl+N`, A-002); proiectele salvate si deschise intra in recente.

---

## Ce ramane pentru alte faze

- **Tabul `Scan` (A-080…A-090)** cere modulul de scanare: se face in faza 6d,
  peste el. Cerintele raman in tabelul fazei 6c (CLAUDE.md §8); pasul care le
  implementeaza e in planul fazei 6d.
- **`PDF Document` (A-010, A-011)** deschide PDF Editor-ul, care vine in faza 7.
  Pana atunci cardul deschide PDF-ul cu aplicatia implicita a sistemului;
  marcat INCOMPLET.
- **`Compare` (A-100, A-101)** deschide modulul de comparare din faza 12. Pana
  atunci cardul e gri, cu explicatie; lista `Recent Comparisons` citeste tabela
  `recent_comparison`, goala.

---

## Decizii autonome

1. **[DECIZIE AUTONOMA] Conversia trece prin proiectul OCR.** Un proiect
   temporar per fisier (sau unul singur la combinare) reutilizeaza tot ce face
   deja nucleul: incarcarea formatelor, PDF-urile cu strat de text, OCR-ul,
   exportul cu matricea de moduri. Nu exista un al doilea drum de conversie.
2. **[DECIZIE AUTONOMA] `Rate This Product` (A-316)** nu se implementeaza, cum
   cere cerinta `X`.
3. **[DECIZIE AUTONOMA] Aplicatia mobila (A-106…A-110).** Nu exista aplicatie
   mobila DocuLens; tabul lucreaza cu un folder local ales de utilizator (de
   exemplu folderul sincronizat al unui client de cloud), fara nicio cerere de
   retea din partea noastra (CLAUDE.md §6.1). Sincronizarea inapoi (A-110) o
   face clientul de cloud, nu DocuLens.
4. **[DECIZIE AUTONOMA] `Ctrl+N` (A-002).** In OCR Editor, `Ctrl+N` e `New Task`
   (SPEC_09 A.3) si deschide Lansatorul; proiectul nou e `Ctrl+Shift+N`.
