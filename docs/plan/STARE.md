# Starea lucrului

Fisierul de unde se reia lucrul in modul autonom (CLAUDE.md sectiunea 11). Se actualizeaza la sfarsitul fiecarui pas, in acelasi commit.

## Unde suntem

- **Gata:** fazele 0, 1, 2, 3; faza 4 (pasii 4.1–4.5.5); faza 4b (4b.1…4b.4); faza 5 (5.1…5.4); faza 6 (6.1…6.8); faza 6b (6b.1…6b.7); faza 6c (6c.1…6c.4, fara tabul Scan, care vine in 6d); faza 6d (6d.1…6d.4); faza 7 (7.1…7.10); faza 8 (8.1…8.6); faza 9 (9.1…9.6); defectele de la testul manual din 21.11.2026.
- **Ultimul commit verificat:** vezi `git log -1`.

## Urmatorii pasi, in ordine

1. **Faza 10:** securitate, redactare, semnaturi (`G-*`), dupa
   `docs/plan/faza_10_pasi.md`. Gata: 10.1…10.3. Urmeaza 10.4 (interfata tabului `Security`).
2. Faza 7 (PDF Editor) e gata, cu tot ce ramane marcat INCOMPLET in
   `docs/plan/faza_7_pasi.md`. De verificat de utilizator, cand vrea: un PDF
   deschis din Lansator, cautarea, copierea, comentariile, stampilele,
   redactarea, salvarea ca PDF cautabil, tiparirea.

## Ce a verificat utilizatorul la oprirea de dupa 6d

- Pornirea: `python -m app.gui.main` (Lansatorul; `Options > General` alege
  pornirea direct in OCR Editor).
- Fluxul pentru dosarele de finantare: Lansator → `Convertește în PDF` cu mai
  multe fisiere si `Combină toate fișierele`; OCR Editor: deschidere, recunoastere
  in romana, verificare, export Word si PDF cautabil.
- Scanarea pe Windows, cu un scaner real (WIA): `Ctrl+K` in OCR Editor si tabul
  `Scanează` din Lansator. In CI scanarea e verificata numai cu dispozitive
  simulate.
- Deciziile autonome: `docs/plan/faza_6b_pasi.md` (1–12), `faza_6c_pasi.md`
  (1–4), `faza_6d_pasi.md` (1–3), plus cele din fazele anterioare.

## Opriri si intrebari pentru utilizator

- **Dosarul cu semnaturile pastrate (faza 8, E-500…E-512), de verificat de
  utilizator:** acceptarea unui dosar real de catre MySMIS si celelalte portaluri,
  si semnaturile calificate reale (STS, certSIGN, DigiSign, Trans Sped). Testele
  folosesc certificate de test. Datele LTV (E-508) nu sunt facute: cer retea si
  certificate reale (`docs/plan/faza_8_pasi.md`, INCOMPLET).

- **Motorul JavaScript pentru PDF (de decis pana la faza 11):** B-038 si
  formularele (H-006, H-058) cer ca scripturile din PDF sa ruleze cand sunt
  activate. Stiva din CLAUDE.md §5 nu are un motor JavaScript; propunerea e
  QuickJS (licenta MIT), cu un subset al obiectelor Acrobat (`app`, `this`,
  `event`, `getField`, `AFNumber_*`). Pana atunci scripturile se detecteaza,
  dar nu ruleaza (`faza_7_pasi.md`, decizia 19).

- **CI-ul nu porneste (22.11.2026):** GitHub refuza joburile pentru o problema de plata sau de limita de cheltuieli a contului. Verificarile ruleaza local pana se rezolva (`docs/plan/faza_7_pasi.md`, decizia 3).

- **INCOMPLET, marcat in cod, de stiut la verificare:** `Find and Replace` (C-015) face inca pagina imagine cu strat de text (`faza_7_pasi.md` decizia 11); editarea din `Edit Content` (faza 9) pastreaza continutul vectorial; compararea (faza 12),
  `Style Editor`, spatierea, majusculele mici, fundalul si scalarea textului (fara
  coloane in SPEC_04), `Pattern Editor...` si `Select Fonts...`, mesajul de
  vizualizator PDF implicit (X-406), „Opened by” (lucrul in grup), zona de scanare
  trasa manual (K-008), manualul local (`docs/manual/index.html` lipseste: `F1`
  arata calea asteptata), plus cele din faza 6 (MRC, I-032, DjVu pe mai multe
  pagini, JBIG2, notele de subsol in Word, fonturile incorporate).
- **Operatiile lungi (recunoastere, conversie) ruleaza pe firul interfetei**, cu
  dialog de progres si `Cancel` intre pagini (faza_6b_pasi.md, decizia 11).

- **TWAIN (K-003, nu blocheaza):** `pytwain` e GPLv2 si nu se foloseste; TWAIN se face cu o legatura proprie, care cere un scaner real pentru verificare. Pana atunci scanarea merge prin WIA (`docs/plan/faza_6d_pasi.md`, deciziile 1, 2).

- **P-044 (nu blocheaza):** importul dictionarelor binare din FineReader 10…14 cere fisiere reale de la utilizator; formatul nu e documentat. Pana atunci se importa numai fisierele text (`docs/plan/faza_4b_pasi.md`, decizia 4).

## Jurnal

| Data | Pas | Rezultat |
|---|---|---|
| 2026-11-21 | 4.5.1 | alegerea automata a limbii (P-001, P-009) |
| 2026-11-21 | 4.5.2 | tabelele pe celule, mutarea paginilor cu text (M-003, M-048, M-049, J-067) |
| 2026-11-21 | defecte test manual | tabelul cu chenar gri / subtire / usor inclinat se gaseste; stampila si linia de pix sunt zone Imagine (N-006, M-040) |
| 2026-11-21 | 4.5.3 | antete si subsoluri, note de subsol, cuprins, liste (N-018…N-021) |
| 2026-11-21 | 4.5.4 | codurile de bare: 11 tipuri autodetectate (Postnet cu decodor propriu), restul manual, optiunea X-066 (M-056…M-060) |
| 2026-11-21 | 4.5.5 | catalogul limbilor: naturale, artificiale, formale; RomanianMoldavia; limbile recente (P-002…P-008). Faza 4 gata |
| 2026-11-21 | 4b.1 | expresiile regulate, limbile proprii, grupurile, limbile proiectului in folderul lui (Z-020…Z-030, P-020…P-030) |
| 2026-11-21 | 4b.2 | dictionarele utilizatorului: adaugare, import (txt/dic/pmd, Windows-1252), folder partajat cu blocare (P-040…P-045, J-080…J-085) |
| 2026-11-21 | 4b.3 | sabloanele de caractere: seturi, antrenare cu efecte, limita 1000, fisierul .fbtx, aplicarea pe cuvintele nesigure (P-050…P-066) |
| 2026-11-21 | 4b.4 | scrieri de la dreapta la stanga, CJK, limbile gotice, fonturile recomandate si cel lipsa (P-070…P-079, P-107, P-120…P-128). Faza 4b gata |
| 2026-11-21 | 5.1 | editarea si verificarea textului, re-recunoasterea unei zone (O-001…O-012, O-020, O-108) |
| 2026-11-21 | 5.2 | cautare si inlocuire, formatare, redactare, celulele de tabel cu text, copiere (O-022…O-027, O-060…O-063, O-070…O-072, O-080…O-083) |
| 2026-11-21 | 5.3 | stilurile: editorul, stil nou, unire, fragmente, rolul de titlu, titlurile detectate (O-035…O-041, O-110, O-111) |
| 2026-11-21 | 5.4 | legaturile din text: web, fisier, e-mail, editare, stergere (O-050…O-056). Faza 5 gata |
| 2026-11-21 | 6.1 | baza exportului, matricea modurilor, avertismentele, exportul TXT (Q-001…Q-007, Q-018, Q-023, Q-024, Q-051) |
| 2026-11-21 | 6.2 | PDF cautabil si doar-imagine: strat de text invizibil cu diacritice, redactare, semne de carte, legaturi (Q-011, Q-012, Q-033, Q-104, I-030, I-031, I-033) |
| 2026-11-21 | 6.3 | PDF/A (1b…3u, verificare pe fisier), PDF/UA etichetat, reducerea dimensiunii (I-008…I-012, I-016, Q-103) |
| 2026-11-21 | 6.4 | DOCX, RTF, ODT in modurile exact, editable, formatted, plain, cu optiunile X-100…X-109 (Q-013, Q-014) |
| 2026-11-21 | 6.5 | XLSX (celule unite, numere romanesti, foi pe pagina), CSV, PPTX (Q-015…Q-017, X-120…X-122) |
| 2026-11-21 | 6.6 | HTML (formatted, plain, flexible, impartirea pe titluri), EPUB 2/3, FB2 (Q-019…Q-021, X-124…X-126) |
| 2026-11-21 | 6.7 | DjVu cu text ascuns (pe pagina), imaginile paginilor TIFF/JPEG/PNG cu compresiile Q-032 (Q-022, Q-030…Q-032, X-127) |
| 2026-11-21 | 6.8 | trimiterea (e-mail .eml, Kindle, PDF Editor, aplicatii) si tiparirea, partea din nucleu (Q-040…Q-050, Q-060…Q-065). Faza 6 gata |
| 2026-11-21 | 6b.1 | fereastra principala si traducerile ro/en: titlul, bara, salvarea dupa modul de layout, panourile (J-400…J-420, Q-001, X-140) |
| 2026-11-21 | 6b.2 | panourile Pages, Image si Zoom; zonele desenate si editate cu mouse-ul prin AreaEditor (J-403…J-418, M-009…M-011, M-015, M-029, M-100…M-111) |
| 2026-11-21 | 6b.3a | panoul Text: editare, sincronizare cu imaginea, nesigure pe caracter, formatare, aliniere si liste, cautare; reparat CI-ul Windows de la 6b.2 (O-020, O-021, O-024, O-025, O-028, O-029, O-064, O-100, O-101, O-103…O-105, J-417) |
| 2026-11-21 | 6b.3b | Verify Text, Mark as Verified, simbolurile, legaturile, bara Text Properties, selectia mixta (O-003…O-011, O-050…O-056, O-102, O-106, O-109) |
| 2026-11-21 | 6b.4 | Image Editor: cele 14 unelte inline, Selection, Crop cu selectie, grila trapezului, histograma Levels, radiera (L-001…L-004, L-100…L-108) |
| 2026-11-21 | 6b.5 | dialogul Options peste toate setarile X-* vizibile, cu dependentele; dialogul de eroare neasteptata (X-400…X-423, Y-025, O-009) |
| 2026-11-21 | 6b.6a | proiectul (nou, deschidere, salvare, intrebarea la modificari), adaugarea imaginilor, recunoasterea si analiza cu progres si anulare, limbile din bara (J-030…J-032, J-401, N-004, N-027, N-028) |
| 2026-11-21 | 6b.6b | salvarea in formate, un fisier pe pagina, avertismentele, imaginile paginilor, trimiterea, e-mailul (.eml), Kindle, tiparirea (Q-001, Q-030, Q-040…Q-051, Q-100…Q-104). Faza 6b gata |
| 2026-11-21 | 6c.1 | nucleul Lansatorului: conversia rapida cu combinarea fisierelor si documentele recente (A-013…A-016, A-024, A-028, A-035…A-073, A-102…A-105) |
| 2026-11-21 | 6c.2 | fereastra Lansatorului: sarcinile, cardurile, Recent cu cautare si golire, Compare, aplicatia mobila peste un folder local (A-001…A-012, A-100…A-111, A-300…A-303) |
| 2026-11-21 | 6c.3 | ecranul de conversie: lista de fisiere, setarile pe format, Custom Settings, combinarea, progresul si raportul (A-017, A-020…A-073, A-305…A-315) |
| 2026-11-21 | 6c.4 | pornirea dupa setare, New Task (Ctrl+N) catre Lansator, cererile Lansatorului legate de OCR Editor si conversie, proiectele in recente (A-001, A-002, A-010, A-012, A-102). Faza 6c gata, fara tabul Scan |
| 2026-11-21 | 6d.1 | nucleul scanarii: setarile, avertismentele, capabilitatile, sesiunea cu ADF, duplex, pauza, anulare, revenirea la interfata proprie (K-002…K-013) |
| 2026-11-21 | 6d.2 | scanarea prin WIA cu comtypes (MIT, numai Windows), verificata cu obiecte COM simulate (K-003, K-005…K-010, K-012) |
| 2026-11-21 | 6d.3 | interfata scanarii: Scan Pages (Ctrl+K), Select Device, tabul Scan din Lansator cu cele sase sarcini, imaginile cu compresia TIFF (K-002…K-012, A-080…A-090, X-404, X-407) |
| 2026-11-21 | 6d.4 | sfaturile pentru fotografierea documentelor si Photo Correction (K-014…K-017). Faza 6d gata: OPRIRE OBLIGATORIE |
| 2026-11-22 | 6b.7 | finisarea vizuala dupa prototip, la cererea utilizatorului: tema, iconite proprii, bara principala, miniaturile, bara de stare, Lansatorul (J-401, J-403…J-412, M-101, A-300…A-302) |
