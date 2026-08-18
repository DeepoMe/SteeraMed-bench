"""Predefined module panels for SteeraMed-bench.

A *panel* is a curated collection of aging / intervention modules used to
rank drugs via cross-validated network-proximity scoring.  The panels below
correspond to the rows of Table 1 in the accompanying paper.  Module names
in ``zscore_matrix.npz`` / ``module_metadata.csv`` carry a ``SOURCE:``
prefix that identifies their family, e.g. ``Hallmarks:A1_genomic_stability``
belongs to the HALLMARKS panel (and its tier sub-panel ``A1``).

Only reference values that are independent of the user's compute environment
are hard-coded here; the actual Recall@20 is recomputed from the bundled
pre-computed matrices at run time.
"""

# ---------------------------------------------------------------------------
# Paper-reported reference values (Table 1 / E7 main table, averaged over
# the 5 benchmark diseases: T2D, Hyper, Dep, Osteo, Athero)
# ---------------------------------------------------------------------------
# ``dim``         : number of modules in the panel
# ``recall_at_20``: paper-reported Recall@20 (None for panels not reported)
# ``perm``        : paper-reported permuted-null Recall@20 (single run)
PANEL_PAPER_VALUES = {
    # Tier sub-panels
    "A1": {"dim": 14, "recall_at_20": 0.242, "perm": 0.051},
    "A2": {"dim": 36, "recall_at_20": 0.312, "perm": 0.021},
    "A3": {"dim": 10, "recall_at_20": 0.262, "perm": 0.051},
    "A4": {"dim": 6,  "recall_at_20": 0.121, "perm": 0.020},
    "A5": {"dim": 6,  "recall_at_20": 0.111, "perm": 0.060},
    "T1": {"dim": 7,  "recall_at_20": 0.131, "perm": 0.030},
    "T2": {"dim": 13, "recall_at_20": 0.171, "perm": 0.071},
    "T3": {"dim": 18, "recall_at_20": 0.292, "perm": 0.020},
    # Family panels
    "HALLMARKS": {"dim": 72,  "recall_at_20": 0.433, "perm": 0.061},
    "TCM":       {"dim": 38,  "recall_at_20": 0.324, "perm": 0.021},
    "NUT":       {"dim": 80,  "recall_at_20": 0.494, "perm": 0.010},
    "NUTX":      {"dim": 37,  "recall_at_20": None,  "perm": None},
    "FAM":       {"dim": 105, "recall_at_20": 0.403, "perm": 0.020},
    # Combination panels
    "HALLMARKS_TCM": {"dim": 110, "recall_at_20": 0.443, "perm": 0.021},
    "TCM_NUT":       {"dim": 118, "recall_at_20": 0.515, "perm": 0.050},
    # Full atlas
    "ALL":       {"dim": 332, "recall_at_20": 0.524, "perm": 0.050},
}

# ---------------------------------------------------------------------------
# Module-name prefixes -> panel assignment
# ---------------------------------------------------------------------------
# Modules are named ``<SOURCE>:<detail>`` in the released matrix:
#   Hallmarks:A1_autophagy, TCM:T1_essence, NUT:Thiamine,
#   NUTX:Alpha_lipoic_acid, YFY:<herb name>
# A module may belong to several panels; ``assign_panel`` returns the
# primary (family) panel.
PANEL_PREFIXES = {
    "HALLMARKS": ("Hallmarks:",),  # Aging hallmark modules (tiers A1-A5)
    "TCM":       ("TCM:",),        # Traditional Chinese Medicine modules
    "NUT":       ("NUT:",),        # Nutrient modules
    "NUTX":      ("NUTX:",),       # Extended nutraceutical modules
    "FAM":       ("YFY:", "FAM:"), # Functional aging modules (YFY herbs)
}

# Tier sub-panel prefixes (subset of the family panels above).
SUBPANEL_PREFIXES = {
    "A1": ("Hallmarks:A1_",),
    "A2": ("Hallmarks:A2_",),
    "A3": ("Hallmarks:A3_",),
    "A4": ("Hallmarks:A4_",),
    "A5": ("Hallmarks:A5_",),
    "T1": ("TCM:T1_",),
    "T2": ("TCM:T2_",),
    "T3": ("TCM:T3_",),
}

PANEL_DESCRIPTIONS = {
    "HALLMARKS": (
        "Aging hallmark modules derived from the 12 canonical hallmarks of "
        "aging, organized into actionable tiers (A1-A5)."
    ),
    "TCM": (
        "Traditional Chinese Medicine concept modules (yin/yang/qi/essence, "
        "organ systems) organized into tiers T1-T3."
    ),
    "NUT": (
        "Nutrient / dietary-supplement modules covering vitamins, minerals, "
        "amino acids, cofactors and botanicals."
    ),
    "NUTX": (
        "Extended nutraceutical modules (second-line nutrient compounds)."
    ),
    "FAM": (
        "Chinese food-therapy herb modules (one module per herb, family "
        "prefix YFY)."
    ),
    "HALLMARKS_TCM": (
        "Combination of the aging hallmark and TCM panels."
    ),
    "TCM_NUT": (
        "Combination of the TCM and nutrient panels."
    ),
    "ALL": (
        "Union of all 332 modules across every panel - the full SteeraMed "
        "module atlas."
    ),
}

# Canonical ordering used by ``list_panels`` (Table 1 row order:
# tiers first, then families, then combinations, then the full atlas).
ALL_PANELS = [
    "A1", "A2", "A3", "A4", "A5",
    "T1", "T2", "T3",
    "HALLMARKS", "TCM", "NUT", "NUTX", "FAM",
    "HALLMARKS_TCM", "TCM_NUT",
    "ALL",
]


def assign_panel(module_name):
    """Return the primary family panel for a module based on its prefix.

    The ALL panel is not returned here because every module belongs to it;
    callers that need ALL membership should treat it as a superset.
    Sub-panels (A1-A5, T1-T3) are resolved by :func:`assign_subpanel`.
    """
    for panel, prefixes in PANEL_PREFIXES.items():
        if module_name.startswith(prefixes):
            return panel
    return None


def assign_subpanel(module_name):
    """Return the tier sub-panel (A1-A5, T1-T3) for a module, or ``None``."""
    for sub, prefixes in SUBPANEL_PREFIXES.items():
        if module_name.startswith(prefixes):
            return sub
    return None


def panels_for_module(module_name):
    """Return every non-ALL panel a module belongs to (family + tier)."""
    out = []
    primary = assign_panel(module_name)
    if primary is not None:
        out.append(primary)
        if primary == "HALLMARKS":
            out.append("HALLMARKS_TCM")
        elif primary == "TCM":
            out.append("HALLMARKS_TCM")
            out.append("TCM_NUT")
        elif primary == "NUT":
            out.append("TCM_NUT")
    sub = assign_subpanel(module_name)
    if sub is not None:
        out.append(sub)
    return out
