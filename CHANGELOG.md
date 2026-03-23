# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.4]

### Bug Fixes

- Update all repository references from `gtauzin` to `stateful-y` org by @gtauzin.
- Handle Dagster 1.12 `asset_key` rename in `dg list defs` test output by @gtauzin.

### Contributors

- @gtauzin

## [0.5.3]

### Bug Fixes

- Fix `DagsterPartitionedDataset` initialisation by ensuring `_partition_cache` is set before calling `super().__init__()` by @gtauzin.

### Contributors

- @gtauzin

## [0.5.2]

### Bug Fixes

- Fix pin on kedro dependency to support all kedro 1.x versions by @gtauzin.

### Contributors

- @gtauzin

## [0.5.1]

### Bug Fixes

- Fix `dg.toml` template as it was not working out-of-the-box for new projects by @gtauzin.

### Documentation

- Enhanced explanation of Dagster partitions integration goals and architecture in the user guide by @gtauzin.

### Contributors

- @gtauzin

## [0.5.0]

### Features

- Add comprehensive logging throughout the translation process with `LOGGER.info()` for major steps and `LOGGER.debug()` for detailed progress tracking by @gtauzin.
- Add FAQ documentation page with common questions, troubleshooting guides, and production deployment considerations by @gtauzin.
- Expand user guide documentation with detailed `DagsterPartitionedDataset` usage examples and migration guides by @gtauzin.
- Restrict `DagsterPartitionedDataset` to only support `StaticPartitionsDefinition`, `StaticPartitionMapping`, and `IdentityPartitionMapping` with clear validation errors for unsupported partition types by @gtauzin.

### Bug Fixes

- Fix missing `after_catalog_created` hook invocation in Dagster job execution by @gtauzin.
- Pass catalog directly to translators instead of accessing via context to avoid potential stale catalog references by @gtauzin.
- Improve error messages throughout the codebase with better context and available options by @gtauzin.
- Add detailed property docstrings to `KedroRunResource` for better API documentation by @gtauzin.
- Rename Technical documentation to User guide and update links accordingly by @gtauzin.

### Breaking Changes

- `KedroRunTranslator` now requires `catalog` as an explicit parameter instead of accessing it from `context.catalog` by @gtauzin.
- `PipelineTranslator` now requires `catalog` as an explicit parameter instead of accessing it from `context.catalog` by @gtauzin.
- `DagsterPartitionedDataset` now raises `NotImplementedError` at instantiation for unsupported partition types (`TimeWindowPartitionsDefinition`, `MultiPartitionsDefinition`, `DynamicPartitionsDefinition`) instead of at runtime by @gtauzin.
- `DagsterPartitionedDataset` now raises `NotImplementedError` at instantiation for unsupported partition mappings (anything other than `StaticPartitionMapping` and `IdentityPartitionMapping`) by @gtauzin.

### Contributors

- @gtauzin

## [0.4.0]

### Features

- Wrap all Dagster `dg` CLI commands to be run from within a Kedro project with `kedro dagster <dg command>` by @gtauzin.
- Add a `kedro_dagster.logging` module meant to replace `logging` imports in Kedro nodes so loggers are captured and integrated with Dagster by @gtauzin.
- Add `loggers` section to `dagster.yml` configuration file to configure Dagster run loggers by @gtauzin.
- Rename `LoggerTranslator` to `LoggerCreator` for consistency with `ExecutorCreator` and `SchedulerCreator` by @gtauzin.
- Declare direct dependency on `pydantic>=1.0.0,<3.0.0` and enable version-agnostic Pydantic configuration by @gtauzin.
- Add conda-forge support for Kedro-Dagster, allowing installation with `conda` or `mamba` by @rxm7706 and @gtauzin.
- Allow setting `group_name` in a dataset's `metadata` to override the pipeline-derived group name; `group_name` is also applied per-AssetOut for multi-assets so each asset can have an individual group by @gtauzin.
- Add links to MLflow run in Dagster run logs, run tags, and materialized asset metadata by @gtauzin.

### Bug Fixes

- Fix how `LoggerCreator` creates loggers for Dagster runs. Generic logging configuration is now supported from `dagster.yml` by @gtauzin.

### Breaking Changes

- Make `env` a required parameter of `KedroProjectTranslator` by @gtauzin.
- Remove `dev` config in `dagster.yml` by @gtauzin.

### Contributors

- @gtauzin
- @rxm7706

## [0.3.0]

### Features

- Add `DagsterNothingDataset`, a Kedro dataset that performs no I/O but enforces node dependency by @gtauzin.
- Add `DagsterPartitionedDataset`, a Kedro dataset for partitioned data compatible with Dagster's asset partitions by @gtauzin.
- Enable fanning out Kedro nodes when creating the Dagster graph when using `DagsterPartitionedDataset` with multiple partition keys by @gtauzin.
- Add support for Kedro >= 1.0.0 and Dagster >= 1.12.0 by @gtauzin.

### Bug Fixes

- Fix bug involving unnamed Kedro nodes making `kedro dagster dev` crash by @gtauzin.
- Fix defaults on K8S execution configuration by @gtauzin.

### Contributors

- @gtauzin

## [0.2.0]

This release is a complete refactoring of Kedro-Dagster and its first stable version.

### Contributors

- @gtauzin

## [0.1.1]

### Bug Fixes

- Fixed CLI entrypoint by @gtauzin.
- Set up documentation, behavior tests, unit tests and CI by @gtauzin.

### Contributors

- @gtauzin

## [0.1.0]

Initial release of Kedro-Dagster.

### Contributors

- @gtauzin

<!-- generated by git-cliff -->
