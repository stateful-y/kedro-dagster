![](assets/logo_dark.png#only-dark){width=800}
![](assets/logo_light.png#only-light){width=800}

# Welcome to Kedro-Dagster's documentation

Kedro-Dagster is a [Kedro](https://kedro.readthedocs.io/) plugin that enables seamless integration between [Kedro](https://kedro.readthedocs.io/), a framework for creating reproducible and maintainable data science code, and [Dagster](https://dagster.io/), a data orchestrator for data (and machine learning) pipelines. This plugin enables the use of Dagster's orchestration capabilities to deploy, automate, and monitor Kedro pipelines effectively.

<div class="grid cards" markdown>

-   **Get Started in 5 Minutes**

    ---

    Install Kedro-Dagster and run your first pipeline in Dagster

    **Install** -> **Initialize** -> **Run** -> **Done**

    [Getting Started](pages/tutorials/getting-started.md)

-   **Need Help?**

    ---

    Find answers to common questions and troubleshooting tips

    [Troubleshooting](pages/how-to/troubleshoot.md)

-   **Learn the Concepts**

    ---

    Understand how Kedro and Dagster work together

    [Concepts](pages/explanation/concepts.md) - [Architecture](pages/explanation/architecture.md)

-   **See It In Action**

    ---

    Explore a complete example with partitions, MLflow, and more

    [Example Project](pages/tutorials/example-project.md)

</div>

<figure markdown>
![Lineage graph of assets involved in the specified jobs](assets/getting-started/asset_graph_dark.png#only-dark)
![Lineage graph of assets involved in the specified jobs](assets/getting-started/asset_graph_light.png#only-light)
<figcaption>Example of a Dagster Asset Lineage Graph generated from a Kedro project.</figcaption>
</figure>

## Table of Contents

### [Tutorials](pages/tutorials/index.md)

  *Step-by-step guides that walk you through using Kedro-Dagster from scratch.*

- [Getting Started](pages/tutorials/getting-started.md) - Install and deploy your first pipeline
- [Example Project](pages/tutorials/example-project.md) - A complete example with partitions, MLflow, and more
- [Migrate an Existing Project](pages/tutorials/migrate-existing-project.md) - Add Kedro-Dagster to a current Kedro project

### [How-to Guides](pages/how-to/index.md)

  *Practical directions for common tasks.*

- [Configure Logging](pages/how-to/configure-logging.md) - Unify Kedro and Dagster logs
- [Configure Executors](pages/how-to/configure-executors.md) - Set up multiprocess, Docker, or Kubernetes executors
- [Use Partitions](pages/how-to/use-partitions.md) - Work with partitioned datasets
- [Use MLflow](pages/how-to/use-mlflow.md) - Integrate experiment tracking
- [Deploy to Production](pages/how-to/deploy-to-production.md) - Production deployment patterns
- [Troubleshooting](pages/how-to/troubleshoot.md) - Common issues and solutions

### [Explanation](pages/explanation/index.md)

  *Background and context on Kedro-Dagster's design and behavior.*

- [Concepts](pages/explanation/concepts.md) - Asset-first alignment, key features, and limitations
- [Architecture](pages/explanation/architecture.md) - How Kedro projects are translated into Dagster code locations
- [Data Flow](pages/explanation/data-flow.md) - How data moves through the system
- [Hook Lifecycle](pages/explanation/hook-lifecycle.md) - Kedro hooks interaction with Dagster

### [Reference](pages/reference/index.md)

  *Technical descriptions of every configurable option, CLI command, and public API.*

- [Configuration Reference](pages/reference/configuration.md) - `dagster.yml` field tables
- [CLI Reference](pages/reference/cli.md) - All `kedro dagster` commands
- [API Reference](pages/reference/api.md) - Auto-generated class and function docs
- [Datasets](pages/reference/datasets.md) - Custom dataset types

## License

Kedro-Dagster is open source and licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0).
You are free to use, modify, and distribute this software under the terms of this license.
