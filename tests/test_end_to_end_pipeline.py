"""End-to-end smoke test: capture fixtures -> score -> ordering sanity.

Requires chromium (`python -m playwright install chromium`) and network on the
FIRST run only (model download into HF cache). Skips cleanly otherwise.
Marked slow: full stack + models.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _chromium_available() -> bool:
    """True if any usable browser exists: bundled Chromium, system Chrome, or Edge."""
    import os

    from playwright.sync_api import sync_playwright

    candidates = [None, os.environ.get("A11Y_BROWSER_CHANNEL") or None,
                  "chrome", "msedge"]
    with sync_playwright() as p:
        for ch in candidates:
            try:
                b = p.chromium.launch(headless=True, channel=ch)
                b.close()
                if ch:
                    os.environ["A11Y_BROWSER_CHANNEL"] = ch
                return True
            except Exception:
                continue
    return False


pytestmark = pytest.mark.skipif(
    not _chromium_available(),
    reason="no browser available (python -m playwright install chromium, "
           "or install Chrome/Edge, or set A11Y_BROWSER_CHANNEL)",
)


@pytest.fixture(scope="module")
def accessible_capture(tmp_path_factory):
    from arwmf.capture import capture_page

    out = tmp_path_factory.mktemp("acc")
    return capture_page(FIXTURES.joinpath("accessible.html").as_uri(), out)


@pytest.fixture(scope="module")
def inaccessible_capture(tmp_path_factory):
    from arwmf.capture import capture_page

    out = tmp_path_factory.mktemp("inacc")
    return capture_page(FIXTURES.joinpath("inaccessible.html").as_uri(), out)


def test_capture_extracts_elements(accessible_capture, inaccessible_capture):
    for cap in (accessible_capture, inaccessible_capture):
        el = cap.elements
        assert len(el["text_elements"]) > 3
        assert len(el["interactive"]) > 0
        assert len(el["links"]) > 0
        assert Path(cap.png_path).exists()
    # both fixtures have images
    assert len(accessible_capture.elements["images"]) >= 1
    assert len(inaccessible_capture.elements["images"]) >= 3


def test_capture_structure_signals(accessible_capture, inaccessible_capture):
    good = accessible_capture.elements["structure"]
    bad = inaccessible_capture.elements["structure"]
    assert good["h1_count"] == 1 and good["has_main"] and good["has_nav"]
    assert good["has_skip_link"]
    assert bad["h1_count"] == 2 and not bad["has_main"]
    assert 3 in bad["heading_levels"] and 5 in bad["heading_levels"]


def test_deterministic_dimensions_without_models(accessible_capture,
                                                 inaccessible_capture):
    """Vision + link heuristics path (no CLIP/embeddings) must still separate."""
    from arwmf.pipeline import score_capture

    acc = score_capture(accessible_capture, use_clip=False, use_embeddings=False)
    inacc = score_capture(inaccessible_capture, use_clip=False, use_embeddings=False)

    assert acc["composite"] > inacc["composite"]
    assert acc["dimensions"]["contrast"] > inacc["dimensions"]["contrast"]
    assert acc["dimensions"]["target_size"] > inacc["dimensions"]["target_size"]
    assert acc["dimensions"]["layout"] > inacc["dimensions"]["layout"]
    # link heuristics: accessible page has descriptive labels, bad page "click here"
    assert acc["dimensions"]["link_text"] > inacc["dimensions"]["link_text"]
    # degraded NLP flagged
    assert "clip" in acc["degraded"]
    assert acc["applied_weights"] and abs(sum(acc["applied_weights"].values()) - 1) < 1e-6


def test_full_stack_with_models(accessible_capture, inaccessible_capture):
    """Full path including CLIP + MiniLM (downloads on first CI run)."""
    from arwmf.pipeline import score_capture

    try:
        acc = score_capture(accessible_capture)
        inacc = score_capture(inaccessible_capture)
    except Exception as exc:  # model download blocked, etc.
        pytest.skip(f"model stack unavailable: {exc}")

    assert "clip" not in acc["degraded"]
    assert acc["composite"] > inacc["composite"]
    # alt text: descriptive alt scores above missing/filename/empty
    assert acc["dimensions"]["alt_text"] > inacc["dimensions"]["alt_text"]
