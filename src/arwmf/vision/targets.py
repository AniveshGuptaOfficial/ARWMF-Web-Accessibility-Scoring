"""Target-size scoring (WCAG 2.5.8 minimum, spec: docs/02-accessibility-scoring-specification.md D2)."""
from __future__ import annotations

from typing import Iterable

MIN_TARGET = 24.0  # px, WCAG 2.5.8


def element_target_score(element: dict) -> float | None:
    """Score one interactive element 0-100.

    Exempt (returns None): not visible, or inline link inside a paragraph
    (WCAG 2.5.8 exception for inline links in a sentence).
    """
    if not element.get("visible", True):
        return None
    if element.get("inline_exception", False):
        return None
    rect = element.get("rect") or {}
    w, h = float(rect.get("w", 0)), float(rect.get("h", 0))
    if w <= 0 or h <= 0:
        return None
    return 100.0 * min(w / MIN_TARGET, 1.0) * min(h / MIN_TARGET, 1.0)


def dimension_target_size(interactive: Iterable[dict]) -> float | None:
    """Mean over applicable interactive elements; None if none applicable."""
    scores = [s for s in (element_target_score(e) for e in interactive)
              if s is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)
