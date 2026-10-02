"""Drop-in logging shim that routes to Dagster logger when available."""

from __future__ import annotations

import logging as _logging

import coloredlogs
import dagster as dg
import structlog


def getLogger(name: str | None = None) -> _logging.Logger:
    """Return a logger, preferring Dagster's logger when a run is active.

    Parameters
    ----------
    name : str or None, optional
        Logger name, consistent with ``logging.getLogger``.

    Returns
    -------
    logging.Logger
        A standard logger instance. When a Dagster run is active, this is
        backed by Dagster's logging machinery.

    See Also
    --------
    `kedro_dagster.dagster.LoggerCreator` :
        Creates Dagster logger definitions from configuration.
    """
    try:
        # If there's an active Dagster context, this will succeed
        context = dg.OpExecutionContext.get()
        if context:
            logger: _logging.Logger = dg.get_dagster_logger(name)
            return logger
    except Exception as e:  # Fallback if no active Dagster context
        _logging.debug(f"No active Dagster context: {e}")

    # Otherwise, fall back to Python logging
    return _logging.getLogger(name)


_COLORED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_COLORED_DATEFMT = "%Y-%m-%d %H:%M:%S %z"


def _foreign_pre_chain() -> list[structlog.typing.Processor]:
    """Return the processors applied to records coming from standard logging."""
    return [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.stdlib.ExtraAdder(),
    ]


class _DagsterProcessorFormatter(structlog.stdlib.ProcessorFormatter):
    """Base for the structlog-backed formatters, configurable through a ``class`` key.

    Kedro 1.3 and later reject the ``()`` factory key in ``logging.yml``, so a
    formatter must be a ``logging.Formatter`` subclass that ``dictConfig`` can
    build from ``format``, ``datefmt`` and ``style`` alone. Rendering is done by
    structlog, so those arguments are accepted for compatibility and ignored.
    """

    def __init__(self, fmt: str | None = None, datefmt: str | None = None, style: str = "%") -> None:  # noqa: ARG002
        renderer = self._renderer()
        try:
            # Try the newer API with processors list
            super().__init__(
                foreign_pre_chain=_foreign_pre_chain(),
                processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
            )
        except TypeError:
            # Fallback to older API with single processor
            super().__init__(foreign_pre_chain=_foreign_pre_chain(), processor=renderer)

    @staticmethod
    def _renderer() -> structlog.typing.Processor:  # pragma: no cover - always overridden
        """Return the structlog processor that renders the final log line."""
        raise NotImplementedError


class DagsterRichFormatter(_DagsterProcessorFormatter):
    """Rich console formatter for Dagster logging.

    Provides human-readable, colorized console output suitable for development
    and interactive use, with timestamps, logger names, log levels, and stack
    info when available. Usable from a Kedro ``logging.yml`` through the
    ``class`` key.

    Parameters
    ----------
    fmt : str or None, optional
        Accepted for ``logging.config.dictConfig`` compatibility and ignored.
    datefmt : str or None, optional
        Accepted for ``logging.config.dictConfig`` compatibility and ignored.
    style : str, optional
        Accepted for ``logging.config.dictConfig`` compatibility and ignored.

    See Also
    --------
    `kedro_dagster.logging.DagsterJsonFormatter` :
        JSON formatter for log aggregation systems.
    `kedro_dagster.logging.DagsterColoredFormatter` :
        Colored formatter using coloredlogs.
    """

    @staticmethod
    def _renderer() -> structlog.typing.Processor:
        """Render records as human-readable console lines."""
        return structlog.dev.ConsoleRenderer()


class DagsterJsonFormatter(_DagsterProcessorFormatter):
    """JSON formatter for Dagster logging.

    Produces structured JSON output suitable for log aggregation systems,
    monitoring tools, and production environments. Each log entry is a single
    JSON object with consistent field names and ISO timestamps. Usable from a
    Kedro ``logging.yml`` through the ``class`` key.

    Parameters
    ----------
    fmt : str or None, optional
        Accepted for ``logging.config.dictConfig`` compatibility and ignored.
    datefmt : str or None, optional
        Accepted for ``logging.config.dictConfig`` compatibility and ignored.
    style : str, optional
        Accepted for ``logging.config.dictConfig`` compatibility and ignored.

    See Also
    --------
    `kedro_dagster.logging.DagsterRichFormatter` :
        Rich console formatter for development use.
    `kedro_dagster.logging.DagsterColoredFormatter` :
        Colored formatter using coloredlogs.
    """

    @staticmethod
    def _renderer() -> structlog.typing.Processor:
        """Render records as sorted-key JSON objects."""
        return structlog.processors.JSONRenderer(sort_keys=True, ensure_ascii=False)


class DagsterColoredFormatter(coloredlogs.ColoredFormatter):
    """Colored formatter for Dagster logging using coloredlogs.

    Provides colorized console output with blue level names, green timestamps,
    and red error messages. Usable from a Kedro ``logging.yml`` through the
    ``class`` key.

    Parameters
    ----------
    fmt : str or None, optional
        Log record format. Defaults to timestamp, logger name, level and message.
    datefmt : str or None, optional
        Timestamp format. Defaults to ``"%Y-%m-%d %H:%M:%S %z"``.
    style : str, optional
        Format style, as in ``logging.Formatter``.

    See Also
    --------
    `kedro_dagster.logging.DagsterRichFormatter` :
        Rich console formatter for development use.
    `kedro_dagster.logging.DagsterJsonFormatter` :
        JSON formatter for log aggregation systems.
    """

    def __init__(self, fmt: str | None = None, datefmt: str | None = None, style: str = "%") -> None:
        super().__init__(
            fmt=fmt or _COLORED_FORMAT,
            datefmt=datefmt or _COLORED_DATEFMT,
            style=style,
            field_styles={
                "levelname": {"color": "blue"},
                "asctime": {"color": "green"},
            },
            level_styles={
                "debug": {},
                "error": {"color": "red"},
            },
        )


def dagster_rich_formatter() -> structlog.stdlib.ProcessorFormatter:
    """Create a rich console formatter for Dagster logging.

    Returns
    -------
    structlog.stdlib.ProcessorFormatter
        A `DagsterRichFormatter` instance.

    See Also
    --------
    `kedro_dagster.logging.DagsterRichFormatter` :
        The formatter class, to reference from a Kedro ``logging.yml``.
    """
    return DagsterRichFormatter()


def dagster_json_formatter() -> structlog.stdlib.ProcessorFormatter:
    """Create a JSON formatter for Dagster logging.

    Returns
    -------
    structlog.stdlib.ProcessorFormatter
        A `DagsterJsonFormatter` instance.

    See Also
    --------
    `kedro_dagster.logging.DagsterJsonFormatter` :
        The formatter class, to reference from a Kedro ``logging.yml``.
    """
    return DagsterJsonFormatter()


def dagster_colored_formatter() -> coloredlogs.ColoredFormatter:
    """Create a colored formatter for Dagster logging using coloredlogs.

    Returns
    -------
    coloredlogs.ColoredFormatter
        A `DagsterColoredFormatter` instance.

    See Also
    --------
    `kedro_dagster.logging.DagsterColoredFormatter` :
        The formatter class, to reference from a Kedro ``logging.yml``.
    """
    return DagsterColoredFormatter()
