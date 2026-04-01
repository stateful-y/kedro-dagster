# Concepts

Kedro-Dagster connects [Kedro](https://kedro.readthedocs.io/) data science projects to [Dagster's](https://docs.dagster.io/) orchestration engine. With minimal setup, you can run, schedule, and monitor Kedro pipelines in Dagster, taking advantage of its UI, asset lineage tracking, and cloud-native executors, without altering your existing codebase.

## The asset-first alignment

Kedro and Dagster share an asset-first philosophy. In Kedro, assets are datasets passed between nodes that make up a pipeline. Dagster mirrors this by treating the output of each computation as an asset with associated execution semantics and lineage. This alignment allows Kedro pipelines to be translated into Dagster assets with minimal effort, preserving structure and enabling rich observability out of the box.

Kedro-Dagster leverages the complementarity of both frameworks. Kedro provides a robust developer experience for building pipelines: modular, testable, and backed by strong configuration and data cataloging. Dagster brings a powerful orchestration layer with scheduling, logging, asset monitoring, and execution control. Whether you start from Kedro or Dagster, each tool plays to its strengths.

### For Kedro users

- **No code changes:** Integrate Dagster without modifying your existing Kedro datasets, config, or pipelines.
- **Enhanced orchestration and observability:** Visualize, launch, and schedule runs, inspect logs, trace asset lineage, and monitor pipeline health through Dagster's UI.
- **Automatic node parallelization across partitions:** Fan out Kedro node execution across partition keys with minimal configuration.
- **Variety of execution targets:** Run locally for development, in Docker, on a remote machine, or scale on Kubernetes and other Dagster-supported executors, selectable per job via configuration.

See the [Dagster documentation](https://docs.dagster.io) and the [Dagster Deployment Options](https://docs.dagster.io/deployment) to evaluate whether Dagster fits your needs.

### For Dagster users

- **Structured projects and configurations:** Kedro enforces a modular project structure with environment-specific configuration files (`base`, `local`, `staging`, `prod`) and a clear separation between code, data, and settings. This makes it straightforward to manage different deployment targets from the same codebase.
- **Straightforward asset and workflow creation:** Define pipelines as sequences of modular, reusable nodes. They are automatically translated into Dagster assets, ready to visualize and orchestrate in Dagster's UI.
- **Built-in data connectors:** Kedro's `DataCatalog` provides a centralized and declarative way to manage all data inputs and outputs, supporting local files, cloud storage (S3, GCS), databases, and more. Each connector handles serialization, versioning, and credentials out of the box.
- **Testable pipelines:** Kedro nodes are plain Python functions with explicit inputs and outputs. They can be unit-tested in isolation without any orchestration framework, then deployed to Dagster unchanged.
- **Full control over Kedro-based Dagster objects:** Any aspect of the generated Dagster assets, jobs, executors, or resources can be modified in the Dagster UI Launchpad without touching Kedro code.

See the [Kedro documentation](https://docs.kedro.org/) and the [Kedro starters](https://docs.kedro.org/en/stable/starters/starters.html) to evaluate whether Kedro fits your project structure needs.

## Key features

### Configuration-driven workflows

Orchestration settings live in a `dagster.yml` file per Kedro environment rather than being scattered across Python code. This keeps infrastructure concerns (which executor to use, what schedule to run) separate from pipeline logic, and makes it possible to change deployment behavior without modifying a single line of Python. See the [configuration reference](../reference/configuration.md) for all available fields.

### Customization

The translation produces a standard Dagster `definitions.py` that serves as the project entry point. Because it is regular Python, you can extend or override any part of the generated definitions for specialized requirements such as custom resources or deployment patterns.

### Kedro hooks preservation

Kedro hooks are preserved across the translation boundary. Custom logic such as data validation, logging, or experiment tracking implemented as Kedro hooks continues to fire at the correct point in the Dagster execution lifecycle. This is what makes integrations like Kedro-MLflow work automatically in Dagster without additional code.

### MLflow compatibility

Kedro-MLflow hooks and Dagster's MLflow resource coexist. Experiments, models, and artifacts tracked through `mlflow.yml` continue to work regardless of whether the pipeline runs via `kedro run` or Dagster. See the [MLflow integration guide](../how-to/use-mlflow.md).

### Logger integration

Kedro and Dagster logging is unified so logs from Kedro nodes appear together in the Dagster UI. The integration provides drop-in formatters and a `getLogger` function that routes to the correct backend depending on the execution context. See the [logging guide](../how-to/configure-logging.md).

### (Experimental) Dagster partitions support

Dagster partitions enable backfilling, scheduling, and processing incremental slices of data. Kedro-Dagster maps partitioned datasets to Dagster partition definitions, fanning out node execution across partition keys. This feature currently supports `StaticPartitionsDefinition`. See the [partitions guide](../how-to/use-partitions.md).

## Limitations and considerations

1. **Evolving feature parity:**
   Not all Dagster features are yet exposed. We encourage you to contribute or raise issues on the [Issue Tracker](https://github.com/stateful-y/kedro-dagster/issues) so missing features can be prioritized.

2. **Compatibility:**
   Both Kedro and Dagster are under active development. Breaking changes in either framework can temporarily affect the integration until a new plugin release addresses them. Always pin your Kedro, Dagster, and Kedro-Dagster versions and test before upgrading.

## See also

- [Architecture](architecture.md): how the translation from Kedro to Dagster works internally
- [Getting Started](../tutorials/getting-started.md): hands-on tutorial to set up your first project
- [Contributing](../how-to/contribute.md): development setup and project standards
