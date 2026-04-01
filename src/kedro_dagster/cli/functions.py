"""Non-Click helper functions for the Kedro-Dagster CLI commands."""

from logging import getLogger
from pathlib import Path

import click

from kedro_dagster.utils import DAGSTER_VERSION, find_kedro_project, write_jinja_template

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
