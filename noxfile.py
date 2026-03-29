"""Nox sessions for Kedro-Dagster."""

from pathlib import Path

import nox

# Require Nox version 2024.3.2 or newer to support the 'default_venv_backend' option
nox.needs_version = ">=2024.3.2"

# Set 'uv' as the default backend for creating virtual environments
nox.options.default_venv_backend = "uv|virtualenv"

# Default sessions to run when nox is called without arguments
nox.options.sessions = ["fix", "test_fast", "serve_docs"]

# Generate list of Python versions from minimum to maximum
ALL_VERSIONS = ["3.11", "3.12", "3.13", "3.14"]
MIN_VERSION = "3.11"
MAX_VERSION = "3.13"
PYTHON_VERSIONS = [v for v in ALL_VERSIONS if v >= MIN_VERSION and v <= MAX_VERSION]


@nox.session(python=PYTHON_VERSIONS[0], venv_backend="uv")
def test_coverage(session: nox.Session) -> None:
    """Run the tests with pytest and coverage under the default Python version."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--extra",
        "mlflow",
        "--no-default-groups",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run unit tests with pytest-cov for coverage collection.
    # pytest-cov natively handles xdist workers (-n auto) so we rely on
    # --cov from addopts rather than wrapping with ``coverage run``.
    session.run(
        "pytest",
        "tests",
        "-n",
        "auto",
        f"--junitxml=junit.{session.python}.xml",
        *session.posargs,
    )


@nox.session(python=PYTHON_VERSIONS, venv_backend="uv")
def test(session: nox.Session) -> None:
    """Run the test suite across multiple Python versions (no coverage)."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--extra",
        "mlflow",
        "--no-default-groups",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run unit tests and doctests with parallel execution
    session.run(
        "pytest",
        "tests",
        "src/kedro_dagster",
        "--doctest-modules",
        "--doctest-continue-on-failure",
        "-n",
        "auto",
        "-v",
        *session.posargs,
    )


@nox.session(python=PYTHON_VERSIONS, venv_backend="uv")
def test_fast(session: nox.Session) -> None:
    """Run fast tests (excludes slow and integration tests)."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run fast tests only with parallel execution
    # --no-cov disables coverage (from addopts) so it cannot fail this step
    session.run(
        "pytest",
        "tests",
        "--no-cov",
        "-m",
        "not slow and not integration",
        "-n",
        "auto",
        "-v",
        *session.posargs,
    )


@nox.session(python=PYTHON_VERSIONS, venv_backend="uv")
def test_slow(session: nox.Session) -> None:
    """Run slow and integration tests."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run slow/integration tests only with parallel execution
    session.run(
        "pytest",
        "tests",
        "-m",
        "slow or integration",
        "-n",
        "auto",
        "-v",
        *session.posargs,
    )


@nox.session(python=PYTHON_VERSIONS, venv_backend="uv")
def test_compat(session: nox.Session) -> None:
    """Run fast tests after pinning one or more dependency versions.

    Usage::

        uvx nox -s test_compat -- some-package==1.0.0
        uvx nox -s test_compat -- some-package==1.0.0 other-package==2.0.0

    Each positional argument must be a pip requirement specifier
    (e.g. ``package==version``).  If none are given the session runs
    with the default (latest compatible) versions.
    """
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Downgrade / pin requested packages
    if session.posargs:
        session.run(
            "uv",
            "pip",
            "install",
            *session.posargs,
            "--python",
            session.virtualenv.location + "/bin/python",
        )

    # Run fast tests
    session.run(
        "pytest",
        "tests",
        "--no-cov",
        "-m",
        "not slow and not integration",
        "-n",
        "auto",
        "-v",
    )


@nox.session(venv_backend="uv")
def test_docstrings(session: nox.Session) -> None:
    """Run docstring examples with pytest."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "tests",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run doctest on source code
    session.run(
        "pytest",
        "--doctest-modules",
        "--doctest-continue-on-failure",
        "--no-cov",
        "src/kedro_dagster",
        *session.posargs,
    )


@nox.session(venv_backend="uv")
def lint(session: nox.Session) -> None:
    """Run linters and type checkers."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "lint",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run ruff check
    session.run("ruff", "check", "src", "tests", external=True)

    # Run rumdl markdown linter
    session.run("uvx", "rumdl", "check", ".", external=True)

    # Run ty
    session.run("ty", "check", "src", external=True)


@nox.session(venv_backend="uv")
def fix(session: nox.Session) -> None:
    """Format the code base to adhere to our styles, and complain about what we cannot do automatically."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "dev",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )
    # Run pre-commit
    session.run("pre-commit", "run", "--all-files", "--show-diff-on-failure", *session.posargs, external=True)


@nox.session(venv_backend="uv")
def build_docs(session: nox.Session) -> None:
    """Build the documentation."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Build the docs (hooks automatically export notebooks and prepare site)
    session.run("mkdocs", "build", "--clean", external=True)


@nox.session(venv_backend="uv")
def serve_docs(session: nox.Session) -> None:
    """Run a development server for working on documentation."""
    # Install dependencies
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Serve the docs (hooks automatically export notebooks and prepare site)
    session.log("###### Starting local server. Press Control+C to stop server ######")
    session.run("mkdocs", "serve", "-a", "localhost:8080", external=True)


@nox.session(venv_backend="uv")
def link_docs(session: nox.Session) -> None:
    """Check the built documentation for dead links."""
    site_dir = Path("site")
    if not site_dir.exists():
        session.error("site/ directory not found. Run 'just build' or 'nox -s build_docs' first.")

    session.run(
        "uvx",
        "linkchecker",
        str(site_dir / "index.html"),
        "--no-status",
        "--no-warnings",
        "--ignore-url",
        "material/overrides",
        *session.posargs,
        external=True,
    )


# --------------------------------------------------------------------------------------
# [ADDITION] Project-specific: Kedro/Dagster version matrix testing
# --------------------------------------------------------------------------------------
KEDRO_SPECS = [
    "kedro>=0.19,<1.0",
    "kedro>=1.0,<2.0",
]

DAGSTER_SPECS = [
    "dagster>=1.10,<1.11",
    "dagster>=1.11,<1.12",
    "dagster>=1.12,<1.13",
]


@nox.session(python=PYTHON_VERSIONS, venv_backend="uv")
@nox.parametrize("kedro_spec", KEDRO_SPECS)
@nox.parametrize("dagster_spec", DAGSTER_SPECS)
@nox.parametrize("with_mlflow", [False, True])
def test_versions(session: nox.Session, dagster_spec: str, kedro_spec: str, with_mlflow: bool) -> None:
    """Run the test suite across a matrix of Kedro and Dagster versions."""
    # Install base deps (tests group + optional mlflow extra)
    sync_args = [
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "tests",
    ]
    if with_mlflow:
        sync_args += ["--extra", "mlflow"]
    session.run_install(*sync_args, env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location})

    # Install specific Kedro / Dagster lines for this run
    webserver_spec = dagster_spec.replace("dagster", "dagster-webserver", 1)
    dg_cli_spec = dagster_spec.replace("dagster", "dagster-dg-cli", 1)

    session.run_install(
        "uv",
        "pip",
        "install",
        kedro_spec,
        dagster_spec,
        webserver_spec,
        dg_cli_spec,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Unit tests directly (no coverage for version tests)
    session.run(
        "pytest",
        "tests",
        *session.posargs,
    )
