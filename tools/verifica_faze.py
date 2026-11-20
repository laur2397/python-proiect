"""Verifica faptul ca fiecare cerinta din SPEC_07 are o faza in CLAUDE.md, sectiunea 8.

Citeste coloana „Cerinte” a tabelului de faze. Forme acceptate:
`X-*` (toata litera), `L-010`…`L-023` (interval), `K-001` (o cerinta).
Iese cu codul 1 si listeaza cerintele fara faza, daca exista.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
MATRICE = ROOT / "docs" / "spec" / "SPEC_07_matrice_trasabilitate.csv"

TOKEN = re.compile(r"`([A-Z])-(\*|\d{3})`(?:\s*…\s*`[A-Z]-(\d{3})`)?")


def faze() -> dict[str, list[tuple[str, int, int]]]:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    sect = text[text.index("## 8."):text.index("## 9.")]
    rezultat: dict[str, list[tuple[str, int, int]]] = {}
    for line in sect.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or not re.fullmatch(r"\d+[a-z]?", cells[0]):
            continue
        intervale = []
        for m in TOKEN.finditer(cells[2]):
            litera, start, stop = m.group(1), m.group(2), m.group(3)
            if start == "*":
                intervale.append((litera, 0, 999))
            else:
                intervale.append((litera, int(start), int(stop or start)))
        rezultat[cells[0]] = intervale
    return rezultat


def main() -> int:
    plan = faze()
    if not plan:
        print("EROARE: tabelul de faze din CLAUDE.md sectiunea 8 nu a fost gasit")
        return 1
    with MATRICE.open(encoding="utf-8-sig", newline="") as f:
        ids = [r["ID cerinta"] for r in csv.DictReader(f, delimiter=";")]
    fara_faza = []
    for cid in ids:
        litera, numar = cid[0], int(cid[2:])
        if not any(lit == litera and a <= numar <= b
                   for intervale in plan.values() for lit, a, b in intervale):
            fara_faza.append(cid)
    print(f"Faze in plan: {len(plan)}; cerinte: {len(ids)}; fara faza: {len(fara_faza)}")
    if fara_faza:
        print("Cerinte fara faza in CLAUDE.md sectiunea 8:")
        for cid in fara_faza:
            print(f"  {cid}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
