"""Sabloanele de caractere (faza 4b, pasul 4b.3): P-050..P-066.

`PatternStore` din SPEC_05, pe tabelele `char_pattern_set` si `char_pattern`
din app.db. Un sablon e un set de caractere antrenate: imaginea glifului
decupata din pagina si caracterul (sau perechea de caractere) pe care il
reprezinta (P-060).

[DECIZIE AUTONOMA] (faza_4b_pasi.md, decizia 2) Efectele (bold, italic,
exponent, indice, P-056), inaltimea glifului si rezolutia paginii (domeniul
din P-064) se scriu in blocuri de text ale PNG-ului (`glyph_image`); schema
SPEC_04 nu se schimba.

Aplicarea (P-050..P-052, P-064): cu `Use user patterns`, glifele cuvintelor
nesigure (fara `Also use built-in patterns`: ale tuturor cuvintelor) se
compara cu caracterele antrenate de aceeasi inaltime (±15%) si aceeasi
rezolutie (±5%); o potrivire buna inlocuieste caracterul.

INCOMPLET, marcat: glifele lipite intre ele (o singura pata pentru doua
litere) nu se separa; asemenea cuvinte raman cum le-a citit motorul.
"""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, PngImagePlugin
from scipy import ndimage as ndi

from app.core.errors import PatternLimitError, ProjectVersionError
from app.core.model import LanguageCode, Rect

EFFECTS = ("bold", "italic", "superscript", "subscript")
"""P-056: efectele care se pot inregistra la antrenare."""
ASIAN_SCRIPTS = ("cjk", "thai")
"""P-059: antrenarea nu e suportata pentru limbile asiatice."""
BUNDLE_SUFFIX = ".fbtx"
BUNDLE_VERSION = 1
MATCH_MIN = 0.85
"""[DECIZIE AUTONOMA] Asemanarea minima (corelatie normalizata) a unui glif."""
_SIZE = 24
"""Latura la care se compara glifele."""


@dataclass(slots=True)
class TrainedChar:
    id: int
    character: str
    effects: tuple[str, ...]
    height: int
    dpi: int
    image: Image.Image


def _info(image: Image.Image) -> dict[str, str]:
    return dict(getattr(image, "text", {}) or {})


# SPEC_05 sect. 7. P-050..P-066
class PatternStore:
    MAX_CHARS_PER_SET: int = 1000

    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    # --- seturile (P-053, P-054, P-061, P-063) ----------------------------------------

    def sets(self) -> list[str]:
        return [r[0] for r in self._con.execute("SELECT name FROM char_pattern_set ORDER BY name")]

    def active_set(self) -> str | None:
        row = self._con.execute("SELECT name FROM char_pattern_set WHERE is_active = 1").fetchone()
        return None if row is None else str(row[0])

    def set_active(self, name: str) -> None:
        """P-061: un singur sablon activ (triggerul din SPEC_04 il dezactiveaza
        pe cel vechi)."""
        self._set_id(name)
        with self._con:
            self._con.execute("UPDATE char_pattern_set SET is_active = 1 WHERE name = ?", (name,))

    def create_set(self, name: str, language: LanguageCode | None = None) -> None:
        """P-054. P-059: nu pentru limbile asiatice."""
        from app.core.ocr.languages import LanguageRegistry, script_of

        name = (name or "").strip()
        if not name:
            raise ValueError("sablonul are nevoie de un nume")
        if name in self.sets():
            raise ValueError(f"exista deja un sablon {name!r}")
        language_id = None
        if language is not None:
            if script_of(language) in ASIAN_SCRIPTS:
                raise ValueError("antrenarea nu e suportata pentru limbile asiatice (P-059)")
            language_id = LanguageRegistry(con=self._con)._language_id(language)
        with self._con:
            self._con.execute("INSERT INTO char_pattern_set (name, language_id) VALUES (?, ?)",
                              (name, language_id))

    def delete_set(self, name: str) -> None:
        """Sablonul activ nu se sterge (SPEC_05)."""
        if self.active_set() == name:
            raise ValueError("sablonul activ nu se poate sterge; activati altul intai")
        sid = self._set_id(name)
        with self._con:
            self._con.execute("DELETE FROM char_pattern_set WHERE id = ?", (sid,))

    # --- caracterele (P-055..P-060, P-062, P-063) --------------------------------------

    def add_pattern(self, set_name: str, glyph_png: bytes, character: str, *,
                    effects: Sequence[str] = (), dpi: int = 300) -> int:
        """P-055: un caracter antrenat. P-058: peste 1000 → PatternLimitError.
        P-060: unul sau doua caractere, fara spatii. Intoarce id-ul lui."""
        sid = self._set_id(set_name)
        character = _check_character(character)
        clean = _check_effects(effects)
        with Image.open(io.BytesIO(glyph_png)) as img:
            image = img.convert("L")
        data = _png(image, clean, image.height, dpi)
        count = self._con.execute("SELECT COUNT(*) FROM char_pattern WHERE pattern_set_id = ?",
                                  (sid,)).fetchone()[0]
        if count >= self.MAX_CHARS_PER_SET:
            raise PatternLimitError("sablonul a atins 1000 de caractere", pattern_set=set_name,
                                    limit=self.MAX_CHARS_PER_SET)
        try:
            with self._con:
                cur = self._con.execute(
                    "INSERT INTO char_pattern (pattern_set_id, glyph_image, character)"
                    " VALUES (?, ?, ?)", (sid, data, character))
        except sqlite3.IntegrityError as exc:  # triggerul char_pattern_limit
            raise PatternLimitError("sablonul a atins 1000 de caractere", pattern_set=set_name,
                                    limit=self.MAX_CHARS_PER_SET) from exc
        return int(cur.lastrowid)

    def train(self, set_name: str, image_path: Path, box: Rect, character: str, *,
              effects: Sequence[str] = (), dpi: int = 300) -> int:
        """P-055: decupeaza glifului din imaginea paginii si il antreneaza."""
        with Image.open(image_path) as src:
            crop = src.convert("L").crop((box.x, box.y, box.right, box.bottom))
        out = io.BytesIO()
        crop.save(out, "PNG")
        return self.add_pattern(set_name, out.getvalue(), character, effects=effects, dpi=dpi)

    def characters(self, set_name: str) -> list[TrainedChar]:
        sid = self._set_id(set_name)
        out = []
        for cid, data, character in self._con.execute(
                "SELECT id, glyph_image, character FROM char_pattern WHERE pattern_set_id = ?"
                " ORDER BY id", (sid,)):
            image = Image.open(io.BytesIO(data))
            image.load()
            info = _info(image)
            out.append(TrainedChar(
                int(cid), str(character),
                tuple(e for e in info.get("effects", "").split(",") if e),
                int(info.get("height", image.height)), int(info.get("dpi", 300)),
                image.convert("L")))
        return out

    def edit(self, char_id: int, *, character: str | None = None,
             effects: Sequence[str] | None = None) -> None:
        """P-062: `Properties...` cu `Character` si `Effects`."""
        row = self._con.execute("SELECT glyph_image, character FROM char_pattern WHERE id = ?",
                                (char_id,)).fetchone()
        if row is None:
            raise ValueError(f"caracterul {char_id} nu exista")
        image = Image.open(io.BytesIO(row[0]))
        image.load()
        info = _info(image)
        new_effects = (_check_effects(effects) if effects is not None
                       else tuple(e for e in info.get("effects", "").split(",") if e))
        data = _png(image.convert("L"), new_effects, int(info.get("height", image.height)),
                    int(info.get("dpi", 300)))
        new_char = _check_character(character) if character is not None else row[1]
        with self._con:
            self._con.execute("UPDATE char_pattern SET character = ?, glyph_image = ? WHERE id = ?",
                              (new_char, data, char_id))

    def delete_pattern(self, char_id: int) -> None:
        """P-063."""
        with self._con:
            self._con.execute("DELETE FROM char_pattern WHERE id = ?", (char_id,))

    # --- P-065, P-066: sabloane si limbi in acelasi fisier ------------------------------

    def save_bundle(self, path: Path) -> None:
        """Fisierul `*.fbtx` (al nostru, decizia 3): sabloanele si limbile proprii."""
        from app.core.ocr.languages import LanguageRegistry

        path = Path(path)
        if path.suffix.lower() != BUNDLE_SUFFIX:
            raise ValueError(f"fisierul de sabloane si limbi are extensia {BUNDLE_SUFFIX}")
        registry = LanguageRegistry(con=self._con)
        manifest: dict[str, Any] = {
            "format": "doculens-patterns", "version": BUNDLE_VERSION,
            "languages": registry.export_user_languages(registry.user_languages()),
            "sets": [],
        }
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for index, name in enumerate(self.sets()):
                active, language = self._con.execute(
                    "SELECT s.is_active, l.code FROM char_pattern_set s LEFT JOIN ocr_language l"
                    " ON l.id = s.language_id WHERE s.name = ?", (name,)).fetchone()
                chars = []
                for i, (data, character) in enumerate(self._con.execute(
                        "SELECT p.glyph_image, p.character FROM char_pattern p"
                        " JOIN char_pattern_set s ON s.id = p.pattern_set_id"
                        " WHERE s.name = ? ORDER BY p.id", (name,)).fetchall()):
                    file = f"sets/{index}/{i}.png"
                    z.writestr(file, data)
                    chars.append({"character": character, "file": file})
                manifest["sets"].append({"name": name, "active": bool(active),
                                         "language": language, "chars": chars})
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))

    def load_bundle(self, path: Path, *, patterns: bool = True, languages: bool = True) -> None:
        """P-066 (`Load Options`): sabloanele si/sau limbile din fisier. Un
        sablon cu acelasi nume se inlocuieste. Fisier dintr-o versiune mai noua
        → `ProjectVersionError`; `*.fbt` (ABBYY) → ValueError."""
        from app.core.ocr.languages import LanguageRegistry

        path = Path(path)
        if path.suffix.lower() == ".fbt":
            raise ValueError("fisierele *.fbt ale altor programe nu se pot citi (format "
                             "nedocumentat); folositi *.fbtx")
        try:
            z = zipfile.ZipFile(path)
        except zipfile.BadZipFile as exc:
            raise ValueError("fisierul nu e un fisier de sabloane si limbi") from exc
        with z:
            try:
                manifest = json.loads(z.read("manifest.json"))
            except KeyError as exc:
                raise ValueError("fisierul nu e un fisier de sabloane si limbi") from exc
            if manifest.get("format") != "doculens-patterns":
                raise ValueError("fisierul nu e un fisier de sabloane si limbi")
            if int(manifest.get("version", 0)) > BUNDLE_VERSION:
                raise ProjectVersionError("fisierul e dintr-o versiune mai noua",
                                          path=str(path), version=manifest.get("version"))
            if languages:
                LanguageRegistry(con=self._con).import_user_languages(manifest["languages"])
            if not patterns:
                return
            for item in manifest["sets"]:
                if item["name"] in self.sets():
                    with self._con:
                        self._con.execute("DELETE FROM char_pattern_set WHERE name = ?",
                                          (item["name"],))
                self.create_set(item["name"], item.get("language"))
                sid = self._set_id(item["name"])
                with self._con:
                    self._con.executemany(
                        "INSERT INTO char_pattern (pattern_set_id, glyph_image, character)"
                        " VALUES (?, ?, ?)",
                        [(sid, z.read(c["file"]), c["character"]) for c in item["chars"]])
                if item.get("active"):
                    self.set_active(item["name"])

    def _set_id(self, name: str) -> int:
        row = self._con.execute("SELECT id FROM char_pattern_set WHERE name = ?",
                                (name,)).fetchone()
        if row is None:
            raise ValueError(f"sablonul {name!r} nu exista")
        return int(row[0])


def _check_character(character: str) -> str:
    """P-060: un caracter sau o combinatie de doua, fara spatii."""
    if not character or len(character) > 2 or any(ch.isspace() for ch in character):
        raise ValueError("un caracter antrenat are unul sau doua caractere, fara spatii (P-060)")
    return character


def _check_effects(effects: Sequence[str]) -> tuple[str, ...]:
    bad = set(effects) - set(EFFECTS)
    if bad:
        raise ValueError(f"efecte necunoscute: {sorted(bad)}; permise: {EFFECTS}")
    if {"superscript", "subscript"} <= set(effects):
        raise ValueError("un caracter nu poate fi si exponent, si indice")
    return tuple(e for e in EFFECTS if e in effects)


def _png(image: Image.Image, effects: Sequence[str], height: int, dpi: int) -> bytes:
    info = PngImagePlugin.PngInfo()
    info.add_text("effects", ",".join(effects))
    info.add_text("height", str(height))
    info.add_text("dpi", str(dpi))
    out = io.BytesIO()
    image.save(out, "PNG", pnginfo=info)
    return out.getvalue()


# --- aplicarea (P-050..P-052, P-064) ---------------------------------------------------


def _ink(gray: np.ndarray) -> np.ndarray:
    from app.core.images.preprocess import otsu_threshold

    if gray.size == 0 or int(gray.max()) == int(gray.min()):
        return np.zeros(gray.shape, bool)
    return gray < otsu_threshold(gray)


def glyph_boxes(page_image: np.ndarray, box: Rect) -> list[Rect]:
    """P-055, P-057: caracterele unui cuvant (componentele conexe ale cernelii din
    caseta lui), de la stanga la dreapta, in coordonatele paginii. Componentele
    suprapuse pe orizontala (punctul lui i, virgula lui ș) se unesc cu litera."""
    x0, y0 = max(0, int(box.x)), max(0, int(box.y))
    crop = page_image[y0:int(box.bottom), x0:int(box.right)]
    mask = _ink(crop if crop.ndim == 2 else crop.mean(axis=2).astype(np.uint8))
    labels, _count = ndi.label(mask, structure=np.ones((3, 3), bool))
    spans: list[list[int]] = []
    for sl in sorted((s for s in ndi.find_objects(labels) if s is not None),
                     key=lambda s: s[1].start):
        left, right, top, bottom = sl[1].start, sl[1].stop, sl[0].start, sl[0].stop
        if spans and left < spans[-1][1] - 1:  # acelasi caracter (diacritic, punct)
            last = spans[-1]
            last[:] = [min(last[0], left), max(last[1], right), min(last[2], top),
                       max(last[3], bottom)]
        else:
            spans.append([left, right, top, bottom])
    return [Rect(x0 + a, y0 + t, b - a, d - t) for a, b, t, d in spans]


def _normalized(mask: np.ndarray) -> np.ndarray:
    """Glif binar adus la _SIZE x _SIZE, centrat, ca vector normalizat."""
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return np.zeros(_SIZE * _SIZE)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
    side = max(crop.shape)
    square = np.zeros((side, side), np.uint8)
    oy, ox = (side - crop.shape[0]) // 2, (side - crop.shape[1]) // 2
    square[oy:oy + crop.shape[0], ox:ox + crop.shape[1]] = crop
    small = np.asarray(Image.fromarray(square).resize((_SIZE, _SIZE), Image.Resampling.BOX),
                       dtype=float).ravel()
    small -= small.mean()
    norm = np.linalg.norm(small)
    return small / norm if norm else small


def _height(mask: np.ndarray) -> int:
    rows = np.nonzero(mask.any(axis=1))[0]
    return int(rows[-1] - rows[0] + 1) if rows.size else 0


@dataclass(slots=True)
class PatternMatcher:
    """Caracterele sablonului activ, pregatite pentru comparare."""

    chars: list[tuple[TrainedChar, np.ndarray]]

    @classmethod
    def from_store(cls, store: PatternStore) -> PatternMatcher | None:
        name = store.active_set()
        if name is None:
            return None
        chars = []
        for c in store.characters(name):
            mask = _ink(np.asarray(c.image))
            c.height = _height(mask) or c.height
            chars.append((c, _normalized(mask)))
        return cls(chars) if chars else None

    def best(self, glyph: np.ndarray, dpi: int) -> tuple[str, float] | None:
        """P-064: numai caracterele de aceeasi inaltime si rezolutie."""
        height = _height(glyph)
        vector = _normalized(glyph)
        found: tuple[str, float] | None = None
        for char, ref in self.chars:
            if abs(char.dpi - dpi) > 0.05 * char.dpi:
                continue
            if abs(char.height - height) > 0.15 * max(char.height, 1):
                continue
            score = float(vector @ ref)
            if found is None or score > found[1]:
                found = (char.character, score)
        return found if found is not None and found[1] >= MATCH_MIN else None

    def apply(self, page_image: np.ndarray, words: Sequence[Any], dpi: int,
              all_words: bool = False) -> int:
        """Reciteste cu sablonul cuvintele nesigure (sau toate). Intoarce cate
        cuvinte s-au schimbat."""
        changed = 0
        for word in words:
            if not (all_words or word.is_uncertain):
                continue
            b = word.bbox
            mask = _ink(page_image[max(0, b.y):b.bottom, max(0, b.x):b.right])
            labels, count = ndi.label(mask, structure=np.ones((3, 3), bool))
            if count == 0:
                continue
            glyphs = sorted(((sl, i) for i, sl in enumerate(ndi.find_objects(labels), start=1)
                             if sl is not None), key=lambda item: item[0][1].start)
            found = [self.best(labels[sl] == i, dpi) for sl, i in glyphs]
            if all(found):
                text = "".join(f[0] for f in found if f)
            elif len(found) == len(word.text):
                text = "".join(f[0] if f else ch for f, ch in zip(found, word.text, strict=True))
            else:
                continue
            if all(found):
                word.confidence = round(100 * min(f[1] for f in found if f), 1)
                word.is_uncertain = False
            if text != word.text or not word.is_uncertain:
                word.text = text
                changed += 1
        return changed
