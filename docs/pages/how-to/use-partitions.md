# How to Use Dagster Partitions

!!! warning "Experimental Status"
    Dagster partitions support in Kedro-Dagster is **experimental** and currently supports only `StaticPartitionsDefinition`.

Kedro-Dagster provides two custom datasets to enable [Dagster partitions](https://docs.dagster.io/guides/build/partitions-and-backfills) in your Kedro project: `DagsterPartitionedDataset` and `DagsterNothingDataset`.

## Define a partitioned dataset

Add a `DagsterPartitionedDataset` to your Kedro catalog:

```yaml
my_partitioned_dataset:
  type: kedro_dagster.datasets.DagsterPartitionedDataset
  path: data/01_raw/my_data/
  dataset:
    type: pandas.CSVDataSet
  partition:
    type: dagster.StaticPartitionsDefinition
    partition_keys: ["2023-01-01.csv", "2023-01-02.csv", "2023-01-03.csv"]
```

When a job includes a `DagsterPartitionedDataset`, Dagster schedules and materializes per-partition runs. You can select partition keys in the Dagster UI launchpad or use backfills for ranges.

If a node depends on or produces a `DagsterPartitionedDataset`, the translator creates per-partition Dagster ops for that node. These ops execute in parallel for each partition key. Downstream nodes are also fanned-out, respecting any defined partition mappings.

!!! note
    Fan-out is static at translation time. Dynamic partitioning based on runtime information is not supported.

!!! danger "No hooks triggered on asset jobs"
    Backfills or materializations from the Dagster UI do not trigger Kedro hooks. In particular, Kedro-MLflow integration relying on hooks will not function in those cases.

## Map partitions to downstream datasets

If you want to map upstream partition keys to downstream partition keys, use `partition_mappings` on the upstream dataset:

```yaml
my_upstream_dataset:
  type: kedro_dagster.datasets.DagsterPartitionedDataset
  path: data/01_raw/upstream/
  dataset:
    type: pandas.CSVDataset
  partition:
    type: dagster.StaticPartitionsDefinition
    partition_keys: ["1.csv", "2.csv", "3.csv"]
  partition_mappings:
    my_downstream_dataset:
      type: dagster.StaticPartitionMapping
      downstream_partition_keys_by_upstream_partition_key:
        1.csv: 10.csv
        2.csv: 20.csv
        3.csv: 30.csv

my_downstream_dataset:
  type: kedro_dagster.datasets.DagsterPartitionedDataset
  path: data/02_intermediate/downstream/
  dataset:
    type: pandas.CSVDataset
  partition:
    type: dagster.StaticPartitionsDefinition
    partition_keys: ["10.csv", "20.csv", "30.csv"]
```

Pattern targets using `{}` syntax are also supported (e.g., `{namespace}.partitioned_dataset`).

If upstream and downstream partitions share the same keys, use `IdentityPartitionMapping` instead:

```yaml
my_upstream_dataset:
  type: kedro_dagster.datasets.DagsterPartitionedDataset
  path: data/02_raw/upstream/
  dataset:
    type: pickle.PickleDataset
  partition:
    type: dagster.StaticPartitionsDefinition
    partition_keys: ["A.pkl", "B.pkl", "C.pkl"]
  partition_mappings:
    my_downstream_dataset:
      type: dagster.IdentityPartitionMapping
```

!!! note
    `DagsterPartitionedDataset` reduces to Kedro's `PartitionedDataset` when run outside of Dagster, so the pipeline remains runnable with `kedro run`.

See [`DagsterPartitionedDataset`](../api/generated/kedro_dagster.datasets.partitioned_dataset.DagsterPartitionedDataset.md) for all parameters.

## Supported partition types

| Type | Description |
|------|-------------|
| `StaticPartitionsDefinition` | Fixed set of partitions (dates, regions, model variants). [Dagster docs](https://docs.dagster.io/api/dagster/partitions#dagster.StaticPartitionsDefinition) |

| Mapping Type | Description |
|-------------|-------------|
| `StaticPartitionMapping` | Explicit upstream-to-downstream key mapping. [Dagster docs](https://docs.dagster.io/api/dagster/partitions#dagster.StaticPartitionMapping) |
| `IdentityPartitionMapping` | 1:1 mapping where keys match exactly. [Dagster docs](https://docs.dagster.io/api/dagster/partitions#dagster.IdentityPartitionMapping) |

!!! info "Need other Dagster partition types?"
    [Open an issue](https://github.com/stateful-y/kedro-dagster/issues) describing your requirements.

## Enforce execution order with `DagsterNothingDataset`

If you need to enforce that one node completes before another without passing data between them, use `DagsterNothingDataset`:

```yaml
my_nothing_dataset:
  type: kedro_dagster.datasets.DagsterNothingDataset
  metadata:
    description: "Enforces preprocessing completion before collection."
```

These appear as `Nothing` assets in Dagster and only enforce execution dependencies.

See [`DagsterNothingDataset`](../api/generated/kedro_dagster.datasets.nothing_dataset.DagsterNothingDataset.md) for details, and the [Example Project](../tutorials/example-project.md#enforcing-order-with-nothing-assets) for a practical usage.
