"""Shared constants for the Kedro-Dagster plugin."""

import re

KEDRO_DAGSTER_SEPARATOR = "__"
"""Separator used to convert dotted Kedro dataset names into Dagster-safe identifiers."""

DAGSTER_ALLOWED_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
"""Regex that matches valid Dagster asset/resource names."""

NOTHING_OUTPUT = "__nothing__"
"""Sentinel value returned by :class:`~kedro_dagster.datasets.DagsterNothingDataset`."""
