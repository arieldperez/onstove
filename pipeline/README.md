# OnStove Production Pipeline (sub-Saharan Africa clean cooking)

This directory contains the **production pipeline scaffolding** for a validated,
audit-grade OnStove modelling workflow, plus the data contract the interactive
dashboard reads from. It is built on top of the `onstove` Python package that
lives in this repository (`../onstove`).

> **Ground-truth rule.** No number leaves this pipeline without a
> `validation_status`. Country/scenario outputs are *provisional* until a real
> OnStove run has been reproduced against a published figure (Phase 2). The
> earlier browser-only JavaScript prototype is **not** a source of truth — none
> of its coefficients were reproduced from OnStove's published runs.

## What this is (and is not)

This is **scaffolding and documentation**, deliberately produced *before* any
model results, in the sequence the build brief mandates:

| Phase | Deliverable in this repo | Status |
|-------|--------------------------|--------|
| 0 — Environment | `environment.yml`, `docs/PHASE0_environment.md`, `scripts/verify_quickstart.py` | ✅ scaffolded |
| 1 — Tanzania inputs | `docs/PHASE1_tanzania_inputs.md`, `config/SOURCES.template.md`, `config/config.template.yaml`, `config/tanzania.yaml` | ✅ scaffolded (data download is a manual GIS step) |
| 2 — Validation | `docs/PHASE2_validation.md`, `src/onstove_pipeline/validate.py` | ✅ template + helper (run blocked on Phase 1 data) |
| 3 — Sensitivity | `src/onstove_pipeline/sweep.py`, `config/*.yaml` sweep block | ✅ harness (runnable once base case validates) |
| 4 — Output schema | `src/onstove_pipeline/schema.py`, `schema/*.schema.json`, `src/onstove_pipeline/export.py`, `docs/PHASE4_data_contract.md` | ✅ contract + exporter |
| 5 — Dashboard | *(separate front-end repo — reads Phase 4 outputs)* | out of scope here |

There are **no model results checked in**, by design. Generating provisional
numbers without a validated base case is exactly the failure mode this pipeline
exists to prevent.

## Layout

```
pipeline/
├── README.md                     # this file
├── environment.yml               # conda env for the pipeline (onstove + parquet + validation)
├── config/
│   ├── config.template.yaml      # per-country config template (every non-layer assumption)
│   ├── tanzania.yaml             # Tanzania assumptions (TOOL33 fNRB floor, etc.)
│   └── SOURCES.template.md       # per-layer provenance log to fill in during Phase 1
├── docs/
│   ├── PHASE0_environment.md     # environment setup + quickstart confirmation
│   ├── PHASE1_tanzania_inputs.md # input-acquisition checklist (URLs, years, licences)
│   ├── PHASE2_validation.md      # validation report template (the credibility anchor)
│   └── PHASE4_data_contract.md   # documented schema contract for the dashboard
├── schema/
│   ├── country_summary.schema.json   # JSON Schema for the country-level tier
│   └── cell_allocation.schema.json   # JSON Schema for the cell-level tier
├── scripts/
│   └── verify_quickstart.py      # Phase 0: confirm the OnStove install works
├── src/onstove_pipeline/
│   ├── __init__.py
│   ├── config.py                 # load + validate a country config.yaml
│   ├── schema.py                 # the output schema, as code (single source of truth)
│   ├── export.py                 # serialise an OnStove model to the contract files
│   ├── sweep.py                  # sensitivity-sweep harness over the parameter grid
│   └── validate.py               # compare a run against a published figure
└── tests/
    ├── test_config.py            # stdlib unittest — runs without the geospatial stack
    └── test_schema.py
```

## Recommended sequencing

1. **Phase 0** — stand up the environment, run `scripts/verify_quickstart.py`.
2. **Phase 1** — assemble Tanzania inputs (the bulk of the GIS effort).
3. **Phase 2** — validate Tanzania against a published figure. **Stop and
   confirm before proceeding.** A single validated country is worth more than
   44 unvalidated ones.
4. **Phase 3** — sensitivities on the validated country.
5. **Phase 4** — export to the data contract.
6. **Phase 5** — rebuild the dashboard against real outputs.
7. **Only then** — generalise to the remaining SSA countries, flagging any
   without a published figure as `provisional`.

## Quick start (developer)

```bash
# from repo root
conda env create -f pipeline/environment.yml      # or mamba
conda activate onstove-pipeline
pip install -e .                                   # install the onstove package (editable)

# Phase 0 sanity check
python pipeline/scripts/verify_quickstart.py --check-imports

# pure-Python tests (no geospatial stack needed)
python -m unittest discover -s pipeline/tests -v
```

## Running against the published Mendeley dataset

The inputs (and the published outputs used for validation) come from
**"OnStove inputs and outputs"**, Mendeley Data
[doi:10.17632/7y943f6wf8.2](https://data.mendeley.com/datasets/7y943f6wf8/2),
generated with **OnStove v0.1.1** — the companion to Khavari et al. (2023),
*Nature Sustainability*. That dataset is both the Phase 1 input source **and**
the Phase 2 published figure (its per-scenario summary CSVs come from
`model.summary()`).

> ⚠️ **Run this locally, not in the Claude-Code-on-the-web sandbox.** That
> environment's network policy blocks `data.mendeley.com` and it has no
> geospatial stack (GDAL/rasterio/conda), so it can neither download the dataset
> nor execute OnStove. To do either *in* a web session, the environment owner
> would need to (a) widen the network policy to allow `data.mendeley.com` and
> (b) add the conda/GDAL stack to the environment's setup script. Otherwise use
> a local machine.

### Where to save the data

Recommended: a repo-relative, gitignored `data/<ISO3>/` bundle mirroring the
canonical per-country tree (`onstove/tests/tests_data/RWA/`). For Tanzania:

```
data/TZA/
├── TZA_prep_file.csv            # demographics/health specs
├── TZA_file_tech_specs.csv      # per-fuel techno-economic specs
├── TZA_scenario_file.csv        # discount rate / VSL / carbon price / COI / weights
├── model.pkl                    # prepared model (IF the dataset ships it)
├── published/summary.csv        # the dataset's published TZA summary (Phase 2 figure)
├── Administrative/ Demographics/ Biomass/ Electricity/ LPG/ Biogas/ ...
data/TZA/sensitivity/            # downloaded sensitivity Scenario_files/Technical_specs
outputs/TZA/                     # exporter + validation outputs
```

You don't have to physically move files — every path is read from
`pipeline/config/<country>.yaml`, so you can instead point `paths:` directly at
wherever the download already sits (absolute paths are fine, including Windows
paths like `C:/Users/.../OnStove inputs and outputs/...`).

### End-to-end on a properly provisioned machine

```bash
# 0. environment (Phase 0)
conda env create -f pipeline/environment.yml && conda activate onstove-pipeline
pip install "onstove==0.1.1"          # match the published figure's version!

# 1. INSPECT your download, then map paths into pipeline/config/tanzania.yaml.
python pipeline/scripts/fetch_inputs.py --from-local "/path/to/OnStove inputs and outputs"
#   - ships model.pkl per country?  -> set paths.model_pickle, skip processing.
#   - ships raw layers + CSVs?       -> align first (notebook / data_processing.py).

# 2. run Tanzania + export to the Phase 4 contract (config-driven, path-portable)
python pipeline/scripts/run_country.py --config pipeline/config/tanzania.yaml

# 3. validate against the dataset's published summary (Phase 2)
python pipeline/scripts/validate_against_published.py \
    --modelled outputs/TZA/TZA_country_summary.csv \
    --published data/TZA/published/summary.csv \
    --iso3 TZA --country Tanzania --tolerance 0.10 --out outputs/TZA/validation
```

Only once step 3 passes within tolerance do you flip `validation_status` to
`validated` in the config and proceed to sensitivities (Phase 3, `sweep.py`).

> The repo also ships the authors' **44-country Snakemake harness**
> (`snakefile.smk`), which expects raw data at a sibling `Clean cooking Africa
> paper/` path and the `ONSTOVE` env var. `run_country.py` is the portable
> single-country alternative and is the recommended starting point.

## Guardrails (read these)

- **No external output without a `validation_status`** and, ideally, a
  reproduced published figure behind it.
- **Every run records** its code version, input-data versions, and config.
  Reproducibility is the whole point.
- **National TOOL33 fNRB is the conservative floor**; sub-national MoFuSS values
  are preferred for project-level Article 6 / VCM crediting. Always label which
  was used (`fnrb_source`).
- **Model and dashboard are decoupled** via the Phase 4 data contract so neither
  blocks the other.
- **Confirm OnStove's licence and citation terms** before publishing or
  commercialising any output. OnStove is MIT-licensed (see `../LICENSE`); the
  SSA methodology is published under CC-BY-4.0 (see `../README.md` → *How to
  cite*).
