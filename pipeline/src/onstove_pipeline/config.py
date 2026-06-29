"""Load and validate a per-country ``config.yaml``.

Dependency-light: standard library + PyYAML only, so it runs without the
geospatial stack. Validation is structural (required keys, types, ranges,
internal consistency) — it does NOT touch GIS data.

CLI::

    python -m onstove_pipeline.config pipeline/config/tanzania.yaml
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import schema

REQUIRED_TOP_LEVEL = ("country", "provenance", "paths", "spatial",
                      "technologies", "assumptions")


@dataclass
class ConfigError(Exception):
    """Raised when a config fails validation. Carries all problems at once."""

    problems: list[str] = field(default_factory=list)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "invalid config:\n  - " + "\n  - ".join(self.problems)


def load(path: str | Path) -> dict[str, Any]:
    """Read a config.yaml into a dict (no validation)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigError([f"{path}: top level must be a mapping"])
    return data


def validate(cfg: dict[str, Any]) -> list[str]:
    """Return a list of problems (empty == valid). Does not raise."""
    problems: list[str] = []

    for key in REQUIRED_TOP_LEVEL:
        if key not in cfg:
            problems.append(f"missing top-level key: {key}")
    if problems:
        return problems  # structure too broken to check further

    country = cfg["country"]
    for key in ("name", "iso3"):
        if not country.get(key):
            problems.append(f"country.{key} is required")
    iso3 = str(country.get("iso3", ""))
    if iso3 and (len(iso3) != 3 or not iso3.isalpha()):
        problems.append(f"country.iso3 must be 3 letters, got {iso3!r}")

    prov = cfg["provenance"]
    status = prov.get("validation_status")
    if status not in schema.VALIDATION_STATUS:
        problems.append(
            f"provenance.validation_status must be one of "
            f"{schema.VALIDATION_STATUS}, got {status!r}")
    # Guardrail: a config cannot claim 'validated' without naming the figure.
    if status == "validated" and not prov.get("validated_against"):
        problems.append(
            "provenance.validation_status='validated' requires "
            "provenance.validated_against (the published figure citation)")

    spatial = cfg["spatial"]
    if not isinstance(spatial.get("project_crs"), int):
        problems.append("spatial.project_crs must be an integer EPSG code")
    if not _is_positive_number(spatial.get("cell_size_m")):
        problems.append("spatial.cell_size_m must be a positive number")

    techs = cfg["technologies"]
    if not isinstance(techs, list) or not techs:
        problems.append("technologies must be a non-empty list")

    a = cfg["assumptions"]
    _check_range(problems, a, "discount_rate", 0.0, 1.0, required=True)
    _check_range(problems, a, "fnrb", 0.0, 1.0, required=False, allow_none=True)
    _check_nonneg(problems, a, "vsl_usd", allow_none=True)
    _check_nonneg(problems, a, "carbon_price_usd_per_tco2", allow_none=True)
    _check_nonneg(problems, a, "crediting_period_years", allow_none=True)
    if a.get("fnrb_source") not in schema.FNRB_SOURCES:
        problems.append(
            f"assumptions.fnrb_source must be one of {schema.FNRB_SOURCES}, "
            f"got {a.get('fnrb_source')!r}")

    # sensitivity block is optional, but if present must be well-formed
    sens = cfg.get("sensitivity")
    if sens is not None:
        _validate_sensitivity(problems, sens)

    return problems


def load_and_validate(path: str | Path) -> dict[str, Any]:
    """Load a config and raise ConfigError if invalid."""
    cfg = load(path)
    problems = validate(cfg)
    if problems:
        raise ConfigError(problems)
    return cfg


# --- helpers -----------------------------------------------------------------
def _is_positive_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def _check_range(problems, d, key, lo, hi, required, allow_none=False):
    if key not in d or d[key] is None:
        if required and not allow_none:
            problems.append(f"assumptions.{key} is required")
        return
    v = d[key]
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        problems.append(f"assumptions.{key} must be a number, got {v!r}")
    elif not (lo <= v <= hi):
        problems.append(f"assumptions.{key}={v} out of range [{lo}, {hi}]")


def _check_nonneg(problems, d, key, allow_none=False):
    v = d.get(key)
    if v is None:
        if not allow_none:
            problems.append(f"assumptions.{key} is required")
        return
    if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
        problems.append(f"assumptions.{key} must be a non-negative number, got {v!r}")


def _validate_sensitivity(problems, sens):
    if not isinstance(sens, dict):
        problems.append("sensitivity must be a mapping")
        return
    axes = sens.get("axes", {})
    if axes and not isinstance(axes, dict):
        problems.append("sensitivity.axes must be a mapping of axis -> [values]")
    elif isinstance(axes, dict):
        for name, values in axes.items():
            if not isinstance(values, list) or not values:
                problems.append(f"sensitivity.axes.{name} must be a non-empty list")
    scenarios = sens.get("scenarios", [])
    if scenarios and not isinstance(scenarios, list):
        problems.append("sensitivity.scenarios must be a list")
    elif isinstance(scenarios, list):
        seen = set()
        for j, sc in enumerate(scenarios):
            if not isinstance(sc, dict) or "id" not in sc:
                problems.append(f"sensitivity.scenarios[{j}] needs an 'id'")
                continue
            if sc["id"] in seen:
                problems.append(f"sensitivity.scenarios: duplicate id {sc['id']!r}")
            seen.add(sc["id"])
            if not isinstance(sc.get("overrides", {}), dict):
                problems.append(
                    f"sensitivity.scenarios[{sc['id']}].overrides must be a mapping")


def _main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m onstove_pipeline.config <config.yaml>", file=sys.stderr)
        return 2
    path = argv[0]
    try:
        cfg = load(path)
    except (OSError, yaml.YAMLError) as exc:
        print(f"could not read {path}: {exc}", file=sys.stderr)
        return 1
    problems = validate(cfg)
    if problems:
        print(f"INVALID: {path}", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    name = cfg["country"]["name"]
    status = cfg["provenance"]["validation_status"]
    print(f"OK: {path} — {name} ({cfg['country']['iso3']}), status={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
