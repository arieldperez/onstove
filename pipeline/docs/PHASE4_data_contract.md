# Phase 4 — Output schema (the data contract)

**Goal:** a clean, structured contract between the model and the dashboard. The
dashboard **never recomputes the model** — it reads pre-computed, validated
results.

The contract is defined **as code** in
[`src/onstove_pipeline/schema.py`](../src/onstove_pipeline/schema.py) — that
module is the single source of truth. The JSON Schema files
([`schema/country_summary.schema.json`](../schema/country_summary.schema.json),
[`schema/cell_allocation.schema.json`](../schema/cell_allocation.schema.json))
are **generated** from it:

```bash
PYTHONPATH=pipeline/src python -m onstove_pipeline.schema   # regenerates *.schema.json
```

The exporter ([`export.py`](../src/onstove_pipeline/export.py)) builds both tiers
from a finished OnStove model and validates them against this contract before
writing.

## Two tiers

### Tier 1 — country-level summary (CSV)

One row per `country × technology × scenario` (plus a `technology = "total"`
row). Small and human-readable; drives the summary table, MAC curve and
cost-curve scatter.

File: `<output_dir>/<ISO3>_country_summary.csv`

| Column | Unit | Source |
|--------|------|--------|
| `country`, `iso3`, `scenario_id`, `technology` | – | config / `summary()` |
| `households_reached`, `population_reached` | households / people | `summary()` ×1e6 |
| `net_benefit_usd_per_hh_yr` | USD/hh/yr | derived |
| `total_net_benefit_usd` | USD | `summary()` ×1e6 |
| `tco2_per_hh_yr` | tCO2e/hh/yr | derived |
| `total_tco2_mt_yr` | Mt CO2e/yr | `summary()` |
| `deaths_avoided` | deaths/yr | `summary()` |
| `time_saved_hours` | h/hh/day | `summary()` |
| `mac_usd_per_tco2` | USD/tCO2e | derived (ex-carbon-revenue) |
| `carbon_revenue_npv_usd_per_hh` | USD/hh | derived |
| `capex_usd_per_hh`, `fuel_cost_usd_per_hh_yr` | USD/hh, USD/hh/yr | derived |
| `fnrb`, `fnrb_source` | fraction, – | config |
| `discount_rate`, `carbon_price`, `vsl` | – | config |
| `model_version`, `run_timestamp`, `validation_status` | – | provenance |

### Tier 2 — cell-level allocation (Parquet)

One row per ~1 km² raster cell. Large → Parquet. Drives the **real**
dot/choropleth map, replacing the prototype's probabilistic placement.

File: `<output_dir>/<ISO3>_cell_allocation.parquet`

| Column | Unit | Source |
|--------|------|--------|
| `cell_id` | – | gdf index |
| `lon`, `lat` | degrees (EPSG:4326) | gdf centroid |
| `country` | – | config |
| `population` | people | gdf `Calibrated_pop` |
| `optimal_technology` | – | gdf `max_benefit_tech` |
| `net_benefit_usd` | USD | gdf `maximum_net_benefit` |
| `settlement_type` | urban/rural | gdf `IsUrban` |

## Derived columns — how they are computed

The exporter never invents numbers. Derived columns are explicit functions of
real model outputs and config assumptions:

- `net_benefit_usd_per_hh_yr = total_net_benefit_usd / households_reached`
- `tco2_per_hh_yr = (total_tco2_mt_yr × 1e6) / households_reached`
- `capex_usd_per_hh = investment_costs_usd / households_reached`
- `fuel_cost_usd_per_hh_yr = fuel_costs_usd / households_reached`
- `carbon_revenue_npv_usd_per_hh = tco2_per_hh_yr × carbon_price ×
   annuity(discount_rate, crediting_period_years)`
- `mac_usd_per_tco2 = −(net_benefit_usd_per_hh_yr / tco2_per_hh_yr) −
   carbon_price`  (marginal abatement cost **excluding** carbon revenue)

If a required input is missing (e.g. no `carbon_price`), the derived column is
written as **null**, not guessed.

## Provenance & validation

Every row in **both** tiers carries `model_version`, `run_timestamp`, and
`validation_status`. The dashboard shows a per-country/scenario badge so users
never mistake a `provisional` country for a `validated` one. A config cannot be
marked `validated` without naming the published figure it reproduced
(enforced in `config.py`).

## Evolving the contract

Because the contract lives in one module, model and front end can evolve
independently: change a field in `schema.py`, regenerate the JSON Schemas,
bump `onstove_pipeline.__version__`, and the dashboard can pin to a schema
version. Treat removals/renames as breaking changes.
