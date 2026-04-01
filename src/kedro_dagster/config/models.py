"""Pydantic configuration models for the Kedro-Dagster plugin.

This module consolidates all configuration models used by the Kedro-Dagster
plugin into a single file. Models are ordered bottom-up by dependency.
"""

from logging import getLogger
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from kedro.framework.context import KedroContext

LOGGER = getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging models
# ---------------------------------------------------------------------------

# Valid Python logging levels (normalized to uppercase)
LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]


class LoggerOptions(BaseModel):
    """Options for defining Dagster loggers.

    Parameters
    ----------
    log_level : LogLevel
        Logging level (CRITICAL/ERROR/WARNING/INFO/DEBUG/NOTSET).
    handlers : list[dict[str, Any]]
        List of handler config dicts.
    formatters : dict[str, dict[str, Any]]
        Formatter configs, name to config.
    filters : dict[str, dict[str, Any]]
        Filter configs, name to config.

    See Also
    --------
    `kedro_dagster.dagster.LoggerCreator` :
        Creates Dagster logger definitions from these options.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    log_level: LogLevel = Field(
        default="INFO",
        description="Python logging level (case-insensitive)",
    )
    handlers: list[dict[str, Any]] = Field(
        default=[],
        description="List of handler configurations",
    )
    formatters: dict[str, dict[str, Any]] = Field(
        default={},
        description="Formatter configurations mapped by name",
    )
    filters: dict[str, dict[str, Any]] = Field(
        default={},
        description="Filter configurations mapped by name",
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Normalize log level to uppercase for case-insensitive matching.

        Parameters
        ----------
        v : str
            Log level string to normalize.

        Returns
        -------
        str
            Normalized log level in uppercase.

        Raises
        ------
        ValueError
            If log level is not a valid string.
        """
        if not isinstance(v, str):
            raise ValueError("Log level must be a string")

        normalized = v.upper().strip()

        # Check if the normalized level is valid
        valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if normalized not in valid_levels:
            raise ValueError(
                f"Invalid log level '{v}'. Must be one of: {', '.join(sorted(valid_levels))} (case-insensitive)"
            )

        return normalized

    @field_validator("handlers")
    @classmethod
    def validate_handlers(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate handler configurations.

        Parameters
        ----------
        v : list[dict[str, Any]]
            Handler configurations to validate.

        Returns
        -------
        list[dict[str, Any]]
            Validated handler configurations.

        Raises
        ------
        ValueError
            If handler configuration is invalid.
        """
        for i, handler in enumerate(v):
            if "class" not in handler:
                raise ValueError(f"Handler at index {i} must specify a 'class' field")

            if not isinstance(handler["class"], str):
                raise ValueError(f"Handler class at index {i} must be a string")

        return v

    @field_validator("formatters")
    @classmethod
    def validate_formatters(cls, v: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Validate formatter configurations.

        Parameters
        ----------
        v : dict[str, dict[str, Any]]
            Formatter configurations to validate.

        Returns
        -------
        dict[str, dict[str, Any]]
            Validated formatter configurations.

        Raises
        ------
        ValueError
            If formatter configuration is invalid.
        """
        for name, formatter in v.items():
            # Require either 'format' for standard formatter or '()' for custom class
            has_format = "format" in formatter
            has_callable = "()" in formatter

            if not (has_format or has_callable):
                raise ValueError(f"Formatter '{name}' must specify either 'format' field or '()' for custom class")

            # Type validation for keys when present
            if has_format and not isinstance(formatter["format"], str):
                raise ValueError(f"Formatter '{name}' 'format' must be a string")

            if has_callable and not isinstance(formatter["()"], str):
                raise ValueError(f"Formatter '{name}' '()' must be a string import path")

        return v

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Validate filter configurations.

        Parameters
        ----------
        v : dict[str, dict[str, Any]]
            Filter configurations to validate.

        Returns
        -------
        dict[str, dict[str, Any]]
            Validated filter configurations.

        Raises
        ------
        ValueError
            If filter configuration is invalid.
        """
        for name, filter_config in v.items():
            # Require either custom callable/class path via '()' or a class path via 'class'
            has_callable = "()" in filter_config
            has_class = "class" in filter_config

            if not (has_callable or has_class):
                raise ValueError(
                    f"Filter '{name}' must specify either '()' for custom callable/class or 'class' for import path"
                )

            # Basic type checks for keys when present
            if has_callable and not isinstance(filter_config["()"], str):
                raise ValueError(f"Filter '{name}' '()' must be a string import path")

            if has_class and not isinstance(filter_config["class"], str):
                raise ValueError(f"Filter '{name}' class must be a string")

        return v

    @model_validator(mode="after")
    def validate_references(self) -> "LoggerOptions":
        """Validate that handler/formatter/filter references are consistent.

        Returns
        -------
        LoggerOptions
            Self after validation.

        Raises
        ------
        ValueError
            If there are inconsistent references.
        """
        # Collect available formatter and filter names
        available_formatters = set(self.formatters.keys()) if self.formatters else set()
        available_filters = set(self.filters.keys()) if self.filters else set()

        # Check handlers reference valid formatters/filters
        if self.handlers:
            for i, handler in enumerate(self.handlers):
                # Check formatter reference
                if "formatter" in handler:
                    formatter_name = handler["formatter"]
                    if formatter_name not in available_formatters:
                        raise ValueError(
                            f"Handler at index {i} references unknown formatter '{formatter_name}'. "
                            f"Available formatters: {sorted(available_formatters)}"
                        )

                # Check filter references
                if "filters" in handler:
                    handler_filters = handler["filters"]
                    if isinstance(handler_filters, list):
                        for filter_name in handler_filters:
                            if filter_name not in available_filters:
                                raise ValueError(
                                    f"Handler at index {i} references unknown filter '{filter_name}'. "
                                    f"Available filters: {sorted(available_filters)}"
                                )

        return self


# ---------------------------------------------------------------------------
# Executor models
# ---------------------------------------------------------------------------


class InProcessExecutorOptions(BaseModel):
    """Options for the in-process executor.

    Parameters
    ----------
    retries : RetriesEnableOptions or RetriesDisableOptions
        Retry configuration for the executor.

    Examples
    --------
    ```yaml
    executors:
        local_inproc:
            in_process: {}
    jobs:
        my_job:
            pipeline:
                pipeline_name: my_pipeline
            executor: local_inproc
    ```

    See Also
    --------
    `kedro_dagster.config.models.MultiprocessExecutorOptions` :
        Extends this class with concurrency settings.
    `kedro_dagster.dagster.ExecutorCreator` :
        Builds Dagster executor definitions from these options.
    """

    class RetriesEnableOptions(BaseModel):
        """Enable retries for the executor."""

        enabled: dict = {}  # type: ignore[type-arg]

    class RetriesDisableOptions(BaseModel):
        """Disable retries for the executor."""

        disabled: dict = {}  # type: ignore[type-arg]

    retries: RetriesEnableOptions | RetriesDisableOptions = Field(
        default=RetriesEnableOptions(),
        description="Whether retries are enabled or not.",
    )


class MultiprocessExecutorOptions(InProcessExecutorOptions):
    """Options for the multiprocess executor.

    Parameters
    ----------
    retries : RetriesEnableOptions or RetriesDisableOptions
        Retry configuration for the executor.
    max_concurrent : int
        Maximum number of concurrent processes.

    Examples
    --------
    ```yaml
    executors:
        local_multi:
            multiprocess:
                max_concurrent: 4
    jobs:
        heavy_job:
            pipeline:
                pipeline_name: heavy_pipeline
            executor: local_multi
    ```

    See Also
    --------
    `kedro_dagster.config.models.InProcessExecutorOptions` :
        Base class providing retry configuration.
    `kedro_dagster.dagster.ExecutorCreator` :
        Builds Dagster executor definitions from these options.
    """

    max_concurrent: int = Field(
        default=1,
        description=(
            "The number of processes that may run concurrently. "
            "By default, this is set to be the return value of `multiprocessing.cpu_count()`."
        ),
    )


class DaskClusterConfig(BaseModel):
    """Configuration for the Dask cluster.

    Parameters
    ----------
    existing : dict[str, str] or None
        Connect to an existing scheduler.
    local : dict[str, Any] or None
        Local cluster configuration.
    yarn : dict[str, Any] or None
        YARN cluster configuration.
    ssh : dict[str, Any] or None
        SSH cluster configuration.
    pbs : dict[str, Any] or None
        PBS cluster configuration.
    moab : dict[str, Any] or None
        Moab cluster configuration.
    sge : dict[str, Any] or None
        SGE cluster configuration.
    lsf : dict[str, Any] or None
        LSF cluster configuration.
    slurm : dict[str, Any] or None
        SLURM cluster configuration.
    oar : dict[str, Any] or None
        OAR cluster configuration.
    kube : dict[str, Any] or None
        Kubernetes cluster configuration.

    See Also
    --------
    `kedro_dagster.config.models.DaskExecutorOptions` :
        Uses this as its cluster configuration.
    """

    existing: dict[str, str] | None = Field(default=None, description="Connect to an existing scheduler.")
    local: dict[str, Any] | None = Field(default=None, description="Local cluster configuration.")
    yarn: dict[str, Any] | None = Field(default=None, description="YARN cluster configuration.")
    ssh: dict[str, Any] | None = Field(default=None, description="SSH cluster configuration.")
    pbs: dict[str, Any] | None = Field(default=None, description="PBS cluster configuration.")
    moab: dict[str, Any] | None = Field(default=None, description="Moab cluster configuration.")
    sge: dict[str, Any] | None = Field(default=None, description="SGE cluster configuration.")
    lsf: dict[str, Any] | None = Field(default=None, description="LSF cluster configuration.")
    slurm: dict[str, Any] | None = Field(default=None, description="SLURM cluster configuration.")
    oar: dict[str, Any] | None = Field(default=None, description="OAR cluster configuration.")
    kube: dict[str, Any] | None = Field(default=None, description="Kubernetes cluster configuration.")


class DaskExecutorOptions(BaseModel):
    """Options for the Dask executor.

    Parameters
    ----------
    cluster : DaskClusterConfig
        Configuration for the Dask cluster.

    Examples
    --------
    ```yaml
    executors:
        dask_cluster:
            dask_executor:
                cluster:
                    local:
                        n_workers: 4
                        threads_per_worker: 2
    jobs:
        dask_job:
            pipeline:
                pipeline_name: dask_enabled_pipeline
            executor: dask_cluster
    ```

    See Also
    --------
    `kedro_dagster.config.models.DaskClusterConfig` :
        Cluster configuration consumed by this executor.
    `kedro_dagster.dagster.ExecutorCreator` :
        Builds Dagster executor definitions from these options.
    """

    cluster: DaskClusterConfig = Field(default=DaskClusterConfig(), description="Configuration for the Dask cluster.")


class DockerExecutorOptions(MultiprocessExecutorOptions):
    """Options for the Docker-based executor.

    Parameters
    ----------
    retries : RetriesEnableOptions or RetriesDisableOptions
        Retry configuration for the executor.
    max_concurrent : int or None
        Maximum number of concurrent processes.
    image : str or None
        Docker image to use.
    network : str or None
        Name of the network to connect the container at creation time.
    registry : dict[str, str] or None
        Information for using a non local/public docker registry.
    env_vars : list[str]
        Environment variables for the container.
    container_kwargs : dict[str, Any] or None
        Key-value pairs for ``containers.create``.
    networks : list[str]
        Names of the networks to connect the container at creation time.

    Examples
    --------
    ```yaml
    executors:
        docker_exec:
            docker_executor:
                image: "myrepo/app:latest"
                max_concurrent: 3
                env_vars: ["ENV=prod", "LOG_LEVEL=INFO"]
    jobs:
        docker_job:
            pipeline:
                pipeline_name: batch_pipeline
            executor: docker_exec
    ```

    See Also
    --------
    `kedro_dagster.config.models.MultiprocessExecutorOptions` :
        Base class providing concurrency and retry settings.
    `kedro_dagster.dagster.ExecutorCreator` :
        Builds Dagster executor definitions from these options.
    """

    image: str | None = Field(
        default=None, description="The docker image to be used if the repository does not specify one."
    )
    network: str | None = Field(
        default=None, description="Name of the network to which to connect the launched container at creation time."
    )
    registry: dict[str, str] | None = Field(
        default=None, description="Information for using a non local/public docker registry."
    )
    env_vars: list[str] = Field(
        default=[],
        description=(
            "The list of environment variables names to include in the docker container. "
            "Each can be of the form KEY=VALUE or just KEY (in which case the value will be pulled "
            "from the local environment)."
        ),
    )
    container_kwargs: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Key-value pairs that can be passed into containers.create. See "
            "https://docker-py.readthedocs.io/en/stable/containers.html for the full list "
            "of available options."
        ),
    )
    networks: list[str] = Field(
        default=[], description="Names of the networks to which to connect the launched container at creation time."
    )


class CeleryExecutorOptions(BaseModel):
    """Options for the Celery-based executor.

    Parameters
    ----------
    broker : str or None
        Celery broker URL.
    backend : str or None
        Celery backend URL.
    include : list[str]
        List of modules every worker should import.
    config_source : dict[str, Any] or None
        Additional settings for the Celery app.
    retries : int or None
        Number of retries for the Celery tasks.

    Examples
    --------
    ```yaml
    executors:
        celery_exec:
            celery_executor:
                broker: "pyamqp://guest@localhost//"
                backend: "rpc://"
                include: ["my_project.workers"]
                retries: 2
    jobs:
        async_job:
            pipeline:
                pipeline_name: async_pipeline
            executor: celery_exec
    ```

    See Also
    --------
    `kedro_dagster.config.models.CeleryDockerExecutorOptions` :
        Combines Celery with Docker container settings.
    `kedro_dagster.config.models.CeleryK8sJobExecutorOptions` :
        Combines Celery with Kubernetes job settings.
    `kedro_dagster.dagster.ExecutorCreator` :
        Builds Dagster executor definitions from these options.
    """

    broker: str | None = Field(
        default=None,
        description=(
            "The URL of the Celery broker. Default: "
            "'pyamqp://guest@{os.getenv('DAGSTER_CELERY_BROKER_HOST',"
            "'localhost')}//'."
        ),
    )
    backend: str | None = Field(
        default="rpc://",
        description="The URL of the Celery results backend. Default: 'rpc://'.",
    )
    include: list[str] = Field(default=[], description="List of modules every worker should import.")
    config_source: dict[str, Any] | None = Field(default=None, description="Additional settings for the Celery app.")
    retries: int | None = Field(default=None, description="Number of retries for the Celery tasks.")


class CeleryDockerExecutorOptions(CeleryExecutorOptions, DockerExecutorOptions):
    """Options for the Celery-based executor which launches tasks as Docker containers.

    Uses fields from both ``CeleryExecutorOptions`` and ``DockerExecutorOptions``
    to configure Celery workers running in Docker.

    Examples
    --------
    ```yaml
    executors:
        celery_docker_exec:
            celery_docker_executor:
                image: "myrepo/celery-worker:latest"
                broker: "redis://redis:6379/0"
                backend: "rpc://"
                include: ["my_project.workers"]
                env_vars: ["WORKER_POOL=default"]
    jobs:
        celery_docker_job:
            pipeline:
                pipeline_name: async_docker_pipeline
            executor: celery_docker_exec
    ```

    See Also
    --------
    `kedro_dagster.config.models.CeleryExecutorOptions` :
        Provides Celery broker and backend configuration.
    `kedro_dagster.config.models.DockerExecutorOptions` :
        Provides Docker container configuration.
    `kedro_dagster.dagster.ExecutorCreator` :
        Builds Dagster executor definitions from these options.
    """

    pass


class K8sJobConfig(BaseModel):
    """Configuration for Kubernetes jobs.

    Parameters
    ----------
    container_config : dict[str, Any]
        Configuration for the Kubernetes container.
    pod_spec_config : dict[str, Any]
        Configuration for the Pod specification.
    pod_template_spec_metadata : dict[str, Any]
        Metadata for the Pod template specification.
    job_spec_config : dict[str, Any]
        Configuration for the Job specification.
    job_metadata : dict[str, Any]
        Metadata for the Job.

    Examples
    --------
    ```yaml
    executors:
        k8s_exec:
            k8s_job_executor:
                step_k8s_config:
                    container_config:
                        image: "python:3.11-slim"
                        env:
                            - name: "KEDRO_ENV"
                              value: "prod"
                    pod_spec_config:
                        nodeSelector:
                            nodepool: cpu
                    pod_template_spec_metadata:
                        labels:
                            app: dagster-step
                    job_spec_config:
                        backoffLimit: 3
                    job_metadata:
                        labels:
                            team: platform
                per_step_k8s_config:
                    op_name_overridden:
                        container_config:
                            resources:
                                limits:
                                    cpu: "2"
                                    memory: "2Gi"
    ```

    See Also
    --------
    `kedro_dagster.config.models.K8sJobExecutorOptions` :
        Uses this as its step and per-step configuration.
    """

    container_config: dict[str, Any] = Field(default={}, description="Configuration for the Kubernetes container.")
    pod_spec_config: dict[str, Any] = Field(
        default={}, description="Configuration for the Kubernetes Pod specification."
    )
    pod_template_spec_metadata: dict[str, Any] = Field(
        default={}, description="Metadata for the Kubernetes Pod template specification."
    )
    job_spec_config: dict[str, Any] = Field(
        default={}, description="Configuration for the Kubernetes Job specification."
    )
    job_metadata: dict[str, Any] = Field(default={}, description="Metadata for the Kubernetes Job.")


class K8sJobExecutorOptions(MultiprocessExecutorOptions):
    """Options for the Kubernetes-based executor.

    Parameters
    ----------
    retries : RetriesEnableOptions or RetriesDisableOptions
        Retry configuration for the executor.
    max_concurrent : int or None
        Maximum number of concurrent processes.
    job_namespace : str
        Kubernetes namespace for jobs.
    load_incluster_config : bool
        Whether the executor is running within a k8s cluster.
    kubeconfig_file : str or None
        Path to a kubeconfig file to use.
    step_k8s_config : K8sJobConfig
        Raw Kubernetes configuration for each step.
    per_step_k8s_config : dict[str, K8sJobConfig]
        Per op k8s configuration overrides.
    image_pull_policy : str or None
        Image pull policy for Pods.
    image_pull_secrets : list[dict[str, str]] or None
        Credentials for pulling images.
    service_account_name : str or None
        Kubernetes service account name.
    env_config_maps : list[str] or None
        ``ConfigMapEnvSource`` names for environment variables.
    env_secrets : list[str] or None
        Secret names for environment variables.
    env_vars : list[str] or None
        Environment variables for the job.
    volume_mounts : list[dict[str, str]]
        Volume mounts for the container.
    volumes : list[dict[str, str]]
        Volumes for the Pod.
    labels : dict[str, str]
        Labels for created pods.
    resources : dict[str, dict[str, str]] or None
        Compute resource requirements.
    scheduler_name : str or None
        Custom Kubernetes scheduler for Pods.
    security_context : dict[str, str]
        Security settings for the container.

    Examples
    --------
    ```yaml
    executors:
        k8s_exec:
            k8s_job_executor:
                job_namespace: "dagster"
                max_concurrent: 2
                image_pull_policy: IfNotPresent
                resources:
                    limits:
                        cpu: "1"
                        memory: "1Gi"
                    requests:
                        cpu: "500m"
                        memory: "512Mi"
                labels:
                    team: platform
    jobs:
        k8s_job:
            pipeline:
                pipeline_name: k8s_pipeline
            executor: k8s_exec
    ```

    See Also
    --------
    `kedro_dagster.config.models.K8sJobConfig` :
        Kubernetes job configuration consumed by this executor.
    `kedro_dagster.config.models.CeleryK8sJobExecutorOptions` :
        Combines Celery with Kubernetes job settings.
    `kedro_dagster.dagster.ExecutorCreator` :
        Builds Dagster executor definitions from these options.
    """

    job_namespace: str = Field(default="dagster")
    load_incluster_config: bool = Field(
        default=True,
        description="""Whether or not the executor is running within a k8s cluster already. If
        the job is using the `K8sRunLauncher`, the default value of this parameter will be
        the same as the corresponding value on the run launcher.
        If ``True``, we assume the executor is running within the target cluster and load config
        using ``kubernetes.config.load_incluster_config``. Otherwise, we will use the k8s config
        specified in ``kubeconfig_file`` (using ``kubernetes.config.load_kube_config``) or fall
        back to the default kubeconfig.""",
    )
    kubeconfig_file: str | None = Field(
        default=None,
        description="""Path to a kubeconfig file to use, if not using default kubeconfig. If
        the job is using the `K8sRunLauncher`, the default value of this parameter will be
        the same as the corresponding value on the run launcher.""",
    )
    step_k8s_config: K8sJobConfig = Field(
        default=K8sJobConfig(),
        description="Raw Kubernetes configuration for each step launched by the executor.",
    )
    per_step_k8s_config: dict[str, K8sJobConfig] = Field(
        default={},
        description="Per op k8s configuration overrides.",
    )
    image_pull_policy: str | None = Field(
        default=None,
        description="Image pull policy to set on launched Pods.",
    )
    image_pull_secrets: list[dict[str, str]] | None = Field(
        default=None,
        description="Specifies that Kubernetes should get the credentials from the Secrets named in this list.",
    )
    service_account_name: str | None = Field(
        default=None,
        description="The name of the Kubernetes service account under which to run.",
    )
    env_config_maps: list[str] | None = Field(
        default=None,
        description="A list of custom ConfigMapEnvSource names from which to draw environment variables (using ``envFrom``) for the Job. Default: ``[]``.",
    )
    env_secrets: list[str] | None = Field(
        default=None,
        description="A list of custom Secret names from which to draw environment variables (using ``envFrom``) for the Job. Default: ``[]``.",
    )
    env_vars: list[str] | None = Field(
        default=None,
        description="A list of environment variables to inject into the Job. Each can be of the form KEY=VALUE or just KEY (in which case the value will be pulled from the current process). Default: ``[]``.",
    )
    volume_mounts: list[dict[str, str]] = Field(
        default=[],
        description="A list of volume mounts to include in the job's container. Default: ``[]``.",
    )
    volumes: list[dict[str, str]] = Field(
        default=[],
        description="A list of volumes to include in the Job's Pod. Default: ``[]``.",
    )
    labels: dict[str, str] = Field(
        default={},
        description="Labels to apply to all created pods.",
    )
    resources: dict[str, dict[str, str]] | None = Field(
        default=None,
        description="Compute resource requirements for the container.",
    )
    scheduler_name: str | None = Field(
        default=None,
        description="Use a custom Kubernetes scheduler for launched Pods.",
    )
    security_context: dict[str, str] = Field(
        default={},
        description="Security settings for the container.",
    )


class CeleryK8sJobExecutorOptions(CeleryExecutorOptions, K8sJobExecutorOptions):
    """Options for the Celery-based executor which launches tasks as Kubernetes jobs.

    Parameters
    ----------
    job_wait_timeout : float
        Wait time in seconds for a job to complete before marking as failed.

    Examples
    --------
    ```yaml
    executors:
        celery_k8s_exec:
            celery_k8s_job_executor:
                broker: "pyamqp://guest@broker//"
                backend: "rpc://"
                job_namespace: "dagster"
                job_wait_timeout: 43200
                env_vars: ["ENV=prod"]
                include: ["my_project.workers"]
    jobs:
        celery_k8s_job:
            pipeline:
                pipeline_name: hybrid_async_pipeline
            executor: celery_k8s_exec
    ```

    See Also
    --------
    `kedro_dagster.config.models.CeleryExecutorOptions` :
        Provides Celery broker and backend configuration.
    `kedro_dagster.config.models.K8sJobExecutorOptions` :
        Provides Kubernetes job configuration.
    `kedro_dagster.dagster.ExecutorCreator` :
        Builds Dagster executor definitions from these options.
    """

    job_wait_timeout: float = Field(
        default=86400.0,
        description=(
            "Wait this many seconds for a job to complete before marking the run as failed."
            f" Defaults to {86400.0} seconds."
        ),
    )


ExecutorOptions = (
    InProcessExecutorOptions
    | MultiprocessExecutorOptions
    | DaskExecutorOptions
    | K8sJobExecutorOptions
    | DockerExecutorOptions
    | CeleryExecutorOptions
    | CeleryDockerExecutorOptions
    | CeleryK8sJobExecutorOptions
)


EXECUTOR_MAP = {
    "in_process": InProcessExecutorOptions,
    "multiprocess": MultiprocessExecutorOptions,
    "dask_executor": DaskExecutorOptions,
    "k8s_job_executor": K8sJobExecutorOptions,
    "docker_executor": DockerExecutorOptions,
    "celery_executor": CeleryExecutorOptions,
    "celery_docker_executor": CeleryDockerExecutorOptions,
    "celery_k8s_job_executor": CeleryK8sJobExecutorOptions,
}


# ---------------------------------------------------------------------------
# Schedule models
# ---------------------------------------------------------------------------


class ScheduleOptions(BaseModel):
    """Options for defining Dagster schedules.

    Parameters
    ----------
    cron_schedule : str
        Cron expression for the schedule.
    execution_timezone : str or None
        Timezone in which the schedule should execute.
    description : str or None
        Optional description of the schedule.
    metadata : dict[str, Any] or None
        Additional metadata for the schedule.

    Examples
    --------
    ```yaml
    schedules:
        daily_schedule:
            cron_schedule: "0 6 * * *"
            execution_timezone: "UTC"
            description: "Run every morning"
            metadata:
                owner: data-platform
    ```

    See Also
    --------
    `kedro_dagster.dagster.ScheduleCreator.create_schedules` :
        Builds Dagster schedule definitions from these options.
    """

    cron_schedule: str
    execution_timezone: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Pipeline and Job models
# ---------------------------------------------------------------------------


class PipelineOptions(BaseModel):
    """Options for filtering and configuring Kedro pipelines within a Dagster job.

    Parameters
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
        Namespace(s) to filter nodes by.
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
    `kedro_dagster.config.models.JobOptions` :
        Wraps this model alongside executor and schedule settings.
    `kedro_dagster.utils.get_filter_params_dict` :
        Extracts filter parameters from this configuration.
    """

    model_config = ConfigDict(extra="forbid")

    pipeline_name: str = "__default__"
    from_nodes: list[str] | None = None
    to_nodes: list[str] | None = None
    node_names: list[str] | None = None
    from_inputs: list[str] | None = None
    to_outputs: list[str] | None = None
    node_namespaces: list[str] | None = None
    tags: list[str] | None = None


class JobOptions(BaseModel):
    """Configuration options for a Dagster job.

    Parameters
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
    `kedro_dagster.config.models.PipelineOptions` :
        Pipeline filtering options within this job.
    `kedro_dagster.config.models.ScheduleOptions` :
        Schedule options referenced by this job.
    `kedro_dagster.config.models.LoggerOptions` :
        Logger options referenced by this job.
    `kedro_dagster.config.models.KedroDagsterConfig` :
        Top-level config that holds a dict of these job options.
    """

    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineOptions
    executor: ExecutorOptions | str | None = None
    schedule: ScheduleOptions | str | None = None
    loggers: list[LoggerOptions | str] | None = None


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class KedroDagsterConfig(BaseModel):
    """Main configuration class representing the ``dagster.yml`` structure.

    Parameters
    ----------
    loggers : dict[str, LoggerOptions] or None
        Mapping of logger names to logger options.
    executors : dict[str, ExecutorOptions] or None
        Mapping of executor names to executor options.
    schedules : dict[str, ScheduleOptions] or None
        Mapping of schedule names to schedule options.
    jobs : dict[str, JobOptions] or None
        Mapping of job names to job options.

    Examples
    --------
    ```yaml
    # conf/base/dagster.yml
    executors:
      sequential:
        in_process: {}

    schedules:
      daily:
        cron_schedule: "0 6 * * *"
        execution_timezone: "UTC"

    jobs:
      __default__:
        pipeline:
          pipeline_name: __default__
        executor: sequential
        schedule: daily
    ```

    See Also
    --------
    `kedro_dagster.config.models.get_dagster_config` :
        Loads and returns an instance of this class.
    """

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    loggers: dict[str, LoggerOptions] | None = None
    executors: dict[str, ExecutorOptions] | None = None
    schedules: dict[str, ScheduleOptions] | None = None
    jobs: dict[str, JobOptions] | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_executors(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Parse raw executor config dicts into typed executor option models.

        Parameters
        ----------
        values : dict[str, Any]
            Raw model data before validation.

        Returns
        -------
        dict[str, Any]
            Model data with executor configs replaced by option instances.

        Raises
        ------
        ValueError
            If an executor type is not recognized.
        """
        executors = values.get("executors") or {}

        parsed_executors = {}
        for name, executor_config in executors.items():
            if "in_process" in executor_config:
                executor_name = "in_process"
            elif "multiprocess" in executor_config:
                executor_name = "multiprocess"
            elif "k8s_job_executor" in executor_config:
                executor_name = "k8s_job_executor"
            elif "docker_executor" in executor_config:
                executor_name = "docker_executor"
            else:
                msg = f"Unknown executor type in {name}"
                LOGGER.error(msg)
                raise ValueError(msg)

            executor_options_class = EXECUTOR_MAP[executor_name]
            executor_options_params = executor_config[executor_name] or {}
            parsed_executors[name] = executor_options_class(**executor_options_params)

        values["executors"] = parsed_executors
        return values


def get_dagster_config(context: "KedroContext") -> "KedroDagsterConfig":
    """Get the Dagster configuration from the ``dagster.yml`` file.

    Parameters
    ----------
    context : KedroContext
        ``KedroContext`` that was created.

    Returns
    -------
    KedroDagsterConfig
        Dagster configuration.

    See Also
    --------
    `kedro_dagster.config.models.KedroDagsterConfig` :
        The configuration model returned.
    """
    from kedro.config import MissingConfigException

    LOGGER.info("Loading Dagster configuration...")

    try:
        if "dagster" not in context.config_loader.config_patterns:
            context.config_loader.config_patterns.update({"dagster": ["dagster*", "dagster*/**", "**/dagster*"]})
        conf_dagster_yml = context.config_loader["dagster"]
    except MissingConfigException:
        LOGGER.warning(
            "No 'dagster.yml' config file found in environment. Default configuration will be used. "
            "Use ``kedro dagster init`` command in CLI to customize the configuration."
        )

        conf_dagster_yml = {}

    dagster_config = KedroDagsterConfig(**conf_dagster_yml)

    return dagster_config


# ---------------------------------------------------------------------------
# Config template
# ---------------------------------------------------------------------------

CONFIG_TEMPLATE_YAML: str = """\
# dagster.yml - Kedro-Dagster orchestration configuration
# See https://kedro-dagster.readthedocs.io/en/latest/pages/reference/configuration/

jobs:
  __default__:
    pipeline:
      pipeline_name: __default__
"""

_CONFIG_TEMPLATE: KedroDagsterConfig = KedroDagsterConfig.model_validate(yaml.safe_load(CONFIG_TEMPLATE_YAML))
