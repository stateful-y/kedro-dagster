# How to Use Job Factories

This guide shows you how to replace repeated, near-identical job definitions with a single **job factory** that expands into one Dagster job per Kedro pipeline namespace. Use this when you run the same pipeline across several namespaces (products, regions, model variants) and your `jobs:` block is mostly copy-paste.

Job factories are the job-level analogue of [Kedro dataset factories](https://docs.kedro.org/en/stable/catalog-data/kedro_dataset_factories/): one templated entry stands in for many concrete ones.

## Prerequisites

- A working Kedro-Dagster project ([Getting Started](../tutorials/getting-started.md))
- One or more pipelines whose nodes carry [namespaces](https://docs.kedro.org/en/stable/build/namespace_pipelines/) (e.g. `reviews_predictor.train_model`)

## How job factories work

A `jobs:` key that contains `{placeholder}` markers is a **factory**. Its concrete jobs are derived from the node namespaces of the pipeline it targets. The first `node_namespaces` entry is the *binding axis*: each `{placeholder}` binds to the matching part of a node's namespace, and the pipeline's distinct namespaces (at that depth) each produce one job.

```yaml
jobs:
  "{product}__data_processing":
    pipeline:
      pipeline_name: data_processing
      node_namespaces: ["{product}"]   # binding axis: {product} = each namespace
```

Rendered job names must be valid Dagster names (`[A-Za-z0-9_]`), so placeholder-derived parts use single `_` and the fixed job-type tail is separated by `__`.

## Convert repeated jobs into a factory

Suppose you run the same two pipelines for two products. Written out by hand, that is four jobs:

```yaml
jobs:
  reviews_predictor_data_processing:
    pipeline: { pipeline_name: data_processing, node_namespaces: [reviews_predictor] }
    executor: multiprocessing
  price_predictor_data_processing:
    pipeline: { pipeline_name: data_processing, node_namespaces: [price_predictor] }
    executor: multiprocessing
  reviews_predictor_data_science:
    pipeline: { pipeline_name: data_science, node_namespaces: [reviews_predictor] }
    executor: sequential
  price_predictor_data_science:
    pipeline: { pipeline_name: data_science, node_namespaces: [price_predictor] }
    executor: sequential
```

Because the product is the only thing that varies, collapse each pipeline into one factory:

```yaml
jobs:
  "{product}__data_processing":
    pipeline:
      pipeline_name: data_processing
      node_namespaces: ["{product}"]
    executor: multiprocessing
  "{product}__data_science":
    pipeline:
      pipeline_name: data_science
      node_namespaces: ["{product}"]
    executor: sequential
```

`{product}` binds to `reviews_predictor` and `price_predictor`, so these two keys render the same four jobs — `reviews_predictor__data_processing`, `price_predictor__data_processing`, and the `data_science` pair.

## Bind deeper namespaces

The binding axis is split on `.`, so a template can bind several placeholders across a nested namespace. A pipeline with nodes in `alpha.hub.champion`, `beta.hub.challenger`, … can be captured with:

```yaml
jobs:
  "{product}__{group}__{variant}__inference":
    pipeline:
      pipeline_name: inference
      node_namespaces: ["{product}.{group}.{variant}"]
```

A literal segment in the axis restricts which namespaces match — `node_namespaces: ["beta.{group}.{variant}"]` only binds namespaces beginning with `beta`.

## Interpolate the whole job body

Placeholders are substituted into **every** string in the job body, not just the key. This lets a factory select a per-namespace executor:

```yaml
executors:
  reviews_predictor_executor:
    multiprocess: { max_concurrent: 2 }
  price_predictor_executor:
    in_process:

jobs:
  "{product}__data_processing":
    pipeline:
      pipeline_name: data_processing
      node_namespaces: ["{product}"]
    executor: "{product}_executor"   # renders to reviews_predictor_executor / price_predictor_executor
```

The same works for `schedule` and `loggers` references.

## Preview the expansion

Check what a factory renders **without** starting Dagster:

```bash
# List the factory keys ({placeholder} entries) in dagster.yml
kedro dagster list-patterns -e <env>

# Print the concrete jobs the factories render, with pipeline, namespaces, and schedule
kedro dagster resolve-patterns -e <env>
```

These mirror `kedro catalog list-patterns` / `resolve-patterns` and are the fastest way to confirm bindings while authoring a factory.

## Mix factories with literal jobs

Factory and literal (non-templated) jobs coexist. A literal job with the same rendered name **wins**, so you can override a single case while a factory handles the rest:

```yaml
jobs:
  "{product}__data_science":
    pipeline: { pipeline_name: data_science, node_namespaces: ["{product}"] }
    executor: sequential
  price_predictor__data_science:   # literal override for one product
    pipeline: { pipeline_name: data_science, node_namespaces: [price_predictor] }
    executor: multiprocessing
```

!!! note "A factory only renders namespaces that exist"
    Jobs are derived from the **pipeline's** namespaces in the active environment. If a namespace is absent (or lacks the `tags` your factory filters on), no job is rendered for it — keep single-namespace or specially-filtered cases as literal jobs.

## See also

- [Configuration Reference — Job factories](../reference/configuration.md#job-factories): field-level detail and precedence rules
- [CLI Reference](../reference/cli.md#kedro-dagster-resolve-patterns): `resolve-patterns` / `list-patterns`
- [Example Project](../tutorials/example-project.md): job factories in the `staging` and `prod` environments
- [`PipelineOptions`](../api/generated/kedro_dagster.config.models.PipelineOptions.md): all pipeline filter parameters
