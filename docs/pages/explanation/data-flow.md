# Data Flow

How data flows between Kedro nodes when executed through Dagster.

## Catalog Resolution

When a Kedro project runs under Dagster, the Kedro catalog is resolved at the
start of each pipeline run. Each catalog entry maps to a Dagster asset or
in-memory intermediate result, depending on whether the dataset is persisted
or transient.

Kedro-Dagster translates catalog entries into Dagster IO managers that handle
loading and saving. Persisted datasets (e.g., `CSVDataset`, `ParquetDataset`)
are backed by Dagster assets, while transient datasets are passed in-memory
between ops within the same graph.

## IO Manager Integration

For each persisted dataset, Kedro-Dagster creates a Dagster IO manager that
delegates `load` and `save` calls to the underlying Kedro dataset
implementation. This keeps the Kedro dataset API intact while gaining Dagster's
asset lineage tracking and materialization history.

## Parameter Handling

Kedro parameters (`params:` and `parameters`) are injected as Dagster
resources. They are resolved once per run from the Kedro configuration loader
and made available to every op in the pipeline graph.

Changes to parameters between runs are tracked through Dagster's configuration
system, ensuring reproducibility and auditability.

## Nothing Assets

Some Kedro nodes produce side effects without returning data (e.g., sending
emails, triggering external processes). Kedro-Dagster represents these
outputs using `DagsterNothingDataset`, which returns a sentinel value and
maps to Dagster's `Nothing` type.

Nothing assets enforce execution order without carrying data. Downstream
nodes that depend on a nothing output will wait for the producing node to
complete, but receive no actual data.

## Partitioned Datasets

`DagsterPartitionedDataset` bridges Kedro's partitioned dataset concept with
Dagster's partitions framework. Each partition key maps to a separate
materialization, enabling:

- Time-based partitioning (daily, weekly, monthly)
- Static partitioning (by region, category)
- Dynamic partitioning (keys determined at runtime)

!!! warning "Experimental"

    Static partitioning is supported experimentally in Kedro-Dagster.
    Other partitioning mappings are not supported. The API and behavior
    may change in future releases.

Partition mappings define how upstream and downstream partitioned assets
relate to each other. Kedro-Dagster supports identity mappings (one-to-one),
all-partitions mappings (fan-in), and custom mappings.

When a partitioned asset is materialized, Kedro-Dagster resolves the
partition key, constructs the appropriate file path, and delegates to the
underlying Kedro dataset for the actual read/write operation.

## See also

- [Architecture](architecture.md): how the full Kedro-to-Dagster translation works
- [How to Use Dagster Partitions](../how-to/use-partitions.md): practical guide to partitioned datasets
- [Datasets Reference](../reference/datasets.md): `DagsterPartitionedDataset` and `DagsterNothingDataset` API details
