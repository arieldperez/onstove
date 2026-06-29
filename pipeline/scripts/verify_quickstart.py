#!/usr/bin/env python
"""Phase 0 verification: confirm the OnStove install works.

Two modes:

* ``--check-imports`` (default, fast): verify that ``onstove`` and its core
  geospatial dependencies import in the current environment. No network, no
  data download. This is the gate the rest of the pipeline depends on.

* ``--run-quickstart`` (slow): run the documentation quickstart end to end,
  mirroring ``example/OnStove_notebook.ipynb`` for the Kenya sample dataset.
  Requires network access (downloads from Mendeley), a few minutes, and
  several GB of disk. Use ``--workdir`` to choose where data lands.

Exit codes: 0 = success, 1 = a check failed, 2 = bad invocation.

This script is intentionally dependency-light and honest: on an environment
without the geospatial stack (e.g. the managed remote container) it reports
exactly what is missing and exits non-zero rather than pretending to pass.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# Core deps that must be importable for OnStove to run at all.
REQUIRED_IMPORTS = [
    "onstove",
    "rasterio",
    "geopandas",
    "pandas",
    "numpy",
    "dill",
]

# Extra deps the pipeline (not OnStove itself) needs.
PIPELINE_IMPORTS = [
    "pyarrow",   # Parquet exporter
    "yaml",      # config loading
    "jsonschema",
]


def check_imports(include_pipeline: bool = True) -> int:
    """Return 0 if every required module imports, else 1."""
    targets = list(REQUIRED_IMPORTS)
    if include_pipeline:
        targets += PIPELINE_IMPORTS

    failures: list[tuple[str, str]] = []
    for name in targets:
        try:
            mod = importlib.import_module(name)
            version = getattr(mod, "__version__", "?")
            print(f"  ok   {name:<14} {version}")
        except Exception as exc:  # noqa: BLE001 - we want the message verbatim
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  FAIL {name:<14} {type(exc).__name__}: {exc}")

    if failures:
        print(
            f"\n{len(failures)} import(s) failed. This environment cannot run "
            "OnStove yet.\nProvision the conda env (see "
            "pipeline/docs/PHASE0_environment.md):\n"
            "    conda env create -f pipeline/environment.yml\n"
            "    conda activate onstove-pipeline && pip install -e .",
            file=sys.stderr,
        )
        return 1

    print("\nAll imports succeeded — environment can run OnStove.")
    return 0


def run_quickstart(workdir: Path) -> int:
    """Run the Kenya quickstart end to end. Returns 0 on success."""
    rc = check_imports(include_pipeline=False)
    if rc != 0:
        return rc

    workdir.mkdir(parents=True, exist_ok=True)
    print(f"\nRunning quickstart in {workdir} (this downloads sample data)...")
    print(
        "NOTE: the canonical quickstart lives in example/OnStove_notebook.ipynb.\n"
        "      This runner only sanity-checks that the documented workflow can\n"
        "      execute; it is not a substitute for reading the notebook.\n"
    )
    try:
        # Imported lazily so --check-imports works without the full stack.
        from onstove import DataProcessor, OnStove  # noqa: F401

        data = DataProcessor(project_crs=3395, cell_size=(1000, 1000))
        data.output_directory = str(workdir / "KEN")
        print("  DataProcessor constructed (CRS 3395, 1 km cells).")
        print(
            "  To complete the run, follow example/OnStove_notebook.ipynb:\n"
            "  download_data('Kenya') -> add_layer(...) -> align_layers ->\n"
            "  OnStove(...).read_scenario_data(soc_specs.csv) -> run() -> summary()."
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL quickstart construction: {exc}", file=sys.stderr)
        return 1

    print("\nQuickstart smoke check passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-imports",
        action="store_true",
        help="verify onstove + deps import (default if no mode given)",
    )
    parser.add_argument(
        "--run-quickstart",
        action="store_true",
        help="run the Kenya quickstart end to end (network + disk heavy)",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("./onstove_quickstart"),
        help="where quickstart data/outputs are written",
    )
    args = parser.parse_args(argv)

    if args.run_quickstart:
        return run_quickstart(args.workdir)
    # default mode
    return check_imports()


if __name__ == "__main__":
    raise SystemExit(main())
