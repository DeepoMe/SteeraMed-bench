"""Null models for SteeraMed-bench.

:func:`column_permutation_null` draws size-matched random panels (columns
of the z-score matrix) to ask whether the *specific* module composition of
a panel matters, controlling for panel size.  It operates purely on the
aggregated z-score matrix, so no gene-set definitions are required.
"""

import numpy as np

from .evaluate import recall_at_k


def column_permutation_null(X, y, panel_size=None, n_iter=200, k=20, seed=42):
    """Size-matched random-panel null distribution for Recall@k.

    Tests whether a specific panel outperforms a random collection of the
    same number of modules drawn from the full atlas.  At each iteration a
    random set of ``panel_size`` columns is drawn (without replacement) from
    ``X``, drugs are scored by the mean z-score over those columns, and
    Recall@k is recorded.

    This corresponds to the "column-permutation" null reported in Table 1 of
    the paper (``perm`` column).  Note that a naive permutation of column
    *order* followed by a mean aggregation is invariant and therefore
    uninformative; the size-matched random subset is the correct control for
    panel identity.

    Parameters
    ----------
    X : ndarray of shape (n_drugs, n_modules)
        Pre-computed z-score matrix.  Pass the **full** atlas matrix so the
        random draw spans all modules; ``panel_size`` then restricts the
        random panel to the size of the panel under test.
    y : array-like of {0,1}
        Binary disease labels.
    panel_size : int, optional
        Number of modules per random panel.  When ``None`` (default) all
        columns of ``X`` are used, so ``X`` should already be restricted to
        the panel of interest.
    n_iter : int, default 200
        Number of random panels to draw.
    k : int, default 20
        Recall@k cutoff.
    seed : int, default 42
        RNG seed for reproducibility.

    Returns
    -------
    ndarray of shape (n_iter,)
        Null Recall@k values.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y).ravel()
    n_modules = X.shape[1]
    if panel_size is None:
        panel_size = n_modules
    panel_size = min(int(panel_size), n_modules)
    rng = np.random.default_rng(seed)
    recalls = np.empty(n_iter, dtype=float)

    for i in range(n_iter):
        cols = rng.choice(n_modules, size=panel_size, replace=False)
        scores = X[:, cols].mean(axis=1)
        recalls[i] = recall_at_k(y, scores, k=k)
    return recalls
