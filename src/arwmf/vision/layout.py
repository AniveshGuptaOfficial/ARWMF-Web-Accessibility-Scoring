"""Layout scoring: DOM structure + screenshot clutter (spec: D3).

structure: deterministic penalties over heading hierarchy and landmarks.
clutter: Canny edge-density of the full-page screenshot, mapped through
[EDGE_MIN, EDGE_MAX] -> [0, 100] (constants frozen in the scoring spec).
"""
from __future__ import annotations

import cv2
import numpy as np

EDGE_MIN = 0.02
EDGE_MAX = 0.20


def structure_score(structure: dict) -> float:
    """structure keys: h1_count (int), heading_levels (sorted used levels),
    has_main (bool), has_nav (bool), nav_link_count (int), has_skip_link (bool)."""
    score = 100.0
    h1 = int(structure.get("h1_count", 0))
    if h1 == 0:
        score -= 20
    elif h1 > 1:
        score -= min(30, 10 * (h1 - 1))
    levels = sorted(set(structure.get("heading_levels", [])))
    for a, b in zip(levels, levels[1:]):
        if b - a > 1:
            score -= 15
            break
    if not structure.get("has_main", False):
        score -= 15
    if structure.get("nav_link_count", 0) > 0 and not structure.get("has_nav", False):
        score -= 15
    if structure.get("nav_link_count", 0) > 20 and not structure.get("has_skip_link", False):
        score -= 10
    return max(score, 0.0)


def clutter_score_from_edge_density(density: float) -> float:
    t = (EDGE_MAX - density) / (EDGE_MAX - EDGE_MIN)
    return 100.0 * float(np.clip(t, 0.0, 1.0))


def edge_density(image_bgr: np.ndarray, canny_low: int = 50, canny_high: int = 150) -> float:
    """Fraction of edge pixels in the (optionally downscaled) image."""
    if image_bgr.size == 0:
        return 0.0
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    # downscale very large captures for speed, density is scale-stable enough
    h, w = gray.shape
    max_dim = 1600
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)),
                          interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(gray, canny_low, canny_high)
    return float(np.count_nonzero(edges)) / float(edges.size)


def dimension_layout(structure: dict, image_bgr: np.ndarray) -> float:
    """Equal mix of structure and clutter (both 0-100)."""
    return 0.5 * structure_score(structure) + 0.5 * clutter_score_from_edge_density(
        edge_density(image_bgr)
    )
