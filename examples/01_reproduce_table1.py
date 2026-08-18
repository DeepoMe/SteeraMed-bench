"""Reproduce Table 1 - panel-level Recall@20.

Run after downloading the benchmark data files into ``steeramed_bench/data/``::

    python examples/01_reproduce_table1.py

The script evaluates every predefined panel, prints Recall@20 averaged over
all diseases, and checks the ALL panel against the paper-reported value of
0.524.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steeramed_bench import Bench


def main():
    bench = Bench()

    diseases = bench.list_diseases()
    print(f"Diseases ({len(diseases)}): {', '.join(diseases)}")
    print()

    header = f"{'Panel':<12}{'Recall@20':>12}{'Paper':>10}{'#mod':>8}"
    print(header)
    print("-" * len(header))

    for panel in bench.list_panels():
        res = bench.evaluate_panel(panel)
        paper = (
            f"{res.paper_recall_at_20:.3f}"
            if res.paper_recall_at_20 is not None
            else "  n/a"
        )
        n_mod = len(bench.get_panel_modules(panel))
        print(
            f"{panel:<12}{res.recall_at_20:>12.3f}{paper:>10}{n_mod:>8}"
        )

    all_res = bench.evaluate_panel("ALL")
    print()
    print("=" * 48)
    print(f"ALL panel  Recall@20 = {all_res.recall_at_20:.3f}")
    print(f"Paper-reported value   = 0.524")
    diff = all_res.recall_at_20 - 0.524
    status = "MATCH" if abs(diff) < 0.01 else "DIFF"
    print(f"Difference             = {diff:+.3f}  [{status}]")

    if all_res.per_disease:
        print()
        print("Per-disease breakdown (ALL panel):")
        for d, r in all_res.per_disease.items():
            print(f"  {d:<24} {r:.3f}")


if __name__ == "__main__":
    main()
