"""Serialise a finished OnStove model run to the dashboard data contract.

Produces the two tiers defined in :mod:`onstove_pipeline.schema`:

* ``<output_dir>/<iso3>_country_summary.csv``  — one row per technology (+ total)
* ``<output_dir>/<iso3>_cell_allocation.parquet`` — one row per raster cell

The dashboard never recomputes the model; it reads these files. Every row
carries provenance columns (``model_version``, ``run_timestamp``,
``validation_status``) so the front end can show whether a country's numbers are
validated or provisional.

This module imports pandas / pyarrow / onstove **lazily**, so the rest of the
pipeline (config, schema) stays importable without the geospatial stack.

Honesty note: the derived MAC and carbon-revenue columns are computed from the
model's cost stack and emissions. They are clearly marked ``derived`` in the
schema. If the inputs needed for a derivation are absent, the column is written
as null rather than guessed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import schema

# OnStove summary() pretty column names -> our contract names (1:1 maps only).
_SUMMARY_RENAME = {
    "Max benefit technology": "technology",
    "Population (Million)": "_population_million",
    "Households (Millions)": "_households_million",
    "Total net benefit (MUSD)": "_total_net_benefit_musd",
    "Total deaths avoided (pp/yr)": "deaths_avoided",
    "Reduced emissions (Mton CO2eq)": "total_tco2_mt_yr",
    "hours/hh.day": "time_saved_hours",
    "Investment costs (MUSD)": "_investment_musd",
    "Fuel costs (MUSD)": "_fuel_musd",
    "O&M costs (MUSD)": "_om_musd",
}


def annuity_factor(rate: float, years: int) -> float:
    """Present-value annuity factor for 1 unit/yr over `years` at `rate`."""
    if years <= 0:
        return 0.0
    if rate == 0:
        return float(years)
    return (1 - (1 + rate) ** -years) / rate


def build_country_summary(model: Any, cfg: dict[str, Any], scenario_id: str = "base") -> "Any":
    """Build the country-level summary DataFrame from a run OnStove `model`.

    `model` must already have had ``model.run(...)`` called (so ``summary()``
    works). `cfg` is a validated config dict (see :mod:`onstove_pipeline.config`).
    """
    import numpy as np  # noqa: F401  (kept for clarity; pandas pulls it in)
    import pandas as pd

    raw = model.summary(total=True, pretty=True).rename(columns=_SUMMARY_RENAME)

    a = cfg["assumptions"]
    prov = cfg["provenance"]
    crediting = a.get("crediting_period_years") or 0
    discount = a["discount_rate"]
    carbon_price = a.get("carbon_price_usd_per_tco2")

    out = pd.DataFrame()
    out["technology"] = raw["technology"].astype(str)
    out["country"] = cfg["country"]["name"]
    out["iso3"] = cfg["country"]["iso3"]
    out["scenario_id"] = scenario_id

    # convert summary units (millions/MUSD) to absolute units
    households = raw["_households_million"] * 1e6
    out["households_reached"] = households
    out["population_reached"] = raw["_population_million"] * 1e6
    out["total_net_benefit_usd"] = raw["_total_net_benefit_musd"] * 1e6
    out["total_tco2_mt_yr"] = raw["total_tco2_mt_yr"]
    out["deaths_avoided"] = raw["deaths_avoided"]
    out["time_saved_hours"] = raw["time_saved_hours"]

    investment_usd = raw["_investment_musd"] * 1e6
    fuel_usd = raw["_fuel_musd"] * 1e6

    # per-household / per-tonne derivations (guard divide-by-zero -> NaN)
    safe_hh = households.replace(0, pd.NA)
    out["net_benefit_usd_per_hh_yr"] = out["total_net_benefit_usd"] / safe_hh
    # total_tco2_mt_yr is in Mt; convert to tonnes for per-hh
    total_tco2_t = out["total_tco2_mt_yr"] * 1e6
    out["tco2_per_hh_yr"] = total_tco2_t / safe_hh
    out["capex_usd_per_hh"] = investment_usd / safe_hh
    out["fuel_cost_usd_per_hh_yr"] = fuel_usd / safe_hh

    # MAC ex-carbon-revenue: net cost per tonne abated. Net annual cost =
    # -(net benefit excluding carbon revenue). We approximate the carbon-revenue
    # component and remove it so the MAC is "ex-carbon".
    if carbon_price:
        carbon_rev_per_hh_yr = out["tco2_per_hh_yr"] * carbon_price
        out["carbon_revenue_npv_usd_per_hh"] = (
            carbon_rev_per_hh_yr * annuity_factor(discount, int(crediting)))
        # net benefit per tonne, then flip sign to a cost; subtract carbon price
        nb_per_tonne = out["net_benefit_usd_per_hh_yr"] / out["tco2_per_hh_yr"].replace(0, pd.NA)
        out["mac_usd_per_tco2"] = -(nb_per_tonne) - carbon_price
    else:
        out["carbon_revenue_npv_usd_per_hh"] = pd.NA
        out["mac_usd_per_tco2"] = pd.NA

    # assumption + provenance columns (constant per scenario)
    out["fnrb"] = a.get("fnrb")
    out["fnrb_source"] = a.get("fnrb_source")
    out["discount_rate"] = discount
    out["carbon_price"] = carbon_price
    out["vsl"] = a.get("vsl_usd")
    out["model_version"] = prov.get("model_version")
    out["run_timestamp"] = prov.get("run_timestamp")
    out["validation_status"] = prov.get("validation_status", "provisional")

    # order columns exactly per the contract
    return out[schema.field_names("country_summary")]


def build_cell_allocation(model: Any, cfg: dict[str, Any]) -> "Any":
    """Build the cell-level allocation DataFrame from a run OnStove `model`."""
    import pandas as pd

    gdf = model.gdf.copy()
    # centroids in lon/lat (EPSG:4326)
    centroids = gdf.geometry.centroid.to_crs(4326)

    out = pd.DataFrame()
    out["cell_id"] = range(len(gdf))
    out["lon"] = centroids.x.to_numpy()
    out["lat"] = centroids.y.to_numpy()
    out["country"] = cfg["country"]["name"]
    out["population"] = gdf.get("Calibrated_pop")
    out["optimal_technology"] = gdf.get("max_benefit_tech")
    out["net_benefit_usd"] = gdf.get("maximum_net_benefit")
    if "IsUrban" in gdf.columns:
        out["settlement_type"] = gdf["IsUrban"].map(
            lambda v: "urban" if v and v > 0 else "rural")
    else:
        out["settlement_type"] = None

    return out[schema.field_names("cell_allocation")]


def export(model: Any, cfg: dict[str, Any], output_dir: Optional[str | Path] = None,
           scenario_id: str = "base", validate: bool = True) -> dict[str, Path]:
    """Write both tiers to disk. Returns the written paths.

    Raises ValueError if `validate=True` and a tier fails the data contract.
    """
    out_dir = Path(output_dir or cfg["paths"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    iso3 = cfg["country"]["iso3"]

    summary_df = build_country_summary(model, cfg, scenario_id=scenario_id)
    cell_df = build_cell_allocation(model, cfg)

    if validate:
        _validate_df("country_summary", summary_df)
        _validate_df("cell_allocation", cell_df)

    summary_path = out_dir / f"{iso3}_country_summary.csv"
    cell_path = out_dir / f"{iso3}_cell_allocation.parquet"
    summary_df.to_csv(summary_path, index=False)
    cell_df.to_parquet(cell_path, index=False)  # needs pyarrow
    return {"country_summary": summary_path, "cell_allocation": cell_path}


def _validate_df(tier: str, df: "Any") -> None:
    """Validate a DataFrame against the contract; raise on first batch of errors."""
    rows = df.where(df.notna(), None).to_dict(orient="records")
    errors = schema.validate_rows(tier, rows)
    if errors:
        preview = "\n  - ".join(errors[:20])
        more = "" if len(errors) <= 20 else f"\n  ...(+{len(errors) - 20} more)"
        raise ValueError(f"{tier} fails the data contract:\n  - {preview}{more}")
