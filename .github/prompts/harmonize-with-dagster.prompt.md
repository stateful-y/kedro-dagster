---
mode: agent
description: >
  Harmonize kedro-azureml-pipeline source, tests, config, docs, and CI with kedro-dagster patterns.
  Adds public API exports, upgrades ty rules, adopts scenario-based test factory, adds version matrix CI,
  and creates a concepts.md explanation page.
---

# Harmonize kedro-azureml-pipeline with kedro-dagster

Apply all changes described below to the kedro-azureml-pipeline repository.
Work through each section sequentially. After each section, run the verification
commands listed at the bottom before continuing to the next section.

## Reference: kedro-dagster target patterns

The sibling repository `stateful-y/kedro-dagster` (branch `chore/project-restructure`)
is the reference for structural patterns. You do NOT need to clone it - the target
patterns are described inline below with code examples.

---

## 1. Add explicit public API exports in `__init__.py`

**File:** `src/kedro_azureml_pipeline/__init__.py`

The current file only exports `__version__`. Add eager imports and an `__all__` list
to make the public API discoverable, matching kedro-dagster's pattern.

**Target content:**

```python
"""Kedro AzureML Pipeline."""

from importlib.metadata import version

__version__ = version(__name__)

import warnings

warnings.filterwarnings("ignore", module="azure.ai.ml")

from kedro_azureml_pipeline.config import KedroAzureMLConfig
from kedro_azureml_pipeline.datasets.asset_dataset import AzureMLAssetDataset
from kedro_azureml_pipeline.datasets.pipeline_dataset import AzureMLPipelineDataset
from kedro_azureml_pipeline.distributed import DistributedNodeConfig, distributed_job
from kedro_azureml_pipeline.generator import AzureMLPipelineGenerator
from kedro_azureml_pipeline.manager import KedroContextManager
from kedro_azureml_pipeline.runner import AzurePipelinesRunner
from kedro_azureml_pipeline.utils import CliContext

__all__ = [
    "__version__",
    "AzureMLAssetDataset",
    "AzureMLPipelineDataset",
    "AzureMLPipelineGenerator",
    "AzurePipelinesRunner",
    "CliContext",
    "DistributedNodeConfig",
    "KedroAzureMLConfig",
    "KedroContextManager",
    "distributed_job",
]
```

**Rules:**
- Verify each import path actually exists before adding it. If a class lives at a
  different path, adjust the import accordingly.
- Keep the `warnings.filterwarnings` call.
- Sort `__all__` alphabetically.

---

## 2. Change ty rules from "ignore" to "warn"

**File:** `pyproject.toml`

Change all ty rules from `"ignore"` to `"warn"`:

```toml
[tool.ty.rules]
invalid-assignment = "warn"
invalid-argument-type = "warn"
invalid-parameter-default = "warn"
invalid-return-type = "warn"
unresolved-attribute = "warn"
unresolved-import = "warn"
no-matching-overload = "warn"
invalid-method-override = "warn"
```

Run `uv run ty check src/` afterward. Fix any errors that are genuine bugs.
For false positives from third-party libraries (azure-ai-ml, kedro), add
`# type: ignore[rule-name]` inline comments rather than reverting to "ignore".

---

## 3. Add `_disable_kedro_plugin_entrypoints` autouse fixture

**File:** `tests/conftest.py`

Add this autouse fixture to prevent third-party Kedro plugin hooks from interfering
with tests. This mirrors the kedro-dagster pattern exactly.

Add these imports at the top of conftest.py:

```python
import importlib.metadata as _ilmd
import kedro.framework.session.session as _kedro_session_mod
from kedro.framework import project as _kedro_project
```

Add this fixture (can go after existing fixtures or near the top):

```python
@fixture(autouse=True)
def _disable_kedro_plugin_entrypoints(monkeypatch):
    """Prevent system-installed Kedro plugin hooks from loading during tests.

    Reads the project's ``ALLOWED_HOOK_PLUGINS`` setting to determine which
    plugin distributions (by name) are permitted. All others are filtered out.
    """

    def _wrapped_register(*args, **kwargs):
        hook_manager = args[0] if args else kwargs.get("hook_manager")

        proj_allowed = getattr(_kedro_project.settings, "ALLOWED_HOOK_PLUGINS", ())
        allowed_set = {str(p).strip() for p in proj_allowed if str(p).strip()}

        if not allowed_set:
            return hook_manager

        def _filtered_loader(group: str):
            try:
                all_entry_points = _ilmd.entry_points()
                if hasattr(all_entry_points, "select"):
                    entry_points = list(all_entry_points.select(group=group))
                else:
                    entry_points = list(all_entry_points.get(group, []))
            except Exception:
                entry_points = []

            for entry_point in entry_points:
                try:
                    dist_name = getattr(getattr(entry_point, "dist", None), "name", None)
                    if dist_name and dist_name in allowed_set:
                        plugin = entry_point.load()
                        hook_manager.register(plugin, name=getattr(entry_point, "name", None))
                except Exception:
                    continue

            return hook_manager

        hook_manager.load_setuptools_entrypoints = _filtered_loader

    monkeypatch.setattr(
        _kedro_session_mod,
        "_register_hooks_entry_points",
        _wrapped_register,
        raising=False,
    )
```

**Integration with test project creation:**

When creating test Kedro projects (in the scenario factory - see section 4), each
project's `settings.py` should declare an `ALLOWED_HOOK_PLUGINS` tuple listing the
plugin distribution names that are allowed to load hooks. For example:

```python
ALLOWED_HOOK_PLUGINS = ("kedro-mlflow",)
```

---

## 4. Create `tests/scenarios/` package with factory pattern

Create a structured test scenario system matching kedro-dagster's pattern. This
replaces inline fixture definitions with composable, reusable project builders.

### 4a. Create `tests/scenarios/__init__.py`

```python
"""Reusable Kedro project scenarios for integration tests."""
```

### 4b. Create `tests/scenarios/project_factory.py`

```python
"""Factory for building isolated Kedro project directories for testing."""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from click.testing import CliRunner
from kedro.framework.cli.starters import create_cli as kedro_cli


@dataclass
class KedroProjectOptions:
    """Options to build a fake Kedro project scenario for testing.

    Attributes
    ----------
    project_name : str | None
        Name of the Kedro project.
    project_path : Path | None
        Path where the project is created (populated by factory).
    package_name : str | None
        Python package name for the Kedro project (populated by factory).
    env : str
        Kedro environment to write configs to (e.g., "base", "local").
    catalog : dict
        Content for catalog.yml under conf/<env>/.
    azureml : dict | None
        Content for azureml.yml under conf/<env>/.
    parameters : dict | None
        Content for parameters file under conf/<env>/.
    parameters_filename : str
        Name for the parameters file (default: "parameters.yml").
    pipeline_registry_py : str | None
        Custom pipeline_registry.py content to inject.
    plugins : list[str]
        Plugin distribution names allowed to load hooks during tests.
    """

    project_name: str | None = None
    project_path: Path | None = None
    package_name: str | None = None
    env: str = "base"
    catalog: dict[str, Any] = field(default_factory=dict)
    azureml: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    parameters_filename: str = "parameters.yml"
    pipeline_registry_py: str | None = None
    plugins: list[str] = field(default_factory=list)


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a dict to a YAML file, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=True,
            allow_unicode=True,
            default_flow_style=False,
            indent=2,
        )


def build_kedro_project_scenario(
    temp_directory: Path,
    options: KedroProjectOptions,
    project_name: str,
) -> KedroProjectOptions:
    """Create a fresh Kedro project in a temp dir and inject scenario configs.

    Parameters
    ----------
    temp_directory : Path
        Temporary base directory for project creation.
    options : KedroProjectOptions
        Scenario options including env, catalog, azureml config, etc.
    project_name : str
        Name for the new project directory.

    Returns
    -------
    KedroProjectOptions
        The options object with project_name, project_path, and package_name populated.
    """
    os.chdir(temp_directory)

    package_name = project_name.replace("-", "_")
    project_path: Path = Path(temp_directory) / project_name
    if project_path.exists():
        shutil.rmtree(project_path)

    cli_runner = CliRunner()
    cli_runner.invoke(
        kedro_cli,
        ["new", "-v", "--name", project_name, "--tools", "none", "--example", "no"],
    )

    # Write ALLOWED_HOOK_PLUGINS to settings.py
    settings_file = project_path / "src" / package_name / "settings.py"
    settings_text = settings_file.read_text(encoding="utf-8")
    allowed_tuple = ", ".join([f"'{p}'" for p in options.plugins])
    settings_text += f"\n\n# Allowed third-party plugin hooks for tests\nALLOWED_HOOK_PLUGINS = ({allowed_tuple})\n"
    settings_file.write_text(settings_text, encoding="utf-8")

    # Inject configuration files
    conf_env_dir = project_path / "conf" / options.env
    conf_env_dir.mkdir(parents=True, exist_ok=True)

    if options.catalog:
        _write_yaml(conf_env_dir / "catalog.yml", options.catalog)

    if options.azureml:
        _write_yaml(conf_env_dir / "azureml.yml", options.azureml)

    if options.parameters is not None:
        filename = options.parameters_filename or "parameters.yml"
        _write_yaml(conf_env_dir / filename, options.parameters)

    # Inject custom pipeline registry if provided
    src_dir = project_path / "src"
    package_dirs = [p for p in src_dir.iterdir() if p.is_dir() and p.name != "__pycache__"]
    if not package_dirs:
        msg = f"No package directory found under {src_dir}"
        raise RuntimeError(msg)

    if package_dirs:
        package_name = package_dirs[0].name
        if options.pipeline_registry_py is not None:
            pipeline_registry_file = package_dirs[0] / "pipeline_registry.py"
            pipeline_registry_file.write_text(options.pipeline_registry_py, encoding="utf-8")

        # Clear cached modules so pipeline registry updates are picked up
        sys.modules.pop("kedro.framework.project", None)
        sys.modules.pop(f"{package_name}.pipeline_registry", None)
        for modname in list(sys.modules.keys()):
            if modname == f"{package_name}.pipelines" or modname.startswith(f"{package_name}.pipelines."):
                sys.modules.pop(modname, None)

    # Configure the Kedro project
    configure_project = importlib.import_module("kedro.framework.project").configure_project
    configure_project(package_name)

    options.project_name = project_name
    options.project_path = project_path
    options.package_name = package_name

    return options
```

### 4c. Create `tests/scenarios/kedro_projects.py`

Create pre-built scenario option functions for common test configurations.
Adapt these to Azure ML-specific patterns. Example structure:

```python
"""Pre-built Kedro project scenario options for Azure ML integration tests."""

from __future__ import annotations

from typing import Any

from .project_factory import KedroProjectOptions


def pipeline_registry_default() -> str:
    """Simple 3-node linear pipeline for basic integration tests."""
    return """
from kedro.pipeline import Pipeline, node


def identity(arg):
    return arg


def register_pipelines():
    pipeline = Pipeline(
        [
            node(identity, ["input_ds"], "intermediate_ds", name="node0"),
            node(identity, ["intermediate_ds"], "output_ds", name="node1"),
            node(identity, ["intermediate_ds"], "output2_ds", name="node2"),
        ],
    )
    return {"__default__": pipeline}
"""


def default_azureml_config() -> dict[str, Any]:
    """Minimal azureml.yml config for tests."""
    return {
        "workspace": {
            "__default__": {
                "subscription_id": "test-sub-id",
                "resource_group": "test-rg",
                "name": "test-workspace",
            }
        },
        "compute": {
            "__default__": {
                "cluster_name": "cpu-cluster",
            }
        },
        "execution": {
            "environment": "test-env:1",
        },
        "jobs": {
            "__default__": {
                "pipeline": {"pipeline_name": "__default__"},
            }
        },
    }


def options_basic_pipeline(env: str = "base") -> KedroProjectOptions:
    """Minimal pipeline with azureml config."""
    catalog = {
        "input_ds": {"type": "MemoryDataset"},
        "intermediate_ds": {"type": "MemoryDataset"},
        "output_ds": {"type": "MemoryDataset"},
        "output2_ds": {"type": "MemoryDataset"},
    }
    return KedroProjectOptions(
        env=env,
        catalog=catalog,
        azureml=default_azureml_config(),
        pipeline_registry_py=pipeline_registry_default(),
    )


def options_with_compute_tags(env: str = "base") -> KedroProjectOptions:
    """Pipeline with compute-tagged nodes for multi-cluster tests."""
    # Adapt from existing test fixtures that test compute tag routing
    opts = options_basic_pipeline(env)
    # Customize pipeline_registry_py with compute-tagged nodes
    return opts


def options_with_azureml_datasets(env: str = "base") -> KedroProjectOptions:
    """Pipeline using AzureMLAssetDataset entries in the catalog."""
    catalog = {
        "input_ds": {
            "type": "kedro_azureml_pipeline.datasets.AzureMLAssetDataset",
            "azureml_dataset": "test-dataset",
            "dataset": {"type": "pandas.CSVDataset"},
        },
        "intermediate_ds": {"type": "MemoryDataset"},
        "output_ds": {"type": "MemoryDataset"},
    }
    return KedroProjectOptions(
        env=env,
        catalog=catalog,
        azureml=default_azureml_config(),
        pipeline_registry_py=pipeline_registry_default(),
    )


def options_with_schedule(env: str = "base") -> KedroProjectOptions:
    """Pipeline with a cron schedule configured."""
    config = default_azureml_config()
    config["jobs"]["__default__"]["schedule"] = "daily"
    config["schedules"] = {
        "daily": {
            "cron": {
                "expression": "0 6 * * *",
                "time_zone": "UTC",
            }
        }
    }
    return KedroProjectOptions(
        env=env,
        catalog={"input_ds": {"type": "MemoryDataset"}, "intermediate_ds": {"type": "MemoryDataset"},
                 "output_ds": {"type": "MemoryDataset"}, "output2_ds": {"type": "MemoryDataset"}},
        azureml=config,
        pipeline_registry_py=pipeline_registry_default(),
    )
```

**Rules:**
- Review existing `conftest.py` inline fixtures and convert them to `options_*` functions.
- Each function returns a `KedroProjectOptions` instance.
- Keep existing test logic intact - only move fixture data into scenario functions.
- The `azureml` field replaces what kedro-dagster calls `dagster` in its `KedroProjectOptions`.

### 4d. Update `tests/conftest.py`

Add the factory fixture and convert existing inline fixtures:

```python
from .scenarios.kedro_projects import (
    options_basic_pipeline,
    options_with_azureml_datasets,
    options_with_compute_tags,
    options_with_schedule,
)
from .scenarios.project_factory import KedroProjectOptions, build_kedro_project_scenario


@fixture(scope="session")
def temp_directory(tmpdir_factory):
    """Session-scoped temporary directory for all test projects."""
    return tmpdir_factory.mktemp("session_temp_dir")


@fixture(scope="session")
def project_scenario_factory(temp_directory):
    """Return a callable that builds Kedro project variants in tmp dirs."""

    def _factory(kedro_project_options: KedroProjectOptions, project_name: str | None = None) -> KedroProjectOptions:
        return build_kedro_project_scenario(
            temp_directory=temp_directory, options=kedro_project_options, project_name=project_name
        )

    return _factory
```

Keep all existing fixtures that are NOT project-scenario-related. Only refactor
fixtures that create Kedro project directories to use the factory pattern.

---

## 5. Add `tests-versions.yml` workflow

**Create:** `.github/workflows/tests-versions.yml`

Model after kedro-dagster's version matrix workflow, adapted for the Azure ML
dependency matrix:

```yaml
name: Run tests for different versions of Kedro and azure-ai-ml
on:
  workflow_call:
  workflow_dispatch:
  push:
    branches: ["main"]
    tags-ignore: ["**"]
  pull_request:
    branches: ["main"]
    types: [opened, synchronize, reopened, ready_for_review]

permissions:
  pull-requests: write

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  versions:
    name: Test ${{ matrix.python-version }} | ${{ matrix.kedro_spec }} | ${{ matrix.azureml_spec }} on ${{ matrix.os }}
    if: ${{ github.event_name != 'pull_request' || github.event.pull_request.draft == false }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
        os: [ubuntu-latest]
        kedro_spec: ["kedro>=1.0,<2.0"]
        azureml_spec: ["azure-ai-ml>=1.2,<1.20", "azure-ai-ml>=1.20"]
    steps:
      - name: Checkout repository
        uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Install the latest version of uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
          cache-dependency-glob: "pyproject.toml"

      - name: Install nox
        run: uv tool install --python-preference only-managed nox

      - name: Install Python ${{ matrix.python-version }}
        run: uv python install --python-preference only-managed ${{ matrix.python-version }}

      - name: Run versioned tests
        shell: bash
        run: |
          nox -s "test_versions-${{ matrix.python-version }}(azureml_spec='${{ matrix.azureml_spec }}', kedro_spec='${{ matrix.kedro_spec }}')"
        env:
          PYTEST_XDIST_AUTO_NUM_WORKERS: 0
```

**Rules:**
- Adjust the matrix values for `azureml_spec` based on which azure-ai-ml versions
  the project actually supports. Check `pyproject.toml` for the current constraint.
- Add a corresponding `test_versions` nox session in `noxfile.py` if one doesn't
  exist yet. Model after kedro-dagster's nox session that parameterizes
  `with_mlflow`, `kedro_spec`, and framework-specific spec.
- The nox session should install the specific version constraints from the matrix
  before running pytest.

---

## 6. Align `.pre-commit-config.yaml` rumdl version

**File:** `.pre-commit-config.yaml`

Update the rumdl hook version from `v0.1.33` to `v0.1.57` to match kedro-dagster:

```yaml
  - repo: https://github.com/rvben/rumdl-pre-commit
    rev: v0.1.57
    hooks:
      - id: rumdl
      - id: rumdl-fmt
```

---

## 7. Add `concepts.md` explanation page

Create a concepts and introduction page for the Explanation section, mirroring
kedro-dagster's `concepts.md` structure adapted for Azure ML.

**Create:** `docs/pages/explanation/concepts.md`

The page should follow the Diataxis explanation pattern (understanding-oriented,
discursive, no step-by-step instructions) and cover these sections:

### Required structure

```markdown
# Concepts

[Opening paragraph: what kedro-azureml-pipeline is and how it connects Kedro to Azure ML Pipelines]

## The pipeline-as-a-service alignment

[How Kedro's pipeline abstraction maps naturally to Azure ML's pipeline concept.
Kedro provides the structured project, catalog, and node definitions. Azure ML
provides managed compute, experiment tracking, and enterprise-scale execution.]

### For Kedro users

[Bullet list of benefits: no code changes, managed compute, data asset versioning,
distributed training, scheduling, MLflow integration]

[Link to Azure ML documentation for evaluation]

### For Azure ML users

[Bullet list of benefits: structured projects, modular pipelines, declarative
catalog, testable nodes, environment-specific configuration]

[Link to Kedro documentation for evaluation]

## Key features

### Configuration-driven workflows
[azureml.yml per environment, separation of infra from pipeline logic]

### Data asset management
[AzureMLAssetDataset, versioning, Azure ML data stores]

### Distributed training
[@distributed_job decorator, multi-GPU scaling]

### Kedro hooks preservation
[Hooks fire during remote execution, MLflow integration]

### Scheduling
[Cron and recurrence schedules via config]

## Limitations and considerations

[Evolving feature parity, compatibility notes, version pinning advice]

## See also

[Links to architecture, getting-started, contributing]
```

**Update `mkdocs.yml` nav:**

Add `concepts.md` to the Explanation section. Target nav for explanation:

```yaml
  - Explanation:
    - pages/explanation/index.md
    - Concepts: pages/explanation/concepts.md
    - Architecture: pages/explanation/architecture.md
    - Data Flow Between Steps: pages/explanation/data-flow.md
    - Hook Lifecycle: pages/explanation/hook-lifecycle.md
```

**Update `docs/pages/explanation/index.md`:**

Add a card or link for the new Concepts page if the index uses a grid layout.

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
uv run python -c "from kedro_azureml_pipeline import KedroAzureMLConfig"
uv run python -c "from kedro_azureml_pipeline import AzureMLPipelineGenerator"
uv run python -c "from kedro_azureml_pipeline import CliContext"
uv run python -c "from kedro_azureml_pipeline.config import CONFIG_TEMPLATE_YAML"

# Docs build
uv run mkdocs build --strict
```
