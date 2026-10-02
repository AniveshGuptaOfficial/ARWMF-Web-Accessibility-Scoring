"""ICC validation against pingouin's wine-judging worked example.

Reference (pingouin intraclass_corr docstring, validated against R psych::ICC):
    8 wines x 4 judges
    ICC(1,1) = 0.728   ICC(A,1) = 0.728   ICC(C,1) = 0.729
    ICC(1,k) = 0.914   ICC(A,k) = 0.914   ICC(C,k) = 0.915
    ICC(A,1): F = 11.787, df1 = 7, df2 = 21, CI95 ~ [0.43, 0.93]
    ICC(A,k): CI95 ~ [0.75, 0.98]
"""
import pathlib

import numpy as np
import pandas as pd
import pytest

from arwmf.stats import (
    bootstrap_icc_ci,
    icc_a1,
    icc_ak,
    median_consensus,
    ratings_to_matrix,
    system_vs_consensus,
)

DATA = pathlib.Path(__file__).parent / "data" / "wine_icc.csv"


@pytest.fixture(scope="module")
def wine_matrix() -> np.ndarray:
    df = pd.read_csv(DATA)
    wide = df.pivot(index="Wine", columns="Judge", values="Scores")
    return wide.sort_index(axis=0).sort_index(axis=1).to_numpy(dtype=float)


def test_icc_a1_matches_reference(wine_matrix):
    res = icc_a1(wine_matrix)
    assert res.icc == pytest.approx(0.728, abs=5e-4)
    assert res.f_value == pytest.approx(11.787, abs=5e-4)
    assert res.n_targets == 8 and res.n_raters == 4
    assert res.p_value < 0.001


def test_icc_a1_ci_matches_reference(wine_matrix):
    res = icc_a1(wine_matrix)
    assert res.ci_low == pytest.approx(0.43, abs=0.01)
    assert res.ci_high == pytest.approx(0.93, abs=0.01)


def test_icc_ak_matches_reference(wine_matrix):
    res = icc_ak(wine_matrix)
    assert res.icc == pytest.approx(0.914, abs=5e-4)
    assert res.ci_low == pytest.approx(0.75, abs=0.01)
    assert res.ci_high == pytest.approx(0.98, abs=0.01)


def test_perfect_agreement(wine_matrix):
    # All raters identical -> ICC = 1
    perfect = wine_matrix[:, :1].repeat(4, axis=1)
    res = icc_a1(perfect)
    assert res.icc == pytest.approx(1.0, abs=1e-9)
    assert res.ci_low == pytest.approx(1.0, abs=1e-6)


def test_m_transform_consistency(wine_matrix):
    # ICC(A,m) must satisfy icc_m = m*icc1 / (1 + (m-1)*icc1)
    r1, rk = icc_a1(wine_matrix), icc_ak(wine_matrix)
    expected = 4 * r1.icc / (1 + 3 * r1.icc)
    assert rk.icc == pytest.approx(expected, abs=1e-9)


def test_system_vs_consensus_perfect():
    humans = np.array([[80.0], [60.0], [40.0], [90.0]])
    system = np.array([80.0, 60.0, 40.0, 90.0])
    res = system_vs_consensus(system, humans)
    assert res.icc == pytest.approx(1.0, abs=1e-9)


def test_bootstrap_ci_brackets_point_estimate(wine_matrix):
    point = icc_a1(wine_matrix).icc
    lo, hi = bootstrap_icc_ci(wine_matrix, m=1, n_boot=2000, seed=42)
    assert lo <= hi
    assert lo - 0.05 <= point <= hi + 0.05  # coarse sanity bracket


def test_validation_errors():
    with pytest.raises(ValueError):
        icc_a1(np.array([[1.0, 2.0]]))  # only one target
    with pytest.raises(ValueError):
        icc_a1(np.array([[1.0, np.nan], [2.0, 3.0]]))
    with pytest.raises(ValueError):
        icc_ak(np.random.rand(5, 3), m=4)  # m > n_raters


def test_ratings_pivot_and_median():
    ratings = pd.DataFrame(
        {
            "page_id": ["p1", "p1", "p1", "p2", "p2"],
            "rater_id": ["r1", "r2", "r3", "r1", "r2"],
            "overall": [80, 60, 70, 50, 55],
            "contrast": [90, 85, 88, 40, 45],
        }
    )
    # median_consensus defaults to the full dimension list; test subset explicitly
    with pytest.raises(KeyError):
        median_consensus(ratings)  # missing target_size etc.
    with pytest.raises(ValueError):
        ratings_to_matrix(ratings, "overall")  # unbalanced: p2 missing r3

    balanced = pd.concat(
        [ratings, pd.DataFrame({"page_id": ["p2"], "rater_id": ["r3"],
                                "overall": [52], "contrast": [42]})],
        ignore_index=True,
    )
    mat, pages, raters = ratings_to_matrix(balanced, "overall")
    assert pages == ["p1", "p2"] and raters == ["r1", "r2", "r3"]
    assert mat.shape == (2, 3)

    cons = median_consensus(balanced, dimensions=["overall", "contrast"])
    assert cons.loc["p1", "median_overall"] == 70
    assert cons.loc["p2", "median_overall"] == 52
    assert cons.loc["p1", "median_contrast"] == 88
