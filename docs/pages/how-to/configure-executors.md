# How to Configure Custom Executors

This guide shows you how to configure different execution backends for your Dagster jobs. Use this when you need parallel execution, containerized runs, or distributed computation.

## Prerequisites

- A working Kedro-Dagster project ([Getting Started](../tutorials/getting-started.md))
- Additional packages installed for your chosen executor (noted per section)

## How executor configuration works

Executors are defined in `conf/<env>/dagster.yml` under the `executors` key. Each job references an executor by name. If no executor is specified, Dagster uses in-process execution by default.

```yaml
executors:
  my_executor:
    <executor_type>:
      <options>

jobs:
  my_job:
    pipeline: __default__
    executor: my_executor
```

## In-process executor

Runs all steps sequentially in a single process. Useful for debugging and development.

```yaml
executors:
  sequential:
    in_process:
      retries:
        enabled: {}
```

## Multiprocess executor

Runs steps in parallel using separate OS processes on a single machine.

```yaml
executors:
  parallel:
    multiprocess:
      max_concurrent: 4
```

Set `max_concurrent` to the number of CPU cores available or tune based on memory constraints.

## Docker executor

Runs each step in an isolated Docker container. **Requires:** `dagster-docker`.

```bash
pip install dagster-docker
```

```yaml
executors:
  docker:
    docker_executor:
      image: my-project:latest
      network: my_network
      env_vars:
        - KEDRO_ENV=production
        - AWS_DEFAULT_REGION
      container_kwargs:
        volumes:
          - "/data:/data"
```

If you use a private registry:

```yaml
executors:
  docker_private:
    docker_executor:
      image: registry.example.com/my-project:latest
      registry:
        url: registry.example.com
        username: user
        password: pass
```

## Kubernetes executor

Runs each step as a Kubernetes Job. **Requires:** `dagster-k8s`.

```bash
pip install dagster-k8s
```

```yaml
executors:
  k8s:
    k8s_job:
      job_namespace: dagster
      load_incluster_config: true
      max_concurrent: 10
      image_pull_policy: Always
      service_account_name: dagster-worker
      labels:
        team: data-science
      resources:
        requests:
          cpu: "500m"
          memory: "1Gi"
        limits:
          cpu: "2"
          memory: "4Gi"
      step_k8s_config:
        container_config:
          image: my-project:latest
```

If you are running outside the cluster, provide a kubeconfig:

```yaml
executors:
  k8s_external:
    k8s_job:
      load_incluster_config: false
      kubeconfig_file: /path/to/kubeconfig
      job_namespace: dagster
      step_k8s_config:
        container_config:
          image: my-project:latest
```

To override configuration for specific steps:

```yaml
executors:
  k8s_mixed:
    k8s_job:
      job_namespace: dagster
      step_k8s_config:
        container_config:
          image: my-project:latest
      per_step_k8s_config:
        train_model:
          container_config:
            image: my-project-gpu:latest
          pod_spec_config:
            node_selector:
              gpu: "true"
```

## Dask executor

Distributes steps across a Dask cluster. **Requires:** `dagster-dask`.

```bash
pip install dagster-dask
```

Connect to an existing scheduler:

```yaml
executors:
  dask_existing:
    dask:
      cluster:
        existing:
          address: tcp://scheduler:8786
```

Or use a local cluster for development:

```yaml
executors:
  dask_local:
    dask:
      cluster:
        local:
          n_workers: 4
          threads_per_worker: 1
```

## Celery executor

Routes steps through Celery task queues. **Requires:** `dagster-celery`.

```bash
pip install dagster-celery
```

```yaml
executors:
  celery:
    celery:
      broker: redis://redis:6379/0
      backend: redis://redis:6379/1
      include:
        - my_package.definitions
      config_source:
        task_serializer: json
```

## Celery + Docker executor

Combines Celery task routing with Docker container isolation. **Requires:** `dagster-celery-docker`.

```yaml
executors:
  celery_docker:
    celery_docker:
      broker: redis://redis:6379/0
      backend: redis://redis:6379/1
      image: my-project:latest
      network: my_network
```

## Celery + Kubernetes executor

Routes steps through Celery and runs each as a Kubernetes Job. **Requires:** `dagster-celery-k8s`.

```yaml
executors:
  celery_k8s:
    celery_k8s:
      broker: redis://redis:6379/0
      backend: redis://redis:6379/1
      job_namespace: dagster
      job_wait_timeout: 86400
      step_k8s_config:
        container_config:
          image: my-project:latest
```

## Assigning executors to jobs

Each job can target a different executor:

```yaml
executors:
  dev:
    in_process: {}
  prod:
    multiprocess:
      max_concurrent: 8

jobs:
  quick_test:
    pipeline: __default__
    executor: dev

  full_run:
    pipeline: __default__
    executor: prod
```

Use environment-specific `dagster.yml` files to switch executors between deployments without changing job definitions:

- `conf/local/dagster.yml`: in-process executor for development
- `conf/production/dagster.yml`: Kubernetes executor for production

## See also

- [Configuration Reference](../reference/configuration.md): complete field tables for all executor options
- [How to Deploy to Production](deploy-to-production.md): end-to-end production deployment
- [Dagster Executor Documentation](https://docs.dagster.io/deployment/executors): official Dagster executor docs
