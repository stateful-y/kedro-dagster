"""Configuration definitions for Kedro-Dagster schedules.

Defines the schema for schedule entries referenced by jobs in ``dagster.yml``."""

from typing import Any

from pydantic import BaseModel


class ScheduleOptions(BaseModel):
    """Options for defining Dagster schedules.

    Attributes
    ----------
    cron_schedule : str
        Cron expression for the schedule.
    execution_timezone : str or None
        Timezone in which the schedule should execute.
    description : str or None
        Optional description of the schedule.
    metadata : dict[str, Any] or None
        Additional metadata for the schedule.

    Examples
    --------
    ```yaml
    schedules:
        daily_schedule:
            cron_schedule: "0 6 * * *"
            execution_timezone: "UTC"
            description: "Run every morning"
            metadata:
                owner: data-platform
    ```

    See Also
    --------
    `kedro_dagster.dagster.ScheduleCreator.create_schedules` :
        Builds Dagster schedule definitions from these options.
    """

    cron_schedule: str
    execution_timezone: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None
