# RWMF / A-RWMF Fusion Methodology (technical annex)

Implements PROPOSAL Sections 5.3–5.4. Everything here is frozen before held-out
scores are unblinded; changes go to `04-protocol-deviation-log.md`.

## 1. Notation

- D = 5 dimensions: `contrast`, `target_size`, `layout`, `alt_text`, `link_text`.
- s_d(p) ∈ [0, 100] — automated dimension score for page p (None if not applicable).
- h_d(p) ∈ [0, 100] — human median consensus for dimension d on page p (`median_<d>` column).
- CAL / VAL — calibration and held-out page sets (stratified 1/3 : 2/3 by bucket).

## 2. Reliability estimate ICC_d (RWMF prior)

For each dimension d on CAL pages only:

```
matrix_d = column_stack[ s_d(p) for p in CAL , h_d(p) for p in CAL ]   # (|CAL| x 2)
ICC_d    = icc_a1(matrix_d).icc          # two-way random, absolute agreement
```

The system's own score is entered as an extra "rater" against the consensus
column — the same construction as `system_vs_consensus`, restricted to one
dimension at a time. Dims with s_d ≡ None on more than half of CAL pages get
ICC_d := 0 (module barely applies; shrinkage below keeps it alive).

## 3. Static weights

```
floored_d = max(ICC_d, 0)
w_d       = (floored_d + λ) / Σ_j (floored_j + λ)      λ = 0.1 (fixed)
```

Fallback: if Σ floored < 0.05 → declare fit uninformative → equal weights 1/D,
flagged `fit_status: "fallback_equal"`.

Per page at scoring time:

```
applicable = { d : s_d(p) is not None }
S(p) = Σ_{d∈applicable} s_d(p) · w_d / Σ_{d∈applicable} w_d      (renormalised)
```

## 4. Page-context profile x_p (computed at capture, zero marginal cost)

| feature | definition | source |
|---|---|---|
| `image_ratio` | IMG nodes / total DOM nodes | capture JS |
| `interactive_ratio` | interactive elements / total DOM nodes | capture JS |
| `mean_text_len` | mean characters per text-bearing element | capture JS |
| `dom_depth` | max element nesting depth | capture JS |

## 5. Bucket assignment (deterministic first-match, thresholds from CAL quantiles)

```
if image_ratio >= T_img            -> "image-heavy"
elif interactive_ratio >= T_int    -> "form-heavy"
elif mean_text_len  <  T_text      -> "form-heavy"?  NO -> "text-heavy"
else                               -> "text-heavy"
```

- T_img = CAL 66th percentile of image_ratio (default floor 0.05)
- T_int = CAL 66th percentile of interactive_ratio (default floor 0.15)
- T_text = CAL 40th percentile of mean_text_len (default cap 120 chars)
- Frozen after calibration inspection; misclassification on CAL is hand-audited
  and the rate reported (PROPOSAL §5.7).

## 6. Per-bucket weights (A-RWMF, bucketed form)

For bucket b:

```
CAL_b = { p ∈ CAL : bucket(p) = b }
if |CAL_b| < 5:  w_d(b) := w_d            # global fallback, flag bucket_sparse
else:            same §3 formula with ICC_d computed on CAL_b only
```

Equivalent to the softmax formulation with β_d · x_p constant per bucket;
softmax temperature fixed at 1.0 (sensitivity analysis only, never headline).
ICC floor carries into the gating argument so a negative in-bucket ICC cannot
suppress a dimension.

Weight table artifact (`human_study/fit/rwmf_weights.json`):

```json
{
  "frozen_date": "...", "calibration_pages": ["p01", "..."],
  "lambda": 0.1, "fit_status": "ok",
  "global": {"contrast": 0.24, "target_size": 0.16, "...": 0.0},
  "icc_global": {"contrast": 0.71, "...": 0.0},
  "buckets": {
    "image-heavy":  {"weights": {"...": 0.0}, "n_cal": 6, "status": "ok"},
    "form-heavy":   {"weights": {"...": 0.0}, "n_cal": 3, "status": "bucket_sparse"}
  },
  "thresholds": {"T_img": 0.05, "T_int": 0.15, "T_text": 120}
}
```

## 7. Variant comparison (PROPOSAL §5.6, pre-registered)

| variant | weights | artifact |
|---|---|---|
| equal | 1/D | built in |
| RWMF | §3 global | `rwmf_weights.json` → `global` |
| A-RWMF | §6 per bucket | → `buckets` |
| axe-core | frozen mapping (docs §D0) | `axe.json` |

On VAL pages only, for each variant: ICC(A,1) + F-CI + 10,000 page bootstrap,
Spearman ρ, MAE vs `median_*`. Decisions:

1. RWMF > equal iff ΔMAE(paired bootstrap 95% CI) < 0 pooled.
2. A-RWMF > RWMF iff pooled MAE lower **and** pooled ICC not lower, **or**
   pooled ties within CI and A-RWMF wins ≥ 2/3 buckets (Holm–Bonferroni).
3. Else: negative result, reported as such.

Run: `python scripts/report_correlation_and_compute.py --ratings human_study/ratings.csv ...`

## 8. Guard rails

- Weights fit ONLY on CAL; reported ICC2k ONLY on VAL (never reuse pages).
- Any constant (λ, floor, thresholds, split ratio, temperature) changed after
  freeze → deviation log entry BEFORE re-running held-out evaluation.
- All three weighted variants share the identical front-end; only §3/§6 differ,
  so Δ is attributable to weighting alone.
- Fusion overhead measured, expected µs (four-feature table lookup).
