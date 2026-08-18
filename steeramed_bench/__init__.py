"""SteeraMed Bench: Module panel evaluation for drug repurposing."""

__version__ = "0.1.0"

from .data import Bench
from .evaluate import (
    recall_at_k,
    aupr,
    excess_gain,
    capped_recall_at_k,
    cv_logistic_scores,
    panel_recall_at_k,
)

__all__ = [
    "Bench",
    "recall_at_k",
    "aupr",
    "excess_gain",
    "capped_recall_at_k",
    "cv_logistic_scores",
    "panel_recall_at_k",
    "__version__",
]
