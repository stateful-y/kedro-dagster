# Explanation

Background and context to deepen your understanding of Kedro-Dagster's design and behavior.

- **[Concepts](concepts.md)**: The asset-first alignment between Kedro and Dagster, key features, and what the integration provides for each framework's users.
- **[Architecture](architecture.md)**: How Kedro projects are translated into Dagster code locations: catalog, node, pipeline, and hook mapping.
- **[Data Flow](data-flow.md)**: How the catalog resolves at run time, and how IO managers move data between nodes as Dagster assets or in-memory results.
- **[Hook Lifecycle](hook-lifecycle.md)**: Which Kedro hooks fire under Dagster, when each one runs, and how they survive the execution boundary.
