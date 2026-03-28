![](assets/logo_dark.png#only-dark){width=800}
![](assets/logo_light.png#only-light){width=800}

# Welcome to Kedro-Dagster's documentation

Kedro-Dagster is a [Kedro](https://kedro.readthedocs.io/) plugin that enables seamless integration between [Kedro](https://kedro.readthedocs.io/), a framework for creating reproducible and maintainable data science code, and [Dagster](https://dagster.io/), a data orchestrator for data (and machine learning) pipelines. This plugin enables the use of Dagster's orchestration capabilities to deploy, automate, and monitor Kedro pipelines effectively.

<div class="grid cards" markdown>

-   **Get Started in 5 Minutes**

    ---

    Install Kedro-Dagster and run your first pipeline in Dagster

    **Install** → **Initialize** → **Run** → **Done**

    [Getting Started](pages/tutorials/getting-started.md)

-   **Need Help?**

    ---

    Find answers to common questions and troubleshooting tips

    [Troubleshooting](pages/how-to/troubleshooting.md)

-   **Learn the Concepts**

    ---

    Understand how Kedro and Dagster work together

    [Key Concepts](pages/explanation/concepts.md) · [Architecture](pages/explanation/architecture.md)

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

## Tutorials

### [Getting Started](pages/tutorials/getting-started.md)

  *Step-by-step guide to installing and setting up Kedro-Dagster in your project.*

### [Example Project](pages/tutorials/example-project.md)

  *A practical example demonstrating how to use Kedro-Dagster with partitions, MLflow, and more.*

## How-to Guides

### [Configure Logging](pages/how-to/configure-logging.md)

  *Set up CLI logging, in-code logging, and custom handlers for Dagster runs.*

### [Integrate MLflow](pages/how-to/integrate-mlflow.md)

  *Use kedro-mlflow tracking and model registry with Dagster orchestration.*

### [Use Partitions](pages/how-to/use-partitions.md)

  *Enable key-based Dagster partitions for parallel processing and backfills.*

### [Troubleshooting](pages/how-to/troubleshooting.md)

  *Diagnose and resolve common issues.*

## Reference

### [API Reference](pages/reference/api.md)

  *Complete API reference for all Kedro-Dagster classes and functions.*

### [Configuration](pages/reference/configuration.md)

  *dagster.yml structure, executors, schedules, and job options.*

## Explanation

### [Key Concepts](pages/explanation/concepts.md)

  *Why Kedro-Dagster exists and its benefits for Kedro and Dagster users.*

### [Architecture](pages/explanation/architecture.md)

  *How Kedro projects are translated into Dagster code locations.*

## License

Kedro-Dagster is open source and licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0).
You are free to use, modify, and distribute this software under the terms of this license.
