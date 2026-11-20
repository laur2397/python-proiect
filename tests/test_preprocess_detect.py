"""Teste pentru uneltele cu detectie din preprocess.py (faza 2, pasul 2b)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.images.preprocess import (
    DESKEW_MIN_ANGLE,
    default_pipeline,
    detect_skew,
    has_white_background,
    is_bilevel,
    looks_inverted,
    to_array,
)
from app.core.model import PreprocessOp

PIPE = default_pipeline()
W, H = 1240, 1754  # A4 la 150 dpi


def tool(op):
    return PIPE.tool_for(op)


def text_page(bg=255, ink=0, mode="L", lines=25):
    """Pagina cu randuri de text adevarat (fontul implicit, marit)."""
    img = Image.new(mode, (W, H), bg if mode == "L" else (bg, bg, bg))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=28)
    fill = ink if mode == "L" else (ink, ink, ink)
    for i in range(lines):
        d.text((90, 120 + i * 60), "Cerere de finantare nr. 4521 din 12.03.2026 - Șoseaua Țării",
               fill=fill, font=font)
    return img


def rotated(img, angle, bg=255):
    fill = bg if img.mode == "L" else (bg, bg, bg)
    return to_array(img.rotate(angle, fillcolor=fill, resample=Image.Resampling.BILINEAR))


# =============================================================================
# L-011: indreptarea paginii
# =============================================================================


@pytest.mark.parametrize("angle", [3.0, -2.0, 0.6, -7.5, 12.0])
def test_T_L011_1_skew_is_detected(angle):
    """T-L011.1: unghiul de inclinare se detecteaza cu cel mult 0,15 grade eroare."""
    assert detect_skew(rotated(text_page(), angle)) == pytest.approx(angle, abs=0.15)


@pytest.mark.parametrize("angle", [4.0, -3.0])
def test_T_L011_2_deskew_straightens_the_page(angle):
    """T-L011.2: dupa indreptare, pagina e dreapta."""
    out, meta = tool(PreprocessOp.DESKEW).apply(rotated(text_page(), angle), {})
    assert meta["angle"] == pytest.approx(angle, abs=0.15)
    assert abs(detect_skew(out)) <= 0.15
    assert out.shape == (H, W)  # aceeasi dimensiune


def test_straight_and_blank_pages_are_left_alone():
    straight = to_array(text_page())
    out, meta = tool(PreprocessOp.DESKEW).apply(straight, {})
    assert abs(meta["angle"]) < DESKEW_MIN_ANGLE or meta["angle"] == 0.0
    blank = np.full((H, W), 255, np.uint8)
    out, meta = tool(PreprocessOp.DESKEW).apply(blank, {})
    assert meta["angle"] == 0.0 and np.array_equal(out, blank)


def test_deskew_with_given_angle_and_fill():
    page = rotated(text_page(bg=230), 5.0, bg=230)
    out, meta = tool(PreprocessOp.DESKEW).apply(page, {"angle": 5.0})
    assert meta["angle"] == 5.0
    assert out[0, 0] == pytest.approx(230, abs=2)  # colturile iau culoarea hartiei


def test_deskew_color_and_bilevel():
    color = rotated(text_page(mode="RGB"), 2.0)
    out, meta = tool(PreprocessOp.DESKEW).apply(color, {})
    assert out.shape == (H, W, 3) and meta["angle"] == pytest.approx(2.0, abs=0.15)
    bw = np.where(rotated(text_page(), 2.0) > 128, 255, 0).astype(np.uint8)
    out, _ = tool(PreprocessOp.DESKEW).apply(bw, {})
    assert is_bilevel(out)


@pytest.mark.parametrize("params", [{"angle": 46}, {"max_angle": 0.1}, {"angle": "3"}])
def test_deskew_parameters(params):
    with pytest.raises(ValueError, match="deskew"):
        tool(PreprocessOp.DESKEW).apply(np.full((10, 10), 255, np.uint8), params)


# =============================================================================
# X-028: culori inversate
# =============================================================================


def test_T_X028_1_inverted_page_is_fixed():
    """T-X028.1: pagina cu fundal negru si text alb se inverseaza automat."""
    inverted = to_array(text_page(bg=0, ink=255))
    assert looks_inverted(inverted)
    out, meta = tool(PreprocessOp.INVERT).apply(inverted, {"auto": True})
    assert meta["inverted"] is True and not looks_inverted(out)


def test_normal_page_is_not_inverted_automatically():
    page = to_array(text_page())
    out, meta = tool(PreprocessOp.INVERT).apply(page, {"auto": True})
    assert meta["inverted"] is False and np.array_equal(out, page)


def test_white_on_black_heading_does_not_invert_the_page():
    page = text_page()
    ImageDraw.Draw(page).rectangle((0, 0, W, int(H * 0.4)), fill=0)  # banda neagra mare
    assert not looks_inverted(to_array(page))


def test_manual_invert_is_unconditional():
    page = to_array(text_page())
    out, meta = tool(PreprocessOp.INVERT).apply(page, {})
    assert meta["inverted"] is True and np.array_equal(out, 255 - page)


# =============================================================================
# L-023: marcaje colorate
# =============================================================================


def _marked_scan(bg=(255, 255, 255)):
    page = text_page(mode="RGB", bg=255)
    if bg != (255, 255, 255):
        arr = to_array(page)
        arr[(arr == 255).all(axis=2)] = bg
        page = Image.fromarray(arr)
    d = ImageDraw.Draw(page)
    d.line((100, 900, 900, 950), fill=(20, 40, 200), width=6)  # pix albastru
    d.ellipse((800, 1300, 1100, 1550), outline=(200, 30, 30), width=10)  # stampila
    return to_array(page)


def test_T_L023_1_color_marks_are_removed_from_white_scans():
    """T-L023.1: pixul albastru si stampila rosie dispar; textul negru ramane."""
    scan = _marked_scan()
    out, meta = tool(PreprocessOp.REMOVE_COLOR_MARKS).apply(scan, {})
    assert meta["removed_pixels"] > 1000
    sat = out.max(axis=2).astype(int) - out.min(axis=2)
    assert (sat > 60).sum() == 0
    dark_before = (scan.max(axis=2) < 80).sum()
    dark_after = (out.max(axis=2) < 80).sum()
    assert dark_after >= dark_before * 0.95  # textul negru e pastrat


def test_T_L023_2_not_for_colored_backgrounds_or_photos():
    """T-L023.2: pe hartie colorata sau pe o fotografie unealta nu schimba nimic."""
    yellow = _marked_scan(bg=(250, 235, 140))
    assert not has_white_background(yellow)
    out, meta = tool(PreprocessOp.REMOVE_COLOR_MARKS).apply(yellow, {})
    assert meta["skipped"] == "background_not_white" and np.array_equal(out, yellow)
    gray = to_array(text_page())
    _, meta = tool(PreprocessOp.REMOVE_COLOR_MARKS).apply(gray, {})
    assert meta["skipped"] == "grayscale"


# =============================================================================
# X-024: albirea fundalului (fotografii)
# =============================================================================


def _unevenly_lit():
    """Fotografie de document: hartia trece de la gri inchis (stanga) la deschis."""
    page = to_array(text_page()).astype(np.float32)
    light = np.linspace(0.55, 0.95, W, dtype=np.float32)[None, :]
    return np.clip(page * light, 0, 255).astype(np.uint8)


def test_T_X024_1_background_becomes_white_and_even():
    """T-X024.1: hartia devine alba si uniforma; textul ramane inchis."""
    photo = _unevenly_lit()
    paper = photo > 100  # in fotografie, inainte
    out, _ = tool(PreprocessOp.WHITEN_BACKGROUND).apply(photo, {})
    left, right = out[400:1500, 40:80], out[400:1500, W - 80:W - 40]
    assert np.median(left) >= 240 and np.median(right) >= 240
    assert np.median(out[~paper]) < 90  # textul


def test_whiten_color_and_strength_zero():
    photo = np.stack([_unevenly_lit()] * 3, axis=-1)
    out, _ = tool(PreprocessOp.WHITEN_BACKGROUND).apply(photo, {})
    assert out.shape == photo.shape and np.median(out[:, :80]) >= 240
    same, _ = tool(PreprocessOp.WHITEN_BACKGROUND).apply(photo, {"strength": 0.0})
    assert np.abs(same.astype(int) - photo).max() <= 1


# =============================================================================
# X-025: zgomot ISO (fotografii)
# =============================================================================


def test_T_X025_1_noise_is_reduced_and_text_kept():
    """T-X025.1: punctele de zgomot dispar, literele raman."""
    clean = to_array(text_page())
    rng = np.random.default_rng(3)
    noisy = clean.copy()
    pts = rng.integers(0, noisy.size, 20_000)
    noisy.ravel()[pts[:10_000]] = 0
    noisy.ravel()[pts[10_000:]] = 255
    noise = noisy != clean
    out, meta = tool(PreprocessOp.DENOISE).apply(noisy, {})
    repaired = ((out == clean) & noise).sum() / noise.sum()
    assert repaired >= 0.80
    assert (out < 128).sum() >= 0.98 * (clean < 128).sum()  # literele raman
    damaged = ((out != clean) & ~noise).sum()
    assert damaged < 0.02 * (clean < 200).sum()  # aproape niciun pixel de text atins
    err_before = np.abs(noisy.astype(int) - clean).mean()
    err_after = np.abs(out.astype(int) - clean).mean()
    assert err_after < err_before / 3
    assert meta["replaced_pixels"] > 0


def test_denoise_color_and_sizes():
    rng = np.random.default_rng(1)
    img = rng.integers(0, 256, (60, 80, 3), dtype=np.uint8)
    out, _ = tool(PreprocessOp.DENOISE).apply(img, {"size": 5})
    assert out.shape == img.shape
    with pytest.raises(ValueError, match="denoise.size"):
        tool(PreprocessOp.DENOISE).apply(img, {"size": 4})
