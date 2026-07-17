# How-to Guides

Practical directions for common tasks. Each guide addresses a specific goal and assumes you already have a working Kedro-Dagster setup.

- **[How to Configure Logging](configure-logging.md)**: Unify Kedro and Dagster logs and customize formatters.
- **[How to Configure Custom Executors](configure-executors.md)**: Set up multiprocess, Docker, Kubernetes, Dask, or Celery executors.
- **[How to Use Job Factories](use-job-factories.md)**: Replace repeated per-namespace jobs with a single templated factory.
- **[How to Use Dagster Partitions](use-partitions.md)**: Define partitioned datasets and map partitions across your pipeline.
- **[How to Use MLflow](use-mlflow.md)**: Track experiments and artifacts with Kedro-MLflow and Dagster.
- **[How to Deploy to Production](deploy-to-production.md)**: Move from local dev to a production Dagster deployment.
- **[Troubleshoot](troubleshoot.md)**: Diagnose and resolve common issues.
- **[Contributing to Kedro-Dagster](contribute.md)**: Development setup, workflow, and project standards.

Bringing a project you already have across to Dagster is covered by the [Migrate an Existing Project](../tutorials/migrate-existing-project.md) tutorial.
