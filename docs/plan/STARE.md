# Starea lucrului

Fisierul de unde se reia lucrul in modul autonom (CLAUDE.md sectiunea 11). Se actualizeaza la sfarsitul fiecarui pas, in acelasi commit.

## Unde suntem

- **Gata:** fazele 0, 1, 2, 3; faza 4 (pasii 4.1–4.5.5); defectele de la testul manual din 21.11.2026.
- **Ultimul commit verificat:** vezi `git log -1`.

## Urmatorii pasi, in ordine

1. **Faza 4b:** `P-020`…`P-128`, `Z-020`…`Z-030`. Planul: `docs/plan/faza_4b_pasi.md`, pasii 4b.1…4b.4; 4b.1 si 4b.2 gata, urmeaza 4b.3.
2. **Faza 5:** `O-*` (nucleul; interfata in 6b).
3. **Faza 6:** export, `Q-*`, `I-008`…`I-016`, `I-030`…`I-033`.
4. **Faza 6b:** interfata OCR Editor.
5. **Faza 6c:** Lansatorul, `A-*`.
6. **Faza 6d:** scanare si fotografii, `K-002`…`K-017`. **Oprire obligatorie dupa 6d** (CLAUDE.md sectiunea 11).

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
