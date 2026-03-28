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

### Dev database not reachable

If using the example project's `dev` environment, ensure the Docker container is running and environment variables match `conf/dev/credentials.yml`:

```bash
docker compose -f docker/dev.docker-compose.yml up -d
export POSTGRES_USER=dev_db
export POSTGRES_PASSWORD=dev_password
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
```

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

## Still need help?

- **Documentation**: [Full documentation](../../index.md)
- **Community**: [Kedro Slack](https://slack.kedro.org/)
- **Discussions**: [GitHub Discussions](https://github.com/stateful-y/kedro-dagster/discussions)
- **Bug reports**: [GitHub Issues](https://github.com/stateful-y/kedro-dagster/issues)
