![](assets/logo_dark.png#only-dark){width=800}
![](assets/logo_light.png#only-light){width=800}

# Welcome to Kedro-Dagster's documentation

Kedro-Dagster makes it easy to deploy Kedro projects to Dagster.

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

    Understand the design and core ideas behind Kedro-Dagster.

    [Concepts](pages/explanation/concepts.md)

- **See It In Action**

    ---

    Explore a complete example with partitions, MLflow, and more.

    [Example Project](pages/tutorials/example-project.md)

- **Reference**

    ---

    Complete field tables for `dagster.yml` and all CLI flags.

    [Configuration Reference](pages/reference/configuration.md) | [CLI Reference](pages/reference/cli.md)

- **Need Help?**

    ---

    Find answers to common questions and troubleshooting tips.

    [Troubleshooting](pages/how-to/troubleshoot.md)

</div>

## Key capabilities

- **No code changes** - integrate Dagster without touching your Kedro datasets, catalog, or pipelines.
- **Full orchestration** - schedule, monitor, and inspect Kedro pipelines through Dagster's UI, asset lineage tracking, and cloud-native executors.
- **Configuration-driven** - define jobs, executors, schedules, and loggers in a `dagster.yml` per environment.
- **Ecosystem compatibility** - works with Kedro hooks, Kedro-MLflow, and all Dagster-supported execution backends (multiprocess, Docker, Kubernetes, Dask, Celery).

<figure markdown>
![Lineage graph of assets involved in the specified jobs](assets/getting-started/asset_graph_dark.png#only-dark)
![Lineage graph of assets involved in the specified jobs](assets/getting-started/asset_graph_light.png#only-light)
<figcaption>Example of a Dagster Asset Lineage Graph generated from a Kedro project.</figcaption>
</figure>

## License

Kedro-Dagster is open source and licensed under the [Apache-2.0 License](https://opensource.org/licenses/Apache-2.0).
