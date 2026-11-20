"""Teste pentru app/core/errors.py (SPEC_05 sectiunea 2).

Verifica ca fiecare exceptie din contract exista in implementare, cu acelasi
nume, aceeasi baza si acelasi cod.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.core import errors
from app.core.errors import CoreError

SPEC_05 = Path(__file__).resolve().parent.parent / "docs" / "spec" / "SPEC_05_api_core.py"


def _contract_exceptions() -> dict[str, str]:
    """{nume clasa: cod} pentru toate exceptiile din SPEC_05, citite cu ast."""
    tree = ast.parse(SPEC_05.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
        if node.name != "CoreError" and "CoreError" not in bases:
            continue
        for stmt in node.body:
            targets = (
                [stmt.target] if isinstance(stmt, ast.AnnAssign)
                else stmt.targets if isinstance(stmt, ast.Assign) else []
            )
            if any(isinstance(t, ast.Name) and t.id == "code" for t in targets):
                out[node.name] = stmt.value.value  # type: ignore[union-attr]
    return out


CONTRACT = _contract_exceptions()


def test_contract_was_parsed():
    assert len(CONTRACT) == 42
    assert CONTRACT["CoreError"] == "CORE_ERROR"


@pytest.mark.parametrize(("name", "code"), sorted(CONTRACT.items()))
def test_exception_matches_contract(name, code):
    cls = getattr(errors, name, None)
    assert cls is not None, f"{name} lipseste din app/core/errors.py"
    assert issubclass(cls, CoreError)
    assert cls.code == code


def test_no_extra_exceptions_beyond_contract():
    implemented = {
        n for n, v in vars(errors).items() if isinstance(v, type) and issubclass(v, CoreError)
    }
    assert implemented == set(CONTRACT)


def test_codes_are_unique():
    assert len(set(CONTRACT.values())) == len(CONTRACT)


def test_params_are_kept_and_read_only():
    exc = errors.AreaTooSmallError("zona prea mica", w=4, h=4, min_size=8)
    assert dict(exc.params) == {"w": 4, "h": 4, "min_size": 8}
    assert exc.message == "zona prea mica"
    with pytest.raises(TypeError):
        exc.params["w"] = 100  # type: ignore[index]


def test_message_defaults_to_code():
    exc = errors.WrongPasswordError()
    assert str(exc) == "WRONG_PASSWORD"
    assert exc.params == {}


def test_T_U027_1_errors_can_be_caught_by_base_and_carry_code():
    """T-U027.1: CLI-ul mapeaza excepția la codul de iesire dupa `code`."""
    with pytest.raises(CoreError) as info:
        raise errors.OperationCancelledError()
    assert info.value.code == "CANCELLED"


def test_repr_shows_params():
    assert repr(errors.FileLockedError(path="a.pdf")) == "FileLockedError(path='a.pdf')"
