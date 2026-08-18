"""Basic functional tests for steeramed_bench.

The metric and panel tests below do **not** require the benchmark data
files, so they always run.  A data-dependent smoke test is included but is
skipped automatically when the pre-computed matrices are absent.
"""

import os

import numpy as np
import pytest

from steeramed_bench import panels
from steeramed_bench.evaluate import (
    recall_at_k,
    aupr,
    excess_gain,
    capped_recall_at_k,
    cv_logistic_scores,
    panel_recall_at_k,
)
from steeramed_bench.null_models import column_permutation_null
from steeramed_bench.data import Bench

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_HERE), "data")
_HAS_DATA = all(
    os.path.exists(os.path.join(_DATA_DIR, f))
    for f in Bench.REQUIRED_FILES
)


# ---------------------------------------------------------------------------
# Metric tests (no data required)
# ---------------------------------------------------------------------------
class TestRecallAtK:
    def test_perfect_recovery(self):
        y = [1, 0, 1, 0, 0]
        scores = [2.0, 1.0, 1.5, 0.5, 0.0]
        # top-2 by score are indices 0, 2 -> both positive -> 2/2 = 1.0
        assert recall_at_k(y, scores, k=2) == pytest.approx(1.0)

    def test_no_positives(self):
        assert recall_at_k([0, 0, 0], [1.0, 2.0, 3.0], k=2) == 0.0

    def test_zero_recovery(self):
        y = [1, 0, 1, 0, 0]
        # top-2 by score are indices 1, 3 -> both negative -> 0/2
        scores = [0.0, 5.0, 1.0, 4.0, 3.0]
        assert recall_at_k(y, scores, k=2) == pytest.approx(0.0)

    def test_k_exceeds_n(self):
        y = [1, 0]
        scores = [1.0, 0.0]
        assert recall_at_k(y, scores, k=20) == pytest.approx(1.0)

    def test_length_mismatch(self):
        with pytest.raises(ValueError):
            recall_at_k([1, 0, 0], [1.0, 2.0], k=1)


class TestAupr:
    def test_perfect_ranking(self):
        y = [1, 1, 0, 0]
        scores = [0.9, 0.8, 0.2, 0.1]
        assert aupr(y, scores) == pytest.approx(1.0)

    def test_no_positives(self):
        assert aupr([0, 0, 0], [0.1, 0.2, 0.3]) == 0.0


class TestExcessGain:
    def test_scalar(self):
        assert excess_gain(0.5, 0.2) == pytest.approx(0.3)

    def test_array_mean(self):
        assert excess_gain(0.5, [0.2, 0.4]) == pytest.approx(0.2)


class TestCappedRecallAtK:
    """Paper Table 1 metric: denominator is min(k, n_positives)."""

    def test_capped_denominator_when_few_positives(self):
        # 3 positives, k=20 -> denominator 3; top-20 contains all 3.
        y = [1, 1, 1, 0, 0, 0]
        scores = [5.0, 4.0, 3.0, 2.0, 1.0, 0.0]
        assert capped_recall_at_k(y, scores, k=20) == pytest.approx(1.0)

    def test_partial_hits(self):
        # 4 positives, k=2, only 1 in top-2 -> 1 / min(2, 4) = 0.5
        y = [1, 0, 1, 1, 1]
        scores = [9.0, 8.0, 1.0, 0.5, 0.0]
        assert capped_recall_at_k(y, scores, k=2) == pytest.approx(0.5)

    def test_no_positives(self):
        assert capped_recall_at_k([0, 0], [1.0, 2.0], k=2) == 0.0

    def test_length_mismatch(self):
        with pytest.raises(ValueError):
            capped_recall_at_k([1, 0, 0], [1.0, 2.0], k=1)


class TestCvLogisticScores:
    def test_shape_and_finiteness(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(60, 5))
        y = np.r_[np.ones(10), np.zeros(50)]
        preds = cv_logistic_scores(X, y, seeds=(42,))
        assert preds.shape == (60,)
        assert np.all(np.isfinite(preds))

    def test_reproducible_with_fixed_seeds(self):
        rng = np.random.default_rng(1)
        X = rng.normal(size=(50, 4))
        y = np.r_[np.ones(8), np.zeros(42)]
        a = cv_logistic_scores(X, y, seeds=(42, 123))
        b = cv_logistic_scores(X, y, seeds=(42, 123))
        np.testing.assert_array_equal(a, b)

    def test_informative_features_score_higher(self):
        # Positives get systematically larger feature values; out-of-fold
        # LR predictions should rank them above negatives on average.
        rng = np.random.default_rng(2)
        n_pos, n_neg = 20, 80
        X = rng.normal(size=(n_pos + n_neg, 3))
        X[:n_pos] += 2.0
        y = np.r_[np.ones(n_pos), np.zeros(n_neg)]
        preds = cv_logistic_scores(X, y, seeds=(42,))
        assert preds[:n_pos].mean() > preds[n_pos:].mean()

    def test_panel_recall_at_k_composes(self):
        rng = np.random.default_rng(3)
        X = rng.normal(size=(60, 4))
        y = np.r_[np.ones(10), np.zeros(50)]
        r = panel_recall_at_k(X, y, k=5, seeds=(42,))
        assert 0.0 <= r <= 1.0


# ---------------------------------------------------------------------------
# Panel constant tests (no data required)
# ---------------------------------------------------------------------------
class TestPanels:
    def test_all_panels_have_metadata(self):
        for p in panels.ALL_PANELS:
            assert p in panels.PANEL_PAPER_VALUES
            assert "dim" in panels.PANEL_PAPER_VALUES[p]

    def test_prefix_assignment(self):
        assert panels.assign_panel("Hallmarks:A1_telomere") == "HALLMARKS"
        assert panels.assign_panel("TCM:T1_essence") == "TCM"
        assert panels.assign_panel("NUT:Thiamine") == "NUT"
        assert panels.assign_panel("NUTX:Alpha_lipoic_acid") == "NUTX"
        assert panels.assign_panel("YFY:ginseng") == "FAM"
        assert panels.assign_panel("unknown:foo") is None

    def test_subpanel_assignment(self):
        assert panels.assign_subpanel("Hallmarks:A1_telomere") == "A1"
        assert panels.assign_subpanel("Hallmarks:A4_something") == "A4"
        assert panels.assign_subpanel("TCM:T3_x") == "T3"
        assert panels.assign_subpanel("NUT:Thiamine") is None

    def test_all_panel_is_superset_note(self):
        # assign_panel never returns ALL; documented behaviour.
        assert panels.assign_panel("Hallmarks:A1_telomere") != "ALL"

    def test_combination_panel_membership(self):
        assert "HALLMARKS_TCM" in panels.panels_for_module("Hallmarks:A1_x")
        assert "HALLMARKS_TCM" in panels.panels_for_module("TCM:T1_x")
        assert "TCM_NUT" in panels.panels_for_module("NUT:Thiamine")
        assert "TCM_NUT" not in panels.panels_for_module("Hallmarks:A1_x")

    def test_module_definitions_not_shipped(self):
        # Minimal-definition policy: no gene lists anywhere in the package.
        import steeramed_bench
        pkg_dir = os.path.dirname(steeramed_bench.__file__)
        assert not os.path.exists(os.path.join(pkg_dir, "module_atlas.json"))
        assert Bench.REQUIRED_FILES == (
            "zscore_matrix.npz",
            "disease_labels.csv",
            "panel_mapping.csv",
            "module_metadata.csv",
        )


# ---------------------------------------------------------------------------
# Null model tests (no data required, uses synthetic matrix)
# ---------------------------------------------------------------------------
class TestNullModels:
    def test_column_permutation_shape_and_range(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(50, 10))
        y = np.r_[np.ones(5), np.zeros(45)]
        null = column_permutation_null(X, y, panel_size=3, n_iter=25, k=5, seed=1)
        assert null.shape == (25,)
        assert null.min() >= 0.0
        assert null.max() <= 1.0

    def test_size_matched_has_variance(self):
        # Size-matched random subset must produce a non-degenerate null.
        rng = np.random.default_rng(0)
        X = rng.normal(size=(60, 20))
        y = np.r_[np.ones(6), np.zeros(54)]
        null = column_permutation_null(X, y, panel_size=3, n_iter=30, seed=2)
        assert null.std() > 0.0

    def test_reproducible(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(40, 8))
        y = np.r_[np.ones(4), np.zeros(36)]
        a = column_permutation_null(X, y, panel_size=3, n_iter=10, seed=7)
        b = column_permutation_null(X, y, panel_size=3, n_iter=10, seed=7)
        np.testing.assert_array_equal(a, b)


# ---------------------------------------------------------------------------
# Bench loader tests
# ---------------------------------------------------------------------------
class TestBenchImport:
    def test_import_without_data(self):
        # Importing the package must never fail when data files are absent.
        import steeramed_bench

        assert steeramed_bench.__version__ == "0.1.0"
        assert hasattr(steeramed_bench, "Bench")

    def test_missing_data_raises_friendly_error(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc:
            Bench(data_dir=str(tmp_path))
        msg = str(exc.value).lower()
        assert "not found" in msg or "missing" in msg
        assert "release" in msg  # install hint present


@pytest.mark.skipif(not _HAS_DATA, reason="benchmark data files not present")
class TestBenchWithData:
    def test_lists(self):
        bench = Bench()
        assert "ALL" in bench.list_panels()
        assert len(bench.list_diseases()) > 0

    def test_module_inventory(self):
        bench = Bench()
        assert len(bench.list_modules()) == 332
        # Family sizes from the paper (Table 1 / E7 main table).
        assert len(bench.list_modules("Hallmarks")) == 72
        assert len(bench.list_modules("TCM")) == 38
        assert len(bench.list_modules("NUT")) == 80
        assert len(bench.list_modules("NUTX")) == 37
        assert len(bench.list_modules("YFY")) == 105

    def test_module_info_has_no_genes(self):
        bench = Bench()
        m = bench.list_modules("NUT")[0]
        info = bench.module_info(m)
        assert "n_genes" in info
        assert "genes" not in info  # minimal-definition policy

    def test_all_panel_recall_near_paper(self):
        bench = Bench()
        res = bench.evaluate_panel("ALL")
        assert 0.0 <= res.recall_at_20 <= 1.0
        # Paper reports 0.524 averaged over 5 diseases.
        assert abs(res.recall_at_20 - 0.524) < 0.05

    def test_family_panels_match_paper(self):
        bench = Bench()
        for panel, ref in [
            ("HALLMARKS", 0.433),
            ("TCM", 0.324),
            ("NUT", 0.494),
            ("FAM", 0.403),
            ("ALL", 0.524),
        ]:
            res = bench.evaluate_panel(panel)
            assert abs(res.recall_at_20 - ref) < 0.02, (
                f"{panel}: got {res.recall_at_20:.4f}, paper {ref}"
            )

    def test_custom_modules_runs(self):
        bench = Bench()
        # Pick a small deterministic custom panel from the NUT family.
        modules = bench.list_modules("NUT")[:5]
        res = bench.evaluate_custom_modules(modules, disease=bench.list_diseases()[0])
        assert 0.0 <= res.recall_at_20 <= 1.0
        assert res.n_modules == 5
        assert res.matched_modules == modules

    def test_custom_modules_unknown_name_raises(self):
        bench = Bench()
        with pytest.raises(ValueError):
            bench.evaluate_custom_modules(["NOSUCH:module"])
