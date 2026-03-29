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

Refer to the [Dagster documentation](https://docs.dagster.io) and the [Dagster Deployment Options](https://docs.dagster.io/deployment) to evaluate whether Dagster fits your needs.

### For Dagster users

- **Structured projects and configurations:** Kedro enforces a modular project structure with environment-specific configuration files and a clear separation between code, data, and settings.
- **Straightforward asset and workflow creation:** Define pipelines as sequences of modular, reusable nodes. They are automatically translated into Dagster assets, ready to visualize and orchestrate in Dagster's UI.
- **Built-in data connectors:** Kedro's `DataCatalog` provides a centralized and declarative way to manage all data inputs and outputs, supporting local files, cloud storage (S3, GCS), databases, and more.
- **Full control over Kedro-based Dagster objects:** Any aspect of the generated Dagster assets, jobs, executors, or resources can be modified in the Dagster UI Launchpad without touching Kedro code.

## Key features

### Configuration-driven workflows

Centralize orchestration settings in a `dagster.yml` file per Kedro environment:

- Define jobs from filtered Kedro pipelines.
- Assign executors, retries, and resource limits.
- Assign cron-based schedules.

### Customization

The core integration lives in the auto-generated Dagster `definitions.py`. For specialized requirements such as custom resources, deployment patterns, or non-standard executors, you can extend or override parts of these definitions manually.

### Kedro hooks preservation

Kedro hooks are preserved and called at the appropriate time during pipeline execution. Custom logic such as data validation or logging implemented as Kedro hooks continues to work when running pipelines via Dagster.

### MLflow compatibility

Use [Kedro-MLflow](https://github.com/Galileo-Galilei/kedro-mlflow) alongside Dagster's [MLflow integration](https://dagster.io/integrations/dagster-mlflow). Whether you run pipelines with Kedro or Dagster, experiments, models, and artifacts are tracked automatically through the `mlflow.yml` configuration file.

### Logger integration

Kedro and Dagster logging is unified so logs from Kedro nodes appear together in the Dagster UI and are easy to configure. See the [logging guide](../how-to/configure-logging.md) for details.

### (Experimental) Dagster partitions support

Enable key-based [Dagster partitions](https://docs.dagster.io/guides/build/partitions-and-backfills) to backfill, schedule, and process incremental slices of your pipelines. Currently supports `StaticPartitionsDefinition` with `StaticPartitionMapping` or `IdentityPartitionMapping`. See the [partitions guide](../how-to/use-partitions.md) for details.

## Limitations and considerations

1. **Evolving feature parity:**
   Not all Dagster features are yet exposed. We encourage you to contribute or raise issues on the [Issue Tracker](https://github.com/stateful-y/kedro-dagster/issues) so missing features can be prioritized.

2. **Compatibility:**
   Both Kedro and Dagster are under active development. Breaking changes in either framework can temporarily affect the integration until a new plugin release addresses them. Always pin your Kedro, Dagster, and Kedro-Dagster versions and test before upgrading.

## Contributing and community

We welcome contributions, feedback, and questions:

- **Report issues or request features:** [GitHub Issues](https://github.com/stateful-y/kedro-dagster/issues)
- **Join the discussion:** [Kedro Slack](https://slack.kedro.org/)
- **Contributing guide:** [CONTRIBUTING.md](https://github.com/stateful-y/kedro-dagster/blob/main/CONTRIBUTING.md)

If you are interested in becoming a maintainer or taking a more active role, reach out to Guillaume Tauzin on the [Kedro Slack](https://slack.kedro.org/).

---

## Next steps

- **Getting started:** Follow the step-by-step [Getting Started](../tutorials/getting-started.md) tutorial.
- **Advanced example:** Browse the [Example Project](../tutorials/example-project.md) for a real-life data science deployment with Dagster.
