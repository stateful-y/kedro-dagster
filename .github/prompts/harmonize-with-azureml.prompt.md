---
mode: agent
description: >
  Harmonize kedro-dagster tooling, config model patterns, and tests with
  kedro-azureml-pipeline conventions.  Bumps pydantic/kedro pins, raises
  interrogate to 100%, adds ty rules, switches docstrings to Parameters style,
  and adds Hypothesis property-based tests.
---

# Harmonize kedro-dagster with kedro-azureml-pipeline

Apply all changes described below to the kedro-dagster repository.
Work through each section sequentially. After each section, run the verification
commands listed at the bottom before continuing to the next section.

## Reference: kedro-azureml-pipeline target patterns

The sibling repository `stateful-y/kedro-azureml-pipeline`
(branch `refactor/codebase-quality-overhaul`) is the reference for structural
patterns. You do NOT need to clone it - the target patterns are described inline
below with code examples.

## Shared conventions

Both Kedro orchestration plugins share these conventions. Preserve them in every
change you make:

- **Naming**: snake_case for modules and functions, PascalCase for classes
- **Imports**: `from __future__ import annotations` at top of every file
- **Docstrings**: NumPy style with `Parameters`, `Returns`, `See Also`, `Examples` sections
- **Test classes**: `TestClassName` mirrors the source class being tested
- **Fixture naming**: lowercase with underscores, descriptive (e.g., `dummy_pipeline`, not `pipeline1`)
- **Pydantic models**: `ConfigDict(extra="forbid")`, `Field(description=...)`, minimal validators
- **Config template**: `CONFIG_TEMPLATE_YAML` string + `_CONFIG_TEMPLATE` validated instance at EOF of `models.py`
- **`[ADDITION]` comments**: Only modify `pyproject.toml` sections marked with `# [ADDITION]` to avoid conflicting with copier template updates

---

## 1. Bump Pydantic to v2 only

**File:** `pyproject.toml`

Change the pydantic dependency from `pydantic>=1.0.0,<3.0.0` to `pydantic>=2.6.4`.

The codebase already uses Pydantic v2 APIs exclusively (`model_validator`,
`field_validator`, `ConfigDict`, `model_dump()`). The lower bound should reflect
this to prevent installation under Pydantic v1 where the code would fail.

**In source code:**

- Search for any remaining `PYDANTIC_VERSION` constants or `if PYDANTIC_VERSION`
  branching and remove them.
- Search for `create_pydantic_config` helper and remove it if it exists.
- Ensure all config models use `model_config = ConfigDict(...)` directly.

---

## 2. Bump Kedro to >=1.0.0

**File:** `pyproject.toml`

Change `kedro>=0.19,<2.0` to `kedro>=1.0.0`.

**In source code:**

- Search for `KEDRO_VERSION` in `utils.py`. If it is only used for
  version-gating between 0.x and 1.x APIs, remove the constant and all
  conditional branches. Keep only the Kedro 1.x code path.
- In `PipelineOptions` (config/models.py), if there is any `node_namespace` vs
  `node_namespaces` branching, keep only `node_namespaces: list[str] | None`
  (the Kedro 1.x field name).
- Search the entire source tree for other `KEDRO_VERSION` guards and remove
  the pre-1.0 branches.

**Note:** Keep `KEDRO_VERSION` and `DAGSTER_VERSION` constants if they are used
for non-version-gating purposes (e.g., the `DgProxyCommand` gating on
`DAGSTER_VERSION >= (1, 10, 6)`). Only remove the pre-1.0 Kedro branches.

---

## 3. Add missing ty rules

**File:** `pyproject.toml`

Add two additional ty rules to match kedro-azureml-pipeline's superset.
Keep the existing eleven rules and add:

```toml
[tool.ty.rules]
# -- existing rules (keep all) --
invalid-assignment = "warn"
invalid-argument-type = "warn"
invalid-return-type = "warn"
unresolved-attribute = "warn"
unresolved-import = "warn"
no-matching-overload = "warn"
not-subscriptable = "warn"
call-non-callable = "warn"
unsupported-operator = "warn"
missing-argument = "warn"
invalid-type-form = "warn"
# -- new rules from kedro-azureml-pipeline --
invalid-parameter-default = "warn"
invalid-method-override = "warn"
```

**After applying**, run `uv run ty check src/`. Fix genuine bugs, use inline
`# type: ignore[rule-name]` for false positives from dagster/kedro SDKs.

---

## 4. Raise interrogate to 100%

**File:** `pyproject.toml`

Change `fail-under = 75` to `fail-under = 100` in `[tool.interrogate]`.

Run `uv run interrogate -vv src/` and add missing docstrings to every file
that fails. Follow NumPy docstring style with `Parameters`, `Returns`,
`See Also` sections.

---

## 5. Harmonize config model docstring style

**File:** `src/kedro_dagster/config/models.py`

Switch all Pydantic model docstrings from `Attributes` section style to
`Parameters` section style. This matches kedro-azureml-pipeline and is
consistent with NumPy docstring conventions for dataclass-like types.

**Before (dagster pattern):**

```python
class ScheduleOptions(BaseModel):
    """Options for defining Dagster schedules.

    Attributes
    ----------
    cron_schedule : str
        Cron expression for the schedule.
    execution_timezone : str or None
        Timezone for the schedule.
    """
```

**After (target pattern):**

```python
class ScheduleOptions(BaseModel):
    """Options for defining Dagster schedules.

    Parameters
    ----------
    cron_schedule : str
        Cron expression for the schedule.
    execution_timezone : str or None
        Timezone for the schedule.
    """
```

**Rules:**

- Replace `Attributes` with `Parameters` in every Pydantic model docstring
  in `config/models.py`.
- Keep `See Also` and `Examples` sections unchanged.
- Keep `Field(description=...)` on all attributes (already present - do not
  remove).
- Keep `model_config = ConfigDict(extra="forbid")` (already present).

---

## 6. Remove overly defensive validators

**File:** `src/kedro_dagster/config/models.py`

Remove `@field_validator` methods that only normalize values that Pydantic's
type system already constrains. Specifically:

- **`LoggerOptions.normalize_log_level`**: The `LogLevel` Literal type already
  constrains valid values. If case-insensitive input is needed, use
  `mode="before"` but keep it only if users genuinely pass lowercase in YAML.
  Otherwise remove it.

- **`LoggerOptions.validate_handlers`**: If this only checks that `"class"` is
  present in each handler dict, consider whether `extra="forbid"` on a proper
  handler model would be cleaner. If converting to a typed model is out of
  scope, keep the validator but document why.

- **`LoggerOptions.validate_formatters`** and **`validate_filters`**: Same
  consideration. Keep only if the validation adds value beyond what types
  provide.

- **`LoggerOptions.validate_references`**: This model validator checks
  cross-references between handlers, formatters, and filters. This IS
  genuine business logic - keep it.

**Principle:** Only keep validators that enforce constraints the type system
cannot express (cross-field validation, business rules, XOR constraints).

---

## 7. Add YAML Examples to top-level model docstrings

**File:** `src/kedro_dagster/config/models.py`

Add `Examples` sections to these models if not already present:

- `KedroDagsterConfig` - show a complete `dagster.yml` example
- `JobOptions` - show a job definition with pipeline, executor, schedule

Follow NumPy docstring style:

```python
class KedroDagsterConfig(BaseModel):
    """Main configuration class representing the ``dagster.yml`` structure.

    Parameters
    ----------
    ...

    Examples
    --------
    ```yaml
    # conf/base/dagster.yml
    executors:
      sequential:
        in_process: {}

    schedules:
      daily:
        cron_schedule: "0 6 * * *"
        execution_timezone: "UTC"

    jobs:
      __default__:
        pipeline:
          pipeline_name: __default__
        executor: sequential
        schedule: daily
    ```

    See Also
    --------
    ...
    """
```

---

## 8. Add Hypothesis property-based tests for config models

**File:** `tests/config/test_config.py` (or `tests/test_config.py` depending on layout)

Add `@given` property-based tests for all top-level config models. This matches
kedro-azureml-pipeline's testing pattern.

Add these imports:

```python
from hypothesis import given, settings
from hypothesis import strategies as st
```

Add roundtrip test classes:

```python
class TestPipelineOptionsHypothesis:
    """Property-based tests for PipelineOptions roundtrip serialization."""

    @given(
        pipeline_name=st.text(min_size=1, max_size=50),
        tags=st.none() | st.lists(st.text(min_size=1, max_size=20), max_size=3),
    )
    @settings(max_examples=20)
    def test_roundtrip(self, pipeline_name, tags):
        """PipelineOptions survives dump/validate cycle."""
        instance = PipelineOptions(pipeline_name=pipeline_name, tags=tags)
        dumped = instance.model_dump()
        restored = PipelineOptions.model_validate(dumped)
        assert restored == instance


class TestScheduleOptionsHypothesis:
    """Property-based tests for ScheduleOptions roundtrip serialization."""

    @given(
        cron_schedule=st.from_regex(r"[0-9*/ ]{5,20}", fullmatch=True),
    )
    @settings(max_examples=20)
    def test_roundtrip(self, cron_schedule):
        """ScheduleOptions survives dump/validate cycle."""
        instance = ScheduleOptions(cron_schedule=cron_schedule)
        dumped = instance.model_dump()
        restored = ScheduleOptions.model_validate(dumped)
        assert restored == instance


class TestJobOptionsHypothesis:
    """Property-based tests for JobOptions roundtrip serialization."""

    @given(
        pipeline_name=st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=20)
    def test_roundtrip(self, pipeline_name):
        """JobOptions survives dump/validate cycle."""
        pipeline = PipelineOptions(pipeline_name=pipeline_name)
        instance = JobOptions(pipeline=pipeline)
        dumped = instance.model_dump()
        restored = JobOptions.model_validate(dumped)
        assert restored == instance
```

**Rules:**

- Keep all existing unit tests. Add hypothesis tests as NEW test classes in the
  same file.
- Use `@settings(max_examples=20)` to keep CI fast.
- Test at minimum: `PipelineOptions`, `ScheduleOptions`, `JobOptions`,
  `KedroDagsterConfig`.
- For executor option classes, testing roundtrip on the simplest
  (`InProcessExecutorOptions`) is sufficient.

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
