# How to Use Dagster Partitions

!!! warning "Experimental Status"
    Dagster partitions support in Kedro-Dagster is **experimental** and currently supports only a limited subset of Dagster's partition types.

Kedro-Dagster's integration of [Dagster partitions](https://docs.dagster.io/guides/build/partitions-and-backfills) has the following goals:

- Represent partitioned datasets as Dagster assets equipped with a Dagster partition definitions and potentially partition mappings of downstream assets
- Enable job-level fan-out of Kedro nodes when partitioned datasets are involved so that partitioned runs can be executed in parallel per partition key

This asset-job duality allows users to leverage Dagster's parallel partition processing as well as asset-based backfilling and partition-aware lineage.

Kedro-Dagster provides two custom datasets to enable Dagster partitioning:

- **`DagsterPartitionedDataset`**: A Kedro dataset that is partitioned according to Dagster's partitioning definition and enforces partition mappings to downstream assets.
- **`DagsterNothingDataset`**: A special Kedro dataset that represents a "no-op" or empty dataset in Dagster. This can be useful for cases where an order in execution between two nodes needs to be enforced. It can also be used to forced dependency between nodes outside of the Dagster partitions context.

Fan-out occurs at the Kedro node level during translation. If a node depends on or produces a `DagsterPartitionedDataset` dataset, the translator creates per-partition Dagster ops for that node. Ops created this way will be executed in parallel for each partition key defined in the `DagsterPartitionedDataset`. Downstream nodes depending on the partitioned dataset will also be fanned-out accordingly, respecting any defined partition mappings. When ops are fanned-out, their name is suffixed with the partition key to ensure uniqueness.

The corresponding assets are equipped with their corresponding partition definitions and mappings, therefore one may use Dagster UI to perform backfills, materialize specific partitions, and observe partition-aware asset lineage.

!!! note "Fanning-out is static at translation time"
    Kedro-Dagster's fan-out mechanism is static and occurs at translation time. Therefore, dynamic partitioning based on runtime information is not supported.

## `DagsterPartitionedDataset`

This dataset wraps Kedro's `PartitionedDataset` to enable Dagster partitioning and optional partition mappings to downstream datasets. When a job includes a `DagsterPartitionedDataset`, Dagster will schedule and materialize per-partition runs; you can select partition keys in the Dagster UI launchpad or use backfills for ranges.

!!! danger "No hooks triggered on asset jobs"
    If you decide to run backfills or materialize specific partitions from the Dagster UI, be aware that no Kedro hooks will be triggered in those runs. In particular, this means that any Kedro-MLflow integration relying on hooks will not function in those cases.

### Example Usage

A `DagsterPartitionedDataset` can be defined in your Kedro data catalog as follows:

```yaml
my_downstream_partitioned_dataset:
  type: kedro_dagster.datasets.DagsterPartitionedDataset
  path: data/01_raw/my_data/
  dataset: # Underlying Kedro PartitionedDataset configuration
    type: pandas.CSVDataSet
  partition: dagster.StaticPartitionsDefinition # Define Dagster partitions
    partitions:
      - 2023-01-01.csv
      - 2023-01-02.csv
      - 2023-01-03.csv
```

To define a partition mapping to downstream datasets, you can use the `partition_mappings` parameter:

```yaml
my_upstream_partitioned_dataset:
  type: kedro_dagster.datasets.DagsterPartitionedDataset
  partition: dagster.StaticPartitionsDefinition
    partitions:
      - 2023-01-01.csv
      - 2023-01-02.csv
      - 2023-01-03.csv
  partition_mappings:
    my_downstream_partitioned_dataset: # Map to downstream dataset
      type: dagster.StaticPartitionMapping
      downstream_partition_keys_by_upstream_partition_key:
        1.csv: 2023-01-01.csv
        2.csv: 2023-01-02.csv
        3.csv: 2023-01-03.csv
```

The dataset mapped to in `partition_mappings` can also be refered to using a pattern with the `{}` syntax:

```yaml
my_upstream_partitioned_dataset:
  ...
  partition_mappings:
    {namespace}.partitioned_dataset: # Map to downstream dataset
      type: dagster.StaticPartitionMapping
  ...
```

!!! note
    The `partition` and `partition_mapping` parameters expect Dagster partition definitions and mappings. Refer to the [Dagster Partitions documentation](https://docs.dagster.io/concepts/partitions-schedules-sensors/partitions) for more details on available partition types and mappings.

See the API reference for [`DagsterPartitionedDataset`](../api/generated/kedro_dagster.datasets.partitioned_dataset.DagsterPartitionedDataset.md) for more details.

### Supported partition definitions and mappings

Currently, only **`StaticPartitionsDefinition`** is supported. It works for a fixed sets of partitions (e.g., specific dates, regions, model variants). See [Dagster StaticPartitionsDefinition docs](https://docs.dagster.io/api/dagster/partitions#dagster.StaticPartitionsDefinition) for more details.

Two partition mapping types are supported:

1. **`StaticPartitionMapping`**: Explicitly maps upstream partition keys to downstream partition keys. See [Dagster StaticPartitionMapping docs](https://docs.dagster.io/api/dagster/partitions#dagster.StaticPartitionMapping) for more details.

2. **`IdentityPartitionMapping`**: One-to-one mapping where partition keys match exactly. See [Dagster IdentityPartitionMapping docs](https://docs.dagster.io/api/dagster/partitions#dagster.IdentityPartitionMapping) for more details.

Example with `StaticPartitionMapping`:

```yaml
upstream_dataset:
  type: kedro_dagster.DagsterPartitionedDataset
  path: data/02_raw/upstream/
  dataset:
    type: pandas.CSVDataSet
  partition:
    type: dagster.StaticPartitionsDefinition
    partition_keys: ["1.csv", "2.csv", "3.csv"]
  partition_mappings:
    downstream_dataset:
      type: dagster.StaticPartitionMapping
      downstream_partition_keys_by_upstream_partition_key:
        1.csv: 10.csv
        2.csv: 20.csv
        3.csv: 30.csv
```

Example with `IdentityPartitionMapping`:

```yaml
upstream_dataset:
  type: kedro_dagster.DagsterPartitionedDataset
  path: data/02_raw/upstream/
  dataset:
    type: pickle.PickleDataset
  partition:
    type: dagster.StaticPartitionsDefinition
    partition_keys: ["A.pkl", "B.pkl", "C.pkl"]
  partition_mappings:
    downstream_dataset:
      type: dagster.IdentityPartitionMapping  # Keys match exactly
```

!!! info "Need Support for other Dagster partitions?"
    If you have a use case that requires any unsupported partition types, please [open an issue](https://github.com/stateful-y/kedro-dagster/issues) describing your requirements.

## `DagsterNothingDataset`

A dummy dataset representing a Dagster asset of type `Nothing` without associated data used to enforce links between nodes. It does not read or write any data but allows you to create dependencies between nodes in your Kedro pipelines that translate to Dagster assets of type `Nothing`.

### Example usage

It is straightforward to define a `DagsterNothingDataset` in your Kedro data catalog as follows:

```yaml
my_nothing_dataset:
  type: kedro_dagster.datasets.DagsterNothingDataset
  metadata:
      description: "Nothing dataset."
```

See the API reference for [`DagsterNothingDataset`](../api/generated/kedro_dagster.datasets.nothing_dataset.DagsterNothingDataset.md) for more details.

## Future roadmap

Support for additional partition types may be added in future releases. Track progress and request features at:

- [Kedro-Dagster Issue Tracker](https://github.com/stateful-y/kedro-dagster/issues)

If you have a use case requiring specific partition types, please open a feature request with your requirements.
