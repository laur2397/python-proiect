# Starea lucrului

Fisierul de unde se reia lucrul in modul autonom (CLAUDE.md sectiunea 11). Se actualizeaza la sfarsitul fiecarui pas, in acelasi commit.

## Unde suntem

- **Gata:** fazele 0, 1, 2, 3; faza 4 pasii 4.1–4.4, 4.5.1 si 4.5.2.
- **Ultimul commit verificat:** vezi `git log -1`.

## Urmatorii pasi, in ordine

1. **Defecte gasite la testul manual din 21.11.2026**, inainte de restul pasului 4.5:
   - pe o scanare curata a unui tabel cu chenar, `analyze_pages` nu gaseste zona Tabel (pe fotografia corectata a aceluiasi tabel o gaseste); liniile tabelului sunt citite ca text („mp fm mn”);
   - o stampila rotunda si o linie de pix primesc zone de tip Text in loc de Imagine.
   Pentru fiecare: test care reproduce, cauza in `app/core/layout/analyzer.py`, reparatie.
2. **Restul pasului 4.5** din `docs/plan/faza_4_pasi.md`: elementele de structura (N-018…N-021), codurile de bare (M-057…M-060), limbile ramase (P-001…P-009).
3. **Faza 4b:** `P-020`…`P-128`, `Z-020`…`Z-030`.
4. **Faza 5:** `O-*` (nucleul; interfata in 6b).
5. **Faza 6:** export, `Q-*`, `I-008`…`I-016`, `I-030`…`I-033`.
6. **Faza 6b:** interfata OCR Editor.
7. **Faza 6c:** Lansatorul, `A-*`.
8. **Faza 6d:** scanare si fotografii, `K-002`…`K-017`. **Oprire obligatorie dupa 6d** (CLAUDE.md sectiunea 11).

## Opriri si intrebari pentru utilizator

(niciuna deocamdata)

## Jurnal

| Data | Pas | Rezultat |
|---|---|---|
| 2026-11-21 | 4.5.1 | alegerea automata a limbii (P-001, P-009) |
| 2026-11-21 | 4.5.2 | tabelele pe celule, mutarea paginilor cu text (M-003, M-048, M-049, J-067) |
