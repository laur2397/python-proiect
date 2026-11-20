# Proba practica pentru SPEC_11 (E-500…E-512)

Scripturile cu care s-a verificat, pe 21.11.2026, ce se intampla cu semnaturile la unire. Nu sunt cod de produs: sunt referinta pentru implementarea din faza 8.

| Script | Ce arata |
|---|---|
| `poc.py` | creeaza un certificat de test si doua PDF-uri semnate; unirea clasica sterge semnaturile; portofoliul le pastreaza |
| `poc2.py` | paginile adaugate incremental: semnatura intacta, dar `modificat dupa semnare`; portofoliul semnat la randul lui: toate semnaturile valide |
| `poc3.py` | varianta hibrida (cuprins, copii de citire etichetate, originale atasate, sigiliu) — modelul din E-500…E-506 |

Se ruleaza in ordine, din acelasi folder gol: `poc.py` creeaza certificatele si fisierele folosite de celelalte. Cer `pyhanko`, `pikepdf`, `reportlab`, `cryptography`.
