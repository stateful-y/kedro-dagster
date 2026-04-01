# How to Deploy to Production

This guide shows you how to move from `kedro dagster dev` to a production Dagster deployment. Use this when your pipelines are working locally and you need to run them on a schedule, with monitoring, in a remote environment.

## Prerequisites

- A working Kedro-Dagster project ([Getting Started](../tutorials/getting-started.md))
- Familiarity with your target infrastructure (Docker, Kubernetes, or a cloud VM)

## 1. Create a production environment

Kedro's environment system lets you maintain separate configurations per deployment target. Create a production `dagster.yml` alongside your existing `base` or `local` one:

```bash
kedro dagster init -e production
```

Edit `conf/production/dagster.yml` to configure production-appropriate settings:

```yaml
executors:
  prod_executor:
    multiprocess:
      max_concurrent: 8

schedules:
  nightly:
    cron_schedule: "0 2 * * *"

jobs:
  training_pipeline:
    pipeline: data_science
    executor: prod_executor
    schedule: nightly
```

Run with the production environment:

```bash
kedro dagster dev -e production
```

## 2. Choose an executor

The executor determines where and how your pipeline steps run. Pick based on your infrastructure:

| Executor | Use when |
|----------|----------|
| `in_process` | Single-machine debugging, simplest setup |
| `multiprocess` | Single machine, parallel steps |
| `docker_executor` | Steps need isolated environments or specific system dependencies |
| `k8s_job` | Running on Kubernetes with per-step pods |
| `dask` | Large-scale distributed computation on a Dask cluster |
| `celery` | Celery-based task queues are already part of your infrastructure |

See the [executor configuration how-to](configure-executors.md) for YAML examples of each executor.

## 3. Build a deployable code location

Dagster deploys projects as code locations. The generated `definitions.py` in your Kedro source directory is the entry point.

Package your project as a Python package:

```bash
uv build
```

If deploying with Docker, create a `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install .

# Dagster loads the definitions module
ENV DAGSTER_HOME=/opt/dagster/dagster_home
ENV KEDRO_ENV=production
```

## 4. Configure the Dagster instance

In production, Dagster needs persistent storage for run history, event logs, and schedules. Create a `dagster.yaml` (Dagster's own config, separate from `dagster.yml` in Kedro):

```yaml
run_storage:
  module: dagster_postgres.run_storage
  class: PostgresRunStorage
  config:
    postgres_url:
      env: DAGSTER_PG_URL

event_log_storage:
  module: dagster_postgres.event_log_storage
  class: PostgresEventLogStorage
  config:
    postgres_url:
      env: DAGSTER_PG_URL

schedule_storage:
  module: dagster_postgres.schedule_storage
  class: PostgresScheduleStorage
  config:
    postgres_url:
      env: DAGSTER_PG_URL
```

See the [Dagster deployment documentation](https://docs.dagster.io/deployment) for complete instance configuration options.

## 5. Verify before deploying

Before deploying, confirm that the production configuration translates correctly:

```bash
# List all definitions with the production environment
kedro dagster list-defs -e production

# Start the UI locally with production config to inspect
kedro dagster dev -e production
```

Check that jobs, schedules, and executor assignments appear as expected in the Dagster UI.

## See also

- [How to Configure Custom Executors](configure-executors.md) - YAML examples for all executor types
- [Configuration Reference](../reference/configuration.md) - complete `dagster.yml` field tables
- [Example Project](../tutorials/example-project.md) - multi-environment setup with local/dev/staging/prod
- [Dagster Deployment Guide](https://docs.dagster.io/deployment) - official Dagster deployment documentation
