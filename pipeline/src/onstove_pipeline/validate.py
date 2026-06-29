"""Phase 2 — validate a run against a published figure.

This is the credibility anchor for the whole project. It compares a run's
headline metrics to a published OnStove/IEA figure, reports the percentage
difference per metric, and decides pass/fail against an agreed tolerance.

It does **not** fetch or invent published numbers — you supply them (typically
read from ``docs/PHASE2_validation.md``'s table or a small JSON file). The
output is a structured report you commit alongside the validated base case.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Headline metrics worth validating (contract column -> human label).
DEFAULT_METRICS = {
    "population_reached": "Population gaining clean cooking access",
    "total_tco2_mt_yr": "Emissions reduced (Mt CO2e/yr)",
    "deaths_avoided": "Premature deaths avoided",
    "total_net_benefit_usd": "Net benefit (USD)",
}


@dataclass
class MetricComparison:
    metric: str
    label: str
    published: float
    modelled: float
    pct_difference: float   # (modelled - published) / published
    within_tolerance: bool


@dataclass
class ValidationReport:
    country: str
    iso3: str
    published_source: str
    tolerance: float
    comparisons: list[MetricComparison]
    passed: bool
    generated_at: str

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def to_markdown(self) -> str:
        lines = [
            f"# Validation report — {self.country} ({self.iso3})",
            "",
            f"- **Published source:** {self.published_source}",
            f"- **Tolerance:** ±{self.tolerance:.0%}",
            f"- **Generated:** {self.generated_at}",
            f"- **Result:** {'PASS ✅' if self.passed else 'FAIL ❌'}",
            "",
            "| Metric | Published | Modelled | Δ% | Within tol? |",
            "|--------|-----------|----------|-----|-------------|",
        ]
        for c in self.comparisons:
            lines.append(
                f"| {c.label} | {c.published:,.3g} | {c.modelled:,.3g} | "
                f"{c.pct_difference:+.1%} | {'yes' if c.within_tolerance else 'NO'} |")
        if not self.passed:
            lines += [
                "",
                "## Residual gap — investigate before freezing",
                "Check, in order: OnStove version vs publication, input-layer "
                "years, baseline-fuel shares, and parameter differences "
                "(discount rate, VSL, fNRB, carbon price). Iterate until within "
                "tolerance, then tag the code + data + config that produced it.",
            ]
        return "\n".join(lines) + "\n"


def compare(modelled: dict[str, float], published: dict[str, float],
            country: str, iso3: str, published_source: str,
            tolerance: float = 0.10,
            metrics: Optional[dict[str, str]] = None) -> ValidationReport:
    """Compare modelled vs published headline metrics.

    `modelled` / `published` are flat dicts of metric -> value. Only metrics
    present in BOTH (and in `metrics`) are compared.
    """
    metrics = metrics or DEFAULT_METRICS
    comparisons: list[MetricComparison] = []
    for metric, label in metrics.items():
        if metric not in modelled or metric not in published:
            continue
        pub = float(published[metric])
        mod = float(modelled[metric])
        pct = (mod - pub) / pub if pub != 0 else float("inf")
        comparisons.append(MetricComparison(
            metric=metric, label=label, published=pub, modelled=mod,
            pct_difference=pct, within_tolerance=abs(pct) <= tolerance))

    passed = bool(comparisons) and all(c.within_tolerance for c in comparisons)
    return ValidationReport(
        country=country, iso3=iso3, published_source=published_source,
        tolerance=tolerance, comparisons=comparisons, passed=passed,
        generated_at=_utc_now())


def modelled_from_summary(summary_df: "Any", technology: str = "total") -> dict[str, float]:
    """Pull headline metrics out of a country-summary DataFrame for one row."""
    row = summary_df[summary_df["technology"] == technology]
    if row.empty:
        raise ValueError(f"no '{technology}' row in summary")
    row = row.iloc[0]
    return {m: float(row[m]) for m in DEFAULT_METRICS if m in summary_df.columns}


def write_report(report: ValidationReport, out_dir: str | Path) -> dict[str, Path]:
    """Write the report as both JSON (machine) and Markdown (human)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{report.iso3}_validation.json"
    md_path = out_dir / f"{report.iso3}_validation.md"
    json_path.write_text(json.dumps(report.to_dict(), indent=2) + "\n")
    md_path.write_text(report.to_markdown())
    return {"json": json_path, "markdown": md_path}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
