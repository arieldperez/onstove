"""Phase 3 — sensitivity-sweep harness.

Given a validated base case, this expands a country config's ``sensitivity``
block into a grid of runs, executes each through OnStove, and collects the
country-level summary for every run into one tidy frame for elasticity / tornado
analysis.

Two sweep kinds (both from the config's ``sensitivity`` block):

* **one-at-a-time axes** — each value of each axis swept while everything else
  is held at the base case (for clean elasticities).
* **named scenarios** — a handful of combined overrides (e.g. high-ambition).

Runnable ONLY after the base case validates (Phase 2). The harness refuses to
run a config whose ``validation_status`` is not ``validated`` unless explicitly
forced, so you cannot accidentally publish sensitivities off an unvalidated base.

The actual OnStove execution is delegated to ``run_fn`` — by default
:func:`_default_run_fn`, which mirrors ``scripts/sensitivity.py`` (read model,
apply parameter overrides, ``model.run(...)``). Inject a fake ``run_fn`` to unit
test the grid logic without the geospatial stack.

Design intent matches the repo's existing ``sensitivity.smk`` / ``scripts/
sensitivity.py`` so this can later be wired into Snakemake for parallelism.
"""
from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

# An override is a flat mapping of assumption-key -> value applied on top of base.
Override = dict[str, Any]
RunFn = Callable[[dict[str, Any], str], "Any"]  # (cfg, run_id) -> country_summary df


@dataclass
class SweepRun:
    """One planned run in the grid."""

    run_id: str
    kind: str            # "base" | "axis" | "scenario"
    axis: Optional[str]  # which axis varied (one-at-a-time runs)
    overrides: Override
    label: str = ""


def plan(cfg: dict[str, Any]) -> list[SweepRun]:
    """Expand a config's sensitivity block into the list of runs to execute.

    Always includes the base case as the first run. One-at-a-time axis values
    equal to the base value are de-duplicated.
    """
    sens = cfg.get("sensitivity") or {}
    base_assumptions = cfg["assumptions"]
    runs: list[SweepRun] = [SweepRun("base", "base", None, {}, "Base case")]

    # one-at-a-time axes
    for axis, values in (sens.get("axes") or {}).items():
        base_val = base_assumptions.get(axis)
        for v in values:
            if v == base_val:
                continue  # already covered by base
            rid = f"axis__{axis}__{_slug(v)}"
            runs.append(SweepRun(rid, "axis", axis, {axis: v},
                                 label=f"{axis} = {v}"))

    # named combined scenarios
    for sc in (sens.get("scenarios") or []):
        rid = f"scenario__{sc['id']}"
        runs.append(SweepRun(rid, "scenario", None, dict(sc.get("overrides", {})),
                             label=sc.get("label", sc["id"])))

    return runs


def apply_overrides(cfg: dict[str, Any], overrides: Override) -> dict[str, Any]:
    """Return a deep copy of cfg with `overrides` merged into `assumptions`."""
    new = copy.deepcopy(cfg)
    new["assumptions"].update(overrides)
    return new


def run(cfg: dict[str, Any], run_fn: Optional[RunFn] = None,
        output_dir: Optional[str | Path] = None,
        force_unvalidated: bool = False) -> "Any":
    """Execute the full sweep, returning one concatenated country-summary frame.

    Parameters
    ----------
    cfg : validated config dict.
    run_fn : callable (cfg, run_id) -> country-summary DataFrame. Defaults to a
        real OnStove run (:func:`_default_run_fn`). Inject a stub for testing.
    output_dir : where per-run summaries + the combined frame are written.
    force_unvalidated : allow running off a non-validated base case (NOT for
        anything published).
    """
    import pandas as pd

    status = cfg.get("provenance", {}).get("validation_status")
    if status != "validated" and not force_unvalidated:
        raise RuntimeError(
            "refusing to sweep: base case validation_status is "
            f"{status!r}, not 'validated'. Complete Phase 2 first, or pass "
            "force_unvalidated=True for a dry run (results stay provisional).")

    run_fn = run_fn or _default_run_fn
    out_dir = Path(output_dir or cfg["paths"]["output_dir"]) / "sensitivity"
    out_dir.mkdir(parents=True, exist_ok=True)

    runs = plan(cfg)
    frames = []
    for r in runs:
        run_cfg = apply_overrides(cfg, r.overrides)
        summary = run_fn(run_cfg, r.run_id)
        summary = summary.copy()
        summary["scenario_id"] = r.run_id
        summary["sweep_kind"] = r.kind
        summary["sweep_axis"] = r.axis
        summary["sweep_label"] = r.label
        summary.to_csv(out_dir / f"{r.run_id}.csv", index=False)
        frames.append(summary)

    combined = pd.concat(frames, ignore_index=True)
    combined_path = out_dir / f"{cfg['country']['iso3']}_sensitivity.csv"
    combined.to_csv(combined_path, index=False)
    return combined


def elasticities(combined: "Any", metric: str = "total_net_benefit_usd") -> "Any":
    """Compute simple arc elasticities of `metric` w.r.t. each swept axis.

    For each one-at-a-time axis run, elasticity ≈ (%Δmetric) / (%Δparameter)
    relative to the base case 'total' row. Returns a tidy frame suitable for a
    tornado chart.
    """
    import pandas as pd

    totals = combined[combined["technology"] == "total"].copy()
    base = totals[totals["scenario_id"] == "base"]
    if base.empty:
        raise ValueError("no base-case 'total' row found in combined frame")
    base_metric = float(base[metric].iloc[0])

    rows = []
    axis_runs = totals[totals["sweep_kind"] == "axis"]
    for _, run_row in axis_runs.iterrows():
        axis = run_row["sweep_axis"]
        # parameter value is carried in its own column where it exists
        new_param = run_row.get(axis)
        base_param = base.get(axis)
        base_param = float(base_param.iloc[0]) if base_param is not None and not base_param.empty else None
        new_metric = float(run_row[metric])
        d_metric = _pct_change(base_metric, new_metric)
        d_param = _pct_change(base_param, new_param) if base_param not in (None, 0) and new_param is not None else None
        elasticity = (d_metric / d_param) if d_param else None
        rows.append({
            "axis": axis,
            "scenario_id": run_row["scenario_id"],
            "base_metric": base_metric,
            "run_metric": new_metric,
            "pct_change_metric": d_metric,
            "elasticity": elasticity,
        })
    return pd.DataFrame(rows)


# --- helpers -----------------------------------------------------------------
def _slug(v: Any) -> str:
    return str(v).replace(".", "p").replace("-", "m").replace(" ", "_")


def _pct_change(base: Optional[float], new: Optional[float]) -> Optional[float]:
    if base in (None, 0) or new is None:
        return None
    return (new - base) / base


def _default_run_fn(cfg: dict[str, Any], run_id: str) -> "Any":
    """Real OnStove run for one parameter set. Mirrors scripts/sensitivity.py.

    Reads the prepared model pickle, applies the config's assumptions to the
    scenario data + tech specs, runs the allocation, and returns the
    country-level summary in the data contract's shape.
    """
    from onstove import OnStove  # lazy: geospatial stack only needed here

    from . import export

    paths = cfg["paths"]
    model = OnStove.read_model(paths["model_pickle"])
    model.read_scenario_data(paths["soc_specs"], delimiter=",")
    model.output_directory = str(Path(cfg["paths"]["output_dir"]) / "sensitivity" / run_id)

    # Push config assumptions onto the model's scenario specs where they map.
    a = cfg["assumptions"]
    _apply_assumption(model, "Discount_rate", a.get("discount_rate"))
    _apply_assumption(model, "Cost of carbon emissions", a.get("carbon_price_usd_per_tco2"))
    _apply_assumption(model, "VSL", a.get("vsl_usd"))
    # fNRB and LPG-specific overrides apply to technology objects:
    if a.get("lpg_fuel_cost_usd_per_kg") is not None and "LPG" in model.techs:
        model.techs["LPG"].fuel_cost = a["lpg_fuel_cost_usd_per_kg"]
    if a.get("lpg_capex_usd") is not None and "LPG" in model.techs:
        model.techs["LPG"].inv_cost = a["lpg_capex_usd"]

    if "Electricity" in model.techs:
        model.techs["Electricity"].get_capacity_cost(model)
    model.run(technologies=cfg["technologies"], restriction=a.get("restriction", True))

    return export.build_country_summary(model, cfg, scenario_id=run_id)


def _apply_assumption(model: Any, spec_key: str, value: Any) -> None:
    if value is None:
        return
    try:
        model.specs[spec_key] = value
    except Exception:  # noqa: BLE001 - spec layout differs across versions
        pass
