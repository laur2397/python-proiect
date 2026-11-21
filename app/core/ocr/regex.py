"""Expresiile regulate ale limbilor proprii (faza 4b, pasul 4b.1): Z-020..Z-030.

O limba proprie poate avea ca dictionar o expresie regulata (P-022, P-025):
un cuvant recunoscut e „din dictionar” daca se potriveste intreg cu ea. Se
folosesc pentru campuri ca data sau adresa de e-mail (Z-030).

Dialectul (SPEC_03 sectiunea Z.2), tradus in `re` din Python:

| Simbol | Inteles |
|---|---|
| `.` | orice caracter (Z-020) |
| `[ ]` | un caracter din grup, cu intervale `a-z` (Z-021, Z-027) |
| `[^ ]` | un caracter din afara grupului (Z-022) |
| `|` | sau (Z-023) |
| `*` | zero sau mai multe repetari (Z-024) |
| `+` | una sau mai multe repetari (Z-025) |
| `\\d`, `\\a`, `\\U`, `\\L` | cifra, litera, majuscula, minuscula (Z-026) |
| `@` | rezervat (Z-028) |
| `\\x` | caracterul x, ca literal (Z-029) |

[DECIZIE AUTONOMA] Numele claselor (`\\d`, `\\a`, `\\U`, `\\L`) sunt ale
noastre: SPEC_03 cere „clase predefinite pentru litere si cifre” fara sa le
numeasca. Intervalele latine si chirilice se scriu ca in orice grup:
`[a-z]`, `[A-Z]`, `[а-я]`, `[А-Я]` (majusculele si minusculele separat).
`@` neevadat e o eroare; `\\@` e caracterul @ (Z-029: caracterele speciale se
evadeaza), ca sa se poata scrie o adresa de e-mail. Parantezele si celelalte
semne nelistate sunt literali.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache

SPECIAL = set(".[]^|*+\\@")


@cache
def _letters(category: str) -> str:
    """Clasa de caractere (fara paranteze) cu literele latine, grecesti si
    chirilice din categoria Unicode data ('L' = toate literele)."""
    chars = [chr(c) for c in range(0x41, 0x530)
             if unicodedata.category(chr(c)).startswith(category)]
    return "".join(re.escape(ch) for ch in chars)


_CLASSES = {
    "d": lambda: "0-9",
    "a": lambda: _letters("L"),
    "U": lambda: _letters("Lu"),
    "L": lambda: _letters("Ll"),
}


def translate(expression: str) -> str:
    """Expresia din dialectul nostru, ca sablon `re`. Arunca ValueError cu
    pozitia si motivul daca nu e corecta (P-025, Z-030)."""
    out: list[str] = []
    i, n = 0, len(expression)
    if not expression:
        raise ValueError("expresia e goala")
    while i < n:
        ch = expression[i]
        if ch == "@":
            raise ValueError(f"pozitia {i + 1}: „@” e rezervat (Z-028); scrieti „\\@”")
        if ch == "\\":
            out.append(_escape(expression, i))
            i += 2
            continue
        if ch == "[":
            part, i = _group(expression, i)
            out.append(part)
            continue
        if ch == "]":
            raise ValueError(f"pozitia {i + 1}: „]” fara „[”")
        if ch in "|*+.":
            if ch in "*+" and (not out or out[-1] in ("|", "*", "+")):
                raise ValueError(f"pozitia {i + 1}: „{ch}” nu repeta nimic")
            out.append(ch)
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def _escape(expression: str, i: int) -> str:
    if i + 1 >= len(expression):
        raise ValueError(f"pozitia {i + 1}: „\\” la sfarsitul expresiei")
    nxt = expression[i + 1]
    if nxt in _CLASSES:
        return f"[{_CLASSES[nxt]()}]"
    return re.escape(nxt)


def _group(expression: str, start: int) -> tuple[str, int]:
    """Un grup `[...]` sau `[^...]`; intoarce (sablon, pozitia de dupa `]`)."""
    i = start + 1
    negate = i < len(expression) and expression[i] == "^"
    if negate:
        i += 1
    parts: list[str] = []
    while i < len(expression) and expression[i] != "]":
        ch = expression[i]
        if ch == "@":
            raise ValueError(f"pozitia {i + 1}: „@” e rezervat (Z-028); scrieti „\\@”")
        if ch == "\\":
            if i + 1 >= len(expression):
                break
            nxt = expression[i + 1]
            parts.append(_CLASSES[nxt]() if nxt in _CLASSES else re.escape(nxt))
            i += 2
            continue
        if (ch == "-" and parts and i + 1 < len(expression)
                and expression[i + 1] not in "]\\"):
            lo, hi = expression[i - 1], expression[i + 1]
            if lo > hi:
                raise ValueError(f"pozitia {i + 1}: intervalul „{lo}-{hi}” e inversat")
            parts.append("-" + re.escape(hi))
            i += 2
            continue
        parts.append(re.escape(ch))
        i += 1
    if i >= len(expression):
        raise ValueError(f"pozitia {start + 1}: „[” fara „]”")
    if not parts:
        raise ValueError(f"pozitia {start + 1}: grup gol")
    return f"[{'^' if negate else ''}{''.join(parts)}]", i + 1


# P-025, Z-030
def compile_expression(expression: str) -> re.Pattern[str]:
    """Expresia compilata, sau ValueError cu mesajul erorii."""
    pattern = translate(expression)
    try:
        return re.compile(pattern)
    except re.error as exc:  # pragma: no cover - translate prinde aproape tot
        raise ValueError(f"expresia nu compileaza: {exc}") from exc


def matches(expression: str | re.Pattern[str], word: str) -> bool:
    """Cuvantul intreg se potriveste cu expresia (Z-030)."""
    pattern = expression if isinstance(expression, re.Pattern) else compile_expression(
        expression)
    return pattern.fullmatch(word) is not None
