"""Dagster integration utilities: executors, schedules, and loggers.

This module provides small translators/creators that build Dagster artifacts
from the validated Kedro-Dagster configuration: executors, schedules and
loggers.
"""

import importlib
import logging
import sys
from logging import getLogger
from typing import TYPE_CHECKING, Any

import dagster as dg

from kedro_dagster.config import (
    EXECUTOR_MAP,
    ExecutorOptions,
)

if TYPE_CHECKING:
    from kedro_dagster.config import KedroDagsterConfig

LOGGER = getLogger(__name__)


class ExecutorCreator:
    """Create Dagster executor definitions from Kedro-Dagster configuration.

    Parameters
    ----------
    dagster_config : KedroDagsterConfig
        Parsed Kedro-Dagster config containing executor entries.

    See Also
    --------
    `kedro_dagster.dagster.ScheduleCreator` :
        Creates schedule definitions from configuration.
    `kedro_dagster.dagster.LoggerCreator` :
        Creates logger definitions from configuration.

    Notes
    -----
    Executor entries are validated against ``ExecutorOptions``, the union of the
    supported executor option models: ``InProcessExecutorOptions``,
    ``MultiprocessExecutorOptions``, ``DaskExecutorOptions``,
    ``K8sJobExecutorOptions``, ``DockerExecutorOptions``,
    ``CeleryExecutorOptions``, ``CeleryDockerExecutorOptions`` and
    ``CeleryK8sJobExecutorOptions``. The union is a type alias rather than a
    class, so it has no API page of its own; see the individual models above.
    """

    def __init__(self, dagster_config: "KedroDagsterConfig"):
        self._dagster_config = dagster_config
        # Instance-scoped: registrations must not leak between creators.
        self._registered_executors: dict[type[ExecutorOptions], dg.ExecutorDefinition] = {}

    def register_executor(self, executor_option: type[ExecutorOptions], executor: dg.ExecutorDefinition) -> None:
        """Register a mapping between an options model and a Dagster executor factory.

        Registrations take precedence over the executors resolved from
        ``EXECUTOR_MAP`` and are scoped to this creator.

        Parameters
        ----------
        executor_option : type[ExecutorOptions]
            Pydantic model type acting as the key.
        executor : ExecutorDefinition
            Dagster executor factory to use for that key.

        See Also
        --------
        `kedro_dagster.dagster.ExecutorCreator.create_executors` :
            Consumes registered executor mappings.
        """
        self._registered_executors[executor_option] = executor

    def _resolve_executors(
        self,
    ) -> tuple[dict[type[ExecutorOptions], dg.ExecutorDefinition], dict[type, tuple[str, str]]]:
        """Resolve every ``EXECUTOR_MAP`` entry to a Dagster executor factory.

        Returns
        -------
        tuple[dict, dict]
            Resolved factories keyed by option model, and the entries whose
            providing module is not installed, keyed by option model and holding
            ``(yaml_key, module)``.
        """
        resolved: dict[type[ExecutorOptions], dg.ExecutorDefinition] = {}
        unavailable: dict[type, tuple[str, str]] = {}

        for yaml_key, registration in EXECUTOR_MAP.items():
            try:
                module = importlib.import_module(registration.module)
            except ImportError:
                unavailable[registration.options] = (yaml_key, registration.module)
                continue
            resolved[registration.options] = getattr(module, registration.symbol)

        # Explicit registrations win over the built-in registry.
        resolved.update(self._registered_executors)
        return resolved, unavailable

    @staticmethod
    def _unsupported_executor_error(
        name: str,
        options_type: type,
        unavailable: dict[type, tuple[str, str]],
    ) -> str:
        """Build the error for an executor that could not be resolved.

        Distinguishes an uninstalled optional library from an unknown executor
        type, so the two failures do not read alike.

        Parameters
        ----------
        name : str
            Name of the offending executor entry.
        options_type : type
            Option model type that failed to resolve.
        unavailable : dict
            Entries whose providing module is not installed.

        Returns
        -------
        str
            Message naming either the package to install or the valid YAML keys.
        """
        if options_type in unavailable:
            yaml_key, module = unavailable[options_type]
            package = module.replace("_", "-")
            return (
                f"Executor '{name}' uses '{yaml_key}', which is provided by the '{module}' module. "
                f"That module is not installed -- install it with `pip install {package}`."
            )

        valid_keys = ", ".join(sorted(EXECUTOR_MAP))
        return (
            f"Executor '{name}' has unsupported type '{options_type.__name__}'. Valid executor types are: {valid_keys}."
        )

    def create_executors(self) -> dict[str, dg.ExecutorDefinition]:
        """Instantiate executor definitions declared in the configuration.

        Returns
        -------
        dict[str, ExecutorDefinition]
            Mapping of executor name to configured executor.

        See Also
        --------
        `kedro_dagster.dagster.ExecutorCreator.register_executor` :
            Registers new executor types before creation.
        """
        LOGGER.info("Creating Dagster executors...")
        resolved_executors, unavailable_executors = self._resolve_executors()

        named_executors = {}

        # First, create executors from the global executors configuration
        if self._dagster_config.executors is not None:
            for executor_name, executor_config in self._dagster_config.executors.items():
                LOGGER.debug(f"Creating executor '{executor_name}'...")
                # Make use of the executor map to create the executor
                executor = resolved_executors.get(type(executor_config), None)
                if executor is None:
                    msg = self._unsupported_executor_error(executor_name, type(executor_config), unavailable_executors)
                    LOGGER.error(msg)
                    raise ValueError(msg)
                executor = executor.configured(executor_config.model_dump())
                named_executors[executor_name] = executor

        # Next, iterate over jobs to handle inline executor configurations
        if self._dagster_config.jobs is not None:
            available_executor_names = set(named_executors.keys())

            for job_name, job_config in self._dagster_config.jobs.items():
                if job_config.executor is not None:
                    LOGGER.debug(f"Processing executor configuration for job '{job_name}'...")
                    if isinstance(job_config.executor, str):
                        # String reference - validate it exists in available executors
                        if job_config.executor not in available_executor_names:
                            msg = (
                                f"Executor named '{job_config.executor}' for job '{job_name}' not found in available executors. "
                                f"Available executors: {sorted(available_executor_names)}"
                            )
                            LOGGER.error(msg)
                            raise ValueError(msg)
                    else:
                        # Inline executor configuration - create executor definition
                        executor = resolved_executors.get(type(job_config.executor), None)
                        if executor is None:
                            msg = self._unsupported_executor_error(
                                f"<inline executor for job '{job_name}'>",
                                type(job_config.executor),
                                unavailable_executors,
                            )
                            LOGGER.error(msg)
                            raise ValueError(msg)

                        # Create the executor with job-specific naming
                        executor_name = f"{job_name}__executor"
                        executor_def = executor.configured(job_config.executor.model_dump())
                        named_executors[executor_name] = executor_def

        LOGGER.debug(f"Created {len(named_executors)} executor(s)")
        return named_executors


class ScheduleCreator:
    """Create Dagster schedule definitions from Kedro configuration.

    Parameters
    ----------
    dagster_config : KedroDagsterConfig
        Parsed Kedro-Dagster config containing schedule entries.
    named_jobs : dict[str, JobDefinition]
        Mapping of job names to Dagster job definitions.

    See Also
    --------
    `kedro_dagster.dagster.ExecutorCreator` :
        Creates executor definitions from configuration.
    `kedro_dagster.dagster.LoggerCreator` :
        Creates logger definitions from configuration.
    `kedro_dagster.config.automation.ScheduleOptions` :
        Schedule option model.
    """

    def __init__(self, dagster_config: "KedroDagsterConfig", named_jobs: dict[str, dg.JobDefinition]):
        self._dagster_config = dagster_config
        self._named_jobs = named_jobs

    def create_schedules(self) -> dict[str, dg.ScheduleDefinition]:
        """Create schedule definitions from the configuration.

        Returns
        -------
        dict[str, ScheduleDefinition]
            Dict of schedule definitions keyed by job name.

        See Also
        --------
        `kedro_dagster.config.automation.ScheduleOptions` :
            Schedule option model used as input.
        """
        LOGGER.info("Creating Dagster schedules...")
        named_schedule_config = {}
        if self._dagster_config.schedules is not None:
            for schedule_name, schedule_config in self._dagster_config.schedules.items():
                LOGGER.debug(f"Registering schedule '{schedule_name}'...")
                named_schedule_config[schedule_name] = schedule_config.model_dump()

        available_schedule_names = set(named_schedule_config.keys())

        named_schedules = {}
        if self._dagster_config.jobs is not None:
            for job_name, job_config in self._dagster_config.jobs.items():
                if job_config.schedule is not None:
                    LOGGER.debug(f"Creating schedule for job '{job_name}'...")
                    if isinstance(job_config.schedule, str):
                        schedule_name = job_config.schedule
                        if schedule_name in named_schedule_config:
                            schedule = dg.ScheduleDefinition(
                                name=f"{job_name}_{schedule_name}_schedule",
                                job=self._named_jobs[job_name],
                                **named_schedule_config[schedule_name],
                            )
                        else:
                            msg = (
                                f"Schedule named '{schedule_name}' for job '{job_name}' not found. "
                                f"Available schedules: {sorted(available_schedule_names)}"
                            )
                            LOGGER.error(msg)
                            raise ValueError(msg)
                    else:
                        # If schedule_config is not a string, create schedule definition using inline config
                        schedule = dg.ScheduleDefinition(
                            name=f"{job_name}__schedule",
                            job=self._named_jobs[job_name],
                            **job_config.schedule.model_dump(),
                        )

                    named_schedules[job_name] = schedule

        LOGGER.debug(f"Created {len(named_schedules)} schedule(s)")
        return named_schedules


class LoggerCreator:
    """Create Dagster logger definitions from Kedro-Dagster configuration.

    Parameters
    ----------
    dagster_config : KedroDagsterConfig
        Parsed Kedro-Dagster config containing logger entries.

    See Also
    --------
    `kedro_dagster.dagster.ExecutorCreator` :
        Creates executor definitions from configuration.
    `kedro_dagster.dagster.ScheduleCreator` :
        Creates schedule definitions from configuration.
    `kedro_dagster.config.logging.LoggerOptions` :
        Logger option model.
    """

    def __init__(self, dagster_config: "KedroDagsterConfig"):
        self._dagster_config = dagster_config

    def _get_logger_definition(self, logger_name: str) -> dg.LoggerDefinition:
        """Create a Dagster logger definition from the configuration.

        Parameters
        ----------
        logger_name : str
            Name of the logger.

        Returns
        -------
        LoggerDefinition
            Dagster logger definition.

        See Also
        --------
        `kedro_dagster.dagster.LoggerCreator.create_loggers` :
            Entry point that calls this method for each configured logger.
        """

        def _resolve_reference(ref: Any) -> Any:
            """Resolve a string with "module.ClassName", "module:function_name", or "ext://module.attr"."""
            if isinstance(ref, str):
                # Handle ext:// protocol used in logging configurations
                if ref.startswith("ext://"):
                    ref = ref[6:]  # Remove "ext://" prefix

                module_path, _, attr = ref.rpartition(".")
                if module_path:
                    module = importlib.import_module(module_path)
                    return getattr(module, attr)

            raise TypeError(f"Unable to resolve reference {ref!r}")

        def dagster_logger(context: dg.InitLoggerContext) -> logging.Logger:
            """Build a stdlib logger from the Dagster logger config."""
            # Use the provided config directly instead of dynamic schema
            config_data = dict(context.logger_config)
            level = config_data.get("log_level", "INFO").upper()

            klass = logging.getLoggerClass()
            logger_ = klass(logger_name, level=level)

            # Optionally clear existing handlers to prevent duplicates
            for h in list(logger_.handlers):
                logger_.removeHandler(h)

            # Build formatter registry
            default_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            formatter_registry: dict[str, logging.Formatter] = {}
            if config_data.get("formatters"):
                for fname, fcfg in config_data["formatters"].items():
                    if "()" in fcfg:
                        # Callable given to create formatter
                        formatter_callable = _resolve_reference(fcfg["()"])
                        # remove the special key for constructor params
                        init_kwargs = {k: v for k, v in fcfg.items() if k != "()"}
                        fmt_inst = formatter_callable(**init_kwargs)
                    elif "class" in fcfg:
                        # Assume class path given in "class" key
                        cls_path = fcfg.get("class")
                        formatter_cls = _resolve_reference(cls_path)
                        init_kwargs = {k: v for k, v in fcfg.items() if k != "class"}
                        fmt_inst = formatter_cls(**init_kwargs)
                    else:
                        # Use standard logging.Formatter
                        fmt_str = fcfg.get("format", None)
                        datefmt = fcfg.get("datefmt", None)
                        style = fcfg.get("style", "%")
                        fmt_inst = logging.Formatter(fmt_str, datefmt=datefmt, style=style)
                    formatter_registry[fname] = fmt_inst

            # Build filter registry
            filter_registry: dict[str, logging.Filter] = {}
            if config_data.get("filters"):
                for fname, fcfg in config_data["filters"].items():
                    if "()" in fcfg:
                        filter_callable = _resolve_reference(fcfg["()"])
                        init_kwargs = {k: v for (k, v) in fcfg.items() if k != "()"}
                        filter_inst = filter_callable(**init_kwargs)
                    else:
                        # assume class path in "class" key
                        cls_path = fcfg.get("class")
                        filter_cls = _resolve_reference(cls_path)
                        init_kwargs = {k: v for (k, v) in fcfg.items() if k != "class"}
                        filter_inst = filter_cls(**init_kwargs)
                    filter_registry[fname] = filter_inst

            # Build handlers
            if config_data.get("handlers"):
                for hcfg in config_data["handlers"]:
                    fmt_ref = hcfg.get("formatter", None)
                    filter_refs = hcfg.get("filters", [])
                    h_level = hcfg.get("level", level).upper()
                    # Resolve handler class
                    if "()" in hcfg:
                        handler_callable = _resolve_reference(hcfg["()"])
                        init_kwargs = {k: v for (k, v) in hcfg.items() if k != "()"}
                        # Resolve stream references like "ext://sys.stdout"
                        if "stream" in init_kwargs and isinstance(init_kwargs["stream"], str):
                            init_kwargs["stream"] = _resolve_reference(init_kwargs["stream"])
                        handler_inst = handler_callable(**init_kwargs)
                    else:
                        cls_path = hcfg.get("class", "logging.StreamHandler")
                        handler_cls = _resolve_reference(cls_path)
                        init_kwargs = {
                            k: v for (k, v) in hcfg.items() if k not in ("class", "level", "formatter", "filters")
                        }
                        # Resolve stream references like "ext://sys.stdout"
                        if "stream" in init_kwargs and isinstance(init_kwargs["stream"], str):
                            init_kwargs["stream"] = _resolve_reference(init_kwargs["stream"])
                        handler_inst = handler_cls(**init_kwargs)

                    # Set handler level
                    handler_inst.setLevel(h_level)

                    # Attach formatter
                    if fmt_ref is not None and formatter_registry.get(fmt_ref):
                        handler_inst.setFormatter(formatter_registry[fmt_ref])
                    elif fmt_ref is None:
                        # No formatter specified for this handler, attach default
                        handler_inst.setFormatter(default_formatter)

                    # Attach filters
                    for fref in filter_refs:
                        if fref in filter_registry:
                            handler_inst.addFilter(filter_registry[fref])

                    logger_.addHandler(handler_inst)
            else:
                # No handlers specified, default to StreamHandler
                sh = logging.StreamHandler(stream=sys.stdout)
                sh.setLevel(level)
                sh.setFormatter(default_formatter)
                logger_.addHandler(sh)

            return logger_

        config_schema = {
            "log_level": dg.Field(str, default_value="INFO"),
            "handlers": dg.Field(list, is_required=False),
            "formatters": dg.Field(dict, is_required=False),
            "filters": dg.Field(dict, is_required=False),
        }

        return dg.LoggerDefinition(
            dagster_logger,
            description=f"Logger definition `{logger_name}`.",
            config_schema=config_schema,
        )

    def create_loggers(self) -> dict[str, dg.LoggerDefinition]:
        """Create logger definitions from the configuration.

        Returns
        -------
        dict[str, LoggerDefinition]
            Mapping of fully-qualified logger name to definition.

        See Also
        --------
        `kedro_dagster.config.logging.LoggerOptions` :
            Logger option model used as input.

        Notes
        -----
        Each individual logger definition is created by the private
        ``_get_logger_definition`` method.
        """
        LOGGER.info("Creating Dagster loggers...")
        named_loggers = {}
        if self._dagster_config.loggers:
            for logger_name in self._dagster_config.loggers:
                LOGGER.debug(f"Creating logger '{logger_name}'...")
                logger = self._get_logger_definition(logger_name)
                named_loggers[logger_name] = logger

        # Iterate over jobs to handle job-specific logger configurations
        if hasattr(self._dagster_config, "jobs") and self._dagster_config.jobs:
            available_logger_names = list(named_loggers.keys())
            for job_name, job_config in self._dagster_config.jobs.items():
                if hasattr(job_config, "loggers") and job_config.loggers:
                    LOGGER.debug(f"Processing {len(job_config.loggers)} loggers for job '{job_name}'...")
                    for idx, logger_config in enumerate(job_config.loggers):
                        if isinstance(logger_config, str):
                            # If logger_config is a string, check it exists in available_logger_names
                            if logger_config not in available_logger_names:
                                raise ValueError(
                                    f"Logger '{logger_config}' referenced in job '{job_name}' "
                                    f"not found in available loggers: {available_logger_names}"
                                )
                        else:
                            # If logger_config is not a string, create logger definition named after the job
                            job_logger_name = f"{job_name}__logger_{idx}"
                            logger = self._get_logger_definition(job_logger_name)
                            named_loggers[job_logger_name] = logger

        LOGGER.debug(f"Created {len(named_loggers)} logger(s)")
        return named_loggers
