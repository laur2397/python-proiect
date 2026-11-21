# Starea lucrului

Fisierul de unde se reia lucrul in modul autonom (CLAUDE.md sectiunea 11). Se actualizeaza la sfarsitul fiecarui pas, in acelasi commit.

## Unde suntem

- **Gata:** fazele 0, 1, 2, 3; faza 4 (pasii 4.1–4.5.5); faza 4b (4b.1…4b.4); faza 5 (5.1…5.4); defectele de la testul manual din 21.11.2026.
- **Ultimul commit verificat:** vezi `git log -1`.

## Urmatorii pasi, in ordine

1. **Faza 6:** export, `Q-*`, `I-008`…`I-016`, `I-030`…`I-033`. Planul: `docs/plan/faza_6_pasi.md`, pasii 6.1…6.8; 6.1…6.4 gata, urmeaza 6.5.
2. **Faza 6b:** interfata OCR Editor.
3. **Faza 6c:** Lansatorul, `A-*`.
4. **Faza 6d:** scanare si fotografii, `K-002`…`K-017`. **Oprire obligatorie dupa 6d** (CLAUDE.md sectiunea 11).

## Opriri si intrebari pentru utilizator

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
