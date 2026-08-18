# Benchmark Data Files

This directory holds the four pre-computed artefacts required by
`steeramed_bench`. **These files are intentionally not committed to the git
repository** — download them from the
[latest GitHub Release](https://github.com/DeepoMe/SteeraMed-bench/releases)
(`steeramed-bench-data.zip`) and extract them here.

> **Minimal-definition policy**: module gene-set definitions (gene lists)
> are proprietary and are **not** part of this release.  Only aggregated
> z-scores and module metadata (family, panel, gene count) are distributed.

## Required files

### 1. `zscore_matrix.npz`

A NumPy compressed archive with three arrays:

| Array | Shape | Dtype | Description |
|-------|-------|-------|-------------|
| `matrix` | `(1916, 332)` | float64 | Network-proximity z-score of each drug against each module |
| `drug_names` | `(1916,)` | str | Drug names (DrugBank / STITCH identifiers) |
| `module_names` | `(332,)` | str | Module names matching `module_metadata.csv` |

Load it with:

```python
import numpy as np
d = np.load("zscore_matrix.npz", allow_pickle=False)
matrix, drugs, modules = d["matrix"], d["drug_names"], d["module_names"]
```

Every module name carries a `SOURCE:` prefix identifying its family:

| Prefix | Family | Count |
|--------|--------|-------|
| `Hallmarks:` | Aging hallmark modules (tiers `A1_`–`A5_`) | 72 |
| `TCM:` | Traditional Chinese Medicine modules (tiers `T1_`–`T3_`) | 38 |
| `NUT:` | Nutrient / dietary-supplement modules (incl. botanicals) | 80 |
| `NUTX:` | Extended nutraceutical modules | 37 |
| `YFY:` | Chinese food-therapy herb modules (one per herb) | 105 |

### 2. `disease_labels.csv`

Long-format positive drug labels. One row per (disease, positive drug):

```csv
disease,drug
T2D,Metformin
T2D,Acarbose
Hyper,Amlodipine
...
```

Five benchmark diseases are included: `T2D`, `Hyper`, `Dep`, `Osteo`,
`Athero`.

### 3. `panel_mapping.csv`

Module-to-panel mapping in long format (a module can belong to several
panels: family panel, tier sub-panel, combination panel, `ALL`):

```csv
module,panel
Hallmarks:A1_telomere,HALLMARKS
Hallmarks:A1_telomere,A1
Hallmarks:A1_telomere,HALLMARKS_TCM
Hallmarks:A1_telomere,ALL
NUT:Thiamine,NUT
NUT:Thiamine,TCM_NUT
NUT:Thiamine,ALL
...
```

### 4. `module_metadata.csv`

One row per module with the public metadata (no gene lists):

```csv
module,source,primary_panel,n_genes,visibility
Hallmarks:A1_telomere,Hallmarks,HALLMARKS,42,private
NUT:ATP,NUT,NUT,40,private
...
```

- `source` — family: `Hallmarks` / `TCM` / `NUT` / `NUTX` / `YFY`
- `primary_panel` — the family-level panel
- `n_genes` — number of genes in the module definition (count only)
- `visibility` — always `private`: gene-set definitions are not distributed

## How to obtain the data

```bash
# 1. Download from GitHub Releases
#    https://github.com/DeepoMe/SteeraMed-bench/releases

# 2. Extract into this folder
unzip steeramed-bench-data.zip -d data/

# 3. Verify
python -c "from steeramed_bench import Bench; b=Bench(); print(b.list_panels())"
```

## Data provenance

The pre-computed matrices are derived from publicly available sources and
redistributed **in aggregated form only**:

- **Module z-scores**: STRING v12 PPI network + DrugBank / STITCH drug
  targets, aggregated per module via the Guney network-proximity metric.
  The underlying module gene-set definitions are proprietary and are not
  redistributed.
- **Disease labels**: DrugBank approved-indication mappings for the five
  benchmark diseases.

**Raw source files are NOT redistributed** due to licensing (DrugBank) and
size (STRING). Users who wish to recompute from scratch should obtain:

- DrugBank XML — <https://go.drugbank.com/> (license required)
- STRING PPI — <https://string-db.org/cgi/download>
- repoDB — <https://apps.chiragjpgroup.org/repoDB/>

## Verification

After placing the files, run:

```bash
pytest tests/test_bench.py
python examples/01_reproduce_table1.py
```

The ALL panel should report Recall@20 = **0.524** (Table 1).  The protocol
is fully deterministic (fixed CV seeds 42/123/456, deterministic
logistic-regression solver), so on an identical software stack the value
reproduces exactly; across library versions the outcome is robust because
Recall@20 depends only on a discrete ranking, not on score magnitudes.
