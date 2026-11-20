"""Identificarea sesiunii curente si verificarea daca un proces mai traieste.

Folosit de curatarea temporarelor (Y-023) si de recuperare (Y-026), ca sa nu
atingem fisierele unei alte instante a aplicatiei care ruleaza in paralel.
"""

from __future__ import annotations

import os
import sys
import uuid


def new_session_id() -> str:
    """'<pid>-<hex>': procesul care detine sesiunea, plus un sufix unic."""
    return f"{os.getpid()}-{uuid.uuid4().hex[:12]}"


def session_pid(session_id: str) -> int | None:
    """PID-ul din id-ul de sesiune, sau None daca id-ul nu are forma asteptata."""
    head, sep, _ = session_id.partition("-")
    if not sep or not head.isdigit():
        return None
    return int(head)


def pid_alive(pid: int) -> bool:
    """True daca un proces cu acest PID ruleaza acum.

    Nu trimite niciun semnal care sa afecteze procesul. Un PID refolosit de alt
    program da un fals pozitiv: fisierele raman pana la urmatoarea pornire,
    ceea ce e sigur.
    """
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)  # semnalul 0 doar verifica existenta, pe POSIX
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exista, dar e al altui utilizator
    return True


def _pid_alive_windows(pid: int) -> bool:  # pragma: no cover - doar pe Windows
    # Pe Windows os.kill(pid, 0) ar OPRI procesul, deci folosim API-ul sistemului.
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED: exista
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)
