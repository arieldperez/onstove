"""The OnStove pipeline output data contract — as code.

This module is the **single source of truth** for the two output tiers the
dashboard reads. The JSON Schema files in ``pipeline/schema/*.schema.json`` are
*generated* from here (run this module as ``__main__`` to regenerate them), and
the exporter (:mod:`onstove_pipeline.export`) validates against these field
definitions before writing.

Two tiers (per the build brief):

* **Country-level summary** — one row per ``country × technology × scenario``.
  CSV. Small, human-readable, drives the tables / MAC curve / cost-curve.
* **Cell-level allocation** — one row per ~1 km² raster cell. Parquet (large).
  Drives the real dot/choropleth map (replacing the prototype's probabilistic
  placement).

Every field carries: dtype, unit, whether it is required, whether nulls are
allowed, a human description, and — crucially — ``source``: where the value
comes from in the OnStove model (which keeps the contract honest about what is
a real model output vs. a derived/provenance field).

Dependency-light by design: standard library only. Validation operates on any
"row-dict iterable", so it does not require pandas.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

# --- JSON-schema type mapping ------------------------------------------------
_JSON_TYPES = {
    "string": "string",
    "float": "number",
    "int": "integer",
    "bool": "boolean",
}


@dataclass(frozen=True)
class Field:
    """One column in an output tier."""

    name: str
    dtype: str  # one of _JSON_TYPES keys
    unit: str
    description: str
    source: str  # provenance: OnStove summary() col, gdf col, config, or "derived"
    required: bool = True
    nullable: bool = False
    enum: Optional[tuple[str, ...]] = None

    def json_property(self) -> dict[str, Any]:
        json_type = _JSON_TYPES[self.dtype]
        types: list[str] = [json_type]
        if self.nullable:
            types.append("null")
        prop: dict[str, Any] = {
            "type": types if len(types) > 1 else json_type,
            "description": f"{self.description} [{self.unit}] (source: {self.source})",
        }
        if self.enum is not None:
            prop["enum"] = list(self.enum) + ([None] if self.nullable else [])
        return prop


# Allowed values shared across tiers.
VALIDATION_STATUS = ("provisional", "validated")
FNRB_SOURCES = ("TOOL33_national", "MoFuSS_subnational", "global_0.30")
SETTLEMENT_TYPES = ("urban", "rural")


# =============================================================================
# Tier 1 — country-level summary (CSV)
# =============================================================================
COUNTRY_SUMMARY_FIELDS: tuple[Field, ...] = (
    Field("country", "string", "-", "Country name", "config"),
    Field("iso3", "string", "-", "ISO3166-1 alpha-3 code", "config"),
    Field("scenario_id", "string", "-",
          "Scenario identifier (base case or a sensitivity scenario)", "config/sweep"),
    Field("technology", "string", "-",
          "Allocated cooking technology (or 'total')", "summary: Max benefit technology"),
    # reach
    Field("households_reached", "float", "households",
          "Households for which this tech is optimal",
          "summary: Households (Millions) ×1e6"),
    Field("population_reached", "float", "people",
          "Population for which this tech is optimal",
          "summary: Population (Million) ×1e6"),
    # net benefit
    Field("net_benefit_usd_per_hh_yr", "float", "USD/household/yr",
          "Annualised net benefit per household",
          "derived: total_net_benefit_usd / households_reached"),
    Field("total_net_benefit_usd", "float", "USD",
          "Total net benefit for this tech×scenario",
          "summary: Total net benefit (MUSD) ×1e6"),
    # emissions
    Field("tco2_per_hh_yr", "float", "tCO2e/household/yr",
          "Avoided emissions per household per year",
          "derived: total_tco2 / households_reached"),
    Field("total_tco2_mt_yr", "float", "Mt CO2e/yr",
          "Total avoided emissions per year",
          "summary: Reduced emissions (Mton CO2eq)"),
    # health + time
    Field("deaths_avoided", "float", "deaths/yr",
          "Premature deaths avoided per year",
          "summary: Total deaths avoided (pp/yr)"),
    Field("time_saved_hours", "float", "hours/household/day",
          "Time saved (cooking + collection) per household per day",
          "summary: hours/hh.day"),
    # economics for the MAC / cost curves
    Field("mac_usd_per_tco2", "float", "USD/tCO2e",
          "Marginal abatement cost, EX carbon revenue", "derived", nullable=True),
    Field("carbon_revenue_npv_usd_per_hh", "float", "USD/household",
          "NPV of carbon credit revenue per household over the crediting period",
          "derived: tco2_per_hh_yr × carbon_price × annuity(crediting_period, discount)",
          nullable=True),
    Field("capex_usd_per_hh", "float", "USD/household",
          "Up-front capital cost per household",
          "derived: Investment costs (MUSD) ×1e6 / households_reached"),
    Field("fuel_cost_usd_per_hh_yr", "float", "USD/household/yr",
          "Annual fuel cost per household",
          "derived: Fuel costs (MUSD) ×1e6 / households_reached"),
    # assumption columns (so each row is self-describing)
    Field("fnrb", "float", "fraction",
          "Fraction of non-renewable biomass used", "config", nullable=True),
    Field("fnrb_source", "string", "-",
          "Provenance of the fNRB value", "config", enum=FNRB_SOURCES),
    Field("discount_rate", "float", "fraction", "Discount rate", "config"),
    Field("carbon_price", "float", "USD/tCO2e", "Carbon price assumption",
          "config", nullable=True),
    Field("vsl", "float", "USD/life", "Value of a statistical life",
          "config", nullable=True),
    # provenance
    Field("model_version", "string", "-",
          "OnStove code version / git sha that produced the run", "provenance"),
    Field("run_timestamp", "string", "ISO-8601 UTC",
          "When the run was executed", "provenance"),
    Field("validation_status", "string", "-",
          "Whether this row is validated against a published figure",
          "provenance", enum=VALIDATION_STATUS),
)


# =============================================================================
# Tier 2 — cell-level allocation (Parquet)
# =============================================================================
CELL_ALLOCATION_FIELDS: tuple[Field, ...] = (
    Field("cell_id", "int", "-", "Stable per-country cell index", "derived: gdf index"),
    Field("lon", "float", "degrees", "Cell centroid longitude (EPSG:4326)",
          "derived: gdf geometry centroid"),
    Field("lat", "float", "degrees", "Cell centroid latitude (EPSG:4326)",
          "derived: gdf geometry centroid"),
    Field("country", "string", "-", "Country name", "config"),
    Field("population", "float", "people", "Calibrated population in the cell",
          "gdf: Calibrated_pop"),
    Field("optimal_technology", "string", "-",
          "Technology with the highest net benefit in the cell",
          "gdf: max_benefit_tech", nullable=True),
    Field("net_benefit_usd", "float", "USD",
          "Maximum net benefit in the cell (per household)",
          "gdf: maximum_net_benefit", nullable=True),
    Field("settlement_type", "string", "-", "Urban or rural",
          "gdf: IsUrban", enum=SETTLEMENT_TYPES, nullable=True),
)


TIERS: dict[str, tuple[Field, ...]] = {
    "country_summary": COUNTRY_SUMMARY_FIELDS,
    "cell_allocation": CELL_ALLOCATION_FIELDS,
}


# --- JSON Schema generation --------------------------------------------------
def to_json_schema(tier: str) -> dict[str, Any]:
    """Build a JSON Schema (draft 2020-12) for one tier's row objects."""
    if tier not in TIERS:
        raise KeyError(f"unknown tier {tier!r}; choose from {list(TIERS)}")
    fields = TIERS[tier]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"OnStove pipeline — {tier} row",
        "type": "object",
        "additionalProperties": False,
        "required": [f.name for f in fields if f.required],
        "properties": {f.name: f.json_property() for f in fields},
    }


def field_names(tier: str) -> list[str]:
    return [f.name for f in TIERS[tier]]


# --- lightweight, pandas-free validation -------------------------------------
def validate_rows(tier: str, rows: Iterable[dict[str, Any]]) -> list[str]:
    """Validate an iterable of row dicts against a tier. Returns a list of error
    strings (empty == valid). Pure-Python; does not require pandas/jsonschema.
    """
    fields = TIERS[tier]
    by_name = {f.name: f for f in fields}
    required = {f.name for f in fields if f.required}
    errors: list[str] = []

    for i, row in enumerate(rows):
        missing = required - row.keys()
        if missing:
            errors.append(f"row {i}: missing required columns {sorted(missing)}")
        extra = row.keys() - by_name.keys()
        if extra:
            errors.append(f"row {i}: unexpected columns {sorted(extra)}")
        for name, value in row.items():
            f = by_name.get(name)
            if f is None:
                continue
            if value is None:
                if not f.nullable:
                    errors.append(f"row {i}: column '{name}' is null but not nullable")
                continue
            if not _type_ok(f.dtype, value):
                errors.append(
                    f"row {i}: column '{name}'={value!r} is not {f.dtype}")
            if f.enum is not None and value not in f.enum:
                errors.append(
                    f"row {i}: column '{name}'={value!r} not in {f.enum}")
    return errors


def _type_ok(dtype: str, value: Any) -> bool:
    if dtype == "string":
        return isinstance(value, str)
    if dtype == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if dtype == "float":
        # ints are acceptable where floats are expected
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if dtype == "bool":
        return isinstance(value, bool)
    return False


def write_json_schemas(out_dir: Path) -> list[Path]:
    """(Re)generate the .schema.json files from the field definitions."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for tier in TIERS:
        path = out_dir / f"{tier}.schema.json"
        path.write_text(json.dumps(to_json_schema(tier), indent=2) + "\n")
        written.append(path)
    return written


if __name__ == "__main__":
    # Regenerate pipeline/schema/*.schema.json from this module.
    # __file__ = pipeline/src/onstove_pipeline/schema.py -> parents[2] = pipeline/
    schema_dir = Path(__file__).resolve().parents[2] / "schema"
    for p in write_json_schemas(schema_dir):
        print(f"wrote {p}")
