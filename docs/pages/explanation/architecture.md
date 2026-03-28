# Architecture

This section provides an in-depth look at the architecture and core concepts behind Kedro-Dagster. Here you'll find details on how Kedro projects are mapped to Dagster constructs and compatibility considerations.

## How the translation works

Kedro-Dagster reads your Kedro project and the configuration under `conf/<ENV>/` to generate a Dagster code location. The selected environment determines which `catalog.yml` and `dagster.yml` are loaded. Translators then build Dagster assets and IO managers from the Kedro catalog, map nodes to ops and multi-assets, and construct jobs by filtering pipelines according to `dagster.yml`. All generated objects are registered in a single `dagster.Definitions` instance exposed by the Kedro-Dagster's generated `definitions.py`.

For a walkthrough with concrete examples, see the [example page](../tutorials/example-project.md).

## Kedro-Dagster concept mapping

Kedro-Dagster translates core Kedro concepts into their Dagster equivalents. Understanding this mapping helps you reason about how your Kedro project appears and behaves in Dagster.

| Kedro Concept   | Dagster Concept      | Description |
|-----------------|----------------------|-------------|
| **Node**        | Op,&nbsp;Asset            | Each [Kedro node](https://docs.kedro.org/en/stable/build/nodes/) becomes a Dagster op. Node parameters are passed as config. |
| **Pipeline**    | Job                  | [Kedro pipelines](https://docs.kedro.org/en/stable/build/pipeline_introduction/) are filtered and translated into a Dagster job. Jobs can be scheduled and can target executors. |
| **Dataset**     | Asset,&nbsp;IO&nbsp;Manager    | Each [Kedro data catalog](https://docs.kedro.org/en/stable/catalog-data/introduction/)'s dataset become Dagster assets managed by a dedicated IO managers. |
| **Hooks**       | Hooks,&nbsp;Sensors       | [Kedro hooks](https://docs.kedro.org/en/stable/extend/hooks/introduction/) are executed at the appropriate points in the Dagster job lifecycle. |
| **Parameters**  | Config,&nbsp;Resources    | [Kedro parameters](https://docs.kedro.org/en/stable/configuration/parameters.html) are passed as Dagster config. |
| **Logging**     | Logger               | [Kedro logging](https://docs.kedro.org/en/stable/develop/logging/) is integrated with Dagster's logging system. |

Additionally, we provide Kedro datasets, namely `DagsterPartitionedDataset` and `DagsterNothingDataset`, to enable [Dagster partitions](https://docs.dagster.io/guides/build/partitions-and-backfills).

### Catalog

Kedro-Dagster translates Kedro datasets into Dagster assets and IO managers. For the Kedro pipelines specified in `dagster.yml`, the following Dagster objects are defined:

- **External assets**: Input datasets to the pipelines are registered as Dagster external assets.
- **Assets**: Output datasets to the pipelines are defined as Dagster assets
- **IO Managers**: Custom Dagster IO managers are created for each dataset involved in the deployed pipelines mapping both their save and load functions.

See the API reference for [`CatalogTranslator`](../api/generated/kedro_dagster.catalog.CatalogTranslator.md) for more details.

#### Dataset `metadata`

Each Kedro dataset can take a `metadata` parameter to define additional metadata for the dataset. Kedro-Dagster takes advantage of this to populate the corresponding Dagster asset, and propagates parameters such as `description` to the asset. A `description` provided this way will appear in the Dagster UI. In addition to common metadata like `description`, a Kedro dataset's `metadata` can include a `group_name` field. When present, `group_name` is used to set the asset's group in Dagster and overrides the default group inferred from the node's pipeline. For multi-asset translations, `group_name` is applied per-AssetOut, allowing each asset produced by a multi-asset to belong to its own group when needed.

### Node

Kedro nodes are translated into Dagster ops and assets. Each node becomes a Dagster op, and, additionally, nodes that return outputs are mapped to Dagster multi-assets.

For the Kedro pipelines specified in `dagster.yml`, the following Dagster objects are defined:

- **Ops**: Each Kedro node within the pipelines is mapped to a Dagster op.
- **Assets**: Kedro nodes that return output datasets are registered as Dagster multi-assets.
- **Parameters**: Node parameters are passed as Dagster config to enable them to be modified in a Dagster run launchpad.

See the API reference for [`NodeTranslator`](../api/generated/kedro_dagster.nodes.NodeTranslator.md) for more details.

### Pipeline

Kedro pipelines are translated into Dagster jobs. Each job is defined as a filtered pipeline and can be scheduled and assigned an executor and a list of loggers via the `dagster.yml` configuration.

- **Filtering**: Jobs are defined granuarily from Kedro pipelines by allowing the filtering of their nodes, namespaces, tags, and inputs/outputs.
- **Scheduling**: Jobs can be scheduled using cron expressions defined in `dagster.yml`. See the [schedules section](../reference/configuration.md#customizing-schedules) for more details.
- **Executors**: Jobs can be assigned different executors defined in `dagster.yml`. See the [executors section](../reference/configuration.md#customizing-executors) for more details.
- **Loggers**: Jobs can be assigned different loggers defined in `dagster.yml`. See the [logging section](../how-to/configure-logging.md#custom-logger-configuration) for more details.

If one of the datasets involved in the pipeline is a `DagsterPartitionedDataset`, the corresponding job will fan-out the nodes the partitioned datasets are involved in according to the defined partitions.

See the API reference for [`PipelineTranslator`](../api/generated/kedro_dagster.pipelines.PipelineTranslator.md) for more details.

### Hook

Kedro-Dagster preserves all [Kedro hooks](https://docs.kedro.org/en/stable/extend/hooks/introduction/) in the Dagster context. Hooks are executed at the appropriate points in the Dagster job lifecycle. Dataset hooks are called in the `handle_output` and `load_input` function of each Dagster IO manager. Node hooks are plugged in the appropriate Dagster Op. As for the Context hook `after_context_created` and the Catalog hook `after_catalog_created`, they are called within a Dagster Op running at the beginning of each job along with the `before_pipeline_run` pipeline hook. The `after_pipeline_run` is called in a Dagster op running at the end of each job. Finally the `on_pipeline_error` pipeline, is embedded in a dedicated Dagster sensor that is triggered by a run failure.

## Compatibility notes between Kedro and Dagster

### Naming conventions

Dagster enforces strong constraints for asset, op, and job names as they must match the regex `^[A-Za-z0-9_]+$`. As those Dagster objects are created directly from Kedro datasets, nodes, and pipelines, Kedro-Dagster applies a small set of deterministic transformations so Kedro names map predictably to Dagster names:

- **Datasets**: only the dot "." namespace separator is converted to a double underscore "__" when mapping a Kedro dataset name to a Dagster-friendly identifier. Example: `my.dataset.name` -> `my__dataset__name`. Other characters (for example, hyphens `-`) are preserved by the formatter. Internally Kedro-Dagster will get back the dataset name from the asset name by replacing double underscored by dots.
- **Nodes**: dots are replaced with double underscores to keep namespaces (`my.node` -> `my__node`). If the resulting node name still contains disallowed characters (anything outside A-Z, a-z, 0-9 and underscore), the node name is replaced with a stable hashed placeholder of the form `unnamed_node_<md5>` to ensure it meets Dagster's constraints.

These rules are implemented in `src/kedro_dagster/utils.py` by `format_dataset_name`, `format_node_name`, and `unformat_asset_name` and are intentionally minimal and deterministic so names remain readable while complying with Dagster's requirements.
