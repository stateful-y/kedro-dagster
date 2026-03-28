# How to Integrate with MLflow

Kedro-Dagster provides seamless integration with MLflow when using [kedro-mlflow](https://github.com/Galileo-Galilei/kedro-mlflow) for experiment tracking. When MLflow is configured in your Kedro project, Kedro-Dagster automatically captures MLflow run information and displays it in the Dagster UI. Checkout the [Kedro-MLflow documentation](https://kedro-mlflow.readthedocs.io/en/stable/) for details on setting up MLflow tracking in Kedro.

## Automatic MLflow run tracking

When a Kedro node executes within a Dagster context and the active MLflow run triggered by the Kedro-MLflow hook is detected, Kedro-Dagster automatically:

1. **Captures run metadata**: Extracts experiment ID, run ID, and tracking URI from the active MLflow run
2. **Generates run URLs**: Creates clickable links to view the MLflow run in the MLflow UI
3. **Logs to Dagster**: Records MLflow run information in Dagster logs for easy access and debugging

Those details appear in the Dagster run logs, run tags, and asset materialization metadata, allowing users to quickly navigate between Dagster runs and their corresponding MLflow experiments.
