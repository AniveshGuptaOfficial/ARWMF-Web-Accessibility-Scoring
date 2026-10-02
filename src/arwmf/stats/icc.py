"""Intraclass correlation coefficients — two-way random, absolute agreement.

Implements ICC(A,1) and ICC(A,m) (McGraw & Wong 1996, "ICC2"/"ICC2k" as used by
Kuzikov et al.), with F-based 95% confidence intervals.

Formulas follow McGraw & Wong (1996) and the validated implementation in
pingouin (which is itself validated against R's psych::ICC). Point estimates
and CIs in the test suite are checked against pingouin's worked wine-judging
example (ICC(A,1) = 0.728, ICC(A,4) = 0.914).

Input convention: ``data`` is a 2-D array of shape (n_targets, n_raters) —
rows = pages (targets rated), columns = raters. Complete balanced design
required (no NaNs) for the two-way models.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class ICCResult:
    icc: float
    ci_low: float
    ci_high: float
    f_value: float
    p_value: float
    ms_target: float
    ms_rater: float
    ms_error: float
    n_targets: int
    n_raters: int
    m_averaged: int

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"ICC(A,{self.m_averaged})={self.icc:.3f} "
            f"(95% CI [{self.ci_low:.3f}, {self.ci_high:.3f}]), "
            f"F={self.f_value:.2f}, p={self.p_value:.4g}, "
            f"n={self.n_targets} targets x {self.n_raters} raters"
        )


def _validate(data: np.ndarray) -> tuple[int, int]:
    if data.ndim != 2:
        raise ValueError("data must be 2-D (n_targets, n_raters)")
    n, k = data.shape
    if n < 2 or k < 2:
        raise ValueError("need at least 2 targets and 2 raters")
    if not np.isfinite(data).all():
        raise ValueError("complete balanced design required: no NaN/inf allowed")
    return n, k


def _anova(data: np.ndarray) -> tuple[float, float, float]:
    """Return (MS_targets, MS_raters, MS_error) for a two-way layout, no replication."""
    n, k = data.shape
    grand = data.mean()
    row_means = data.mean(axis=1)  # per target
    col_means = data.mean(axis=0)  # per rater
    ss_targets = k * np.sum((row_means - grand) ** 2)
    ss_raters = n * np.sum((col_means - grand) ** 2)
    ss_error = np.sum((data - row_means[:, None] - col_means[None, :] + grand) ** 2)
    ms_target = ss_targets / (n - 1)
    ms_rater = ss_raters / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))
    return ms_target, ms_rater, ms_error


def icc_absolute(data, m: int = 1, alpha: float = 0.05) -> ICCResult:
    """Two-way random-effects, absolute-agreement ICC(A, m).

    Parameters
    ----------
    data : array-like, shape (n_targets, n_raters)
    m : int
        Number of measures averaged: 1 -> ICC(A,1) (single rating);
        m == n_raters -> ICC(A,k) (panel mean, the "ICC2k" of Kuzikov et al.).
        1 <= m <= n_raters.
    alpha : float
        Two-sided significance level for the CI (0.05 -> 95% CI).
    """
    data = np.asarray(data, dtype=float)
    n, k = _validate(data)
    if not (1 <= m <= k):
        raise ValueError(f"m must be in [1, {k}]")
    msb, msj, mse = _anova(data)

    # Degenerate cases: zero residual variance means raters agree exactly.
    if mse == 0:
        if msb == 0:
            raise ValueError(
                "ICC undefined: no between-target and no residual variance"
            )
        # perfect absolute agreement -> ICC = 1 (point and CI), F -> inf
        return ICCResult(
            icc=1.0, ci_low=1.0, ci_high=1.0,
            f_value=float("inf"), p_value=0.0,
            ms_target=float(msb), ms_rater=float(msj), ms_error=0.0,
            n_targets=n, n_raters=k, m_averaged=m,
        )

    # ICC(A,1): uses ALL k raters in the error structure (McGraw & Wong eq. 10)
    icc2 = (msb - mse) / (msb + (k - 1) * mse + (k / n) * (msj - mse))

    # F test of H0: ICC = 0
    f_value = msb / mse
    p_value = stats.f.sf(f_value, n - 1, (n - 1) * (k - 1))

    # Case-2 (absolute agreement) CI, McGraw & Wong / pingouin formulation
    fj = msj / mse
    df1, df2 = n - 1, (n - 1) * (k - 1)
    term = n * (1 + (k - 1) * icc2) - k * icc2
    vn = df2 * (k * icc2 * fj + term) ** 2
    vd = df1 * k**2 * icc2**2 * fj**2 + term**2
    v = vn / vd
    f2u = stats.f.ppf(1 - alpha / 2, n - 1, v)
    f2l = stats.f.ppf(1 - alpha / 2, v, n - 1)
    l1 = n * (msb - f2u * mse) / (f2u * (k * msj + (k * n - k - n) * mse) + n * msb)
    u1 = n * (f2l * msb - mse) / (k * msj + (k * n - k - n) * mse + n * f2l * msb)

    # Extend to ICC(A,m) via the standard m-transform (applies to point and CI)
    def extend(x: float) -> float:
        return m * x / (1 + (m - 1) * x)

    icc = extend(icc2)
    ci_low, ci_high = extend(l1), extend(u1)

    return ICCResult(
        icc=float(np.clip(icc, -1.0, 1.0)),
        ci_low=float(np.clip(ci_low, -1.0, 1.0)),
        ci_high=float(np.clip(ci_high, -1.0, 1.0)),
        f_value=float(f_value),
        p_value=float(p_value),
        ms_target=float(msb),
        ms_rater=float(msj),
        ms_error=float(mse),
        n_targets=n,
        n_raters=k,
        m_averaged=m,
    )


def icc_a1(data, alpha: float = 0.05) -> ICCResult:
    """ICC(A,1): single-measure absolute agreement."""
    return icc_absolute(data, m=1, alpha=alpha)


def icc_ak(data, m: int | None = None, alpha: float = 0.05) -> ICCResult:
    """ICC(A,k): average-measure absolute agreement over ``m`` raters (default: all)."""
    data = np.asarray(data, dtype=float)
    _, k = _validate(data)
    return icc_absolute(data, m=k if m is None else m, alpha=alpha)


def system_vs_consensus(system_scores, human_matrix) -> ICCResult:
    """ICC(A,1) with the system entered as an additional rater.

    Parameters
    ----------
    system_scores : array-like, shape (n_targets,)
    human_matrix : array-like, shape (n_targets, n_raters) or (n_targets,)
        Full rater matrix, or a single consensus column.
    """
    system_scores = np.asarray(system_scores, dtype=float).reshape(-1, 1)
    humans = np.asarray(human_matrix, dtype=float)
    if humans.ndim == 1:
        humans = humans.reshape(-1, 1)
    matrix = np.hstack([system_scores, humans])
    return icc_a1(matrix)


def bootstrap_icc_ci(data, m: int = 1, n_boot: int = 10000, alpha: float = 0.05,
                     seed: int = 0) -> tuple[float, float]:
    """Page-level (target) bootstrap CI for ICC(A,m), cross-check for the F-based CI.

    Resamples targets (rows) with replacement; falls back gracefully when a
    resample is degenerate (all-equal rows -> undefined ICC) by skipping it.
    """
    data = np.asarray(data, dtype=float)
    n, _ = _validate(data)
    rng = np.random.default_rng(seed)
    vals: list[float] = []
    while len(vals) < n_boot:
        idx = rng.integers(0, n, size=n)
        sample = data[idx]
        if np.all(sample == sample[0:1]):  # zero between-target variance
            continue
        try:
            vals.append(icc_absolute(sample, m=m).icc)
        except (ValueError, ZeroDivisionError, FloatingPointError):
            continue
        if len(vals) > n_boot * 10:  # safety valve
            break
    arr = np.asarray(vals)
    return (
        float(np.quantile(arr, alpha / 2)),
        float(np.quantile(arr, 1 - alpha / 2)),
    )
