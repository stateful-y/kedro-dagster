---
mode: agent
description: >
  Harmonize kedro-dagster source, tests, config, CLI, docs, and CI with kedro-azureml-pipeline patterns.
  Bumps to kedro>=1.0, drops Pydantic v1 compat, restructures modules, and aligns doc pages.
---

# Harmonize kedro-dagster with kedro-azureml-pipeline

Apply all changes described below to the kedro-dagster repository.
Work through each section sequentially. After each section, run the verification
commands listed at the bottom before continuing to the next section.

## Reference: kedro-azureml-pipeline target patterns

The sibling repository `stateful-y/kedro-azureml-pipeline` (branch
`refactor/codebase-quality-overhaul`) is the reference for structural patterns.
You do NOT need to clone it - the target patterns are described inline below.

---

## 1. Consolidate config models into `config/models.py`

Merge the five config files into a single `src/kedro_dagster/config/models.py`:

**Files to merge (then delete originals):**
- `src/kedro_dagster/config/kedro_dagster.py` - `KedroDagsterConfig`, `get_dagster_config()`
- `src/kedro_dagster/config/execution.py` - all executor option classes + `EXECUTOR_MAP`
- `src/kedro_dagster/config/automation.py` - `ScheduleOptions`
- `src/kedro_dagster/config/job.py` - `PipelineOptions`, `JobOptions`
- `src/kedro_dagster/config/logging.py` - `LoggerOptions`, `LogLevel`

**Rules:**
- Preserve the exact same class names, fields, validators, and docstrings.
- Order classes bottom-up by dependency: `LogLevel` -> `LoggerOptions` -> executor classes -> `EXECUTOR_MAP` -> `ScheduleOptions` -> `PipelineOptions` -> `JobOptions` -> `KedroDagsterConfig` -> `get_dagster_config()`.
- All Pydantic models use `model_config = ConfigDict(...)` directly (no v1 compat - see section 2).
- Add a `CONFIG_TEMPLATE_YAML` string constant and a `_CONFIG_TEMPLATE` validated instance at the end of the file (see section 7).

**Update `src/kedro_dagster/config/__init__.py`:**

```python
"""Pydantic configuration models for the Kedro-Dagster plugin."""

from kedro_dagster.config.models import (
    CONFIG_TEMPLATE_YAML,
    EXECUTOR_MAP,
    ExecutorOptions,
    JobOptions,
    KedroDagsterConfig,
    LoggerOptions,
    LogLevel,
    PipelineOptions,
    ScheduleOptions,
    _CONFIG_TEMPLATE,
    get_dagster_config,
)

__all__ = [
    "CONFIG_TEMPLATE_YAML",
    "EXECUTOR_MAP",
    "ExecutorOptions",
    "JobOptions",
    "KedroDagsterConfig",
    "LogLevel",
    "LoggerOptions",
    "PipelineOptions",
    "ScheduleOptions",
    "_CONFIG_TEMPLATE",
    "get_dagster_config",
]
```

Also re-export all individual executor classes (`InProcessExecutorOptions`,
`MultiprocessExecutorOptions`, etc.) if they were previously importable.

Update every import across `src/` and `tests/` that referenced the old file paths.

---

## 2. Remove Pydantic v1 compatibility layer

**In `src/kedro_dagster/utils.py`:**
- Delete the `create_pydantic_config(**kwargs)` function entirely.
- Delete the `PYDANTIC_VERSION` constant.
- Remove any `from kedro_dagster.utils import create_pydantic_config` imports.

**In all config models (now in `config/models.py`):**
- Replace every `create_pydantic_config(...)` call with direct `model_config = ConfigDict(...)`.
- Remove any `if PYDANTIC_VERSION[0] >= 2:` branching.
- Use only Pydantic v2 APIs: `model_validator`, `field_validator`, `ConfigDict`, `model_dump()`.

**In `pyproject.toml`:**
- Change `pydantic>=1.0.0,<3.0.0` to `pydantic>=2.6.4`.

---

## 3. Bump Kedro and kedro-datasets

**In `pyproject.toml` `[project.dependencies]`:**
- Change `kedro>=0.19,<2.0` to `kedro>=1.0.0`.
- Add `kedro-datasets>=1.0.0` (with explicit lower bound).

**In source code:**
- Remove the `KEDRO_VERSION` constant from `utils.py` if it was only used for version gating.
- In `PipelineOptions`, remove any `node_namespace` vs `node_namespaces` branching.
  Keep only `node_namespaces: list[str] | None` (the Kedro 1.x field name).
- Search for any other `KEDRO_VERSION` guards and remove the pre-1.0 branches.

---

## 4. Split CLI into a package

Create `src/kedro_dagster/cli/` with three files:

**`src/kedro_dagster/cli/__init__.py`:**
```python
"""Click CLI commands for the Kedro-Dagster plugin."""
```

**`src/kedro_dagster/cli/commands.py`:**
- Move: the `commands` Click group, `dagster` subgroup, `init` command, `dev` command, `_register_dg_commands()`, and `DgProxyCommand` class.
- Import business logic from `cli.functions`.

**`src/kedro_dagster/cli/functions.py`:**
- Move: `write_jinja_template`, `find_kedro_project`, `render_jinja_template`, and any other non-Click helper functions that the commands call.

**Delete `src/kedro_dagster/cli.py`.**

**In `pyproject.toml`:**
- Change entry point from `kedro_dagster.cli:commands` to `kedro_dagster.cli.commands:commands`.

**In `src/kedro_dagster/__init__.py`:**
- Update any import that referenced `kedro_dagster.cli`.

---

## 5. Add `CliContext` dataclass

**In `src/kedro_dagster/utils.py`, add:**

```python
from dataclasses import dataclass
from typing import Any


@dataclass
class CliContext:
    """Runtime context passed to CLI command handlers.

    Parameters
    ----------
    env : str
        Kedro environment name.
    metadata : Any
        Kedro ``ProjectMetadata`` instance.
    """

    env: str
    metadata: Any
```

**In `cli/commands.py`:**
- Use `CliContext` as the Click context object: store `CliContext(env=env, metadata=metadata)` via `ctx.obj = CliContext(...)` in the group callback.
- Each subcommand receives it via `@click.pass_obj`.

---

## 6. Create `constants.py`

**Create `src/kedro_dagster/constants.py`:**

Extract from `utils.py` and `datasets/__init__.py`:
- `KEDRO_DAGSTER_SEPARATOR = "__"`
- `DAGSTER_ALLOWED_PATTERN = "^[A-Za-z0-9_]+$"`
- `NOTHING_OUTPUT` (the sentinel string used for nothing assets)
- Any other string/regex constants that were previously inline in `utils.py`.

Update all imports across `src/` and `tests/`.

---

## 7. Add `CONFIG_TEMPLATE_YAML` for dagster.yml

**At the end of `src/kedro_dagster/config/models.py`, add:**

```python
CONFIG_TEMPLATE_YAML: str = """\
# dagster.yml - Kedro-Dagster orchestration configuration
# See https://kedro-dagster.readthedocs.io/en/latest/pages/reference/configuration/

jobs:
  __default__:
    pipeline:
      pipeline_name: __default__
"""

_CONFIG_TEMPLATE: KedroDagsterConfig = KedroDagsterConfig.model_validate(
    yaml.safe_load(CONFIG_TEMPLATE_YAML)
)
```

Add `import yaml` at the top of the file.

**In `cli/functions.py` or `cli/commands.py`:**
- Use `CONFIG_TEMPLATE_YAML` for the `kedro dagster init` command when writing `dagster.yml`.
- Keep Jinja2 templates for `definitions.py` and `dg.toml` (they need dynamic package names).

---

## 8. Add Hypothesis property-based tests for config models

**Create or update `tests/test_config.py`:**

Add `@given` property-based tests for all top-level config models. Follow this pattern:

```python
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.pydantic import from_model

from kedro_dagster.config import (
    JobOptions,
    KedroDagsterConfig,
    LoggerOptions,
    PipelineOptions,
    ScheduleOptions,
)


class TestPipelineOptionsHypothesis:
    @given(instance=from_model(PipelineOptions))
    @settings(max_examples=20)
    def test_roundtrip(self, instance: PipelineOptions):
        dumped = instance.model_dump()
        restored = PipelineOptions.model_validate(dumped)
        assert restored == instance


class TestScheduleOptionsHypothesis:
    @given(instance=from_model(ScheduleOptions))
    @settings(max_examples=20)
    def test_roundtrip(self, instance: ScheduleOptions):
        dumped = instance.model_dump()
        restored = ScheduleOptions.model_validate(dumped)
        assert restored == instance
```

Repeat for `JobOptions`, `LoggerOptions`, `KedroDagsterConfig`, and executor option classes.

Keep existing unit tests. Add the hypothesis tests as new test classes in the same file.

---

## 9. Rename test files to mirror source modules

Rename these test files (update any pytest imports or conftest references):

| Old name | New name |
|---|---|
| `tests/test_catalog_translator.py` | `tests/test_catalog.py` |
| `tests/test_node_translator.py` | `tests/test_nodes.py` |
| `tests/test_pipeline_translator.py` | `tests/test_pipelines.py` |
| `tests/test_kedro_run_translator.py` | `tests/test_kedro.py` |
| `tests/test_dagster_creators.py` | `tests/test_dagster.py` |

Use `git mv` instead of creating new files so git history is preserved.

---

## 10. Raise interrogate fail-under to 100

**In `pyproject.toml`:**
- Change `fail-under = 75` to `fail-under = 100`.

Run `uv run interrogate -vv src/` and add missing docstrings to any file that fails.

---

## 11. Align `.pre-commit-config.yaml` rumdl version

kedro-azureml-pipeline uses `rumdl` at `v0.1.33`. kedro-dagster currently has `v0.1.57`.
Keep the higher version (`v0.1.57`). No change needed here - the azureml prompt will
upgrade to match.

---

## 12. Documentation alignment

### Move Migrate Existing Project to Tutorials

- Move `docs/pages/how-to/migrate-existing-project.md` to `docs/pages/tutorials/migrate-existing-project.md`.
- Update `mkdocs.yml` nav: remove from "How-to Guides" and add under "Tutorials".
- Update any internal links pointing to the old path.

### Rename MLflow guide

- Rename `docs/pages/how-to/integrate-mlflow.md` to `docs/pages/how-to/use-mlflow.md`.
- Update `mkdocs.yml` nav entry.
- Update all internal links (in `concepts.md`, `index.md`, other how-to pages).

### Rename Troubleshooting

- Rename `docs/pages/how-to/troubleshooting.md` to `docs/pages/how-to/troubleshoot.md`.
- Update `mkdocs.yml` nav entry.
- Update all internal links.

### Add missing Explanation pages

Create these new explanation pages following the Diataxis explanation pattern
(understanding-oriented, discursive, no step-by-step instructions):

- `docs/pages/explanation/data-flow.md` - How data flows between Kedro nodes when
  executed through Dagster. Cover: IO managers, catalog resolution, partitioned datasets,
  nothing assets, and parameter handling.
- `docs/pages/explanation/hook-lifecycle.md` - How Kedro hooks are preserved across
  the Dagster execution boundary. Cover: which hooks fire, when they fire in the
  Dagster lifecycle, MLflow hook integration, and custom hook considerations.

Add both to `mkdocs.yml` under the Explanation section.

### Add Datasets reference page

Create `docs/pages/reference/datasets.md` - Reference documentation for
`DagsterNothingDataset` and `DagsterPartitionedDataset`. Use `::: kedro_dagster.datasets`
mkdocstrings directive for auto-generated API docs where possible.

Add to `mkdocs.yml` under Reference section, between "CLI" and "API".

### Target mkdocs.yml nav after all changes

```yaml
nav:
  - Home: index.md
  - Tutorials:
    - pages/tutorials/index.md
    - Getting Started: pages/tutorials/getting-started.md
    - Example Project: pages/tutorials/example-project.md
    - Migrate Existing Project: pages/tutorials/migrate-existing-project.md
  - How-to Guides:
    - pages/how-to/index.md
    - Configure Logging: pages/how-to/configure-logging.md
    - Configure Executors: pages/how-to/configure-executors.md
    - Use MLflow: pages/how-to/use-mlflow.md
    - Use Partitions: pages/how-to/use-partitions.md
    - Deploy to Production: pages/how-to/deploy-to-production.md
    - Troubleshoot: pages/how-to/troubleshoot.md
    - Contributing: pages/how-to/contribute.md
  - Reference:
    - pages/reference/index.md
    - Configuration: pages/reference/configuration.md
    - CLI: pages/reference/cli.md
    - Datasets: pages/reference/datasets.md
    - API: pages/reference/api.md
  - Explanation:
    - pages/explanation/index.md
    - Concepts: pages/explanation/concepts.md
    - Architecture: pages/explanation/architecture.md
    - Data Flow: pages/explanation/data-flow.md
    - Hook Lifecycle: pages/explanation/hook-lifecycle.md
```

### Verify README section order

Ensure `README.md` follows this section order (matching kedro-azureml-pipeline):
logo, badges, note/disclaimer, what-is paragraph, features, installation, quickstart,
documentation link, contributing, license, acknowledgements.

---

## Verification

Run these commands after each section to catch regressions early:

```bash
# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type check
uv run ty check src/

# Docstring coverage
uv run interrogate -vv src/

# Tests
uv run pytest tests/ --no-cov -x

# Import smoke tests
uv run python -c "from kedro_dagster import KedroProjectTranslator"
uv run python -c "from kedro_dagster.cli.commands import commands"
uv run python -c "from kedro_dagster.config import KedroDagsterConfig, CONFIG_TEMPLATE_YAML"
uv run python -c "from kedro_dagster.constants import KEDRO_DAGSTER_SEPARATOR"
uv run python -c "from kedro_dagster.utils import CliContext"

# Docs build
uv run mkdocs build --strict
```
