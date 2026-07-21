# Troubleshooting

This guide helps you diagnose and resolve common issues when using Kedro-Dagster.

## Common issues

### Logs not appearing in Dagster UI

Make sure you use `kedro_dagster.logging.getLogger` **inside your node functions**:

```python
def process_data(data):
    from kedro_dagster.logging import getLogger
    logger = getLogger(__name__)

    logger.info("This will appear in Dagster UI")
    return processed_data
```

Module-level loggers do not capture the Dagster context. See the [logging guide](configure-logging.md) for details.

### Asset names differ from Kedro names

Kedro-Dagster converts dots (`.`) to double underscores (`__`) in asset names to comply with Dagster's naming requirements:

- **Kedro**: `namespace.my_dataset`
- **Dagster**: `local__namespace__my_dataset`

This is automatic and reversible. See [naming conventions](../explanation/architecture.md#naming-conventions) for details.

### Job failed with `NotImplementedError`

You are likely using an unsupported partition type:

- **Supported**: `StaticPartitionsDefinition`, `StaticPartitionMapping`, `IdentityPartitionMapping`
- **Not supported**: `TimeWindowPartitionsDefinition`, `DynamicPartitionsDefinition`, `MultiPartitionsDefinition`

Use `StaticPartitionsDefinition` with explicit partition keys, or use Dagster schedules for time-based execution. See the [partitions guide](use-partitions.md).

### UI not reflecting configuration changes

1. Stop the Dagster development server.
2. Restart with `kedro dagster dev --env <ENV>`.
3. Hard-refresh your browser (Ctrl+Shift+R or Cmd+Shift+R).

Some configuration changes require a full server restart and are not hot-reloaded.

### `InterpolationKeyError` when loading `dagster.yml`

```text
InterpolationKeyError: Interpolation key 'WAREHOUSE_USER' not found
    full_key: executors.pipeline_docker.docker_executor.container_kwargs.environment[0]
```

Or, with the `oc.env` prefix:

```text
UnsupportedInterpolationType: Unsupported interpolation type oc.env
```

Environment variables are **not** interpolated in `dagster.yml`. Kedro's `OmegaConfigLoader` clears the `oc.env` resolver and re-enables it only for the `credentials` config key, so `${MY_VAR}` and `${oc.env:MY_VAR}` both raise there.

Move the variable reference into `credentials.yml`, and forward the variable into containers with bare names under `env_vars`:

```yaml
executors:
  pipeline_docker:
    docker_executor:
      image: registry.example.com/my-project:latest
      env_vars:
        - WAREHOUSE_USER
        - WAREHOUSE_PASSWORD
```

See [How to Pass Database Credentials](pass-credentials.md).

### `'environment' cannot be used in 'container_kwargs'`

```text
Exception: 'environment' cannot be used in 'container_kwargs'. Use the 'env_vars' config key instead.
```

`dagster-docker` rejects this key outright. `container_kwargs` is applied *after* the container environment is assembled, so an `environment` entry would overwrite the variables Dagster injects to track the run (`DAGSTER_RUN_JOB_NAME`, `DAGSTER_RUN_STEP_KEY`).

Use `env_vars` instead:

```yaml
# Rejected
container_kwargs:
  environment:
    - "WAREHOUSE_USER=analytics"

# Correct
env_vars:
  - WAREHOUSE_USER
```

`image` and `network` are rejected inside `container_kwargs` for the same reason, so use the `image` and `networks` config keys. See [How to Pass Database Credentials](pass-credentials.md).

### Executor requires a package that is not installed

```text
Executor 'dask' uses 'dask_executor', which is provided by the 'dagster_dask' module.
That module is not installed. Install it with `pip install dagster-dask`.
```

Executors other than `in_process` and `multiprocess` come from separate Dagster packages. Install the one named in the message. The full key-to-package table is in the [Configuration Reference](../reference/configuration.md#executor-key-naming).

## Debugging guide

When encountering an issue, follow this systematic approach:

### 1. Check logs

- **Terminal output**: Look for error messages and stack traces where you ran `kedro dagster dev`.
- **Dagster UI logs**: Navigate to the failed run, click the failed op/asset, and check the "Logs" tab.

### 2. Verify configuration

```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('conf/local/dagster.yml'))"

# Verify Kedro project loads
kedro run --dry-run --env local

# See what Dagster sees
kedro dagster list defs --env local
```

### 3. Test in isolation

```bash
# Bypass Dagster to isolate Kedro issues
kedro run --env local

# Test a single node
kedro run --node=<node_name> --env local
```

Or use the Dagster UI to materialize a single asset and check if the issue is pipeline-wide or asset-specific.

### 4. Search GitHub Issues

Search [Kedro-Dagster Issues](https://github.com/stateful-y/kedro-dagster/issues) for similar problems.

If not found, [open a new issue](https://github.com/stateful-y/kedro-dagster/issues/new) with:

- Versions: `kedro --version`, `dagster --version`, `pip show kedro-dagster`
- Minimal reproducible example
- Error message and stack trace
- Configuration files (sanitized)

## See also

- [How to Configure Logging](configure-logging.md): logger setup and common logging pitfalls
- [Architecture](../explanation/architecture.md): understanding the Kedro-to-Dagster translation
- [CLI Reference](../reference/cli.md): available commands and options

## Still need help?

- **Documentation**: [Full documentation](../../index.md)
- **Community**: [Kedro Slack](https://slack.kedro.org/)
- **Discussions**: [GitHub Discussions](https://github.com/stateful-y/kedro-dagster/discussions)
- **Bug reports**: [GitHub Issues](https://github.com/stateful-y/kedro-dagster/issues)
