"""Fusion + NLP rule tests (D4/D5 deterministic parts, axe mapping)."""
import pytest

from arwmf.baselines import axe_score
from arwmf.fusion import DEFAULT_WEIGHTS, fuse
from arwmf.nlp.alt_text import classify_alt, generic_label_multiplier
from arwmf.nlp.link_text import heuristic_score, link_score


# ---------------- fusion ----------------

def test_fuse_full_weights():
    scores = {k: 80.0 for k in DEFAULT_WEIGHTS}
    out = fuse(scores)
    assert out.composite == pytest.approx(80.0)
    assert sum(out.applied_weights.values()) == pytest.approx(1.0)


def test_fuse_renormalises_missing_dimension():
    scores = {"contrast": 100.0, "target_size": 100.0, "layout": 100.0,
              "alt_text": None, "link_text": None}
    out = fuse(scores)
    assert out.composite == pytest.approx(100.0)
    assert "alt_text" not in out.applied_weights
    # remaining weights renormalise: .25/.60, .15/.60, .20/.60
    assert out.applied_weights["contrast"] == pytest.approx(0.25 / 0.60)


def test_fuse_weighted_example():
    # contrast 100 (w .25), target 0 (w .15), others None (layout dropped too)
    scores = {"contrast": 100.0, "target_size": 0.0, "layout": None,
              "alt_text": None, "link_text": None}
    out = fuse(scores)
    assert out.composite == pytest.approx(100 * (0.25 / 0.40) + 0 * (0.15 / 0.40))


def test_fuse_rejects_bad_input():
    with pytest.raises(ValueError):
        fuse({k: None for k in DEFAULT_WEIGHTS})
    with pytest.raises(ValueError):
        fuse({"contrast": 150.0, "target_size": 50.0, "layout": 50.0,
              "alt_text": 50.0, "link_text": 50.0})
    with pytest.raises(ValueError):
        fuse({"contrast": -5.0, "target_size": 50.0, "layout": 50.0,
              "alt_text": 50.0, "link_text": 50.0})
    with pytest.raises(KeyError):
        fuse({"bogus": 50.0})


def test_fuse_tolerates_float_epsilon():
    # regression: perfect-contrast pages produced 100.00000000000013
    out = fuse({"contrast": 100.00000000000013, "target_size": 100.0,
                "layout": 100.0, "alt_text": 100.0, "link_text": 100.0})
    assert out.composite == pytest.approx(100.0, abs=1e-6)
    assert out.composite <= 100.0


def test_perfect_contrast_dimension_capped():
    from arwmf.vision import dimension_contrast

    els = [{"fg": "#000000", "bg": "#ffffff", "font_px": 40, "bold": False,
            "visible": True, "rect": {"w": w, "h": h}}
           for w, h in [(1000, 80), (500, 40), (300, 24)]]
    score = dimension_contrast(els)
    assert score is not None and score <= 100.0


def test_fuse_default_weights_sums_to_one():
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


# ---------------- alt-text rules ----------------

def test_classify_alt_routing():
    assert classify_alt({"alt": None}) == "missing"
    assert classify_alt({"alt": None, "role": "presentation"}) == "decorative"
    assert classify_alt({"alt": None, "aria_hidden": True}) == "decorative"
    assert classify_alt({"alt": ""}) == "missing"
    assert classify_alt({"alt": "", "role": "presentation"}) == "decorative"
    assert classify_alt({"alt": "photo_2024.jpg", "src": "x/photo_2024.jpg"}) == "filename"
    assert classify_alt({"alt": "A red barn in Vermont", "src": "barn.jpg"}) == "score"


def test_generic_label_penalty():
    # spec D4: alt consisting ONLY of interface words with <=3 tokens
    assert generic_label_multiplier("image") == 0.5
    assert generic_label_multiplier("photo") == 0.5
    assert generic_label_multiplier("logo image") == 0.5
    assert generic_label_multiplier("photo of dog") == 1.0  # contains content words
    assert generic_label_multiplier("a red barn in Vermont") == 1.0


# ---------------- link-text rules ----------------

def test_vague_labels_score_zero():
    for label in ["Click here", "here", "READ MORE", "more", "this link", ""]:
        heuristic, _ = heuristic_score(label)
        assert heuristic == 0.0, label
    # link_score without embedder also 0 for exact vague
    assert link_score({"text": "click here", "context": "anything"}) == 0.0


def test_url_like_label_scores_zero():
    assert link_score({"text": "https://example.com/page/1"}) == 0.0


def test_good_label_scores_high_with_context():
    score = link_score({
        "text": "VIT Vellore admission portal",
        "context": "Apply through the VIT Vellore admission portal before the deadline.",
    })
    assert score > 60


def test_generic_verb_partial_penalty_applies():
    # tokens all in vague-partial set -> generic verb path
    score = link_score({"text": "click", "context": "to proceed click on the button next"})
    assert score <= 100 * 0.6 + 1e-9


# ---------------- axe mapping ----------------

def test_axe_score_formula():
    # 10 serious violations, 100 elements: penalty 30 / (4*100) -> 92.5
    violations = [{"id": "x", "impact": "serious", "nodes_count": 10}]
    assert axe_score(violations, 100) == pytest.approx(92.5)
    # no violations -> 100
    assert axe_score([], 100) == 100.0
    # catastrophic: penalty exceeds denominator -> floors at 0
    violations = [{"id": "x", "impact": "critical", "nodes_count": 1000}]
    assert axe_score(violations, 50) == 0.0
    # unknown impact treated as minor
    assert axe_score([{"id": "y", "impact": None, "nodes_count": 4}], 100) == pytest.approx(99.0)


def test_axe_min_denominator():
    # tiny page: denominator floors at 4*50 = 200
    violations = [{"id": "x", "impact": "moderate", "nodes_count": 20}]
    assert axe_score(violations, 3) == pytest.approx(100 * (1 - 40 / 200))
