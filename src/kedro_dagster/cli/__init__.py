"""Click CLI commands for the Kedro-Dagster plugin."""

from kedro_dagster.cli.commands import commands, dagster_commands, init
from kedro_dagster.utils import DAGSTER_VERSION

if DAGSTER_VERSION >= (1, 10, 6):
    from kedro_dagster.cli.commands import DgProxyCommand  # noqa: F401

__all__ = [
    "commands",
    "dagster_commands",
    "init",
]

if DAGSTER_VERSION >= (1, 10, 6):
    __all__.append("DgProxyCommand")
