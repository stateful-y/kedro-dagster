# How to Configure Logging

Any configuration of Dagster loggers should not be directly attempted as Dagster CLI and API will override them. Therefore, one cannot use Kedro's `logging.yml` configuration file to configure `dagster` loggers. In place, Kedro-Dagster provides ways to integrate Dagster logging into Kedro projects.

## CLI

It is possible to run Dagster CLI commands from within a Kedro project using the `kedro dagster <dg command>` wrapper. This ensures that the Kedro environment is properly set up when running Dagster commands. Those commands accept the `--log-level` and `--log-format` options to configure logging, where `--log-format` supports `colored`, `json`, and `rich`.

!!! note
    The `rich` formatter is not based on the `rich` library like the Kedro logging handler of the same name. It should be understood as a simple formatter with enhanced readability.

To ensure homogeneity in log formatting between Kedro, Kedro-Dagster, Dagster, and any third-party libraries used, Kedro-Dagster provides implementations of the Dagster formatters. They can be used directly in the Kedro's `logging.yml` configuration file as follows:

```yaml

formatters:
  simple:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

  colored:
    "()": kedro_dagster.dagster_colored_formatter

  json:
    "()": kedro_dagster.dagster_json_formatter

  rich:
    "()": kedro_dagster.dagster_rich_formatter

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

## In-code logging

### Overview

Kedro-Dagster integrates Kedro's logging with Dagster's logging system to provide unified log visibility. Logs generated within your Kedro node functions can be captured and displayed in the Dagster UI when you use the `kedro_dagster.logging` module.

**How it works:**

The `kedro_dagster.logging.getLogger` function automatically detects the execution context:

- During Dagster runs: Returns a Dagster logger (logs appear in Dagster UI)
- During Kedro runs: Returns a standard Python logger (logs appear in terminal)

This allows the same node code to work seamlessly in both Kedro and Dagster contexts.

### Using kedro_dagster.logging in node functions

Logs generated within Kedro nodes are captured if `getLogger` is imported from the `kedro_dagster.logging` module instead of the `logging` package and the `getLogger` calls are made inside the node functions. These logs are then displayed in the Dagster UI, allowing for easier tracing and debugging of pipeline executions.

**Example:**

```python

def process_data(data: pd.DataFrame) -> pd.DataFrame:
    from kedro_dagster.logging import getLogger
    logger = getLogger(__name__)
    logger.info(f"Processing {len(data)} rows")

    # Your processing logic
    processed = data.dropna()

    logger.info(f"After processing: {len(processed)} rows")
    return processed
```

!!! tip "Logger Creation"
    Always import `getLogger` and create the logger **inside** the node function, not at module level. This ensures the logger is properly initialized in the Dagster execution context.

### Custom logger configuration

Additionally, to configure logging within Dagster runs, use the Kedro-Dagster `loggers` section of the `dagster.yml` configuration file to define and customize loggers for your Dagster runs:

```yaml
loggers:
  console_logger: # Logger name
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

### Custom handlers, formatters, and filters

You can define custom formatters and filters using either the `()` callable syntax or the `class` key:

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
        class: my_package.formatters.AnotherFormatter
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

See the [Example page](../tutorials/example-project.md#custom-logging-integration) for a complete example of configuring logging in Kedro-Dagster.
