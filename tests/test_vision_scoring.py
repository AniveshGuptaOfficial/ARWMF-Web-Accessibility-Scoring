"""Vision scoring unit tests (D1-D3)."""
import numpy as np
import pytest

from arwmf.vision import (
    clutter_score_from_edge_density,
    contrast_ratio,
    dimension_contrast,
    dimension_target_size,
    element_contrast_score,
    element_target_score,
    parse_color,
    relative_luminance,
    structure_score,
)


def test_known_contrast_values():
    # White on black is the WCAG maximum
    assert contrast_ratio((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0, abs=0.01)
    # White on white is the minimum
    assert contrast_ratio((255, 255, 255), (255, 255, 255)) == pytest.approx(1.0)
    # #777777 on white is the canonical borderline case (~4.48:1)
    assert contrast_ratio((0x77, 0x77, 0x77), (255, 255, 255)) == pytest.approx(4.48, abs=0.02)
    # #767676 on white is the canonical pass (~4.54:1)
    assert contrast_ratio((0x76, 0x76, 0x76), (255, 255, 255)) > 4.5


def test_relative_luminance_endpoints():
    assert relative_luminance((255, 255, 255)) == pytest.approx(1.0)
    assert relative_luminance((0, 0, 0)) == pytest.approx(0.0)


def test_parse_color_formats():
    assert parse_color("#ff0000") == (255, 0, 0, 1.0)
    assert parse_color("#f00") == (255, 0, 0, 1.0)
    assert parse_color("rgb(0, 128, 255)") == (0, 128, 255, 1.0)
    assert parse_color("rgba(0, 0, 0, 0.5)")[3] == pytest.approx(0.5)
    assert parse_color("transparent") is None
    assert parse_color("") is None


def test_element_contrast_partial_credit():
    # #777 on white: ratio 4.48 vs required 4.5 -> just under, ~99.5
    el = {"fg": "#777777", "bg": "#ffffff", "font_px": 16, "bold": False,
          "visible": True, "rect": {"w": 100, "h": 20}}
    score = element_contrast_score(el)
    assert score is not None and 95 < score < 100
    # truly failing: #aaa on white (~2.3:1 vs 4.5)
    el["fg"] = "#aaaaaa"
    assert element_contrast_score(el) < 60


def test_large_text_threshold():
    # Large text only needs 3:1; #949494 on white is ~3:1
    fg = "#949494"
    small = {"fg": fg, "bg": "#ffffff", "font_px": 16, "bold": False, "visible": True}
    large = {"fg": fg, "bg": "#ffffff", "font_px": 26, "bold": False, "visible": True}
    assert element_contrast_score(small) < 75
    assert element_contrast_score(large) > 95


def test_invisible_and_unparseable_excluded():
    assert element_contrast_score({"fg": "#000", "bg": "#fff", "visible": False}) is None
    assert element_contrast_score({"fg": "inherit", "bg": "#fff", "visible": True,
                                   "rect": {"w": 1, "h": 1}}) is None
    assert dimension_contrast([]) is None


def test_dimension_contrast_weighted_mean():
    els = [
        # perfect hero text, huge
        {"fg": "#000000", "bg": "#ffffff", "font_px": 40, "bold": False,
         "visible": True, "rect": {"w": 1000, "h": 80}},
        # failing body text, small
        {"fg": "#cccccc", "bg": "#ffffff", "font_px": 14, "bold": False,
         "visible": True, "rect": {"w": 50, "h": 14}},
    ]
    score = dimension_contrast(els)
    assert score is not None
    # hero dominates: should be much closer to 100 than to the tiny element's ~30
    assert score > 70


def test_target_size():
    assert element_target_score({"rect": {"w": 48, "h": 48}, "visible": True}) == 100
    assert element_target_score({"rect": {"w": 12, "h": 24}, "visible": True}) == pytest.approx(50.0)
    assert element_target_score({"rect": {"w": 48, "h": 48}, "visible": True,
                                 "inline_exception": True}) is None
    assert dimension_target_size([{"rect": {"w": 0, "h": 0}, "visible": True}]) is None


def test_structure_penalties():
    good = {"h1_count": 1, "heading_levels": [1, 2, 3], "has_main": True,
            "has_nav": True, "nav_link_count": 5, "has_skip_link": False}
    assert structure_score(good) == 100
    bad = {"h1_count": 0, "heading_levels": [1, 3, 5], "has_main": False,
           "has_nav": False, "nav_link_count": 30, "has_skip_link": False}
    # 20 (no h1) + 15 (skip) + 15 (main) + 15 (nav) + 10 (skip-link) = 75 -> 25
    assert structure_score(bad) == 25


def test_clutter_monotone():
    assert clutter_score_from_edge_density(0.0) == 100
    assert clutter_score_from_edge_density(0.02) == 100
    assert clutter_score_from_edge_density(0.20) == 0
    assert clutter_score_from_edge_density(0.5) == 0
    lo = clutter_score_from_edge_density(0.15)
    hi = clutter_score_from_edge_density(0.05)
    assert lo < hi


def test_edge_density_on_synthetic_images():
    # flat image: zero edges
    flat = np.full((200, 200, 3), 200, dtype=np.uint8)
    from arwmf.vision import edge_density

    assert edge_density(flat) < 0.01
    # coarse checkerboard (10px cells survive the Canny Gaussian blur)
    block = 10
    yy, xx = np.indices((200, 200))
    checker = ((yy // block + xx // block) % 2 * 255).astype(np.uint8)
    checker = np.stack([checker] * 3, axis=-1)
    assert edge_density(checker) > 0.05
