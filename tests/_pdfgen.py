"""Generator minimal de PDF-uri pentru teste, fara dependente.

Scrie pagini cu dreptunghiuri colorate si, optional, criptare standard RC4
pe 40 de biti (PDF 1.x, Security Handler revizia 2), ca sa testam parolele
fara o biblioteca in plus. Doar pentru teste: RC4 e slab si nu se foloseste
niciodata la scriere in produs (G-007).
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")
_P = -44
_ID = bytes(range(16))


def _rc4(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) % 256
        s[i], s[j] = s[j], s[i]
    out, i, j = bytearray(), 0, 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + s[i]) % 256
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) % 256])
    return bytes(out)


def _pad(pw: str) -> bytes:
    return (pw.encode("latin-1") + _PAD)[:32]


def make_pdf(
    path: Path,
    pages: list[tuple[float, float, tuple[float, float, float] | None]],
    *,
    version: str = "1.7",
    user_password: str | None = None,
    owner_password: str = "proprietar",
) -> Path:
    """`pages`: (latime_pt, inaltime_pt, culoare_dreptunghi sau None).

    Fiecare pagina cu culoare are un dreptunghi plin in jumatatea de jos-stanga.
    """
    key = o_value = u_value = None
    if user_password is not None:
        o_value = _rc4(hashlib.md5(_pad(owner_password)).digest()[:5], _pad(user_password))
        key = hashlib.md5(
            _pad(user_password) + o_value + struct.pack("<i", _P) + _ID
        ).digest()[:5]
        u_value = _rc4(key, _PAD)

    objects: dict[int, bytes] = {}
    n_pages = len(pages)
    page_ids = [3 + 2 * i for i in range(n_pages)]
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{p} 0 R" for p in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode()
    for i, (w, h, color) in enumerate(pages):
        pid, cid = page_ids[i], page_ids[i] + 1
        content = b""
        if color is not None:
            r, g, b = color
            content = f"{r} {g} {b} rg 0 0 {w / 2} {h / 2} re f".encode()
        if key is not None:
            obj_key = hashlib.md5(key + cid.to_bytes(3, "little") + b"\x00\x00").digest()[:10]
            content = _rc4(obj_key, content)
        objects[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] /Contents {cid} 0 R >>"
        ).encode()
        objects[cid] = f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
    encrypt_id = None
    if key is not None:
        encrypt_id = max(objects) + 1
        objects[encrypt_id] = (
            f"<< /Filter /Standard /V 1 /R 2 /O <{o_value.hex()}> /U <{u_value.hex()}>"
            f" /P {_P} >>"
        ).encode()

    out = bytearray(f"%PDF-{version}\n%\xe2\xe3\xcf\xd3\n".encode("latin-1"))
    offsets = {}
    for oid in sorted(objects):
        offsets[oid] = len(out)
        out += f"{oid} 0 obj\n".encode() + objects[oid] + b"\nendobj\n"
    xref = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for oid in range(1, size):
        out += f"{offsets[oid]:010d} 00000 n \n".encode()
    trailer = f"<< /Size {size} /Root 1 0 R /ID [<{_ID.hex()}><{_ID.hex()}>]"
    if encrypt_id is not None:
        trailer += f" /Encrypt {encrypt_id} 0 R"
    out += f"trailer\n{trailer} >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


A4 = (595.0, 842.0)
BLACK = (0, 0, 0)
RED = (1, 0, 0)
