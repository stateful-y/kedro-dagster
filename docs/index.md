![](assets/logo_dark.png#only-dark){width=800}
![](assets/logo_light.png#only-light){width=800}

# Welcome to Kedro-Dagster's documentation

Kedro-Dagster is a [Kedro](https://kedro.readthedocs.io/) plugin that enables seamless integration between [Kedro](https://kedro.readthedocs.io/), a framework for creating reproducible and maintainable data science code, and [Dagster](https://dagster.io/), a data orchestrator for data (and machine learning) pipelines. This plugin enables the use of Dagster's orchestration capabilities to deploy, automate, and monitor Kedro pipelines effectively.

<div class="grid cards" markdown>

-   **Get Started in 5 Minutes**

    ---

    Install Kedro-Dagster and run your first pipeline in Dagster

    **Install** → **Initialize** → **Run** → **Done**

    [Getting Started](pages/getting-started.md)

-   **Need Help?**

    ---

    Find answers to common questions and troubleshooting tips

    [FAQ & Troubleshooting](pages/faq.md)

-   **Learn the Concepts**

    ---

    Understand how Kedro and Dagster work together

    [Introduction](pages/intro.md) · [User guide](pages/user-guide.md)

-   **See It In Action**

    ---

    Explore a complete example with partitions, MLflow, and more

    [Example Project](pages/example.md)

</div>

<figure markdown>
![Lineage graph of assets involved in the specified jobs](assets/getting-started/asset_graph_dark.png#only-dark)
![Lineage graph of assets involved in the specified jobs](assets/getting-started/asset_graph_light.png#only-light)
<figcaption>Example of a Dagster Asset Lineage Graph generated from a Kedro project.</figcaption>
</figure>

## Table of Contents

### [Introduction](pages/intro.md)

  *Overview of Kedro-Dagster, its purpose, and key concepts.*

- [What Is Kedro?](pages/intro.md#what-is-kedro)
- [What Is Dagster?](pages/intro.md#what-is-dagster)
- [Why Kedro-Dagster?](pages/intro.md#why-kedrodagster)
- [Key features](pages/intro.md#key-features)
- [Limitations & considerations](pages/intro.md#limitations-and-considerations)
- [Contributing & community](pages/intro.md#contributing-and-community)

### [Getting started](pages/getting-started.md)

  *Step-by-step guide to installing and setting up Kedro-Dagster in your project.*

- [1. Create a Kedro project (Optional)](pages/getting-started.md#1-create-a-kedro-project-optional)
- [2. Installation](pages/getting-started.md#2-installation)
- [3. Initialize the Kedro-Dagster plugin](pages/getting-started.md#3-initialize-the-kedro-dagster-plugin)
- [4. Configure jobs, loggers, executors, and schedules](pages/getting-started.md#4-configure-jobs-loggers-executors-and-schedules)
- [5. Browse the Dagster UI](pages/getting-started.md#5-browse-the-dagster-ui)

### [Example](pages/example.md)

  *A practical example demonstrating how to use Kedro-Dagster in a real project.*

- [Project overview](pages/example.md#project-overview)
- [Quick start](pages/example.md#quick-start)
- [User guide](pages/user-guide.md#user-guide)

### [User guide](pages/user-guide.md)

  *In-depth documentation on the design, architecture, and core concepts of the plugin.*

- [Project configuration](pages/user-guide.md#project-configuration)
- [Kedro-Dagster concept mapping](pages/user-guide.md#kedro-dagster-concept-mapping)
- [Compatibility notes between Kedro and Dagster](pages/user-guide.md#compatibility-notes-between-kedro-and-dagster)

### [Reference](pages/api-reference.md)

  *Complete API reference for all Kedro-Dagster classes and functions with searchable index.*

## License

Kedro-Dagster is open source and licensed under the [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0).
You are free to use, modify, and distribute this software under the terms of this license.
