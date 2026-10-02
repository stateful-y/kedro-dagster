# How to Configure Logging

Dagster CLI and API override logger settings, so Kedro's `logging.yml` cannot be used directly for Dagster loggers. Kedro-Dagster provides dedicated integration points to unify logging across both frameworks.

## Unify terminal log formatting

If you want consistent log formatting between Kedro and Dagster on the terminal, use Kedro-Dagster's Dagster formatter classes in your Kedro `logging.yml`:

```yaml
formatters:
  simple:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

  colored:
    class: kedro_dagster.logging.DagsterColoredFormatter

  json:
    class: kedro_dagster.logging.DagsterJsonFormatter

  rich:
    class: kedro_dagster.logging.DagsterRichFormatter

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    stream: ext://sys.stdout
    formatter: colored

loggers:
  kedro:
    level: INFO

  kedro_dagster:
    level: INFO

root:
  handlers: [console]
```

Kedro only imports logging classes from `logging`, `kedro.logging`, and the modules listed in the `KEDRO_LOGGING_MODULE_ALLOWLIST` environment variable, so allow `kedro_dagster` wherever Kedro runs (shell, CI, Docker image):

```bash
export KEDRO_LOGGING_MODULE_ALLOWLIST=kedro_dagster
```

!!! warning
    Since Kedro 1.3, `logging.yml` rejects the `"()"` factory key for security reasons. Configurations that reference `kedro_dagster.dagster_colored_formatter`, `dagster_json_formatter` or `dagster_rich_formatter` through `"()"` fail with `ValueError: The '()' key is not allowed in logging configuration`. Switch them to the `class` key shown above. The factory functions remain available for use from Python.

The three Dagster formatters available are `colored`, `json`, and `rich`. These match the `--log-format` options accepted by `kedro dagster <command>`.

!!! note
    The `rich` formatter is not based on the `rich` library. It is a simple formatter with enhanced readability.

## Show Kedro node logs in the Dagster UI

If you want logs from your Kedro node functions to appear in the Dagster UI, replace `logging.getLogger` with `kedro_dagster.logging.getLogger` inside your node functions:

```python
def process_data(data: pd.DataFrame) -> pd.DataFrame:
    from kedro_dagster.logging import getLogger
    logger = getLogger(__name__)
    logger.info(f"Processing {len(data)} rows")

    processed = data.dropna()

    logger.info(f"After processing: {len(processed)} rows")
    return processed
```

!!! tip
    Always import `getLogger` and create the logger **inside** the node function, not at module level. This ensures the Dagster execution context is available.

The `getLogger` function automatically detects the execution context: it returns a Dagster logger during Dagster runs (logs appear in the UI) and a standard Python logger during Kedro runs (logs appear in the terminal).

## Configure Dagster run loggers

If you want to customize logging within Dagster runs, define loggers in the `loggers` section of `dagster.yml` and assign them to jobs:

```yaml
loggers:
  console_logger:
    log_level: INFO
    handlers:
      - class: logging.StreamHandler
        level: INFO
        stream: ext://sys.stdout
        formatter: simple
    formatters:
      simple:
        format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

jobs:
  my_job:
    pipeline:
      pipeline_name: __default__
    executor: sequential
    loggers: [console_logger]
```

## Use custom handlers, formatters, and filters

If you need advanced logging, define custom formatters and filters using either the `()` callable syntax or the `class` key:

```yaml
loggers:
  advanced_logger:
    log_level: DEBUG
    formatters:
      custom_formatter:
        "()": my_package.formatters.CustomFormatter
        prefix: "CUSTOM"
        format: "%(message)s"
      class_formatter:
        "()": my_package.formatters.AnotherFormatter
        custom_param: "value"
    filters:
      custom_filter:
        "()": my_package.filters.CustomFilter
        keyword: "important"
    handlers:
      - class: logging.StreamHandler
        level: DEBUG
        formatter: custom_formatter
        filters: [custom_filter]
```

See the [Example Project](../tutorials/example-project.md#custom-logging-integration) for a complete logging setup across environments.

## See also

- [Configuration Reference](../reference/configuration.md#loggers): `dagster.yml` logger field tables
- [Troubleshooting](troubleshoot.md#logs-not-appearing-in-dagster-ui): common logging issues
- [Architecture](../explanation/architecture.md): how Kedro logging integrates with Dagster
