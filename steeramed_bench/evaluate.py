"""Evaluation metrics for SteeraMed-bench.

All functions accept simple numpy-array-like inputs so they can be used
stand-alone, independent of the :class:`~steeramed_bench.data.Bench` loader.
"""

import numpy as np


def recall_at_k(y_true, scores, k=20):
    """Compute Recall@k.

    Parameters
    ----------
    y_true : array-like of {0,1}
        Binary disease labels for each drug (1 = positive / approved).
    scores : array-like of float
        Drug scores; higher means the drug is predicted more relevant.
    k : int, default 20
        Number of top-scoring drugs to consider.

    Returns
    -------
    float
        Fraction of true positives recovered within the top-k predictions.
        Returns ``0.0`` when there are no positives.
    """
    y_true = np.asarray(y_true).ravel()
    scores = np.asarray(scores, dtype=float).ravel()
    if y_true.shape[0] != scores.shape[0]:
        raise ValueError(
            "y_true and scores must have the same length, "
            f"got {y_true.shape[0]} and {scores.shape[0]}"
        )
    n_pos = int(y_true.sum())
    if n_pos == 0:
        return 0.0
    k = min(k, scores.shape[0])
    if k <= 0:
        return 0.0
    # Indices of the k highest scores (ties broken by original order).
    top_k = np.argpartition(scores, -k)[-k:]
    hits = float(y_true[top_k].sum())
    return hits / n_pos


def aupr(y_true, scores):
    """Compute the Area Under the Precision-Recall curve (AUPR).

    Thin wrapper around :func:`sklearn.metrics.average_precision_score` so
    that users need only depend on the metric name used in the paper.
    """
    from sklearn.metrics import average_precision_score

    y_true = np.asarray(y_true).ravel()
    scores = np.asarray(scores, dtype=float).ravel()
    if y_true.sum() == 0:
        return 0.0
    return float(average_precision_score(y_true, scores))


def excess_gain(real_recall, null_recall):
    """Compute the excess gain of a panel over its null model.

    Defined simply as ``real_recall - null_recall``.  When ``null_recall``
    is an array (e.g. a permutation distribution) the mean is used.

    Parameters
    ----------
    real_recall : float
        Empirical Recall@k of the real panel.
    null_recall : float or array-like
        Null Recall@k (scalar) or a null distribution.

    Returns
    -------
    float
    """
    null_recall = np.asarray(null_recall, dtype=float)
    return float(real_recall) - float(np.mean(null_recall))


# ---------------------------------------------------------------------------
# Paper-aligned panel evaluation (Table 1 protocol)
# ---------------------------------------------------------------------------
def capped_recall_at_k(y_true, scores, k=20):
    """Recall@k with the capped denominator used in the paper (Table 1).

    The paper defines Recall@20 as the number of positive drugs inside the
    top-20 ranked drugs divided by ``min(20, n_positives)``.  With 20 or more
    positives this is the hit fraction within the top-20; with fewer
    positives the denominator shrinks to the number of positives.

    Ranking ties are broken identically to the paper scripts
    (``np.argsort(scores)[::-1]``), so results match Table 1 bit-for-bit.

    Parameters
    ----------
    y_true : array-like of {0,1}
    scores : array-like of float
    k : int, default 20

    Returns
    -------
    float
    """
    y_true = np.asarray(y_true).ravel()
    scores = np.asarray(scores, dtype=float).ravel()
    if y_true.shape[0] != scores.shape[0]:
        raise ValueError(
            "y_true and scores must have the same length, "
            f"got {y_true.shape[0]} and {scores.shape[0]}"
        )
    n_pos = int(y_true.sum())
    if n_pos == 0:
        return 0.0
    k = min(k, scores.shape[0])
    if k <= 0:
        return 0.0
    order = np.argsort(scores)[::-1]
    hits = float(y_true[order[:k]].sum())
    return hits / min(k, n_pos)


def cv_logistic_scores(X, y, seeds=(42, 123, 456), n_folds=5, C=0.1):
    """Out-of-fold drug scores from stratified cross-validated logistic
    regression - the exact scoring protocol behind Table 1 of the paper.

    For every seed a ``n_folds``-fold stratified split is drawn
    (``shuffle=True``), a logistic regression (``C=0.1``, ``max_iter=1000``)
    is fitted on the training folds and predicts ``P(positive)`` for the
    held-out fold.  Per-drug predictions are averaged over seeds; folds
    without both classes in training are skipped.

    Parameters
    ----------
    X : ndarray of shape (n_drugs, n_modules)
        Module z-score sub-matrix (the "panel").
    y : array-like of {0,1}
        Binary disease labels.
    seeds : tuple of int, default (42, 123, 456)
    n_folds : int, default 5
    C : float, default 0.1

    Returns
    -------
    ndarray of shape (n_drugs,)
        Averaged out-of-fold probability scores.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    X = np.asarray(X, dtype=float)
    y = np.asarray(y).ravel().astype(int)
    if X.shape[0] != y.shape[0]:
        raise ValueError(
            "X and y must have the same length, "
            f"got {X.shape[0]} and {y.shape[0]}"
        )
    preds = np.zeros(len(y), dtype=float)
    cnt = np.zeros(len(y), dtype=float)
    for s in seeds:
        skf = StratifiedKFold(n_folds, shuffle=True, random_state=s)
        for tr, te in skf.split(X, y):
            if len(set(y[tr])) < 2:
                continue
            m = LogisticRegression(C=C, max_iter=1000, random_state=s)
            m.fit(X[tr], y[tr])
            preds[te] += m.predict_proba(X[te])[:, 1]
            cnt[te] += 1
    valid = cnt > 0
    preds[valid] /= cnt[valid]
    return preds


def panel_recall_at_k(X, y, k=20, seeds=(42, 123, 456), n_folds=5, C=0.1):
    """Paper Table 1 protocol: CV-LR out-of-fold ranking + capped Recall@k.

    Composes :func:`cv_logistic_scores` and :func:`capped_recall_at_k`.
    Feed a module sub-matrix (the panel columns) and binary disease labels;
    get back the Recall@20 exactly as reported in Table 1.

    Parameters
    ----------
    X, y, k, seeds, n_folds, C
        See :func:`cv_logistic_scores` and :func:`capped_recall_at_k`.

    Returns
    -------
    float
    """
    preds = cv_logistic_scores(X, y, seeds=seeds, n_folds=n_folds, C=C)
    return capped_recall_at_k(y, preds, k=k)
