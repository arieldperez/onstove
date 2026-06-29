"""OnStove production pipeline.

Validated, audit-grade OnStove modelling for sub-Saharan Africa clean cooking,
plus the data contract the interactive dashboard reads.

Submodules
----------
config   : load + validate a per-country ``config.yaml``.
schema   : the output data contract, as code (single source of truth).
export   : serialise an OnStove model to the contract files (CSV + Parquet).
sweep    : sensitivity-sweep harness over the parameter grid (Phase 3).
validate : compare a run's headline metrics against a published figure (Phase 2).

Design rule: ``config`` and ``schema`` import with the standard library + PyYAML
only, so they run anywhere. ``export``/``sweep``/``validate`` import pandas,
pyarrow and onstove lazily, inside the functions that need them.
"""

__version__ = "0.1.0"

__all__ = ["config", "schema", "export", "sweep", "validate"]
