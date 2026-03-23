"""Configuration definitions for Kedro-Dagster jobs.

These pydantic models describe the shape of the ``dagster.yml`` entries used to
translate Kedro pipelines into Dagster jobs, including pipeline filtering and
executor/schedule selection."""

from pydantic import BaseModel

from kedro_dagster.utils import KEDRO_VERSION, PYDANTIC_VERSION, create_pydantic_config

from .automation import ScheduleOptions
from .execution import ExecutorOptions
from .logging import LoggerOptions


class PipelineOptions(BaseModel):
    """Options for filtering and configuring Kedro pipelines within a Dagster job.

    Attributes
    ----------
    pipeline_name : str
        Name of the Kedro pipeline to run. Defaults to ``__default__``.
    from_nodes : list[str] or None
        List of node names to start execution from.
    to_nodes : list[str] or None
        List of node names to end execution at.
    node_names : list[str] or None
        List of specific node names to include in the pipeline.
    from_inputs : list[str] or None
        List of dataset names to use as entry points.
    to_outputs : list[str] or None
        List of dataset names to use as exit points.
    node_namespaces : list[str] or None
        Namespace(s) to filter nodes by (Kedro >= 1.0). For older Kedro
        versions, the field is ``node_namespace`` (singular string).
    tags : list[str] or None
        List of tags to filter nodes by.

    Examples
    --------
    ```yaml
    jobs:
      sales_etl:
        pipeline:
          pipeline_name: etl
          node_namespaces: ["sales", "shared"]
          tags: ["daily", "priority"]
          from_nodes: ["extract_raw_sales"]
          to_nodes: ["publish_clean_sales"]
          from_inputs: ["raw_sales"]
          to_outputs: ["clean_sales"]
    ```

    See Also
    --------
    `kedro_dagster.config.job.JobOptions` :
        Wraps this model alongside executor and schedule settings.
    `kedro_dagster.utils.get_filter_params_dict` :
        Extracts filter parameters from this configuration.
    """

    pipeline_name: str = "__default__"
    from_nodes: list[str] | None = None
    to_nodes: list[str] | None = None
    node_names: list[str] | None = None
    from_inputs: list[str] | None = None
    to_outputs: list[str] | None = None
    # Kedro 1.x renamed the namespace filter kwarg to `node_namespaces` (plural).
    # Expose the appropriate field name based on the installed Kedro version while
    # keeping the rest of the configuration stable.
    if KEDRO_VERSION[0] >= 1:
        node_namespaces: list[str] | None = None
    else:  # pragma: no cover
        node_namespace: str | None = None
    tags: list[str] | None = None

    # Version-aware Pydantic configuration
    if PYDANTIC_VERSION[0] >= 2:  # noqa: PLR2004
        model_config = create_pydantic_config(extra="forbid")
    else:  # pragma: no cover
        Config = create_pydantic_config(extra="forbid")


class JobOptions(BaseModel):
    """Configuration options for a Dagster job.

    Attributes
    ----------
    pipeline : PipelineOptions
        Pipeline options specifying which pipeline and nodes to run.
    executor : ExecutorOptions or str or None
        Executor options instance or string key referencing an executor.
    schedule : ScheduleOptions or str or None
        Schedule options instance or string key referencing a schedule.
    loggers : list[LoggerOptions or str] or None
        List of logger configurations (inline ``LoggerOptions``) or
        logger names (strings) to attach to the job.

    Examples
    --------
    ```yaml
    jobs:
      my_data_processing:
        pipeline:
          pipeline_name: data_processing
          node_namespaces: [price_predictor]
          tags: [test1]
        executor: multiprocessing
        schedule: daily_schedule
        loggers: [console, file_logger]
    ```

    See Also
    --------
    `kedro_dagster.config.job.PipelineOptions` :
        Pipeline filtering options within this job.
    `kedro_dagster.config.automation.ScheduleOptions` :
        Schedule options referenced by this job.
    `kedro_dagster.config.logging.LoggerOptions` :
        Logger options referenced by this job.
    `kedro_dagster.config.kedro_dagster.KedroDagsterConfig` :
        Top-level config that holds a dict of these job options.
    """

    pipeline: PipelineOptions
    executor: ExecutorOptions | str | None = None
    schedule: ScheduleOptions | str | None = None
    loggers: list[LoggerOptions | str] | None = None

    # Version-aware Pydantic configuration
    if PYDANTIC_VERSION[0] >= 2:  # noqa: PLR2004
        model_config = create_pydantic_config(extra="forbid")
    else:  # pragma: no cover
        Config = create_pydantic_config(extra="forbid")
