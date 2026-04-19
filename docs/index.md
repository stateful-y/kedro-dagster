![](assets/logo_dark.png#only-dark){width=800}
![](assets/logo_light.png#only-light){width=800}

# Welcome to Kedro-Dagster's documentation

Kedro-Dagster is an integration plugin that lets you deploy
[Kedro](https://docs.kedro.org/) data pipelines on
[Dagster](https://docs.dagster.io/) without modifying your existing project
code. It translates your catalog, nodes, and pipelines into Dagster assets,
ops, and jobs so you can schedule, monitor, and inspect runs through
Dagster's UI and execution backends.

<div class="grid cards" markdown>

- **Get Started in 5 Minutes**

    ---

    Install Kedro-Dagster and run your first pipeline in Dagster.

    [Getting Started](pages/tutorials/getting-started.md)

- **How-to Guides**

    ---

    Step-by-step instructions.

    [How-to Guides](pages/how-to/index.md)

- **Understand the Design**

    ---

    Learn how Kedro-Dagster maps catalogs, nodes, and pipelines to Dagster assets, ops, and jobs.

    [Concepts](pages/explanation/concepts.md)

- **See It In Action**

    ---

    Explore a complete example with partitions, MLflow, and more.

    [Example Project](pages/tutorials/example-project.md)

- **Reference**

    ---

    Complete field tables for `dagster.yml`, all CLI flags, and the Python API.

    [Configuration Reference](pages/reference/configuration.md) | [CLI Reference](pages/reference/cli.md) | [API Reference](pages/reference/api.md)

- **Need Help?**

    ---

    Find answers to common questions and troubleshooting tips.

    [Troubleshooting](pages/how-to/troubleshoot.md)

</div>

## Key capabilities

- **No code changes**: integrate Dagster without touching your Kedro datasets, catalog, or pipelines.
- **Full orchestration**: schedule, monitor, and inspect Kedro pipelines through Dagster's UI, asset lineage tracking, and cloud-native executors.
- **Configuration-driven**: define jobs, executors, schedules, and loggers in a `dagster.yml` per environment.
- **Ecosystem compatibility**: works with Kedro hooks, Kedro-MLflow, and all Dagster-supported execution backends (multiprocess, Docker, Kubernetes, Dask, Celery).

<figure markdown>
![Lineage graph of assets involved in the specified jobs](assets/getting-started/asset_graph_dark.png#only-dark)
![Lineage graph of assets involved in the specified jobs](assets/getting-started/asset_graph_light.png#only-light)
<figcaption>Example of a Dagster Asset Lineage Graph generated from a Kedro project.</figcaption>
</figure>

## License

This project is licensed under the terms of the [Apache-2.0 License](https://github.com/stateful-y/kedro-dagster/blob/main/LICENSE).

## Acknowledgements

This project is maintained by [stateful-y](https://stateful-y.io), an ML consultancy specializing in MLOps and data science & engineering. If you're interested in collaborating or learning more about our services, please visit our website.

![Made by stateful-y](assets/made_by_stateful-y.png){width=200}
