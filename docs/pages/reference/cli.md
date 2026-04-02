# CLI Reference

All commands are invoked as subcommands of `kedro dagster`.

## `kedro dagster init`

Scaffold or refresh Dagster integration files for the current Kedro project. Creates or updates the configuration and entry points so the project can be run from Dagster. Existing files are preserved unless `--force` is used.

```text
kedro dagster init [OPTIONS]
```

**Created/updated files:**

| File | Description |
|------|-------------|
| `conf/<env>/dagster.yml` | Dagster run parametrization for Kedro-Dagster |
| `src/<package>/definitions.py` | Dagster `Definitions` entry point |
| `dg.toml` | Dagster `dg` CLI configuration (Dagster >= 1.10.6 only) |

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--env` | `-e` | Kedro environment under `conf/` where `dagster.yml` is written | `base` |
| `--force` | `-f` | Overwrite existing files without prompting | `false` |
| `--silent` | `-s` | Suppress success messages | `false` |

### Examples

```bash
# Initialize in the default base environment
kedro dagster init

# Target a specific environment
kedro dagster init -e production

# Overwrite existing files
kedro dagster init --force

# Quiet output (useful in CI)
kedro dagster init -e base --force --silent
```

---

## `kedro dagster dev`

Launch the Dagster developer UI for the current Kedro project. Bootstraps the project, resolves the Dagster `definitions.py`, and starts the Dagster web server.

!!! note "Dagster >= 1.10.6"
    With Dagster 1.10.6+, `dev` is a proxy to `dg dev` and inherits its options. The table below documents the legacy (< 1.10.6) options. For newer versions, run `kedro dagster dev --help` to see all available flags.

```text
kedro dagster dev [OPTIONS]
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--env` | `-e` | Kedro configuration environment to load | `local` |
| `--log-level` | | Log verbosity: `debug`, `info`, `warning`, `error`, `critical` | |
| `--log-format` | | Output format: `color`, `json`, `default` | |
| `--port` | `-p` | HTTP port to bind the Dagster web UI | |
| `--host` | `-h` | Interface or IP to bind (e.g., `127.0.0.1`, `0.0.0.0`) | |
| `--live-data-poll-rate` | | Polling interval in seconds for live data | |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `KEDRO_ENV` | Set automatically by the command. Overrides the `--env` option in child processes. |

### Examples

```bash
# Start the UI with the local environment
kedro dagster dev

# Use a specific environment with JSON logs
kedro dagster dev -e staging --log-format json --log-level info

# Bind to a custom port
kedro dagster dev --port 3000
```

---

## `kedro dagster list-defs`

!!! note "Dagster >= 1.10.6"
    Available only with Dagster 1.10.6+. Proxies to `dg list-defs` within the Kedro project context.

List Dagster definitions (assets, jobs, schedules, sensors) discovered in the project.

```text
kedro dagster list-defs [OPTIONS] [ARGS]...
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--env` | `-e` | Kedro configuration environment to use | `local` |

All additional arguments and options are forwarded to the underlying `dg list-defs` command.

### Examples

```bash
# List all definitions
kedro dagster list-defs

# List definitions for a specific environment
kedro dagster list-defs -e production
```

---

## Proxied `dg` Commands

With Dagster >= 1.10.6, all commands from the `dg` CLI are available under `kedro dagster`. Each proxied command receives an additional `--env/-e` option to specify the Kedro environment. All other arguments are forwarded to the underlying `dg` command.

Run `kedro dagster --help` to see the full list of available commands for your Dagster version.

```bash
# Example: any dg command is accessible
kedro dagster <command> -e local [ARGS]...
```

## See also

- [Configuration Reference](configuration.md): `dagster.yml` field tables
- [Getting Started](../tutorials/getting-started.md): First-time setup walkthrough
