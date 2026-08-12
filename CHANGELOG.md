# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.8.0] - 2026-08-12

This **minor release** includes 39 commits.


### Features
- Make uv.lock the single source of truth for lint tooling  ([#118](https://github.com/stateful-y/kedro-dagster/pull/118)) by @gtauzin
- Add job factory deriving jobs from pipeline namespaces  ([#122](https://github.com/stateful-y/kedro-dagster/pull/122)) by @gtauzin
- Map Kedro namespaces to hierarchical Dagster asset groups  ([#120](https://github.com/stateful-y/kedro-dagster/pull/120)) by @gtauzin
- Add Kedro dataset preview output metadata  ([#117](https://github.com/stateful-y/kedro-dagster/pull/117)) by @Muhtasim-Munif-Fahim

### Bug Fixes
- Resolve executor types from a single registry, document credential passing  ([#131](https://github.com/stateful-y/kedro-dagster/pull/131)) by @gtauzin
- Pin exact uv version in setup-uv steps (template v0.29.6)  ([#137](https://github.com/stateful-y/kedro-dagster/pull/137)) by @gtauzin
- Pin ossf/scorecard-action to the existing v2.4.4 tag by @gtauzin
- Raise mlflow floor to >=3.13 to keep pyarrow cp314-capable  ([#155](https://github.com/stateful-y/kedro-dagster/pull/155)) by @gtauzin
- Declare a read-only token for tests-versions  ([#157](https://github.com/stateful-y/kedro-dagster/pull/157)) by @gtauzin
- Stop a PR title reaching the release shell as code  ([#158](https://github.com/stateful-y/kedro-dagster/pull/158)) by @gtauzin
- Name the nightly coverage upload and discover every Codecov step  ([#160](https://github.com/stateful-y/kedro-dagster/pull/160)) by @gtauzin
- Unblock PyPI publishing and split the nightly matrix by version  ([#163](https://github.com/stateful-y/kedro-dagster/pull/163)) by @gtauzin

### Refactoring
- Move throwaway build output to .artifacts/ and CODEOWNERS to .github/  ([#159](https://github.com/stateful-y/kedro-dagster/pull/159)) by @gtauzin

### Miscellaneous Tasks
- Fix See Also links and root export 404s in the API docs (template v0.26.1)  ([#123](https://github.com/stateful-y/kedro-dagster/pull/123)) by @gtauzin
- Run pre-commit hooks with prek and filter changelog entries (template v0.27.0)  ([#124](https://github.com/stateful-y/kedro-dagster/pull/124)) by @gtauzin
- Exempt the docs build scripts from ruff's lint rules (template v0.27.3)  ([#129](https://github.com/stateful-y/kedro-dagster/pull/129)) by @gtauzin
- Render API page structure from mkdocstrings templates (template v0.28.1)  ([#130](https://github.com/stateful-y/kedro-dagster/pull/130)) by @gtauzin
- Discover the API surface with Griffe (template v0.28.3)  ([#132](https://github.com/stateful-y/kedro-dagster/pull/132)) by @gtauzin
- Replace stale git hooks by installing with prek install -f (template v0.28.4)  ([#133](https://github.com/stateful-y/kedro-dagster/pull/133)) by @gtauzin
- Make the generated docs build engine-independent (template v0.29.3)  ([#134](https://github.com/stateful-y/kedro-dagster/pull/134)) by @gtauzin
- Replace Dependabot with Renovate for dependency updates (template v0.31.1)  by @gtauzin
- Add pre-push gates and a single CI roll-up check (template v0.32.1)  ([#141](https://github.com/stateful-y/kedro-dagster/pull/141)) by @gtauzin
- Add Versions passed roll-up to gate the version matrix  ([#142](https://github.com/stateful-y/kedro-dagster/pull/142)) by @gtauzin
- Restrict workflow permissions and add secret scanning (template v0.35.0)  ([#143](https://github.com/stateful-y/kedro-dagster/pull/143)) by @gtauzin
- Switch Codecov to OIDC and pin the Scorecard action (template v0.36.0)  ([#144](https://github.com/stateful-y/kedro-dagster/pull/144)) by @gtauzin
- Document signing release tags with gitsign (template v0.37.0)  ([#145](https://github.com/stateful-y/kedro-dagster/pull/145)) by @gtauzin
- Add a CLAUDE.md project-instructions file for AI assistants (template v0.38.0)  ([#146](https://github.com/stateful-y/kedro-dagster/pull/146)) by @gtauzin
- Fix three release-pipeline defects (template v0.39.0)  ([#148](https://github.com/stateful-y/kedro-dagster/pull/148)) by @gtauzin
- Let Renovate see the SBOM tool's version pin (template v0.39.1)  ([#149](https://github.com/stateful-y/kedro-dagster/pull/149)) by @gtauzin
- Add a nightly job that exercises the release path (template v0.40.0)  ([#150](https://github.com/stateful-y/kedro-dagster/pull/150)) by @gtauzin

### Build
- Bump codecov/codecov-action from 6 to 7  ([#115](https://github.com/stateful-y/kedro-dagster/pull/115)) by @dependabot[bot]
- Bump actions/checkout from 6 to 7  ([#116](https://github.com/stateful-y/kedro-dagster/pull/116)) by @dependabot[bot]
- Bump the lint-tools group with 2 updates  ([#125](https://github.com/stateful-y/kedro-dagster/pull/125)) by @dependabot[bot]
- Bump the python-dependencies group with 5 updates  ([#126](https://github.com/stateful-y/kedro-dagster/pull/126)) by @dependabot[bot]
- Bump the lint-tools group with 2 updates  ([#127](https://github.com/stateful-y/kedro-dagster/pull/127)) by @dependabot[bot]
- Bump hypothesis in the python-dependencies group  ([#128](https://github.com/stateful-y/kedro-dagster/pull/128)) by @dependabot[bot]
- Bump gitpython from 3.1.51 to 3.1.55  ([#135](https://github.com/stateful-y/kedro-dagster/pull/135)) by @gtauzin
- Bump aiohttp in the uv group across 1 directory  ([#153](https://github.com/stateful-y/kedro-dagster/pull/153)) by @dependabot[bot]
- Bump gitpython from 3.1.55 to 3.1.58  ([#156](https://github.com/stateful-y/kedro-dagster/pull/156)) by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @dependabot[bot]
- @gtauzin
- @Muhtasim-Munif-Fahim

## [0.7.0] - 2026-06-02

This **minor release** includes 6 commits.

### Miscellaneous Tasks
- Add Python 3.14 support  ([#111](https://github.com/stateful-y/kedro-dagster/pull/111)) by @gtauzin

### Bug Fixes
- Dagster 1.13 compatibility and flaky serdes under xdist  ([#110](https://github.com/stateful-y/kedro-dagster/pull/110)) by @gtauzin
- Fix dg subprocess tests for CI compatibility  ([#113](https://github.com/stateful-y/kedro-dagster/pull/113)) by @gtauzin

### Documentation
- Update license and acknowledgements in index page  ([#105](https://github.com/stateful-y/kedro-dagster/pull/105)) by @gtauzin

### Contributors

Thanks to all contributors for this release:
- @dependabot[bot]
- @gtauzin

## [0.6.0] - 2026-04-04

This **minor release** includes 5 commits.


### Refactoring

- Harmonize project structure and codebase to align with the stateful-y `python-package-copier` template by @gtauzin
- Split CLI from single `cli.py` into `cli/` subpackage with `commands.py` and `functions.py` by @gtauzin
- Consolidate config models from multiple files (`automation.py`, `execution.py`, `job.py`, `kedro_dagster.py`, `logging.py`) into single `config/models.py` by @gtauzin
- Rename test files to match source module names by @gtauzin

### Bug Fixes

- Add `cachetools>=4.1` as an explicit dependency by @gtauzin
- Resolve CI failures in test suite and version matrix by @gtauzin

### Documentation

- Restructure documentation into Diataxis quadrants (tutorials, how-to guides, reference, explanation) by @gtauzin
- Rewrite all docstrings based on NumpyDoc by @gtauzin
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
