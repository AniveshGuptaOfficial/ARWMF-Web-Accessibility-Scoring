"""WCAG contrast scoring from captured element records (spec: docs/02-accessibility-scoring-specification.md D1)."""
from __future__ import annotations

import math
from typing import Iterable


def parse_color(value: str) -> tuple[int, int, int, float] | None:
    """Parse 'rgb()/rgba()/#hex' to (r, g, b, alpha). Returns None if unparseable."""
    value = value.strip().lower()
    if not value or value in ("transparent", "none"):
        return None
    if value.startswith("#"):
        h = value[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            try:
                return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
            except ValueError:
                return None
        if len(h) == 8:
            try:
                return (int(h[0:2], 16), int(h[2:4], 16),
                        int(h[4:6], 16), int(h[6:8], 16) / 255.0)
            except ValueError:
                return None
        return None
    if value.startswith("rgb"):
        inner = value[value.find("(") + 1:value.find(")")]
        parts = [p.strip() for p in inner.replace("/", " ").split(",") if p.strip()]
        if len(parts) < 3:
            return None
        try:
            r, g, b = (int(float(parts[i])) for i in range(3))
            a = float(parts[3]) if len(parts) > 3 else 1.0
            return r, g, b, a
        except ValueError:
            return None
    return None


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.x relative luminance."""
    def chan(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    """WCAG contrast ratio in [1, 21]."""
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def blend(fg: tuple[int, int, int], bg: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """Alpha-composite fg over bg."""
    return tuple(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg))  # type: ignore[return-value]


def is_large_text(font_px: float, bold: bool) -> bool:
    """WCAG 'large text': >=24px, or >=18.66px bold."""
    return font_px >= 24.0 or (bold and font_px >= 18.66)


def required_ratio(font_px: float, bold: bool) -> float:
    return 3.0 if is_large_text(font_px, bold) else 4.5


def element_contrast_score(element: dict) -> float | None:
    """Score one captured text element 0-100; None if not scorable.

    element keys: fg (str), bg (str, effective), font_px (float), bold (bool),
    alpha (optional fg alpha), rect (dict w/h), visible (bool).
    """
    if not element.get("visible", True):
        return None
    fg = parse_color(element.get("fg", ""))
    bg = parse_color(element.get("bg", ""))
    if fg is None or bg is None:
        return None
    fa = fg[3] * element.get("alpha", 1.0)
    bg_a = bg[3]
    # Flatten alpha onto white (page default) — approximation documented in spec
    fg_rgb = blend(fg[:3], (255, 255, 255), fa) if fa < 1 else fg[:3]
    bg_rgb = blend(bg[:3], (255, 255, 255), bg_a) if bg_a < 1 else bg[:3]
    ratio = contrast_ratio(fg_rgb, bg_rgb)  # type: ignore[arg-type]
    req = required_ratio(float(element.get("font_px", 16.0)), bool(element.get("bold", False)))
    return 100.0 * min(ratio / req, 1.0)


def dimension_contrast(elements: Iterable[dict]) -> float | None:
    """Area-weighted (sqrt area) mean of per-element scores. None if no scorable text."""
    total_w = 0.0
    acc = 0.0
    for el in elements:
        score = element_contrast_score(el)
        if score is None:
            continue
        rect = el.get("rect") or {}
        area = max(float(rect.get("w", 0)) * float(rect.get("h", 0)), 1.0)
        # clip weight to avoid a single huge container dominating absurdly
        weight = math.sqrt(min(area, 1920 * 1080))
        acc += score * weight
        total_w += weight
    if total_w == 0:
        return None
    # clamp: float summation can exceed 100 by epsilon when all scores are 100
    return float(min(acc / total_w, 100.0))
