# Phase 2 — Validate against published outputs (the critical phase)

**This is the step that makes everything defensible. Do not skip it.** No output
is presented externally until it carries a `validation_status` and, ideally, a
reproduced published figure behind it.

## Procedure

1. **Identify a published figure** for Tanzania (OnStove or IEA Access-for-All)
   with specific reported numbers: population gaining clean-cooking access by
   technology, emissions reduced, premature deaths avoided, and/or net benefit.
   Record the exact citation + DOI in `config/tanzania.yaml →
   provenance.validated_against`.
2. **Configure inputs to match** the publication's stated assumptions as closely
   as possible (layer years, baseline fuel shares, discount rate, VSL, fNRB,
   carbon price). Fill the `# TODO(Phase 2)` fields in `config/tanzania.yaml`.
3. **Run OnStove** and export the country summary (Phase 4 exporter).
4. **Compare** with `src/onstove_pipeline/validate.py` and record the % diff per
   headline metric.
5. **Agree the tolerance up front** (e.g. ±5–10% on headline metrics). If a
   metric is out of tolerance, investigate in order: OnStove version mismatch,
   input-layer year, baseline-fuel assumptions, parameter differences. Iterate
   until within tolerance.
6. **Freeze the validated base case.** Tag the exact code version, input data,
   and config; flip `validation_status` to `validated` (the config validator
   requires `validated_against` to be set before it will accept this).

## Tolerance (agree before running)

| Metric | Published | Tolerance |
|--------|-----------|-----------|
| Population gaining clean cooking access | _fill_ | ±10% |
| Emissions reduced (Mt CO2e/yr) | _fill_ | ±10% |
| Premature deaths avoided | _fill_ | ±10% |
| Net benefit (USD) | _fill_ | ±10% |

## Running the comparison

```python
from onstove_pipeline import config, export, validate

cfg = config.load_and_validate("pipeline/config/tanzania.yaml")
# ... build/run the OnStove model `model` (Phase 1 + model.run(...)) ...
summary = export.build_country_summary(model, cfg)

modelled  = validate.modelled_from_summary(summary, technology="total")
published = {                      # from the published figure (you supply these)
    "population_reached": ...,
    "total_tco2_mt_yr":   ...,
    "deaths_avoided":     ...,
    "total_net_benefit_usd": ...,
}
report = validate.compare(modelled, published,
                          country="Tanzania", iso3="TZA",
                          published_source="<citation + DOI>",
                          tolerance=0.10)
validate.write_report(report, "outputs/TZA/validation")
print(report.to_markdown())
```

`write_report` emits both `TZA_validation.json` (machine-readable, for the
dashboard's provenance badge) and `TZA_validation.md` (the human report).

## Deliverable

A validation report — published figure vs your run, per metric, with the
difference and an explanation of any residual gap. **This report is the
credibility anchor for the whole project.** Without it, no output should be
presented externally.

## Stop here

Per the recommended sequencing: once Tanzania validates, **stop and confirm
before proceeding** to sensitivities and the other countries. A single validated
country is worth more than 44 unvalidated ones.
