# Faza 3 — impartirea in pasi, inainte de cod

Document de lucru pentru confirmare. Faza 3 din CLAUDE.md §8: zonele —
desenare, tipuri, proprietati, sabloane (`M-*`).

Surse citite: SPEC_02 M, M.1, M.2 (M-001…M-060), SPEC_10 M-100…M-112, SPEC_05
sectiunea 6 (`AreaEditor`, `TableAnalyzer`, `LayoutAnalyzer`), SPEC_04
(`area`, `table_cell`, `table_separator`, `area_template`,
`area_template_item`), SPEC_06 (T-M022, T-M032, T-M057, T-M100, T-M110).

Regula ramane: un pas = o sesiune = un commit cu CI verde.

**Status:** impartirea si cele 6 propuneri au fost confirmate de utilizator
pe 2026-11-20. Pasii 3a si 3b sunt implementati.

---

## Ce intra in faza 3 si ce nu

Intra: zonele desenate si editate de utilizator, proprietatile lor, ordinea,
sabloanele si tabelele.

Nu intra:

| Ce | Unde merge | De ce |
|---|---|---|
| Analiza automata a paginii, care gaseste zonele (`LayoutAnalyzer.analyze`, N-001, N-002) | faza 4 | e in N-*, cu recunoasterea |
| Citirea codurilor de bare (M-057…M-060) | faza 4 | cere zxing-cpp; tine de recunoastere |
| M-009, M-010, M-011, M-015, M-029, M-100…M-109, M-111 | faza GUI | taste, desenare cu mouse-ul, aspectul zonelor; nucleul da operatiile |

Culorile zonelor (M-007, M-100, M-101) sunt deja setari, din pasul 0b.

---

## Pasii

### 3a — Zonele pe pagina: creare, editare, proprietati, ordine

`app/core/layout/areas.py`: `AreaEditor` din SPEC_05, peste tabela `area`.

- Citirea si scrierea zonelor unei pagini (`AreaData` ↔ `area`).
- Creare: minimum 8 px (M-008), in interiorul imaginii (M-016), fara
  suprapunere (M-034), cu exceptia zonei de fundal (M-110).
- Mutare (M-016) si redimensionare (M-011).
- Schimbarea tipului (M-017), care invalideaza textul paginii.
- Stergerea zonelor (M-018), a zonelor si a textului (M-019), doar a textului (M-020).
- Proprietatile: limba (M-023, M-030), functia (M-024, numai pe text),
  orientarea (M-025), tipul de tipar (M-026), inversarea (M-027), directia
  CJK (M-028), tipul de cod de bare (M-056, implicit `Autodetect`).
- Ordinea: reordonare (M-021) si numerotare automata (M-022).
- **Undo pentru zone** (J-041, M-033): istoricul din 1e se extinde cu zonele;
  e marcat INCOMPLET de atunci.
- **Mutarea paginilor cu zone** intre proiecte (J-065), marcata INCOMPLET in 1d.

### 3b — Zonele poligon

- `Add area part` (M-013) si `Cut area part` (M-014), numai pe text, imagine
  si imagine de fundal; pe tabel si cod de bare → `WrongAreaTypeError`.
- Adaugarea unui maner (M-012). Zonele de text devin poligoane (M-107).
- Suprapunerea si „punctul in zona” pentru poligoane.

Zonele raman poligoane cu laturi orizontale si verticale (se adauga si se
taie doar dreptunghiuri), deci calculul se poate face exact, cu cod propriu.

### 3c — Sabloanele de zone

- `Save Area Template...` (M-031) si `Load Area Template...` (M-032), aplicate
  pe paginile selectate sau pe toate.
- Pagina de alta dimensiune sau rezolutie → `TemplateSizeMismatchError`; cu
  `scale=True` zonele se scaleaza (T-M032).
- Sabloanele se pastreaza si in biblioteca din app.db (`area_template`).

### 3d — Tabelele

`app/core/layout/tables.py`: `TableAnalyzer` din SPEC_05.

- Detectarea structurii (M-040, M-041): randuri, coloane, celule unite, din
  liniile tabelului si din spatiile goale.
- Structura nedetectabila → o singura celula si un avertisment, nu o eroare (M-049).
- Separatoare: adaugare (M-045, M-046) si stergere (M-047).
- Unirea celulelor (M-043, selectie dreptunghiulara, altfel
  `CellsNotRectangularError`), separarea (M-042, doar celule unite inainte),
  unirea randurilor (M-044).
- Celule tratate ca imagine (M-048).
- Salvate in `table_cell` si `table_separator`.

---

## Decizii care cer confirmarea ta

1. **Impartirea de mai sus**, in 4 pasi (3a…3d).
2. **Nicio dependenta noua.** Poligoanele le calculez cu cod propriu: shapely
   ar aduce GEOS, care e LGPL, ca la OpenCV. Tabelele se fac cu numpy si scipy.
3. **Suprapunerea (M-034):** o zona noua care intra peste alta e **refuzata**
   (`AreaOverlapError`). M-034 permite si varianta in care zona noua o taie pe
   cealalta, dar refuzul e previzibil si nu strica nimic. Exceptie: zona
   „Background picture” poate sta sub alte zone (M-110, T-M110).
4. **Numerotarea automata (M-022):** „de la stanga la dreapta, apoi de sus in
   jos” o citesc ca **pe coloane**: coloanele de la stanga la dreapta, iar in
   fiecare coloana de sus in jos. Acelasi lucru si pentru textele de la dreapta
   la stanga (ebraica), cum cere T-M022.
5. **Formatul sabloanelor:** propriu, JSON, cu extensia `.blkx` (M-031).
   Fisierele `.blk` / `.blkx` facute de ABBYY au un format nepublicat si nu se
   pot citi.
6. **Codurile de bare** se citesc in faza 4, cu zxing-cpp (Apache-2.0). In
   faza 3, zona de cod de bare si tipul ei se pot crea si salva.

## Nepotriviri gasite

ID-urile din SPEC_05 sectiunea 6 si din exceptii sunt din numerotarea veche:

| In SPEC_05 | Scrie | Cerinta reala |
|---|---|---|
| `AreaEditor.change_type` | M-020 | M-017 |
| `AreaEditor.save_template` | M-040 | M-031 |
| `AreaEditor.load_template` | M-041 | M-032 |
| `TableAnalyzer.analyze_structure` (structura nedetectabila) | M-031 | M-040, M-049 |
| `AreaOverlapError` | M-009 | M-034 |
| `AreaOutOfBoundsError` | M-017 | M-016 |
| `TemplateSizeMismatchError` | M-041 | M-032 |
| `WrongAreaTypeError` | M-013, M-031, M-042 | M-013, M-042 |

Si in SPEC_04: comentariul `bbox_w >= 8` din tabela `area` trimite la M-007;
cerinta reala e M-008.
