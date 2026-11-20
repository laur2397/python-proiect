#!/usr/bin/env python3
"""
Genereaza matricea de trasabilitate cerinta -> test, din fisierele de
specificatie. Fiecare cerinta numerotata primeste exact un ID de test.

Rulare:   python -I tools/genereaza_matrice_trasabilitate.py   (din radacina)
Produce:  SPEC_07_matrice_trasabilitate.csv
Verifica: ca nicio cerinta nu rămâne fara test si ca niciun ID din API nu
          trimite la o cerinta inexistenta.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "docs" / "spec"

SPEC_FILES = [
    "SPEC_01_lansator_si_pdf_editor.md",
    "SPEC_02_ocr_editor.md",
    "SPEC_03_compare_automatizare_cli.md",
    "SPEC_09_anexe_referinta.md",
    "SPEC_10_interfata_detaliata.md",
]
API_FILE = "SPEC_05_api_core.py"
SQL_FILE = "SPEC_04_schema_bd.sql"
OUT_CSV = "SPEC_07_matrice_trasabilitate.csv"

MODULE_NAMES = {
    "A": "Lansator",
    "B": "PDF Editor - vizualizare",
    "C": "PDF Editor - cautare si redactare",
    "D": "PDF Editor - comentarii",
    "E": "PDF Editor - organizare pagini",
    "F": "PDF Editor - editare continut",
    "G": "PDF Editor - securitate",
    "H": "PDF Editor - formulare",
    "I": "PDF Editor - salvare si export",
    "J": "OCR Editor - proiect",
    "K": "OCR Editor - achizitie imagini",
    "L": "OCR Editor - preprocesare",
    "M": "OCR Editor - zone",
    "N": "OCR Editor - recunoastere",
    "O": "OCR Editor - verificare text",
    "P": "Limbi si dictionare",
    "Q": "OCR Editor - export",
    "R": "Comparare documente",
    "S": "Hot Folder",
    "T": "Sarcini automatizate",
    "U": "Linia de comanda",
    "V": "Screenshot Reader",
    "W": "Integrari",
    "X": "Setari",
    "Y": "Infrastructura si cerinte de sistem",
    "Z": "Referinte: etichete de data si expresii regulate",
}

# Nivelul de test implicit per modul. U = unitar, I = integrare,
# E = end-to-end prin interfata, M = manual (hardware sau sistem).
DEFAULT_LEVEL = {
    "A": "E", "B": "E", "C": "I", "D": "I", "E": "I", "F": "I",
    "G": "I", "H": "I", "I": "I", "J": "I", "K": "M", "L": "U",
    "M": "U", "N": "I", "O": "U", "P": "U", "Q": "I", "R": "I",
    "S": "I", "T": "I", "U": "I", "V": "M", "W": "M", "X": "U",
    "Y": "M", "Z": "U",
}

# Cerintele critice: cele care, dacă pica, fac produsul greșit, nu doar
# incomod. Ele primesc prioritate 1 si au procedura scrisa in SPEC_06.
CRITICAL = {
    # --- matricea mod de layout -> formate permise ---
    "Q-001", "Q-002", "Q-003", "Q-004", "Q-005", "Q-006",
    # --- decizia dintre stratul de text si OCR ---
    "N-008", "N-009", "I-030", "I-031", "I-032", "I-033", "R-020",
    # --- reguli usor de ratat, confirmate in documentatie ---
    "F-005", "F-006",          # fontul in paranteze patrate, inlocuirea fontului
    "F-002",                   # text vectorial: nu se poate edita
    "F-027",                   # prefixele mailto: si file://
    "F-050",                   # Delete Watermarks sterge toate filigranele
    "E-031", "E-032",          # ce se pierde la Split
    "E-025",                   # split pe dimensiune poate depasi limita
    "M-022", "M-032", "N-026", # numerotarea zonelor, sabloane, invalidarea
    "M-057",                   # ce acopera autodetectarea codurilor de bare
    "O-041", "X-165",          # rolul de titlu, culorile zonelor configurabile
    "C-040", "C-044", "C-047", # copierea continutului
    "J-032",                   # conversia ireversibila a proiectelor vechi
    "Q-041", "I-018",          # ce se pierde intre PDF Editor si OCR Editor
    # --- integritatea datelor ---
    "G-020", "G-021", "I-001", "I-007", "C-018", "F-024",
    "E-005", "J-055", "J-034", "J-037", "I-024",
    # --- securitate ---
    "G-002", "G-004", "G-005", "G-010", "G-030", "G-037", "G-041",
    "G-043", "B-034", "B-035", "B-036", "B-040", "X-145", "Y-001",
    "I-009", "I-010",
    # --- corectitudinea recunoasterii ---
    "N-003", "N-013", "N-024", "N-025", "P-001", "P-008", "B-030",
    # --- formulare ---
    "H-013", "H-015", "H-017", "H-023", "H-024", "H-030", "H-040",
    # --- automatizare, Hot Folder, CLI ---
    "S-005", "S-006", "S-009", "S-032", "S-049", "S-072", "S-073",
    "T-008", "T-010", "T-018",
    "U-001", "U-006", "U-012", "U-020", "U-024", "U-027", "U-051",
    # --- comparare ---
    "R-008", "R-033", "R-034", "R-061", "R-062", "R-065",
    # --- lucrul in grup ---
    "J-083", "J-084", "J-085",
    # --- adaugate la auditul al patrulea: anexele de referinta ---
    "X-204",                                     # scurtaturile se reconfigureaza doar din OCR Editor
    "Y-101", "Y-102", "Y-103", "Y-104", "Y-105", # ce format merge in ce modul
    "Y-106", "Y-107", "Y-108",                   # XPS cere .NET, Office pentru editare, PDF 2.0
    "P-100", "P-101", "P-102",                   # numerele de limbi se contrazic intre surse
    "Y-130", "Y-140",                            # linia Standard/Corporate; imprimanta retrasa
    "N-100", "N-103",                            # praguri de rezolutie; numarul de limbi
    "Y-202", "Y-203", "Y-215",                   # depanare: fonturi lipsa, font in paranteze
    # --- adaugate la auditul al patrulea: interfata recuperata ---
    "B-300", "B-301",                            # uneltele Select si Hand, sterse din specificatie
    "A-311",                                     # "quality loss not allowed" dezactiveaza sliderul
    "G-104", "G-111",                            # motivele predefinite; sase bife, nu patru
    "J-407", "J-413",                            # tooltipul de pagina; banda de strat de text
    "M-100", "M-110",                            # culorile configurabile; tehnica straturilor
    "O-102",                                     # combo de stil la selectie mixta
    "Q-100",                                     # "Open document after saving" si fisier per pagina
    "R-414",                                     # structura raportului Word
    "S-206", "S-211", "S-214", "S-216",          # SharePoint, lista de tipuri, pagini goale, macrocomenzi
    "T-106",                                     # analiza manuala opreste sarcina
    "X-416", "X-421",                            # doua bife de sabloane; PDF/UA forteaza etichetele
}


def read_requirements() -> list[dict[str, str]]:
    """Extrage ID-ul si denumirea fiecarei cerinte din tabelele markdown."""
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for fname in SPEC_FILES:
        text = (HERE / fname).read_text(encoding="utf-8")
        for line in text.splitlines():
            m = re.match(r"^\|\s*([A-Z]-\d{3})\s*\|\s*([^|]*?)\s*\|", line)
            if not m:
                continue
            rid, name = m.group(1), m.group(2).strip()
            if rid in seen:
                print(f"AVERTISMENT: ID duplicat {rid} in {fname}", file=sys.stderr)
                continue
            seen.add(rid)
            rows.append({"id": rid, "name": name, "source": fname})
    rows.sort(key=lambda r: (r["id"][0], int(r["id"][2:])))
    return rows


def main() -> int:
    reqs = read_requirements()
    api_text = (HERE / API_FILE).read_text(encoding="utf-8")
    sql_text = (HERE / SQL_FILE).read_text(encoding="utf-8")
    api_ids = set(re.findall(r"\b([A-Z]-\d{3})\b", api_text))
    sql_ids = set(re.findall(r"\b([A-Z]-\d{3})\b", sql_text))
    all_ids = {r["id"] for r in reqs}

    orphans = sorted(api_ids - all_ids)
    if orphans:
        print(f"EROARE: API-ul trimite la cerinte inexistente: {orphans}",
              file=sys.stderr)
        return 1

    out = HERE / OUT_CSV
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow([
            "ID cerinta", "Modul", "Denumire", "ID test", "Nivel",
            "Prioritate", "Acoperit in API", "Impus in schema BD",
            "Fisier specificatie",
        ])
        for r in reqs:
            rid = r["id"]
            letter = rid[0]
            w.writerow([
                rid,
                MODULE_NAMES[letter],
                r["name"],
                "T-" + rid.replace("-", ""),
                DEFAULT_LEVEL[letter],
                "1" if rid in CRITICAL else "2",
                "da" if rid in api_ids else "nu",
                "da" if rid in sql_ids else "nu",
                r["source"],
            ])

    # --- raport ---
    print(f"Matrice scrisa in {OUT_CSV}")
    print(f"Cerinte: {len(reqs)}")
    print(f"Teste generate: {len(reqs)} (unul per cerinta, 1:1)")
    print(f"Prioritate 1 (critice): {sum(1 for r in reqs if r['id'] in CRITICAL)}")
    print(f"Acoperite de o semnatura din API: {len(all_ids & api_ids)}")
    print(f"Impuse si de schema bazei de date: {len(all_ids & sql_ids)}")
    lvl = Counter(DEFAULT_LEVEL[r["id"][0]] for r in reqs)
    print("Pe nivel de test: "
          f"unitar={lvl['U']}, integrare={lvl['I']}, "
          f"end-to-end={lvl['E']}, manual={lvl['M']}")
    missing_critical = sorted(CRITICAL - all_ids)
    if missing_critical:
        print(f"EROARE: cerinte marcate critice care nu exista: "
              f"{missing_critical}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
