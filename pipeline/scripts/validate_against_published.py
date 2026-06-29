#!/usr/bin/env python
"""Phase 2 driver — validate a run against the Mendeley published summary.

The dataset "OnStove inputs and outputs" (Mendeley doi:10.17632/7y943f6wf8.2,
OnStove v0.1.1) ships, per scenario, a summary CSV produced by OnStove's own
``model.summary()``. That CSV is our published figure.

This script:
  1. reads the **modelled** run's country-summary CSV (the Phase 4 export);
  2. reads the **published** summary CSV from the dataset;
  3. maps both onto the data-contract headline metrics (handling summary()'s
     "Million"/"MUSD" units);
  4. compares them with :mod:`onstove_pipeline.validate` and writes a report.

Pure-Python (stdlib ``csv``) so it runs without the geospatial stack — the same
reason the comparison logic is unit-tested. Run it after a real OnStove run +
``onstove_pipeline.export`` have produced the modelled CSV.

Usage::

    python pipeline/scripts/validate_against_published.py \
        --modelled outputs/TZA/TZA_country_summary.csv \
        --published data/TZA/published/summary.csv \
        --iso3 TZA --country Tanzania --tolerance 0.10 \
        --out outputs/TZA/validation
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from onstove_pipeline import validate  # noqa: E402

# Map data-contract metrics to (substring matchers for the published summary()
# pretty column, scale-to-absolute factor). summary() reports Population in
# millions, net benefit / costs in MUSD, emissions already in Mt.
PUBLISHED_COLUMN_MATCHERS = {
    "population_reached": (("population",), 1e6),
    "total_tco2_mt_yr": (("reduced emissions", "co2"), 1.0),
    "deaths_avoided": (("deaths avoided",), 1.0),
    "total_net_benefit_usd": (("net benefit",), 1e6),
}


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _find_row(rows: list[dict[str, str]], tech: str) -> dict[str, str]:
    """Find the row whose technology/label column matches `tech` (case-insensitive)."""
    tech_l = tech.lower()
    for row in rows:
        for key, val in row.items():
            if val and val.strip().lower() == tech_l and (
                    "tech" in key.lower() or key.lower() in ("technology", "")):
                return row
    # fall back: any column equal to tech
    for row in rows:
        if any((v or "").strip().lower() == tech_l for v in row.values()):
            return row
    raise ValueError(f"no row matching technology {tech!r} found")


def published_metrics(published_csv: str | Path, technology: str = "total") -> dict[str, float]:
    """Extract contract metrics from a published summary() CSV."""
    rows = _read_csv(published_csv)
    row = _find_row(rows, technology)
    lowered = {k.lower(): k for k in row}
    out: dict[str, float] = {}
    for metric, (needles, scale) in PUBLISHED_COLUMN_MATCHERS.items():
        col = _match_column(lowered, needles)
        if col is None:
            continue
        try:
            out[metric] = float(row[col]) * scale
        except (TypeError, ValueError):
            continue
    return out


def modelled_metrics(modelled_csv: str | Path, technology: str = "total") -> dict[str, float]:
    """Extract contract metrics from our Phase 4 export (already contract names)."""
    rows = _read_csv(modelled_csv)
    row = _find_row(rows, technology)
    out: dict[str, float] = {}
    for metric in validate.DEFAULT_METRICS:
        if metric in row and row[metric] not in ("", None):
            try:
                out[metric] = float(row[metric])
            except ValueError:
                pass
    return out


def _match_column(lowered: dict[str, str], needles: tuple[str, ...]):
    for low, original in lowered.items():
        if all(n in low for n in needles):
            return original
    # looser: any needle present
    for low, original in lowered.items():
        if any(n in low for n in needles):
            return original
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--modelled", required=True, help="Phase 4 export country_summary.csv")
    p.add_argument("--published", required=True, help="dataset's published summary.csv")
    p.add_argument("--iso3", required=True)
    p.add_argument("--country", required=True)
    p.add_argument("--technology", default="total", help="row to compare (default: total)")
    p.add_argument("--tolerance", type=float, default=0.10)
    p.add_argument("--out", default=None, help="dir for the JSON+MD report")
    p.add_argument("--source", default="Mendeley doi:10.17632/7y943f6wf8.2 (OnStove v0.1.1)")
    args = p.parse_args(argv)

    modelled = modelled_metrics(args.modelled, args.technology)
    published = published_metrics(args.published, args.technology)
    if not published:
        print("ERROR: no headline metrics parsed from the published CSV; "
              "check its column names / pass the right --technology.", file=sys.stderr)
        return 2

    report = validate.compare(modelled, published, country=args.country,
                              iso3=args.iso3, published_source=args.source,
                              tolerance=args.tolerance)
    print(report.to_markdown())
    if args.out:
        paths = validate.write_report(report, args.out)
        print(f"wrote {paths['json']} and {paths['markdown']}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
