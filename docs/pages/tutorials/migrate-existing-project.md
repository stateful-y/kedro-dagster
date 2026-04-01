# How to Migrate an Existing Kedro Project

This guide shows you how to add Dagster orchestration to an existing Kedro project. Use this when you already have a working Kedro project with custom datasets, hooks, or configuration and want to run it through Dagster.

## Prerequisites

- An existing Kedro project (0.19.x or 1.x)
- The project runs successfully with `kedro run`

## 1. Install Kedro-Dagster

Add the package to your project dependencies:

=== "pip"

    ```bash
    pip install kedro-dagster
    ```

=== "uv"

    ```bash
    uv add kedro-dagster
    ```

Verify the CLI is available:

```bash
kedro dagster --help
```

## 2. Initialize Dagster integration files

From your project root:

```bash
kedro dagster init
```

This creates three files:

| File | Purpose |
|------|---------|
| `conf/base/dagster.yml` | Orchestration configuration (jobs, executors, schedules) |
| `src/<package>/definitions.py` | Dagster entry point that loads your project |
| `dg.toml` | Dagster `dg` CLI configuration (Dagster >= 1.10.6) |

If any of these files already exist (from a previous attempt), use `--force` to overwrite:

```bash
kedro dagster init --force
```

## 3. Check catalog compatibility

Most Kedro datasets work without changes. The translator wraps each dataset's `save()` and `load()` methods into Dagster IO managers automatically.

**Datasets that need attention:**

- **MemoryDataset**: works, but the data lives only within the Dagster run. Cross-job data sharing is not supported.
- **Custom datasets with side effects**: if your dataset's `save()` or `load()` method interacts with external services (APIs, message queues), verify it behaves correctly when called from within a Dagster op.
- **Datasets with credentials**: credentials from `conf/<env>/credentials.yml` are loaded normally. Ensure the Dagster environment has access to the same credential files or environment variables.

## 4. Verify hooks work

Kedro hooks are preserved across the translation. If your project uses custom hooks, they will fire at the same lifecycle points in Dagster.

Test by starting the dev server and running a job:

```bash
kedro dagster dev
```

In the Dagster UI, launch a job and check the logs for your hook output.

!!! warning
    Backfills and asset materializations triggered directly from the Dagster UI do not invoke Kedro pipeline-level hooks (`before_pipeline_run`, `after_pipeline_run`). Node-level and dataset-level hooks still fire.

## 5. Configure jobs

Edit `conf/base/dagster.yml` to define which pipelines become Dagster jobs:

```yaml
jobs:
  full_pipeline:
    pipeline: __default__

  training_only:
    pipeline: data_science
    tags: [train]
```

If you have multiple Kedro pipelines registered in `pipeline_registry.py`, each can become a separate Dagster job with its own executor and schedule.

## 6. Verify the translation

List all generated Dagster definitions to confirm everything translated correctly:

```bash
kedro dagster list-defs
```

Start the UI and inspect:

```bash
kedro dagster dev
```

Check that:

- All expected assets appear in the asset graph
- Jobs contain the correct nodes
- Parameters are visible in the job launchpad

## Common migration issues

**Problem: `ModuleNotFoundError` when starting Dagster**
:   Your project's source package is not installed. Run `pip install -e .` or `uv sync` from the project root.

**Problem: Assets are missing from the graph**
:   Datasets defined only in `parameters.yml` or prefixed with `params:` are passed as config, not assets. This is expected behavior.

**Problem: Node names contain invalid characters**
:   Dagster requires `^[A-Za-z0-9_]+$` for names. The translator converts dots to double underscores automatically. If names still fail, check for other special characters in your node names.

**Problem: Hook order differs from `kedro run`**
:   Hooks fire at equivalent lifecycle points, but the exact timing may differ slightly because Dagster executes ops independently. Avoid hooks that depend on execution order between unrelated nodes.

## See also

- [Getting Started](../tutorials/getting-started.md): tutorial for new projects
- [Architecture](../explanation/architecture.md): how the translation maps Kedro concepts to Dagster
- [Configuration Reference](../reference/configuration.md): all `dagster.yml` options
- [Troubleshooting](../how-to/troubleshoot.md): more common issues and solutions
