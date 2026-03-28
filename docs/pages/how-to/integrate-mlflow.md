# How to Integrate with MLflow

If your Kedro project uses [kedro-mlflow](https://github.com/Galileo-Galilei/kedro-mlflow) for experiment tracking, Kedro-Dagster automatically captures MLflow run information and displays it in the Dagster UI. See the [Kedro-MLflow documentation](https://kedro-mlflow.readthedocs.io/en/stable/) for setting up MLflow tracking in Kedro.

## What happens automatically

When a Kedro node executes within a Dagster context and an active MLflow run is detected, Kedro-Dagster:

1. **Captures run metadata**: Extracts experiment ID, run ID, and tracking URI from the active MLflow run.
2. **Generates run URLs**: Creates clickable links to view the MLflow run in the MLflow UI.
3. **Logs to Dagster**: Records MLflow run information in Dagster logs, run tags, and asset materialization metadata.

No Dagster-specific MLflow code is needed - Kedro-MLflow hooks fire automatically during Dagster runs.

## Configure MLflow for your project

Add an `mlflow.yml` to each environment's configuration directory (`conf/<ENV>/mlflow.yml`). Models and artifacts are tracked via Kedro-MLflow datasets in the catalog:

```yaml
"{namespace}.{variant}.regressor":
   type: kedro_mlflow.io.models.MlflowModelTrackingDataset
   flavor: mlflow.sklearn
   artifact_path: "{namespace}/{variant}/regressor"
```

See the [Example Project](../tutorials/example-project.md#mlflow-integration) for a complete multi-environment MLflow setup with Optuna integration.
