# Phase 0 — Environment setup

**Goal:** a reproducible Python environment that can run OnStove, with the
quickstart confirmed end to end before any real country data is touched.

## 1. Create the environment

OnStove's geospatial dependencies (GDAL, rasterio, geopandas) are far easiest
via `conda-forge`. From the repository root:

```bash
conda env create -f pipeline/environment.yml      # or: mamba env create -f ...
conda activate onstove-pipeline
```

Then install the OnStove package itself from this repo in editable mode so the
pipeline imports the exact code version under test:

```bash
pip install -e .
```

> If the published methodology you are validating against (Phase 2) used a
> specific OnStove release, install **that** version instead of editable HEAD —
> e.g. `conda create -n onstove -c conda-forge onstove=<version>` — and record
> the version in the validation report. The pip/conda release can lag the source
> methodology; check which the target publication used.

## 2. Pin every dependency (lockfile)

Geospatial stacks break across versions; reproducibility depends on pinning.
**After** the environment resolves and the quickstart passes, freeze it:

```bash
conda env export --no-builds > pipeline/environment.lock.yml
pip freeze                    > pipeline/requirements.lock
```

Commit both lockfiles together with the validated base case (Phase 2), tagged
with the OnStove code version that produced it.

## 3. Verify the install

```bash
# Fast check: are onstove + geospatial deps importable in this env?
python pipeline/scripts/verify_quickstart.py --check-imports

# Full check: run the documentation quickstart end to end (downloads ~Kenya
# sample data from Mendeley; needs network + a few minutes + ~GBs of disk).
python pipeline/scripts/verify_quickstart.py --run-quickstart --workdir /tmp/onstove_qs
```

The full quickstart mirrors `../example/OnStove_notebook.ipynb`: it downloads
the Kenya sample dataset, runs `DataProcessor` (CRS 3395, 1 km cells) to align
layers, builds an `OnStove` model from `soc_specs.csv` / `tech_specs.csv`,
calibrates the baseline, runs the net-benefit calculation, and writes a summary.

## 4. Note on this remote execution environment

This managed container does **not** ship the geospatial stack (no conda, no
`rasterio`/`gdal`). `verify_quickstart.py --check-imports` is expected to fail
here and to pass on a properly provisioned conda machine. The script exits
non-zero with a clear message rather than pretending the stack is present.

## Deliverable checklist

- [ ] `onstove-pipeline` conda env created and activates cleanly.
- [ ] `pip install -e .` succeeds; `python -c "import onstove"` works.
- [ ] `verify_quickstart.py --check-imports` passes.
- [ ] `verify_quickstart.py --run-quickstart` reproduces the example end to end.
- [ ] `environment.lock.yml` + `requirements.lock` committed.
- [ ] This README's Phase 0 box ticked.
