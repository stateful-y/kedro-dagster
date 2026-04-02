# Architecture

Kedro-Dagster translates a Kedro project into a Dagster code location, mapping pipelines, datasets, nodes, and hooks to their Dagster equivalents. Understanding this architecture helps you reason about how your Kedro project appears and behaves in Dagster.

## How the translation works

When you run `kedro dagster dev`, Kedro-Dagster reads your Kedro project and the configuration under `conf/<ENV>/` to produce a Dagster code location. The selected environment determines which `catalog.yml` and `dagster.yml` are loaded. Translators then:

1. Build Dagster assets and IO managers from the Kedro catalog.
2. Map nodes to ops and multi-assets.
3. Construct jobs by filtering pipelines according to `dagster.yml`.

All generated objects are registered in a single `dagster.Definitions` instance exposed by the generated `definitions.py`.

For a walkthrough with concrete examples, see the [Example Project](../tutorials/example-project.md).

## Concept mapping

The table below summarizes the correspondence between Kedro and Dagster concepts:

| Kedro Concept   | Dagster Concept         | Description |
|-----------------|-------------------------|-------------|
| **Node**        | Op, Asset               | Each [Kedro node](https://docs.kedro.org/en/stable/build/nodes/) becomes a Dagster op. Node parameters are passed as config. |
| **Pipeline**    | Job                     | [Kedro pipelines](https://docs.kedro.org/en/stable/build/pipeline_introduction/) are filtered and translated into Dagster jobs. Jobs can be scheduled and target executors. |
| **Dataset**     | Asset, IO Manager       | Each [Kedro catalog](https://docs.kedro.org/en/stable/catalog-data/introduction/) dataset becomes a Dagster asset managed by a dedicated IO manager. |
| **Hooks**       | Hooks, Sensors          | [Kedro hooks](https://docs.kedro.org/en/stable/extend/hooks/introduction/) are executed at the appropriate points in the Dagster job lifecycle. |
| **Parameters**  | Config, Resources       | [Kedro parameters](https://docs.kedro.org/en/stable/configuration/parameters.html) are passed as Dagster config. |
| **Logging**     | Logger                  | [Kedro logging](https://docs.kedro.org/en/stable/develop/logging/) is integrated with Dagster's logging system. |

Additionally, `DagsterPartitionedDataset` and `DagsterNothingDataset` enable [Dagster partitions](https://docs.dagster.io/guides/build/partitions-and-backfills).

### Catalog translation

Kedro datasets become three kinds of Dagster objects:

- **External assets**: Input-only datasets are registered as Dagster external assets.
- **Assets**: Output datasets are defined as Dagster assets.
- **IO Managers**: Each dataset gets a dedicated IO manager wrapping its `save` and `load` methods.

A Kedro dataset's `metadata` parameter is propagated to the Dagster asset. For example, `description` appears in the Dagster UI, and `group_name` overrides the default group inferred from the node's pipeline.

See [`CatalogTranslator`](../api/generated/kedro_dagster.catalog.CatalogTranslator.md).

### Node translation

Each Kedro node becomes a Dagster op. Nodes that return outputs are additionally mapped to Dagster multi-assets. Node parameters are passed as Dagster config, making them editable in the Dagster run launchpad.

See [`NodeTranslator`](../api/generated/kedro_dagster.nodes.NodeTranslator.md).

### Pipeline translation

Kedro pipelines become Dagster jobs. Each job is defined from a filtered pipeline and can be scheduled and assigned an executor and loggers via `dagster.yml`.

- **Filtering**: Jobs are defined from Kedro pipelines by filtering nodes, namespaces, tags, and inputs/outputs. See the [configuration reference](../reference/configuration.md#jobs).
- **Scheduling**: Jobs can use cron expressions. See the [schedules section](../reference/configuration.md#schedules).
- **Executors**: Jobs can target different executors. See the [executors section](../reference/configuration.md#executors).
- **Loggers**: Jobs can use custom loggers. See the [logging guide](../how-to/configure-logging.md#configure-dagster-run-loggers).

If a dataset in the pipeline is a `DagsterPartitionedDataset`, the job fans out the involved nodes according to the defined partitions.

See [`PipelineTranslator`](../api/generated/kedro_dagster.pipelines.PipelineTranslator.md).

### Hook preservation

Every Kedro hook type has a corresponding integration point in the Dagster execution lifecycle. This means existing hook-based integrations (such as Kedro-MLflow) work in Dagster without modification.

All [Kedro hooks](https://docs.kedro.org/en/stable/extend/hooks/introduction/) are preserved in the Dagster context:

- **Dataset hooks** (`before_dataset_loaded`, `after_dataset_loaded`, `before_dataset_saved`, `after_dataset_saved`): Called in each Dagster IO manager's `handle_output` and `load_input` methods.
- **Node hooks** (`before_node_run`, `after_node_run`, `on_node_error`): Wrapped in the corresponding Dagster op.
- **Context and catalog hooks** (`after_context_created`, `after_catalog_created`): Called in a Dagster op at the beginning of each job, alongside `before_pipeline_run`.
- **Pipeline completion** (`after_pipeline_run`): Called in a Dagster op at the end of each job.
- **Pipeline error** (`on_pipeline_error`): Embedded in a dedicated Dagster sensor triggered by run failures.

This means integrations like `kedro-mlflow` that rely on hooks work automatically in Dagster without any additional code.

## Naming conventions

Dagster enforces that asset, op, and job names match `^[A-Za-z0-9_]+$`. Kedro-Dagster applies deterministic transformations so Kedro names map predictably to Dagster names:

- **Datasets**: The dot `.` namespace separator is converted to double underscores `__`. Example: `my.dataset.name` becomes `my__dataset__name`. Internally, double underscores are reversed back to dots.
- **Nodes**: Dots are replaced with double underscores. If the result still contains disallowed characters, the name is replaced with a stable hash placeholder (`unnamed_node_<md5>`).

These rules are implemented in `src/kedro_dagster/utils.py` by `format_dataset_name`, `format_node_name`, and `unformat_asset_name`.

## See also

- [Concepts](concepts.md): the asset-first philosophy and key features behind the translation
- [Configuration Reference](../reference/configuration.md): all `dagster.yml` fields that control job, executor, and schedule creation
- [Getting Started](../tutorials/getting-started.md): hands-on walkthrough of the translation in action
