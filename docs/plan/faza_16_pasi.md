# Faza 16 — impachetare, instalare, accesibilitate, formate, mesaje

Cerinte: `Y-001`…`Y-026`, `Y-100`…`Y-112`, `Y-130`…`Y-140`, `Y-200`…`Y-220`,
`Y-300`…`Y-316`. 88 de cerinte; 14 aveau deja test (Y-001, Y-009…Y-011, Y-013,
Y-022…Y-026, Y-101, Y-104, Y-108, Y-110).

Lucrat in modul autonom (CLAUDE.md §11), la cererea utilizatorului din 24.11.2026:
„continua tu tot pana e gata tot”.

## Pasii

| Pas | Ce | Cerinte |
|---|---|---|
| 16.1 | Tabelul formatelor B.1 ca sursa unica (`app/core/formats.py`): intrarea in OCR Editor, in PDF Editor, in Compare, salvarea; filtrele dialogurilor de deschidere din el; PDF Editor deschide si imaginile si formatele editabile (convertite in PDF); formatele necitite spun clar ca nu sunt suportate; `/listformats` si un dialog `Supported formats` arata ce merge in fiecare modul | Y-100…Y-112 |
| 16.2 | `Help > About` cu versiunea si numarul de build, `System Info... > Save...`; fisierul cu licentele componentelor; fara activare, inregistrare, editii, perioada de proba; localizarea (niciun text afisabil in cod); cerintele de sistem si interoperarea declarate | Y-002…Y-008, Y-012, Y-014, Y-015, Y-020, Y-021, Y-130…Y-140, Y-316 |
| 16.3 | Mesajele (Y-300…Y-315) si depanarea (Y-200…Y-220): fiecare situatie are mesajul ei, cu sugestia din cerinta | Y-200…Y-220, Y-300…Y-315 |
| 16.4 | Robustete si accesibilitate: documentele mari pagina cu pagina (Y-016), interfata care nu se blocheaza (Y-017), scalarea 100…200 % (Y-018), navigarea cu tastatura si numele accesibile (Y-019) | Y-016…Y-019 |
| 16.5 | Impachetarea pentru Linux (AppImage) si macOS (`.dmg`), pe langa Windows (Y-009, `X`) | Y-009 |

## Decizii

1. [DECIZIE AUTONOMA] **Formatele binare vechi si cele fara biblioteca libera**
   (`.doc`, `.xls`, `.ppt`, `.vsd`, `.vsdx`, `.xps`, `.djvu`, `.jbig2`) sunt in tabel
   cu capabilitatile originalului, dar marcate „necitit inca” in DocuLens: dialogurile
   nu le ofera, iar un astfel de fisier deschis (tras, din linia de comanda) primeste
   mesajul clar din Y-106 („nu e suportat”), nu o eroare generica. INCOMPLET.
2. [DECIZIE AUTONOMA] **SVG (Y-104)** se deschide numai in PDF Editor, convertit in
   PDF cu QtSvg in stratul de interfata (nucleul nu importa Qt); nu se salveaza.
3. [DECIZIE AUTONOMA] **Cerintele care descriu originalul** (sistemele si cerintele
   minime ale originalului Y-002…Y-005, versiunile Office Y-008, editiile Y-130…Y-136,
   Y-138, Y-140) se acopera cu teste care verifica ce face DocuLens in locul lor: fara
   editii si fara perioada de proba (Y-133, Y-137), fara Office (Y-007, Y-107), fisiere
   scrise de Office citite cu bibliotecile proprii (Y-008).
4. [DECIZIE AUTONOMA] **Clasificarea de documente (Y-139, `N`)** nu se face (functie
   noua, optionala). INCOMPLET.
