"""Weighted five-dimension fusion (spec: docs/02-accessibility-scoring-specification.md weights section)."""
from __future__ import annotations

from dataclasses import dataclass, field

# a priori weights — frozen before benchmark unblinding
DEFAULT_WEIGHTS: dict[str, float] = {
    "contrast": 0.25,
    "target_size": 0.15,
    "layout": 0.20,
    "alt_text": 0.25,
    "link_text": 0.15,
}

DIMENSIONS = tuple(DEFAULT_WEIGHTS)


@dataclass
class FusedScore:
    composite: float
    dimensions: dict[str, float | None]  # None = not applicable on this page
    applied_weights: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "composite": round(self.composite, 1),
            "dimensions": {k: (None if v is None else round(v, 1))
                           for k, v in self.dimensions.items()},
            "applied_weights": {k: round(v, 4) for k, v in self.applied_weights.items()},
        }


def fuse(dimension_scores: dict[str, float | None],
         weights: dict[str, float] | None = None) -> FusedScore:
    """Weighted mean over applicable dimensions; inapplicable weights renormalised.

    Raises if no dimension is applicable, or if an unknown dimension is passed,
    or a dimension score is outside [0, 100].
    """
    weights = dict(weights or DEFAULT_WEIGHTS)
    unknown = set(dimension_scores) - set(weights)
    if unknown:
        raise KeyError(f"unknown dimensions: {sorted(unknown)}")

    applicable = {k: float(v) for k, v in dimension_scores.items() if v is not None}
    EPS = 1e-6  # float summation in dimension means can overshoot by epsilon
    for k, v in applicable.items():
        if v < -EPS or v > 100.0 + EPS:
            raise ValueError(f"dimension {k} out of range [0,100]: {v}")
        applicable[k] = min(max(v, 0.0), 100.0)  # snap epsilon overshoot into range
    if not applicable:
        raise ValueError("no applicable dimensions: composite undefined")

    w_sum = sum(weights[k] for k in applicable)
    if w_sum <= 0:
        raise ValueError("applicable weights sum to zero")
    applied = {k: weights[k] / w_sum for k in applicable}
    composite = sum(applicable[k] * applied[k] for k in applicable)

    return FusedScore(
        composite=float(composite),
        dimensions={k: dimension_scores.get(k) for k in weights},
        applied_weights=applied,
    )
