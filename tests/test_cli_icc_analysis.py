"""CLI smoke tests that don't need a browser: `python -m arwmf icc`."""
import pandas as pd
import pytest

from arwmf.cli import main


def _synthetic_ratings(n_pages=30, n_raters=5, seed=7) -> pd.DataFrame:
    """Plausible ratings: latent page quality + rater noise + rater bias."""
    import numpy as np

    rng = np.random.default_rng(seed)
    latent = rng.uniform(20, 95, size=n_pages)
    rows = []
    for r in range(n_raters):
        bias = rng.normal(0, 3)
        for i in range(n_pages):
            noise = rng.normal(0, 6)
            overall = float(np.clip(latent[i] + bias + noise, 0, 100))
            rows.append({
                "page_id": f"p{i:02d}",
                "rater_id": f"r{r}",
                "contrast": float(np.clip(overall + rng.normal(0, 4), 0, 100)),
                "target_size": float(np.clip(overall + rng.normal(0, 4), 0, 100)),
                "layout": float(np.clip(overall + rng.normal(0, 4), 0, 100)),
                "alt_text": float(np.clip(overall + rng.normal(0, 4), 0, 100)),
                "link_text": float(np.clip(overall + rng.normal(0, 4), 0, 100)),
                "overall": overall,
                "seconds": 30,
                "timestamp": "2026-01-01",
            })
    return pd.DataFrame(rows)


def test_cli_icc_end_to_end(tmp_path, capsys):
    ratings = _synthetic_ratings()
    csv = tmp_path / "ratings.csv"
    consensus = tmp_path / "consensus.csv"
    ratings.to_csv(csv, index=False)

    rc = main(["icc", str(csv), "--dimension", "overall",
               "--bootstrap", "500", "--consensus", str(consensus)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ICC(A,1)" in out and "ICC(A,5)" in out  # 5 raters -> ICC(A,5)
    assert "30 pages x 5 raters" in out
    assert consensus.exists()
    cons = pd.read_csv(consensus)
    assert len(cons) == 30 and "median_overall" in cons.columns
    # synthetic data has strong latent signal: ICC(A,5) should be high
    assert "ICC(A,5)=0." in out.replace("ICC(A, 5)", "ICC(A,5)")
    # extract ICC(A,5) value
    import re

    m = re.search(r"ICC\(A,5\)=([0-9.]+)", out)
    assert m and float(m.group(1)) > 0.7


def test_cli_icc_rejects_unbalanced(tmp_path):
    ratings = _synthetic_ratings(n_pages=4, n_raters=3).iloc[:-1]  # drop one row
    csv = tmp_path / "bad.csv"
    ratings.to_csv(csv, index=False)
    with pytest.raises(ValueError, match="unbalanced"):
        main(["icc", str(csv)])


def test_cli_requires_subcommand():
    with pytest.raises(SystemExit):
        main([])
