"""Generator de PDF-uri cu strat de text (Helvetica) si, optional, o imagine."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def make_text_pdf(path: Path, lines: list[str], *, image: Image.Image | None = None,
                  image_box: tuple[float, float, float, float] = (72, 300, 450, 400)) -> Path:
    """A4. `lines` scrise de sus in jos cu Helvetica 14 (text ASCII).
    `image`: imagine gri desenata in `image_box` (x, y_jos, latime, inaltime) in puncte."""
    content = []
    for i, text in enumerate(lines):
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.append(f"BT /F1 14 Tf 72 {760 - i * 24} Td ({safe}) Tj ET")
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"}
    xobject = ""
    if image is not None:
        gray = image.convert("L")
        data = gray.tobytes()
        objs[6] = (f"<< /Type /XObject /Subtype /Image /Width {gray.width} /Height {gray.height}"
                   f" /ColorSpace /DeviceGray /BitsPerComponent 8 /Length {len(data)} >>\nstream\n"
                   ).encode() + data + b"\nendstream"
        x, y, w, h = image_box
        content.append(f"q {w} 0 0 {h} {x} {y} cm /Im1 Do Q")
        xobject = " /XObject << /Im1 6 0 R >>"
    stream = "\n".join(content).encode("latin-1")
    objs[4] = f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
    objs[3] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R"
               f" /Resources << /Font << /F1 5 0 R >>{xobject} >> >>").encode()
    out = bytearray(b"%PDF-1.7\n")
    offsets = {}
    for oid in sorted(objs):
        offsets[oid] = len(out)
        out += f"{oid} 0 obj\n".encode() + objs[oid] + b"\nendobj\n"
    xref = len(out)
    size = max(objs) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for oid in range(1, size):
        out += (f"{offsets[oid]:010d} 00000 n \n" if oid in offsets
                else "0000000000 65535 f \n").encode()
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path
