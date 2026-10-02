"""Median aggregation of multi-rater ratings (Kuzikov et al. protocol).

Long-format ratings CSV schema (human_study/ratings.csv):
    page_id, rater_id, contrast, target_size, layout, alt_text, link_text, overall, seconds, timestamp
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DIMENSIONS = ["contrast", "target_size", "layout", "alt_text", "link_text", "overall"]
HUMAN_DIMENSIONS = DIMENSIONS  # overall included as the sixth column


def ratings_to_matrix(ratings: pd.DataFrame, dimension: str,
                      page_id: str = "page_id", rater_id: str = "rater_id"):
    """Pivot long-format ratings into (n_pages, n_raters) matrix.

    Rows are sorted by page_id, columns by rater_id (both sorted), so the
    matrix is stable and balanced-design violations raise.
    """
    if dimension not in ratings.columns:
        raise KeyError(f"missing column {dimension!r}")
    wide = ratings.pivot_table(index=page_id, columns=rater_id,
                               values=dimension, observed=True)
    if wide.isna().any().any():
        raise ValueError(
            "unbalanced design: every page must be rated by every rater"
        )
    wide = wide.sort_index(axis=0).sort_index(axis=1)
    return wide.to_numpy(dtype=float), list(wide.index), list(wide.columns)


def median_consensus(ratings: pd.DataFrame, dimensions=None,
                     page_id: str = "page_id", rater_id: str = "rater_id") -> pd.DataFrame:
    """Per-page median across raters for each dimension (consensus label)."""
    dimensions = dimensions or DIMENSIONS
    missing = [d for d in dimensions if d not in ratings.columns]
    if missing:
        raise KeyError(f"missing columns: {missing}")
    grouped = ratings.groupby(page_id, sort=True)[dimensions].median()
    grouped.columns = [f"median_{c}" for c in grouped.columns]
    return grouped


def consensus_matrix(ratings: pd.DataFrame, dimension: str = "overall",
                     page_id: str = "page_id", rater_id: str = "rater_id"):
    """Convenience: (matrix, page_ids, rater_ids) for one dimension."""
    return ratings_to_matrix(ratings, dimension, page_id, rater_id)
