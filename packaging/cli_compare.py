"""Punctul de intrare al executabilului de consola `DocuLensCompare`
(faza 14, pasul 14.3; faza_14_pasi.md decizia 1). Spune nucleului unde e
Tesseract-ul livrat, apoi da comanda liniei de comanda (`app.cli.main`)."""

from __future__ import annotations

import sys

from doculens_launcher import _use_bundled_tesseract

from app.cli.main import compare_entry

if __name__ == "__main__":
    _use_bundled_tesseract()
    sys.exit(compare_entry())
