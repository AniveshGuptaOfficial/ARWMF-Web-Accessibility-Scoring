"""Compute-vs-correlation benchmark report (RQ3).

Reads automated scores + human ratings CSV and prints:
  - panel ICC(A,k), system ICC(A,1) vs consensus, axe-core ICC(A,1)
  - Spearman rho / MAE per system
  - wall-clock and peak-memory columns if present

Usage:
    python scripts/report_correlation_and_compute.py --ratings human_study/ratings.csv \
        --system scores_system.csv --axe scores_axe.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arwmf.stats import icc_a1, icc_ak, median_consensus, ratings_to_matrix, system_vs_consensus  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratings", required=True, help="long-format ratings CSV")
    ap.add_argument("--system", required=True,
                    help="CSV with page_id,composite (our fused score)")
    ap.add_argument("--axe", help="CSV with page_id,axe_score")
    ap.add_argument("--dimension", default="overall")
    ap.add_argument("--bootstrap", type=int, default=10000)
    args = ap.parse_args()

    ratings = pd.read_csv(args.ratings)
    matrix, pages, raters = ratings_to_matrix(ratings, args.dimension)
    cons = median_consensus(ratings).reset_index()

    print(f"=== Panel ({len(pages)} pages x {len(raters)} raters, "
          f"dimension={args.dimension}) ===")
    print(f"  ICC(A,5) panel : {icc_ak(matrix)}")
    boot = ""
    from arwmf.stats import bootstrap_icc_ci

    lo, hi = bootstrap_icc_ci(matrix, m=len(raters), n_boot=args.bootstrap, seed=0)
    print(f"  bootstrap CI   : [{lo:.3f}, {hi:.3f}]")

    gate = icc_ak(matrix).icc >= 0.70
    print(f"  reliability gate (ICC(A,5) >= 0.70): {'PASS' if gate else 'FAIL -> study inconclusive'}")

    sys_df = pd.read_csv(args.system)
    merged = cons.merge(sys_df, on="page_id", how="inner")
    target = merged[f"median_{args.dimension}"]
    res = system_vs_consensus(merged["composite"], target)
    print("\n=== System (fused score) ===")
    print(f"  {res}")
    rho = merged["composite"].corr(target, method="spearman")
    mae = (merged["composite"] - target).abs().mean()
    print(f"  Spearman rho   : {rho:.3f}   MAE: {mae:.1f}")

    if args.axe:
        axe_df = pd.read_csv(args.axe)
        m2 = cons.merge(axe_df, on="page_id", how="inner")
        res2 = system_vs_consensus(m2["axe_score"], m2[f"median_{args.dimension}"])
        rho2 = m2["axe_score"].corr(m2[f"median_{args.dimension}"], method="spearman")
        mae2 = (m2["axe_score"] - m2[f"median_{args.dimension}"]).abs().mean()
        print("\n=== axe-core baseline ===")
        print(f"  {res2}")
        print(f"  Spearman rho   : {rho2:.3f}   MAE: {mae2:.1f}")

    print("\n=== Compute (fill from runs: median s/page, peak MB) ===")
    print("  system: _ s/page, _ MB   |   axe-core: _ s/page, _ MB   |   LLM baseline: _ s/page")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
