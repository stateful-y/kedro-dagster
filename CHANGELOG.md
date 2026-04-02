# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

{%- if version %}
## [{{ version | trim_start_matches(pat="v") }}] - {{ timestamp | date(format="%Y-%m-%d") }}
{%- set release_type = "" %}
{%- if version is matching("v?[0-9]+\.0\.0") %}
{%- set release_type = "major" %}
{%- elif version is matching("v?[0-9]+\.[0-9]+\.0") %}
{%- set release_type = "minor" %}
{%- else %}
{%- set release_type = "patch" %}
{%- endif %}

This **{{ release_type }} release** includes {{ commits | length }} commit{%- if commits | length != 1 %}s{%- endif %}.
{% else %}
## [Unreleased]
{%- endif %}
{%- for group, commits in commits | group_by(attribute="group") %}

### {{ group | striptags | trim | upper_first }}
{%- for commit in commits %}
- {{ commit.message | upper_first }}{%- if commit.remote.pr_number %} ([#{{ commit.remote.pr_number }}](https://github.com/stateful-y/kedro-dagster/pull/{{ commit.remote.pr_number }})){%- endif %}{%- if commit.remote.username %} by @{{ commit.remote.username }}{%- endif %}
{%- endfor %}
{%- endfor %}
{%- set new_contributors = commits | filter(attribute="remote.username") | map(attribute="remote.username") | unique %}
{%- if new_contributors | length > 0 %}

### Contributors

Thanks to all contributors for this release:
{%- for contributor in new_contributors %}
- @{{ contributor }}
{%- endfor %}
{%- endif %}

## [Unreleased]

### Refactoring

- Harmonize project structure and codebase to align with the stateful-y `python-package-copier` template by @gtauzin
- Split CLI from single `cli.py` into `cli/` subpackage with `commands.py` and `functions.py` by @gtauzin
- Consolidate config models from multiple files (`automation.py`, `execution.py`, `job.py`, `kedro_dagster.py`, `logging.py`) into single `config/models.py` by @gtauzin
- Formalize `datasets/` as a proper subpackage with `__init__.py` organizing exports by @gtauzin
- Harmonize all Pydantic model docstrings from `Attributes` to `Parameters` section style by @gtauzin
- Rename test files to match source module names (`test_catalog_translator.py` -> `test_catalog.py`, `test_dagster_creators.py` -> `test_dagster.py`, `test_kedro_run_translator.py` -> `test_kedro.py`, `test_node_translator.py` -> `test_nodes.py`) by @gtauzin
- Raise interrogate docstring coverage requirement from 75% to 100% by @gtauzin

### Bug Fixes

- Add `cachetools>=4.1` as an explicit dependency by @gtauzin
- Resolve CI failures in test suite and version matrix by @gtauzin

### Documentation

- Restructure documentation into Diataxis quadrants (tutorials, how-to guides, reference, explanation) by @gtauzin
- Rewrite all documentation content following Diataxis principles by @gtauzin
- Add contributing guide with full development setup and workflow documentation by @gtauzin

### Miscellaneous Tasks

- Add git-cliff configuration for automated changelog generation from conventional commits by @gtauzin
- Add `.editorconfig` for IDE/editor consistency by @gtauzin
- Add `.copier-answers.yml` for template version tracking by @gtauzin
- Add `justfile` with development task shortcuts by @gtauzin
- Replace CI workflows with consolidated `tests.yml`, `changelog.yml`, `nightly.yml`, `pr-title.yml`, and `publish-release.yml` by @gtauzin
- Modernize GitHub issue templates to form-based YAML format by @gtauzin
- Add `py.typed` marker for PEP 561 compliance by @gtauzin

### Breaking Changes

- Require Python >= 3.11 (previously >= 3.10) by @gtauzin
- Require `kedro>=1.0.0` (previously >= 0.19) by @gtauzin
- Require `pydantic>=2.0.0` (previously >= 1.0.0) by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.5.4] - 2026-03-19

This **patch release** includes 2 commits.

### Bug Fixes

- Update all repository references from `gtauzin` to `stateful-y` org by @gtauzin
- Handle Dagster 1.12 `asset_key` rename in `dg list defs` test output by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.5.3] - 2026-02-22

This **patch release** includes 1 commit.

### Bug Fixes

- Fix `DagsterPartitionedDataset` initialisation by ensuring `_partition_cache` is set before calling `super().__init__()` by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.5.2] - 2025-12-05

This **patch release** includes 1 commit.

### Bug Fixes

- Fix pin on kedro dependency to support all kedro 1.x versions by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.5.1] - 2025-12-04

This **patch release** includes 2 commits.

### Bug Fixes

- Fix `dg.toml` template as it was not working out-of-the-box for new projects by @gtauzin

### Documentation

- Enhanced explanation of Dagster partitions integration goals and architecture in the user guide by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.5.0] - 2025-11-27

This **minor release** includes 13 commits.

### Features

- Add comprehensive logging throughout the translation process with `LOGGER.info()` for major steps and `LOGGER.debug()` for detailed progress tracking by @gtauzin
- Add FAQ documentation page with common questions, troubleshooting guides, and production deployment considerations by @gtauzin
- Expand user guide documentation with detailed `DagsterPartitionedDataset` usage examples and migration guides by @gtauzin
- Restrict `DagsterPartitionedDataset` to only support `StaticPartitionsDefinition`, `StaticPartitionMapping`, and `IdentityPartitionMapping` with clear validation errors for unsupported partition types by @gtauzin

### Bug Fixes

- Fix missing `after_catalog_created` hook invocation in Dagster job execution by @gtauzin
- Pass catalog directly to translators instead of accessing via context to avoid potential stale catalog references by @gtauzin
- Improve error messages throughout the codebase with better context and available options by @gtauzin
- Add detailed property docstrings to `KedroRunResource` for better API documentation by @gtauzin
- Rename Technical documentation to User guide and update links accordingly by @gtauzin

### Refactoring

- `KedroRunTranslator` now requires `catalog` as an explicit parameter instead of accessing it from `context.catalog` by @gtauzin
- `PipelineTranslator` now requires `catalog` as an explicit parameter instead of accessing it from `context.catalog` by @gtauzin
- `DagsterPartitionedDataset` now raises `NotImplementedError` at instantiation for unsupported partition types (`TimeWindowPartitionsDefinition`, `MultiPartitionsDefinition`, `DynamicPartitionsDefinition`) instead of at runtime by @gtauzin
- `DagsterPartitionedDataset` now raises `NotImplementedError` at instantiation for unsupported partition mappings (anything other than `StaticPartitionMapping` and `IdentityPartitionMapping`) by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.4.0] - 2025-11-21

This **minor release** includes 11 commits.

### Features

- Wrap all Dagster `dg` CLI commands to be run from within a Kedro project with `kedro dagster <dg command>` by @gtauzin
- Add a `kedro_dagster.logging` module meant to replace `logging` imports in Kedro nodes so loggers are captured and integrated with Dagster by @gtauzin
- Add `loggers` section to `dagster.yml` configuration file to configure Dagster run loggers by @gtauzin
- Rename `LoggerTranslator` to `LoggerCreator` for consistency with `ExecutorCreator` and `SchedulerCreator` by @gtauzin
- Declare direct dependency on `pydantic>=1.0.0,<3.0.0` and enable version-agnostic Pydantic configuration by @gtauzin
- Add conda-forge support for Kedro-Dagster, allowing installation with `conda` or `mamba` by @rxm7706 and @gtauzin
- Allow setting `group_name` in a dataset's `metadata` to override the pipeline-derived group name; `group_name` is also applied per-AssetOut for multi-assets so each asset can have an individual group by @gtauzin
- Add links to MLflow run in Dagster run logs, run tags, and materialized asset metadata by @gtauzin

### Bug Fixes

- Fix how `LoggerCreator` creates loggers for Dagster runs. Generic logging configuration is now supported from `dagster.yml` by @gtauzin

### Refactoring

- Make `env` a required parameter of `KedroProjectTranslator` by @gtauzin
- Remove `dev` config in `dagster.yml` by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin
- @rxm7706

## [0.3.0] - 2025-11-03

This **minor release** includes 6 commits.

### Features

- Add `DagsterNothingDataset`, a Kedro dataset that performs no I/O but enforces node dependency by @gtauzin
- Add `DagsterPartitionedDataset`, a Kedro dataset for partitioned data compatible with Dagster's asset partitions by @gtauzin
- Enable fanning out Kedro nodes when creating the Dagster graph when using `DagsterPartitionedDataset` with multiple partition keys by @gtauzin
- Add support for Kedro >= 1.0.0 and Dagster >= 1.12.0 by @gtauzin

### Bug Fixes

- Fix bug involving unnamed Kedro nodes making `kedro dagster dev` crash by @gtauzin
- Fix defaults on K8S execution configuration by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.2.0] - 2025-04-26

This **minor release** includes 1 commit.

### Refactoring

- Complete refactoring of Kedro-Dagster and its first stable version by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.1.1] - 2024-12-07

This **patch release** includes 2 commits.

### Bug Fixes

- Fixed CLI entrypoint by @gtauzin
- Set up documentation, behavior tests, unit tests and CI by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

## [0.1.0] - 2024-12-03

This **minor release** includes 1 commit.

### Features

- Initial release of Kedro-Dagster by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @gtauzin

<!-- generated by git-cliff -->
