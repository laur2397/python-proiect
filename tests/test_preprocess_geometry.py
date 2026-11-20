"""Teste pentru uneltele geometrice din preprocess.py (faza 2, pasul 2c)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
from skimage import transform as sk_transform

from app.core.images.preprocess import (
    default_pipeline,
    detect_page_corners,
    detect_skew,
    find_gutter,
    is_bilevel,
    looks_like_facing_pages,
    motion_psf,
    to_array,
)
from app.core.model import PreprocessOp

PIPE = default_pipeline()
FONT = ImageFont.load_default(size=26)
TEXT = "Cerere de finantare nr. 4521 - Soseaua Tarii nr 7"


def tool(op):
    return PIPE.tool_for(op)


def page(w=850, h=1100, x0=60, lines=16, bg=245):
    img = Image.new("L", (w, h), bg)
    d = ImageDraw.Draw(img)
    for i in range(lines):
        d.text((x0, 80 + i * 60), TEXT, fill=0, font=FONT)
    return img


QUAD = [(260, 180), (1150, 240), (1220, 1350), (180, 1290)]


def photo_of_page(table=60):
    """Pagina fotografiata in perspectiva, pe o masa mai inchisa."""
    pg = np.asarray(page(), dtype=np.float64) / 255
    src = np.array([[0, 0], [849, 0], [849, 1099], [0, 1099]], dtype=np.float64)
    tform = sk_transform.ProjectiveTransform.from_estimate(np.array(QUAD, dtype=np.float64), src)
    out = sk_transform.warp(pg, tform, output_shape=(1500, 1400), cval=table / 255)
    return (out * 255).astype(np.uint8)


# =============================================================================
# X-023: marginile paginii
# =============================================================================


def test_T_X023_1_page_corners_are_found():
    """T-X023.1: colturile paginii fotografiate, cu cel mult 6 pixeli eroare."""
    found = detect_page_corners(photo_of_page())
    assert found is not None
    for (fx, fy), (x, y) in zip(found, QUAD, strict=True):
        assert abs(fx - x) <= 6 and abs(fy - y) <= 6


def test_T_X023_2_page_is_cut_out_and_straight():
    """T-X023.2: pagina e decupata din fotografie si adusa la dreptunghi."""
    out, meta = tool(PreprocessOp.DETECT_EDGES).apply(photo_of_page(), {})
    h, w = out.shape
    assert 1000 <= h <= 1200 and 850 <= w <= 1100
    assert len(meta["corners"]) == 4
    assert abs(detect_skew(out)) <= 0.3
    assert np.median(out[:40]) > 200  # sus e hartie, nu masa


@pytest.mark.parametrize("image", [
    np.full((300, 400), 255, np.uint8),  # doar hartie, fara masa
    np.full((300, 400), 30, np.uint8),  # doar masa
])
def test_no_page_found_leaves_image_alone(image):
    out, meta = tool(PreprocessOp.DETECT_EDGES).apply(image, {})
    assert meta["skipped"] == "no_page_found" and np.array_equal(out, image)


# =============================================================================
# L-014: trapezul
# =============================================================================


def test_T_L014_1_trapezoid_with_given_corners():
    """T-L014.1: cele patru colturi trase pe grila aduc pagina la dreptunghi."""
    out, meta = tool(PreprocessOp.TRAPEZOID).apply(photo_of_page(),
                                                   {"corners": [list(c) for c in QUAD]})
    assert abs(detect_skew(out)) <= 0.3
    assert meta["corners"][0] == [260.0, 180.0]


def test_trapezoid_detects_corners_when_not_given():
    out, meta = tool(PreprocessOp.TRAPEZOID).apply(photo_of_page(), {})
    assert "corners" in meta and out.shape[0] > 1000


@pytest.mark.parametrize("corners", [
    [[0, 0], [10, 0], [10, 10]],  # trei colturi
    [[0, 0], [1, 0], [1, 1], [0, 1]],  # prea mic
    [[0, 0], [5000, 0], [5000, 10], [0, 10]],  # in afara imaginii
    [[0, 0], ["a", 0], [1, 1], [0, 1]],
])
def test_trapezoid_rejects_bad_corners(corners):
    with pytest.raises(ValueError, match="trapezoid"):
        tool(PreprocessOp.TRAPEZOID).apply(np.full((100, 100), 200, np.uint8),
                                           {"corners": corners})


def test_trapezoid_keeps_bilevel():
    bw = np.where(photo_of_page() > 128, 255, 0).astype(np.uint8)
    out, _ = tool(PreprocessOp.TRAPEZOID).apply(bw, {"corners": [list(c) for c in QUAD]})
    assert is_bilevel(out)


# =============================================================================
# L-016, X-016: impartirea paginilor alaturate
# =============================================================================


@pytest.fixture
def spread():
    img = Image.new("L", (1700, 1100), 245)
    img.paste(page(), (0, 0))
    img.paste(page(), (850, 0))
    return to_array(img)


def test_T_X016_1_facing_pages_are_recognized(spread):
    """T-X016.1: doua pagini alaturate, nu o singura pagina."""
    assert looks_like_facing_pages(spread)
    assert not looks_like_facing_pages(to_array(page()))


def test_T_L016_1_split_at_the_gutter(spread):
    """T-L016.1: o pagina devine doua; taietura cade in spatiul dintre pagini."""
    parts, meta = tool(PreprocessOp.SPLIT).apply(spread, {})
    assert meta["pages"] == 2 and len(parts) == 2
    cut = meta["position"]
    assert find_gutter(spread) == cut
    ink = spread < 128
    assert not ink[:, cut - 5:cut + 5].any()  # niciun rand de text taiat
    assert parts[0].shape[1] + parts[1].shape[1] == spread.shape[1]


def test_split_vertical_and_horizontal_at_position():
    img = np.arange(100 * 60, dtype=np.uint32).reshape(100, 60).astype(np.uint8)
    (a, b), _ = tool(PreprocessOp.SPLIT).apply(img, {"position": 20})
    assert a.shape == (100, 20) and b.shape == (100, 40)
    (a, b), _ = tool(PreprocessOp.SPLIT).apply(img, {"mode": "horizontal", "position": 30})
    assert a.shape == (30, 60) and b.shape == (70, 60)
    with pytest.raises(ValueError, match="split.position"):
        tool(PreprocessOp.SPLIT).apply(img, {"position": 60})


def test_split_on_a_drawn_line():
    img = np.full((100, 200), 255, np.uint8)
    img[:, :90] = 10  # stanga inchisa
    parts, meta = tool(PreprocessOp.SPLIT).apply(
        img, {"mode": "line", "line": [[100, 0], [100, 99]]})
    assert len(parts) == 2 and meta["pages"] == 2
    widths = sorted(p.shape[1] for p in parts)
    assert widths[0] + widths[1] in (199, 200, 201)


@pytest.mark.parametrize("params", [{"mode": "line"}, {"mode": "line", "line": [[5, 5], [5, 5]]},
                                    {"mode": "diagonal"}])
def test_split_line_validation(params):
    with pytest.raises(ValueError, match="split"):
        tool(PreprocessOp.SPLIT).apply(np.full((50, 50), 200, np.uint8), params)


# =============================================================================
# L-012: randurile curbate
# =============================================================================


def _curved(amount=25.0):
    flat = to_array(page(900, 1100, x0=40))
    h, w = flat.shape
    xs = np.arange(w)
    lift = amount * ((xs - w / 2) / (w / 2)) ** 2
    yy, xx = np.mgrid[0:h, 0:w]
    bent = ndi.map_coordinates(flat.astype(float), [yy - lift[None, :], xx], order=1, cval=245)
    return flat, bent.astype(np.uint8)


def _agreement(img):
    """Cat de bine se potrivesc randurile din stanga cu cele din centru."""
    ink = img < 128
    return float(np.corrcoef(ink[:, 60:200].mean(1), ink[:, 400:540].mean(1))[0, 1])


def test_T_L012_1_curved_lines_are_straightened():
    """T-L012.1: randurile curbate redevin drepte (aproape ca pagina plata)."""
    flat, bent = _curved()
    assert _agreement(bent) < 0.3
    out, meta = tool(PreprocessOp.STRAIGHTEN_LINES).apply(bent, {})
    assert meta["max_offset"] > 5
    assert _agreement(out) > 0.9 * _agreement(flat)


def test_straight_page_is_left_alone():
    flat = to_array(page(900, 1100, x0=40))
    out, meta = tool(PreprocessOp.STRAIGHTEN_LINES).apply(flat, {})
    assert meta["max_offset"] == 0.0 and np.array_equal(out, flat)


def test_straighten_tiny_and_blank_images():
    for img in (np.full((10, 10), 255, np.uint8), np.full((300, 300), 255, np.uint8)):
        out, meta = tool(PreprocessOp.STRAIGHTEN_LINES).apply(img, {})
        assert meta["max_offset"] == 0.0 and np.array_equal(out, img)


# =============================================================================
# X-026: neclaritatea de miscare
# =============================================================================


def _ink_overlap(img, ref):
    a, b = img < 128, ref < 128
    return float((a & b).sum() / (a | b).sum())


def test_T_X026_1_motion_blur_is_reduced():
    """T-X026.1: cu miscarea cunoscuta, textul redevine mai clar."""
    clean = to_array(page(500, 400, lines=5))
    blurred = np.clip(ndi.convolve(clean.astype(float), motion_psf(9, 0), mode="nearest"),
                      0, 255).astype(np.uint8)
    out, meta = tool(PreprocessOp.DEBLUR).apply(blurred, {"length": 9, "angle": 0.0})
    assert meta["method"] == "richardson_lucy"
    assert _ink_overlap(out, clean) > _ink_overlap(blurred, clean) + 0.15


def test_deblur_without_motion_sharpens():
    img = to_array(page(300, 200, lines=2))
    out, meta = tool(PreprocessOp.DEBLUR).apply(np.stack([img] * 3, axis=-1), {})
    assert meta["method"] == "unsharp" and out.shape == (200, 300, 3)


def test_motion_psf_is_normalised_and_oriented():
    psf = motion_psf(9, 0)
    assert psf.sum() == pytest.approx(1.0) and psf.shape == (9, 9)
    assert psf[4].sum() == pytest.approx(1.0)  # orizontal
    assert motion_psf(9, 90)[:, 4].sum() == pytest.approx(1.0)  # vertical
