# Hook Lifecycle

How Kedro hooks are preserved across the Dagster execution boundary.

## Overview

Kedro's hook system provides extension points at key moments in a pipeline
run: before and after context creation, catalog creation, pipeline execution,
and individual node execution. Kedro-Dagster preserves this hook system by
translating hook invocations into Dagster ops and sensors.

## Which Hooks Fire

Kedro-Dagster supports the following hook specifications:

- `after_context_created` - fires once per pipeline run, before any nodes execute
- `after_catalog_created` - fires after the Kedro catalog is built
- `before_pipeline_run` - fires before the pipeline graph begins executing
- `after_pipeline_run` - fires after all nodes in the pipeline have completed
- `on_pipeline_error` - fires when a pipeline run fails
- `before_node_run` - fires before each individual node executes
- `after_node_run` - fires after each individual node completes
- `on_node_error` - fires when an individual node raises an exception

## When Hooks Fire in the Dagster Lifecycle

### Pipeline-Level Hooks

Pipeline-level hooks (`before_pipeline_run`, `after_pipeline_run`,
`on_pipeline_error`) are mapped to dedicated Dagster constructs:

- `before_pipeline_run` is implemented as an op at the start of the pipeline
  graph. All node ops depend on its output (a `Nothing` value) to ensure
  it runs first.
- `after_pipeline_run` is implemented as an op at the end of the pipeline
  graph. It depends on all terminal node outputs to ensure it runs last.
- `on_pipeline_error` is implemented as a Dagster run failure sensor. It
  triggers when the Dagster run enters a failed state and invokes the
  registered Kedro error hooks.

### Node-Level Hooks

Node-level hooks (`before_node_run`, `after_node_run`, `on_node_error`) are
invoked directly within each node's op execution:

- `before_node_run` fires at the start of each op, before the Kedro node
  function is called.
- `after_node_run` fires after the node function returns successfully.
- `on_node_error` fires when the node function raises an exception, before
  the error propagates to Dagster.

## MLflow Hook Integration

When `kedro-mlflow` is installed, its hooks (`MlflowHook`) integrate
seamlessly with Kedro-Dagster. The MLflow tracking context is established
during `before_pipeline_run` and properly closed during `after_pipeline_run`
or `on_pipeline_error`.

Each node run is tracked as a nested MLflow run, preserving the experiment
structure that would exist in a native Kedro execution.

## Custom Hook Considerations

Custom hooks registered in `settings.py` are automatically picked up by
Kedro-Dagster. The hook manager is initialized from the project settings
and used throughout the Dagster execution.

When writing custom hooks for a Kedro-Dagster project:

- Avoid hooks that depend on `KedroSession` internals, as the session
  lifecycle differs under Dagster.
- Pipeline-level hooks should be stateless or store state in the catalog
  rather than in-memory, since `before_pipeline_run` and `after_pipeline_run`
  may execute in different processes depending on the executor.
- Node-level hooks execute within the same process as the node op, so
  in-memory state sharing between `before_node_run` and `after_node_run`
  works as expected.
