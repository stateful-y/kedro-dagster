---
description: "Complete field tables for `dagster.yml`: jobs, executors, schedules, and loggers."
---

# Configuration Reference

Kedro-Dagster expects a standard [Kedro project structure](https://docs.kedro.org/en/stable/get_started/kedro_concepts.html#kedro-project-directory-structure). The main configuration file is `dagster.yml`, located in `conf/<ENV_NAME>/`.

## dagster.yml

Defines jobs, executors, schedules, and loggers for your project.

```yaml
schedules:
  my_job_schedule:
    cron_schedule: "0 0 * * *"

executors:
  my_executor:
    multiprocess:
      max_concurrent: 2

loggers:
  my_logger:
    log_level: INFO
    handlers:
      - class: logging.StreamHandler
        stream: ext://sys.stdout
        formatter: simple
    formatters:
      simple:
        format: "%(asctime)s - %(levelname)s - %(message)s"

jobs:
  my_job:
    pipeline:
      pipeline_name: __default__
      node_namespaces: [my_namespace]
    executor: my_executor
    schedule: my_job_schedule
    loggers: [my_logger]
```

### Jobs

Each job maps a [Kedro pipeline](https://docs.kedro.org/en/stable/build/pipeline_introduction/) to a Dagster job, with optional [filtering](https://docs.kedro.org/en/stable/api/pipeline/kedro.pipeline.Pipeline/#kedro.pipeline.Pipeline.filter). A job can reference a pre-defined executor, schedule, and list of loggers by name.

Accepted pipeline parameters: [`PipelineOptions`](../api/generated/kedro_dagster.config.PipelineOptions.md).

### Job factories

A `jobs:` key that contains `{placeholder}` markers is a **job factory**, the job-level analogue of a [Kedro dataset factory](https://docs.kedro.org/en/stable/catalog-data/kedro_dataset_factories/). Instead of writing one job per namespace by hand, a factory renders one concrete job per **pipeline node namespace**.

The first `node_namespaces` entry is the *binding axis*: it is split on `.`, and each segment is either a `{placeholder}` (bound to that part of a node's namespace) or a literal (which must match). The distinct namespaces of the factory's `pipeline_name` pipeline, at the axis depth, become the jobs:

```yaml
jobs:
  "{product}__data_processing_candidate1":
    pipeline:
      pipeline_name: data_processing
      node_namespaces: ["{product}"] # binding axis: {product} = each namespace
      tags: [candidate1]
    executor: multiprocessing
    schedule: daily
```

If the `data_processing` pipeline has nodes in the namespaces `reviews_predictor` and `price_predictor`, this single key renders two jobs: `reviews_predictor__data_processing_candidate1` and `price_predictor__data_processing_candidate1`, each with the interpolated body.

Key points:

- **Names render forward only.** A concrete name is produced by substituting the binding into the factory key; names are never reverse-parsed. The fixed job-type tail is separated from the placeholder-derived part by `__`, so `{product}__data_processing_candidate1` becomes `reviews_predictor__data_processing_candidate1` (single `_` inside the namespace value, `__` before the tail). Rendered names are valid Dagster names (`[A-Za-z0-9_]`).
- **The whole body is interpolated.** Placeholders are substituted into every string in the job body, not just the key. This includes references such as `executor: "{product}_executor"`.
- **Literal jobs win.** A `jobs:` key without markers is a literal job; on a name collision it takes precedence over a rendered one. When several factories render the same name, the most-specific (most literal characters) supplies the body.

Preview the expansion without launching Dagster:

```bash
kedro dagster list-patterns -e <env>     # the factory ({placeholder}) keys
kedro dagster resolve-patterns -e <env>  # the concrete jobs they render
```

For a step-by-step walkthrough, see [How to Use Job Factories](../how-to/use-job-factories.md).

### Executors

Define how jobs are executed: in-process, multiprocess, Docker, Celery, Kubernetes, etc. Each entry corresponds to a [Dagster executor](https://docs.dagster.io/guides/operate/run-executors#example-executors).

Configuration models per executor type are documented in the [API reference](../api/config.md).

#### Executor key naming

Each executor entry declares exactly one executor type. The key follows one rule:

- Executors provided by **Dagster core** use their short name: `in_process`, `multiprocess`.
- Executors provided by a **`dagster_*` library** use their Dagster symbol name verbatim: `dask_executor`, `docker_executor`, `k8s_job_executor`, `celery_executor`, `celery_docker_executor`, `celery_k8s_job_executor`.

That is why `in_process` sits alongside `docker_executor` rather than `in_process_executor` or `docker`: the suffix tracks where the executor comes from. Library executors additionally require their package to be installed — see the note under each example below.

| Key | Provided by | Requires |
| --- | --- | --- |
| `in_process` | Dagster core | — |
| `multiprocess` | Dagster core | — |
| `dask_executor` | `dagster_dask` | `pip install dagster-dask` |
| `docker_executor` | `dagster_docker` | `pip install dagster-docker` |
| `k8s_job_executor` | `dagster_k8s` | `pip install dagster-k8s` |
| `celery_executor` | `dagster_celery` | `pip install dagster-celery` |
| `celery_docker_executor` | `dagster_celery_docker` | `pip install dagster-celery-docker` |
| `celery_k8s_job_executor` | `dagster_celery_k8s` | `pip install dagster-celery-k8s` |

!!! warning "Environment variables are not interpolated in `dagster.yml`"

    `${oc.env:MY_VAR}` and `${MY_VAR}` do **not** resolve anywhere in `dagster.yml`,
    and the attempt raises at config load rather than leaving the value
    unsubstituted.

    This is deliberate Kedro behaviour, not a plugin limitation: `OmegaConfigLoader`
    clears the `oc.env` resolver and re-enables it only for the `credentials` config
    key. `credentials.yml` is therefore the one Kedro config file where
    `${oc.env:...}` works.

    To pass secrets to a containerized executor, list bare variable names under
    `env_vars` and read them from `credentials.yml` — see
    [How to Pass Database Credentials](../how-to/pass-credentials.md).

**Multiprocess example** ([`MultiprocessExecutorOptions`](../api/generated/kedro_dagster.config.MultiprocessExecutorOptions.md)):

```yaml
executors:
  my_multiprocess_executor:
    multiprocess:
      max_concurrent: 4
```

**Docker example** ([`DockerExecutorOptions`](../api/generated/kedro_dagster.config.DockerExecutorOptions.md)):

```yaml
executors:
  my_docker_executor:
    docker_executor:
      image: my-custom-image:latest
      registry:
        url: "my_registry.com"
        username: "my_user"
        password: "my_password"
      network: "my_network"
      networks: ["my_network_1", "my_network_2"]
      container_kwargs:
        volumes:
          - "/host/path:/container/path"
        environment:
          - "ENV_VAR=value"
```

 wc -l /home/gigi/Workspace/stateful-y/kedro-dagster/docs/pages/reference/configuration.md! note
    The `docker_executor` requires the `dagster-docker` package.

### Schedules

Cron-based schedules for jobs. See the [Dagster scheduling documentation](https://docs.dagster.io/concepts/partitions-schedules-sensors/schedules) and [`ScheduleOptions`](../api/generated/kedro_dagster.config.ScheduleOptions.md).

### Loggers

Custom loggers for Dagster runs. See the [logging guide](../how-to/configure-logging.md) for configuration details and [`LoggerCreator`](../api/generated/kedro_dagster.dagster.LoggerCreator.md).

## definitions.py

Auto-generated by the plugin. Serves as the main entry point for Dagster to discover all translated Kedro objects. Contains the Dagster [`Definitions`](https://docs.dagster.io/api/dagster/definitions#dagster.Definitions) object registering all jobs, assets, resources, schedules, and sensors.

In most cases, you should not manually edit `definitions.py`; instead, update your Kedro project or `dagster.yml`.

## See also

- [CLI Reference](cli.md): command-line interface for the plugin
- [Getting Started](../tutorials/getting-started.md): see the configuration in action
- [How to Configure Custom Executors](../how-to/configure-executors.md): detailed executor YAML examples
