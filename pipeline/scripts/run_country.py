#!/usr/bin/env python
"""Config-driven single-country OnStove run + Phase 4 export.

Portable counterpart to ``scripts/model_run.py``: reads every path from a
country ``config.yaml`` (no ``ONSTOVE`` env var, no hardcoded sibling paths), so
you can point it straight at your downloaded dataset on any OS.

Flow (mirrors ``scripts/model_run.py`` + ``example/OnStove_notebook.ipynb``):
  1. load + validate the config;
  2. read the prepared ``model.pkl`` (``prepare_model`` output);
  3. load the scenario CSV, recompute electricity capacity cost;
  4. ``model.run(...)`` over the configured technologies;
  5. export to the data contract (CSV + Parquet) via ``onstove_pipeline.export``;
  6. save ``results.pkl`` and print the validation next-step.

Requires the geospatial stack + ``onstove`` (ideally ``onstove==0.1.1`` to match
the published figure). Not runnable in the web sandbox.

Building a model from RAW layers (no ``model.pkl`` in the dataset) is out of
scope here — that is what ``scripts/data_processing.py`` + ``model_preparation.py``
(driven by ``snakefile.smk``) or ``example/OnStove_notebook.ipynb`` do. This
script consumes the prepared ``model.pkl``.

Usage::

    python pipeline/scripts/run_country.py --config pipeline/config/tanzania.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from onstove_pipeline import config as cfgmod  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True, help="path to a country config.yaml")
    p.add_argument("--scenario-id", default="base",
                   help="scenario id stamped on the export (default: base)")
    p.add_argument("--no-export", action="store_true",
                   help="run only; skip the Phase 4 export")
    args = p.parse_args(argv)

    cfg = cfgmod.load_and_validate(args.config)
    paths = cfg["paths"]
    country = cfg["country"]["name"]

    # Lazy imports so config validation works without the geospatial stack.
    from onstove import OnStove

    from onstove_pipeline import export

    model_pkl = Path(paths["model_pickle"])
    if not model_pkl.exists():
        print(
            f"ERROR: prepared model not found at {model_pkl}.\n"
            "This runner consumes a prepared model.pkl. If your download only has\n"
            "raw layers, build it first with scripts/data_processing.py +\n"
            "model_preparation.py (see snakefile.smk) or example/OnStove_notebook.ipynb,\n"
            "then point paths.model_pickle at the resulting model.pkl.",
            file=sys.stderr,
        )
        return 2

    print(f"[{country}] reading model: {model_pkl}")
    model = OnStove.read_model(str(model_pkl))

    scenario_csv = paths.get("scenario_specs")
    print(f"[{country}] reading scenario data: {scenario_csv}")
    model.read_scenario_data(scenario_csv, delimiter=",")
    model.output_directory = paths["output_dir"]

    # Electricity capacity cost depends on the loaded scenario (see model_run.py).
    if "Electricity" in getattr(model, "techs", {}):
        model.techs["Electricity"].get_capacity_cost(model)

    techs = cfg["technologies"]
    restriction = cfg["assumptions"].get("restriction", True)
    print(f"[{country}] running {len(techs)} technologies (restriction={restriction})")
    model.run(technologies=techs, restriction=restriction)

    out_dir = Path(paths["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    results_pkl = paths.get("results_pickle", str(out_dir / "results.pkl"))
    model.to_pickle(str(results_pkl))
    print(f"[{country}] wrote {results_pkl}")

    if not args.no_export:
        written = export.export(model, cfg, scenario_id=args.scenario_id)
        for tier, path in written.items():
            print(f"[{country}] exported {tier}: {path}")
        print(
            "\nNext — validate against the published figure (Phase 2):\n"
            f"  python pipeline/scripts/validate_against_published.py \\\n"
            f"    --modelled {written['country_summary']} \\\n"
            f"    --published {paths.get('published_summary_csv', 'data/<ISO3>/published/summary.csv')} \\\n"
            f"    --iso3 {cfg['country']['iso3']} --country {country}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
