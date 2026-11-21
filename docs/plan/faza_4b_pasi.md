# Faza 4b — impartirea in pasi

Faza 4b din CLAUDE.md §8: limbi proprii, dictionare, sabloane de caractere,
expresii regulate (`P-020`…`P-128`, `Z-020`…`Z-030`). Scrisa in modul autonom
(CLAUDE.md §11); deciziile sunt marcate `[DECIZIE AUTONOMA]` si se revad la
oprirea de dupa faza 6d.

Surse citite: SPEC_02 P.2…P.5 (P-020…P-079), SPEC_03 Z.2 (Z-020…Z-030),
SPEC_09 anexa C (P-100…P-128), SPEC_04 (`ocr_language`, `language_group`,
`user_dictionary_word`, `char_pattern_set`, `char_pattern`, toate in app.db),
SPEC_05 (`LanguageRegistry`, `DictionaryService`, `PatternStore`).

Dialogurile (`Language Properties`, `View Dictionaries`, `Pattern Editor`,
`Pattern Training`, `Load Options`) sunt interfata: faza 6b. Aici e nucleul lor.

**Status:** faza 4b e gata (pasii 4b.1…4b.4).

---

## Pasii

### 4b.1 — Limbi proprii, grupuri, expresii regulate

`app/core/ocr/languages.py` (registrul din 4.5.5) si `app/core/ocr/regex.py`.

- Dialectul de expresii (Z-020…Z-030): `.`, `[ ]`, `[^ ]`, `|`, `*`, `+`,
  clasele de litere si cifre, intervalele latine si chirilice, `@` rezervat,
  evadarea cu backslash. Se traduce in `re` din Python; o expresie care nu
  compileaza se refuza cu mesajul erorii (P-025, Z-030).
- Limbile proprii (P-020…P-026): nume, limba sursa, alfabet, modul de
  dictionar (`none` / `builtin` / `user` / `regex`), proprietatile avansate
  (inceput/sfarsit de cuvant, caractere ignorate, interzise, cifre arabe si
  romane, abrevieri). Salvate in `ocr_language` (app.db). Limbile livrate nu
  se sterg (trigger SPEC_04).
- Grupurile de limbi (P-027…P-029): minimum doua limbi, caractere interzise.
- Motorul foloseste o limba proprie: modelul limbii sursa, alfabetul permis
  (`tessedit_char_whitelist`), caracterele interzise
  (`tessedit_char_blacklist`); cu dictionar `regex`, cuvintele care nu se
  potrivesc devin nesigure.
- P-030: limbile proprii stau in app.db; la salvarea proiectului, cele
  folosite de proiect se copiaza in folderul lui (vezi decizia 1).

### 4b.2 — Dictionarele utilizatorului

`app/core/ocr/dictionary.py`: `DictionaryService` din SPEC_05.

- Adaugare (fara spatii; duplicatul da avertisment, P-041), stergere (P-042),
  import din `*.txt`, `*.dic`, `*.pmd` (P-043; Windows-1252 la P-023, codificare
  detectata in rest), export, folderul partajat cu revenire la cel local
  (P-045, X-105).
- Cuvintele din dictionarul utilizatorului ajung la Tesseract
  (`--user-words`) si nu mai sunt marcate nesigure.

### 4b.3 — Sabloanele de caractere

`app/core/ocr/patterns.py`: `PatternStore` din SPEC_05.

- Seturi de sabloane, unul activ (P-061), stergere (P-063; cel activ nu se
  sterge), limita de 1.000 de caractere (P-058, `PatternLimitError`), numai
  caractere din alfabet (P-060), nu pentru limbile asiatice (P-059).
- Antrenarea (P-054…P-057, P-062): caracterul decupat din imagine, cu
  efectele lui (bold, italic, exponent, indice).
- Aplicarea (P-050…P-052, P-064): cu `Use user patterns`, caracterele
  nesigure se compara cu sabloanele de acelasi font, aceeasi dimensiune si
  aceeasi rezolutie; potrivirea buna inlocuieste caracterul.
- Salvarea si incarcarea sabloanelor impreuna cu limbile (P-065, P-066).

### 4b.4 — Scrieri speciale, gotic, fonturi

- Scrierile complexe si directia (P-070, P-073, P-075): araba, ebraica, idis
  de la dreapta la stanga (`text_block.direction = 'rtl'`); CJK (P-072).
- Limbile gotice (P-076…P-079): modelele Tesseract `frk`, `enm`, `frm`,
  `ita_old`, `spa_old`; regula „numai limba gotica” produce un avertisment
  cand e combinata cu o limba moderna.
- Fonturile recomandate pe scrieri (P-071, P-120…P-125), fontul liber livrat
  (P-126), si detectia fontului lipsa (P-127, P-128): care font lipseste, nu
  doar patrate.
- Limbile de interfata (P-107, P-108): lista de date; traducerile vin cu
  interfata (6b), romana si engleza obligatorii.

---

## Decizii autonome

1. **[DECIZIE AUTONOMA] P-030, unde stau limbile proprii.** SPEC_04 pune
   `ocr_language` in app.db (globala), iar P-030 cere „in folderul
   proiectului, implicit”. Ambele se respecta: limbile stau in app.db, iar la
   salvarea unui proiect, limbile proprii pe care le foloseste se scriu si in
   folderul proiectului (`languages.json`), ca proiectul sa se deschida si pe
   alt calculator. La deschidere, cele care lipsesc din app.db se adauga.
2. **[DECIZIE AUTONOMA] P-056, P-064: efectele si domeniul unui caracter
   antrenat.** `char_pattern` are numai imaginea si caracterul. Efectele
   (bold, italic, exponent, indice), inaltimea glifului si rezolutia se scriu
   in blocuri de text ale imaginii PNG (`glyph_image`), fara schimbarea
   schemei.
3. **[DECIZIE AUTONOMA] P-065: fisierul de sabloane si limbi.** Formatul
   `*.fbtx` al nostru e o arhiva ZIP cu JSON si PNG-uri. Fisierele `*.fbt`
   ale ABBYY sunt un format proprietar nedocumentat: se refuza cu un mesaj.
4. **[DECIZIE AUTONOMA] P-044, dictionarele din FineReader 10…14.** Formatul
   lor binar nu e documentat. Importul accepta fisierele text (`*.txt`,
   `*.dic`, `*.pmd` text); un fisier binar se refuza cu `ValueError`
   (SPEC_05). **INCOMPLET, marcat:** importul binar cere fisiere reale de la
   utilizator (CLAUDE.md §11: „ceva ce numai utilizatorul are”) — notat in
   STARE.md la intrebari.
5. **[DECIZIE AUTONOMA] Dictionarul livrat (P-006, P-102).** Modelele
   Tesseract au lista de cuvinte in interior, dar nu o expun. `contains()`
   pentru dictionarul livrat si sugestiile (O-010) vin in faza 5, cu
   verificarea ortografica; in 4b, dictionarul utilizatorului si expresiile.
6. **[DECIZIE AUTONOMA] Latvian Gothic (P-076).** Tesseract nu are un model
   pentru letona gotica. Se foloseste modelul `frk` (Fraktur) cu alfabetul
   leton; **INCOMPLET, marcat:** calitatea nu e masurata.
7. **[DECIZIE AUTONOMA] 4b.1, dialectul (Z-026, Z-028).** Clasele predefinite se
   scriu `\d` (cifra), `\a` (litera), `\U` (majuscula), `\L` (minuscula).
   `@` neevadat e eroare; `\@` e caracterul @, ca o adresa de e-mail sa se
   poata descrie (Z-029, Z-030).
8. **[DECIZIE AUTONOMA] 4b.1, codurile.** O limba proprie are codul
   `user:<nume>`, un grup `group:<nume>`; amandoua se folosesc oriunde se
   foloseste un cod de limba. Limbile livrate intra in `ocr_language` numai cand
   o limba proprie sau un grup se bazeaza pe ele.
9. **[DECIZIE AUTONOMA] 4b.2, folderul partajat (J-080…J-085).** Un fisier
   text pe limba (`<cod>.txt`, UTF-8). Cine adauga sau sterge tine
   `<cod>.lock` pana la `end_edit()` (J-084: ceilalti folosesc dictionarul,
   dar primesc `PermissionError` la modificare). Dictionarele se citesc la
   pornirea serviciului (J-085); cine incepe sa editeze reciteste fisierul.
   J-083 (proprietatile limbii nu se schimba din folderul partajat) e
   respectat prin constructie: in folder sunt numai cuvintele.
10. **[DECIZIE AUTONOMA] 4b.3, aplicarea sabloanelor (P-051, P-064).**
    Tesseract nu se poate antrena din aplicatie. Sablonul se aplica dupa
    recunoastere: glifele (componente conexe) cuvintelor nesigure se compara
    prin corelatie normalizata (prag 0,85) cu caracterele antrenate de aceeasi
    inaltime (±15%) si rezolutie (±5%); fontul nu se poate afla, deci domeniul
    din P-064 e dat de dimensiune si rezolutie. Fara `Also use built-in
    patterns`, se recitesc toate cuvintele. **INCOMPLET, marcat:** glifele
    lipite intre ele nu se separa.
11. **[DECIZIE AUTONOMA] 4b.4, fonturile libere (P-126).** Familia Noto (SIL OFL
    1.1), cate un font pe scriere (`app/core/fonts.py`, `FREE_FONTS`).
    **INCOMPLET, marcat:** fisierele intra in pachet la faza 16.
12. **[DECIZIE AUTONOMA] 4b.4, P-072, P-073.** Pentru CJK amestecat cu text
    european, nucleul intoarce setarile de debifat (`cjk_advice`); interfata
    le propune. Pentru araba, ebraica, idis, impartirea paginilor alaturate
    pune pagina din dreapta prima (`right_to_left`).
13. **P-107, P-108:** lista limbilor de interfata e in `languages.UI_LANGUAGES`;
    traducerile si verificarea suportului sistemului vin cu interfata (6b).
