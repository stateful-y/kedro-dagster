"""Non-Click helper functions for the Kedro-Dagster CLI commands."""

from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from kedro_dagster.utils import DAGSTER_VERSION, find_kedro_project, write_jinja_template

if TYPE_CHECKING:
    from kedro_dagster.config import KedroDagsterConfig, ScheduleOptions

LOGGER = getLogger(__name__)
TEMPLATE_FOLDER_PATH = Path(__file__).parent.parent / "templates"


def scaffold_dagster_files(env: str, force: bool, silent: bool) -> None:
    """Scaffold or refresh Dagster integration files for the current Kedro project.

    Creates or updates the Dagster configuration and entry points so the project
    can be run from Dagster. Existing files are preserved unless ``force`` is used.
    The Python package name is inferred from the Kedro project metadata.

    Parameters
    ----------
    env : str
        Kedro environment under ``conf`` where ``dagster.yml`` is written.
    force : bool
        Overwrite existing files without prompting.
    silent : bool
        Suppress success messages for a quieter output.
    """
    # Lazy import to avoid circular dependency
    from kedro.framework.project import settings
    from kedro.framework.startup import bootstrap_project

    dagster_yml = "dagster.yml"
    project_path = find_kedro_project(Path.cwd()) or Path.cwd()
    project_metadata = bootstrap_project(project_path)
    package_name = project_metadata.package_name
    dagster_yml_path = project_path / settings.CONF_SOURCE / env / dagster_yml

    if dagster_yml_path.is_file() and not force:
        click.secho(
            click.style(
                f"A 'dagster.yml' already exists at '{dagster_yml_path}' You can use the ``--force`` option to override it.",
                fg="red",
            )
        )
    else:
        try:
            write_jinja_template(
                src=TEMPLATE_FOLDER_PATH / dagster_yml,
                is_cookiecutter=False,
                dst=dagster_yml_path,
                python_package=package_name,
            )
            if not silent:
                click.secho(
                    click.style(
                        f"'{settings.CONF_SOURCE}/{env}/{dagster_yml}' successfully updated.",
                        fg="green",
                    )
                )
        except FileNotFoundError:
            click.secho(
                click.style(
                    f"No env '{env}' found. Please check this folder exists inside '{settings.CONF_SOURCE}' folder.",
                    fg="red",
                )
            )

    definitions_py = "definitions.py"
    definitions_py_path = project_path / "src" / package_name / definitions_py

    if definitions_py_path.is_file() and not force:
        click.secho(
            click.style(
                f"A 'definitions.py' already exists at '{definitions_py_path}' You can use the ``--force`` option to override it.",
                fg="red",
            )
        )
    else:
        write_jinja_template(
            src=TEMPLATE_FOLDER_PATH / definitions_py,
            is_cookiecutter=False,
            dst=definitions_py_path,
            python_package=package_name,
        )
        if not silent:
            click.secho(
                click.style(
                    f"'src/{package_name}/{definitions_py}' successfully updated.",
                    fg="green",
                )
            )
    if DAGSTER_VERSION >= (1, 10, 6):
        # Create/Update the project's dg.toml from template
        # - 'project_name' in the template refers to the Python root module (i.e., package name)
        # - 'package_name' in the template refers to the display project name
        dg_toml = "dg.toml"
        dg_toml_path = project_path / dg_toml

        if dg_toml_path.is_file() and not force:
            click.secho(
                click.style(
                    f"A 'dg.toml' already exists at '{dg_toml_path}' You can use the ``--force`` option to override it.",
                    fg="red",
                )
            )
        else:
            write_jinja_template(
                src=TEMPLATE_FOLDER_PATH / dg_toml,
                is_cookiecutter=False,
                dst=dg_toml_path,
                # Map template variables appropriately
                project_name=package_name,
                package_name=project_metadata.project_name,
            )
            if not silent:
                click.secho(
                    click.style(
                        f"'{dg_toml}' successfully updated.",
                        fg="green",
                    )
                )


def _load_config_and_pipelines(env: str) -> tuple["KedroDagsterConfig", dict[str, Any]]:
    """Load the Dagster config and the registered pipelines for *env*.

    Bootstraps the Kedro project, opens a session, and reads the Dagster
    configuration plus the project's registered pipelines. These are the same
    inputs the translator feeds to the job factory, obtained without building a
    Dagster code location.

    Parameters
    ----------
    env : str
        Kedro configuration environment to load.

    Returns
    -------
    tuple[KedroDagsterConfig, dict[str, Any]]
        The parsed Dagster configuration and the registered pipelines by name.
    """
    # Lazy imports to avoid circular dependency and keep CLI import light
    from kedro.framework.project import pipelines
    from kedro.framework.session import KedroSession
    from kedro.framework.startup import bootstrap_project

    from kedro_dagster.config import get_dagster_config

    project_path = find_kedro_project(Path.cwd()) or Path.cwd()
    bootstrap_project(project_path)
    # Mirror `KedroProjectTranslator.initialize_kedro`: assign the created session
    # (typed `KedroSession`) rather than binding the `with ... as` target, whose
    # `AbstractSession` type lacks `load_context`.
    session = KedroSession.create(project_path=project_path, env=env)
    context = session.load_context()
    dagster_config = get_dagster_config(context)
    # Materialize the lazy pipeline registry into a plain dict.
    registered_pipelines = dict(pipelines)
    return dagster_config, registered_pipelines


def _format_schedule(schedule: "ScheduleOptions | str") -> str:
    """Render a job's schedule (named reference or inline options) for display."""
    if isinstance(schedule, str):
        return schedule
    return getattr(schedule, "cron_schedule", None) or "<inline>"


def resolve_job_patterns(env: str) -> None:
    """Print the concrete jobs derived from the job factories and pipelines.

    The analogue of ``kedro catalog resolve-patterns``: renders every job factory
    against the active pipeline namespaces (plus any literal jobs) and lists the
    resulting job names with their pipeline, node namespaces, and schedule. No
    Dagster code location is constructed.

    Parameters
    ----------
    env : str
        Kedro configuration environment to load.
    """
    from kedro_dagster.factory import enumerate_jobs

    dagster_config, registered_pipelines = _load_config_and_pipelines(env)
    jobs = enumerate_jobs(dagster_config, registered_pipelines)
    if not jobs:
        click.echo("No jobs resolved (no job factories or literal jobs in dagster.yml).")
        return
    for name in sorted(jobs):
        job = jobs[name]
        detail = [f"pipeline={job.pipeline.pipeline_name}"]
        namespaces = ", ".join(job.pipeline.node_namespaces or [])
        if namespaces:
            detail.append(f"namespaces=[{namespaces}]")
        if job.schedule:
            detail.append(f"schedule={_format_schedule(job.schedule)}")
        click.echo(f"{name}  ({'; '.join(detail)})")


def list_job_patterns(env: str) -> None:
    """List the job-factory keys (``jobs`` keys containing ``{placeholder}`` markers).

    The analogue of ``kedro catalog list-patterns``. Literal (non-factory) job
    keys are not listed.

    Parameters
    ----------
    env : str
        Kedro configuration environment to load.
    """
    from kedro_dagster.factory import is_factory

    dagster_config, _ = _load_config_and_pipelines(env)
    patterns = sorted(key for key in (dagster_config.jobs or {}) if is_factory(key))
    if not patterns:
        click.echo("No job factory patterns defined in dagster.yml.")
        return
    for pattern in patterns:
        click.echo(pattern)
