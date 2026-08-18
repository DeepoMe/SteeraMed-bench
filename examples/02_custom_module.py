"""Evaluate a user-defined module panel.

Because module gene-set definitions are intentionally NOT distributed with
this benchmark (minimal-definition policy), the custom entry point operates
on **module names** rather than gene symbols.  Pick any modules from
``bench.list_modules()`` and evaluate them with the same Table 1 protocol
(stratified 5-fold CV logistic regression, capped Recall@20) used for the
predefined panels.

Run::

    python examples/02_custom_module.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steeramed_bench import Bench


def main():
    bench = Bench()

    # Inventory: 332 modules across five families.
    print("Module families:")
    for src in ["Hallmarks", "TCM", "NUT", "NUTX", "YFY"]:
        print(f"  {src:<10} {len(bench.list_modules(src)):>4} modules")
    print(f"Available diseases: {', '.join(bench.list_diseases())}")
    print()

    # ------------------------------------------------------------------
    # Example custom panel: mix nutrient and TCM modules.
    # Replace with any names from bench.list_modules(), e.g.
    #   ["NUT:Thiamine", "TCM:T1_xxx", "Hallmarks:A1_xxx", ...]
    # ------------------------------------------------------------------
    my_modules = (
        bench.list_modules("NUT")[:8]            # first 8 nutrient modules
        + bench.list_modules("TCM")[:4]          # + 4 TCM modules
    )
    print(f"Custom panel: {len(my_modules)} modules")
    for m in my_modules:
        print(f"  - {m}")
    print()

    # Evaluate on a single disease (pass disease=None to average over all).
    disease = bench.list_diseases()[0]
    result = bench.evaluate_custom_modules(my_modules, disease=disease)

    print(result)
    print()

    # Compare with the closest predefined family panels on the same disease.
    print(f"Reference panels on the same disease ({disease}):")
    for panel in ["NUT", "TCM", "ALL"]:
        ref = bench.evaluate_panel(panel, disease=disease)
        print(f"  {panel:<10} Recall@20 = {ref.recall_at_20:.3f}")

    print()
    print("Top-10 scored drugs (custom panel):")
    order = result.scores.argsort()[::-1][:10]
    for i in order:
        print(f"  {result.drug_names[i]:<45} score={result.scores[i]:+.3f}")


if __name__ == "__main__":
    main()
