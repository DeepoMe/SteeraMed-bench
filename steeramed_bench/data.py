"""Core data loader and evaluation entry point for SteeraMed-bench.

The :class:`Bench` class loads four pre-computed artefacts and exposes a
small, paper-aligned API for evaluating module panels::

    from steeramed_bench import Bench

    bench = Bench()                          # load pre-computed matrices
    print(bench.list_panels())               # available panels
    res = bench.evaluate_panel("ALL")        # reproduce Table 1
    print(res.recall_at_20)                  # ~0.524

**Module definitions are intentionally NOT part of the public release.**
Gene-set definitions of all 332 modules are proprietary; the benchmark
redistributes only aggregated network-proximity z-scores plus module
metadata (family, panel, gene count).  This "minimal module definition"
policy keeps Table 1 fully reproducible without disclosing how each
module is built.

The four data files are **not** bundled with the source distribution.  See
``data/README_DATA.md`` for download instructions.  When a file is missing a
clear :class:`FileNotFoundError` is raised explaining how to obtain it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .evaluate import capped_recall_at_k, cv_logistic_scores, panel_recall_at_k
from . import panels as _panels


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass
class PanelResult:
    """Result of evaluating a predefined panel.

    ``recall_at_20`` follows the paper's Table 1 protocol: stratified
    5-fold cross-validated logistic-regression out-of-fold ranking, Recall@20
    with a capped denominator, averaged over the benchmark diseases.
    """

    panel: str
    disease: str
    recall_at_20: float
    n_positives: int
    n_modules: int
    method: str = "cv_logistic"
    null_mean: float = float("nan")
    null_std: float = float("nan")
    excess_gain: float = float("nan")
    paper_recall_at_20: Optional[float] = None
    per_disease: Dict[str, float] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"PanelResult(panel={self.panel!r}, disease={self.disease!r}, "
            f"recall@20={self.recall_at_20:.3f}, n_pos={self.n_positives}, "
            f"n_modules={self.n_modules}, method={self.method!r})"
        )


@dataclass
class CustomModuleResult:
    """Result of evaluating a user-defined collection of modules."""

    disease: str
    recall_at_20: float
    n_positives: int
    n_modules: int
    requested_modules: List[str] = field(default_factory=list)
    matched_modules: List[str] = field(default_factory=list)
    scores: Optional[np.ndarray] = None
    drug_names: Optional[Sequence[str]] = None

    def __repr__(self) -> str:
        return (
            f"CustomModuleResult(disease={self.disease!r}, "
            f"recall@20={self.recall_at_20:.3f}, n_pos={self.n_positives}, "
            f"matched_modules={len(self.matched_modules)})"
        )


# ---------------------------------------------------------------------------
# Missing-data error helper
# ---------------------------------------------------------------------------
_DATA_FILES = [
    "zscore_matrix.npz",
    "disease_labels.csv",
    "panel_mapping.csv",
    "module_metadata.csv",
]

_INSTALL_HINT = (
    "The SteeraMed-bench data files are not bundled with the source code.\n"
    "To obtain them:\n"
    "  1. Download `steeramed-bench-data.zip` from the latest GitHub Release:\n"
    "     https://github.com/DeepoMe/SteeraMed-bench/releases\n"
    "  2. Extract the four files into the package `data/` directory (or a\n"
    "     folder of your choice) and pass it as `data_dir=`.\n"
    "  3. The required files are:\n"
    "       - zscore_matrix.npz   (1916 drugs x 332 modules, pre-computed\n"
    "                              network-proximity z-scores)\n"
    "       - disease_labels.csv  (positive drug labels per disease)\n"
    "       - panel_mapping.csv   (module -> panel assignment)\n"
    "       - module_metadata.csv (module family / gene-count metadata;\n"
    "                              gene-set definitions are NOT distributed)"
)


def _missing_file(path: str) -> FileNotFoundError:
    return FileNotFoundError(
        f"Required data file not found: {path}\n\n{_INSTALL_HINT}"
    )


# ---------------------------------------------------------------------------
# Bench
# ---------------------------------------------------------------------------
class Bench:
    """Loader and evaluator for the SteeraMed module-panel benchmark.

    Parameters
    ----------
    data_dir : str or pathlib.Path, optional
        Directory containing the four data files.  Defaults to the ``data/``
        folder shipped alongside the package source.
    """

    #: files the loader expects to find
    REQUIRED_FILES = tuple(_DATA_FILES)

    def __init__(self, data_dir: Optional[os.PathLike] = None):
        if data_dir is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data",
            )
        self.data_dir = os.fspath(data_dir)
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def _path(self, name: str) -> str:
        p = os.path.join(self.data_dir, name)
        if not os.path.exists(p):
            raise _missing_file(p)
        return p

    def _load(self) -> None:
        npz = np.load(self._path("zscore_matrix.npz"), allow_pickle=False)
        self.zscore_matrix = np.asarray(npz["matrix"], dtype=float)
        self.drug_names = [str(x) for x in npz["drug_names"]]
        self.module_names = [str(x) for x in npz["module_names"]]
        if self.zscore_matrix.shape != (
            len(self.drug_names),
            len(self.module_names),
        ):
            raise ValueError(
                "zscore_matrix shape "
                f"{self.zscore_matrix.shape} does not match "
                f"(n_drugs={len(self.drug_names)}, "
                f"n_modules={len(self.module_names)})"
            )

        self.labels_df = pd.read_csv(self._path("disease_labels.csv"))
        if not {"disease", "drug"}.issubset(self.labels_df.columns):
            raise ValueError(
                "disease_labels.csv must contain 'disease' and 'drug' columns"
            )

        self.panel_mapping = pd.read_csv(self._path("panel_mapping.csv"))
        if not {"module", "panel"}.issubset(self.panel_mapping.columns):
            raise ValueError(
                "panel_mapping.csv must contain 'module' and 'panel' columns"
            )

        self.module_metadata = pd.read_csv(self._path("module_metadata.csv"))
        if not {"module", "source", "n_genes"}.issubset(
            self.module_metadata.columns
        ):
            raise ValueError(
                "module_metadata.csv must contain 'module', 'source' and "
                "'n_genes' columns"
            )

        # index maps for fast lookup
        self._drug_idx = {d: i for i, d in enumerate(self.drug_names)}
        self._mod_idx = {m: i for i, m in enumerate(self.module_names)}

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def list_panels(self) -> List[str]:
        """Return the canonical list of predefined panel names."""
        return list(_panels.ALL_PANELS)

    def list_diseases(self) -> List[str]:
        """Return the list of diseases with positive drug labels."""
        return sorted(self.labels_df["disease"].unique().tolist())

    def list_modules(self, source: Optional[str] = None) -> List[str]:
        """Return module names, optionally filtered by source family.

        Sources: ``Hallmarks`` / ``TCM`` / ``NUT`` / ``NUTX`` / ``YFY``.
        """
        if source is None:
            return list(self.module_names)
        return [
            m for m in self.module_names
            if m.startswith(f"{source}:")
        ]

    def module_info(self, module_name: str) -> Dict[str, object]:
        """Return the public metadata of one module.

        Note: gene-set definitions are proprietary and intentionally not
        distributed; only the gene *count* and family metadata are public.
        """
        row = self.module_metadata[
            self.module_metadata["module"] == module_name
        ]
        if row.empty:
            raise KeyError(
                f"Unknown module {module_name!r}. "
                "See list_modules() for valid names."
            )
        return row.iloc[0].to_dict()

    def get_panel_modules(self, panel_name: str) -> List[str]:
        """Return the module names belonging to ``panel_name``.

        Membership is read from ``panel_mapping.csv`` and augmented with the
        prefix rules in :mod:`steeramed_bench.panels` for robustness.
        """
        panel_name = panel_name.upper()
        if panel_name == "ALL":
            return list(self.module_names)

        mapped = set(
            self.panel_mapping.loc[
                self.panel_mapping["panel"].str.upper() == panel_name,
                "module",
            ].tolist()
        )
        # Augment with prefix-based membership for robustness.
        for m in self.module_names:
            if _panels.assign_panel(m) == panel_name:
                mapped.add(m)
            elif _panels.assign_subpanel(m) == panel_name:
                mapped.add(m)
        return [m for m in self.module_names if m in mapped]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _labels_for_disease(self, disease: str) -> np.ndarray:
        pos_drugs = set(
            self.labels_df.loc[
                self.labels_df["disease"] == disease, "drug"
            ].astype(str)
        )
        return np.array(
            [1.0 if d in pos_drugs else 0.0 for d in self.drug_names],
            dtype=float,
        )

    def _module_submatrix(self, modules: Sequence[str]) -> np.ndarray:
        cols = [self._mod_idx[m] for m in modules if m in self._mod_idx]
        if not cols:
            raise ValueError("None of the requested modules exist.")
        return self.zscore_matrix[:, cols]

    # ------------------------------------------------------------------
    # Public evaluation API
    # ------------------------------------------------------------------
    def evaluate_panel(
        self,
        panel_name: str,
        disease: Optional[str] = None,
        k: int = 20,
    ) -> PanelResult:
        """Evaluate a predefined panel with the paper's Table 1 protocol.

        Drugs are ranked by out-of-fold predictions of a stratified
        5-fold cross-validated logistic regression (``C=0.1``, seeds
        42/123/456) fitted on the panel's module z-scores, and Recall@k is
        computed with the capped denominator ``min(k, n_positives)``.

        Parameters
        ----------
        panel_name : str
            One of :meth:`list_panels` (e.g. ``"ALL"``).
        disease : str, optional
            A single disease from :meth:`list_diseases`.  When ``None`` the
            Recall@20 is averaged over all diseases (Table 1 convention).
        k : int, default 20

        Returns
        -------
        PanelResult
        """
        panel_name = panel_name.upper()
        if panel_name not in _panels.ALL_PANELS:
            raise ValueError(
                f"Unknown panel {panel_name!r}. "
                f"Available: {_panels.ALL_PANELS}"
            )
        modules = self.get_panel_modules(panel_name)
        X = self._module_submatrix(modules)
        paper_val = _panels.PANEL_PAPER_VALUES.get(panel_name, {}).get(
            "recall_at_20"
        )

        if disease is not None:
            y = self._labels_for_disease(disease)
            r = panel_recall_at_k(X, y, k=k)
            return PanelResult(
                panel=panel_name,
                disease=disease,
                recall_at_20=r,
                n_positives=int(y.sum()),
                n_modules=len(modules),
                paper_recall_at_20=paper_val,
            )

        per_disease: Dict[str, float] = {}
        total_pos = 0
        for d in self.list_diseases():
            y = self._labels_for_disease(d)
            per_disease[d] = panel_recall_at_k(X, y, k=k)
            total_pos += int(y.sum())
        mean_recall = float(np.mean(list(per_disease.values())))
        return PanelResult(
            panel=panel_name,
            disease="ALL",
            recall_at_20=mean_recall,
            n_positives=total_pos,
            n_modules=len(modules),
            paper_recall_at_20=paper_val,
            per_disease=per_disease,
        )

    def evaluate_custom_modules(
        self,
        modules: Sequence[str],
        disease: Optional[str] = None,
        k: int = 20,
    ) -> CustomModuleResult:
        """Evaluate a user-defined collection of modules.

        Because module gene-set definitions are not distributed, the custom
        entry point operates on **module names** (see :meth:`list_modules`)
        rather than gene symbols.  The same Table 1 CV-LR protocol is used,
        so results are directly comparable to predefined panels.

        Parameters
        ----------
        modules : sequence of str
            Module names, e.g. ``["NUT:Thiamine", "Hallmarks:A1_autophagy"]``.
        disease : str, optional
            Single disease; ``None`` averages over all diseases.
        k : int, default 20

        Returns
        -------
        CustomModuleResult
        """
        requested = [str(m).strip() for m in modules if str(m).strip()]
        matched = [m for m in requested if m in self._mod_idx]
        if not matched:
            raise ValueError(
                "None of the requested modules exist in the benchmark. "
                "See list_modules() for valid names "
                "(e.g. 'NUT:Thiamine', 'Hallmarks:A1_autophagy')."
            )
        X = self._module_submatrix(matched)

        diseases = [disease] if disease is not None else self.list_diseases()
        recalls = []
        total_pos = 0
        scores = None
        for d in diseases:
            y = self._labels_for_disease(d)
            s = cv_logistic_scores(X, y)
            recalls.append(capped_recall_at_k(y, s, k=k))
            total_pos += int(y.sum())
            if disease is not None:
                scores = s
        mean_recall = float(np.mean(recalls)) if recalls else 0.0

        return CustomModuleResult(
            disease=disease if disease is not None else "ALL",
            recall_at_20=mean_recall,
            n_positives=total_pos,
            n_modules=len(matched),
            requested_modules=requested,
            matched_modules=matched,
            scores=scores,
            drug_names=list(self.drug_names),
        )

    def permutation_null(
        self,
        panel_name: str,
        disease: str,
        n_iter: int = 200,
        k: int = 20,
        seed: int = 42,
    ) -> np.ndarray:
        """Size-matched random-panel null for a panel on a single disease.

        Convenience wrapper around
        :func:`steeramed_bench.null_models.column_permutation_null` that
        draws random panels of the same size from the full loaded matrix.

        Note: this size-matched random-panel null is a robustified control;
        the paper's Table 1 ``perm`` column used a single within-row column
        permutation, so values may differ slightly.
        """
        from .null_models import column_permutation_null

        panel_name = panel_name.upper()
        modules = self.get_panel_modules(panel_name)
        panel_size = len([m for m in modules if m in self._mod_idx])
        y = self._labels_for_disease(disease)
        return column_permutation_null(
            self.zscore_matrix, y, panel_size=panel_size,
            n_iter=n_iter, k=k, seed=seed,
        )
