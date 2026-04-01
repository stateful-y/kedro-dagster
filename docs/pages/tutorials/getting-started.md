# Getting Started

In this tutorial, we will set up and deploy a Kedro project with Dagster using the Kedro-Dagster plugin. By the end, we will have a running Dagster UI showing our Kedro pipelines as Dagster jobs, assets, and schedules.

We will use the Kedro `spaceflights-pandas` starter, but you can use your own Kedro project; if so, skip step 1.

## 1. Create a Kedro project (optional)

*Skip this step if you already have a Kedro project you want to deploy with Dagster.*

We start by creating a project from a Kedro starter template:

```bash
kedro new --starter=spaceflights-pandas
```

Follow the prompts to set up the project, then install its dependencies:

```bash
cd spaceflights-pandas
pip install -r requirements.txt
```

## 2. Install Kedro-Dagster

Choose your preferred package manager:

=== "pip"

    ```bash
    pip install kedro-dagster
    ```

=== "uv"

    ```bash
    uv add kedro-dagster
    ```

=== "conda"

    ```bash
    conda install -c conda-forge kedro-dagster
    ```

=== "mamba"

    ```bash
    mamba install -c conda-forge kedro-dagster
    ```

## 3. Initialize the plugin

We use [`kedro dagster init`](../api/generated/kedro_dagster.cli.init.md) to scaffold the Dagster integration:

```bash
kedro dagster init --env local
```

This creates two files:

- `src/definitions.py`: the Dagster entrypoint that exposes all translated Kedro objects:

``` title="definitions.py"
--8<-- "src/kedro_dagster/templates/definitions.py"
```

- `conf/local/dagster.yml`: the Dagster configuration for the `local` Kedro environment:

``` title="dagster.yml"
--8<-- "src/kedro_dagster/templates/dagster.yml"
```

Notice that `definitions.py` does not need editing to get started. The `dagster.yml` file is where we configure what Dagster sees.

## 4. Configure jobs, loggers, executors, and schedules

The `dagster.yml` file has four sections:

- **schedules:** Cron schedules for jobs.
- **executors:** Compute targets for jobs (in-process, multiprocess, k8s, etc).
- **loggers:** Logging configuration for jobs.
- **jobs:** Job definitions built from filtered Kedro pipelines.

We will now edit `conf/local/dagster.yml` to define three jobs:

```yaml
loggers:
  console_logger:
    log_level: INFO
    formatters:
      simple:
        format: "[%(asctime)s] %(levelname)s - %(message)s"
    handlers:
      - class: logging.StreamHandler
        stream: ext://sys.stdout
        formatter: simple

schedules:
  daily: # Schedule name
    cron_schedule: "0 0 * * *" # Schedule parameters

executors: # Executor name
  sequential: # Executor parameters
    in_process:

  multiprocess:
    multiprocess:
      max_concurrent: 2

jobs:
  default: # Job name
    pipeline: # Pipeline filter parameters
      pipeline_name: __default__
    executor: sequential

  parallel_data_processing:
    pipeline:
      pipeline_name: data_processing
      node_names:
      - preprocess_companies_node
      - preprocess_shuttles_node
    loggers: ["console_logger"]
    schedule: daily
    executor: multiprocess

  data_science:
    pipeline:
      pipeline_name: data_science
    loggers: ["console logger"]
    schedule: daily
    executor: sequential
```

Notice that we created a `parallel_data_processing` job that uses the `node_names` filter to select only two nodes from the `data_processing` pipeline. Both `parallel_data_processing` and `data_science` are scheduled daily and use different executors.

See the [configuration reference](../reference/configuration.md) for all available options.

## 5. Browse the Dagster UI

We start the Dagster development server with [`kedro dagster dev`](../reference/cli.md#kedro-dagster-dev):

```bash
kedro dagster dev --env local
```

The Dagster UI opens at [http://127.0.0.1:3000](http://127.0.0.1:3000).

 wc -l /home/gigi/Workspace/stateful-y/kedro-dagster/docs/pages/tutorials/getting-started.md /home/gigi/Workspace/stateful-y/kedro-dagster/docs/pages/explanation/architecture.md! note "Logging Configuration"
    By default, Kedro/Kedro-Dagster and Dagster use different log formats on the terminal. You can unify them by using Dagster formatters in your Kedro project's `logging.yml`. See the [logging guide](../how-to/configure-logging.md) for details.

 wc -l /home/gigi/Workspace/stateful-y/kedro-dagster/docs/pages/tutorials/getting-started.md /home/gigi/Workspace/stateful-y/kedro-dagster/docs/pages/explanation/architecture.md! tip "Logging from Your Kedro Nodes"

    To see logs from your Kedro node functions in the Dagster UI, replace `logging.getLogger` with `kedro_dagster.logging.getLogger` inside your node functions:

    ```python

    def process_data(data):
        from kedro_dagster.logging import getLogger
        logger = getLogger(__name__)
        logger.info("Processing data...")
        # Your code here
        return processed_data
    ```

    For complete logging configuration, see the [Logging guide](../how-to/configure-logging.md).

### Assets

The "Assets" tab shows all assets generated from the Kedro datasets involved in the jobs defined in `dagster.yml`.

<figure markdown>
![List of assets involved in the specified jobs](../../assets/getting-started/asset_list_dark.png#only-dark){data-gallery="assets-dark"}
![List of assets involved in the specified jobs](../../assets/getting-started/asset_list_light.png#only-light){data-gallery="assets-light"}
<figcaption>Asset List.</figcaption>
</figure>

Notice that each asset is prefixed by the Kedro environment (e.g., `local__`). If a dataset was generated from a [dataset factory](https://docs.kedro.org/en/stable/catalog-data/kedro_dataset_factories/#kedro-dataset-factories), its namespace also appears as a prefix.

Clicking "Asset lineage" at the top-right shows the dependency graph between assets:

<figure markdown>
![Lineage graph of assets involved in the specified jobs](../../assets/getting-started/asset_graph_dark.png#only-dark){data-gallery="assets-dark"}
![Lineage graph of assets involved in the specified jobs](../../assets/getting-started/asset_graph_light.png#only-light){data-gallery="assets-light"}
<figcaption>Asset Lineage Graph.</figcaption>
</figure>

### Jobs

The "Jobs" tab lists the jobs defined in `dagster.yml`, with names prefixed by the Kedro environment.

<figure markdown>
![List of the specified jobs](../../assets/getting-started/job_list_dark.png#only-dark){data-gallery="jobs-dark"}
![List of the specified jobs](../../assets/getting-started/job_list_light.png#only-light){data-gallery="jobs-light"}
<figcaption>Job List.</figcaption>
</figure>

Clicking on `parallel_data_processing` shows the translated pipeline graph. Notice that `before_pipeline_run` and `after_pipeline_run` appear as the first and last ops; these preserve your Kedro hooks.

<figure markdown>
![Graph describing the "parallel_data_processing" job](../../assets/getting-started/job_graph_dark.png#only-dark){data-gallery="jobs-dark"}
![Graph describing the "parallel_data_processing" job](../../assets/getting-started/job_graph_light.png#only-light){data-gallery="jobs-light"}
<figcaption>Job Graph.</figcaption>
</figure>

We can launch the job from the "Launchpad" sub-tab. The Kedro parameters (mapped to Dagster Config) and datasets (mapped to IO managers) can be modified before launching:

<figure markdown>
![Launchpad for the "parallel_data_processing" job](../../assets/getting-started/job_launchpad_dark.png#only-dark){data-gallery="jobs-dark"}
![Launchpad for the "parallel_data_processing" job](../../assets/getting-started/job_launchpad_light.png#only-light){data-gallery="jobs-light"}
<figcaption>Job Launchpad.</figcaption>
</figure>

<figure markdown>
![Running the "parallel_data_processing" job](../../assets/getting-started/job_running_dark.png#only-dark){data-gallery="jobs-dark"}
![Running the "parallel_data_processing" job](../../assets/getting-started/job_running_light.png#only-light){data-gallery="jobs-light"}
<figcaption>Job Run Timeline.</figcaption>
</figure>

### Resources and Automation

The "Resources" tab shows one Dagster IO Manager per Kedro dataset; these interface with each dataset's `save` and `load` methods.

<figure markdown>
![List of the resources involved in the specified jobs](../../assets/getting-started/resource_list_dark.png#only-dark){data-gallery="resources-dark"}
![List of the resources involved in the specified jobs](../../assets/getting-started/resource_list_light.png#only-light){data-gallery="resources-light"}
<figcaption>Resource list.</figcaption>
</figure>

The "Automation" tab shows the defined schedules and sensors. Kedro-Dagster uses a sensor to enable the `on_pipeline_error` hook.

<figure markdown>
![List of the schedules and sensors involved in the specified jobs](../../assets/getting-started/automation_list_dark.png#only-dark){data-gallery="automation-dark"}
![List of the schedules and sensors involved in the specified jobs](../../assets/getting-started/automation_list_light.png#only-light){data-gallery="automation-light"}
<figcaption>Schedule and Sensor List.</figcaption>
</figure>

---

## Next steps

- **Advanced example:** Visit the [Example Project](example-project.md) for partitions, MLflow, and multi-environment configuration.
- **Configuration:** Explore the [configuration reference](../reference/configuration.md) for all available options.
- **API:** See the [API reference](../reference/api.md) for details on available classes and functions.
