"""Nox sessions for Kedro-Dagster."""

from pathlib import Path

import nox

# Require Nox version 2024.3.2 or newer to support the 'default_venv_backend' option
nox.needs_version = ">=2024.3.2"

# Set 'uv' as the default backend for creating virtual environments
nox.options.default_venv_backend = "uv|virtualenv"

# Default sessions to run when nox is called without arguments
nox.options.sessions = ["fix", "test_fast", "serve_docs"]

# Keep the session virtualenvs under `.artifacts/` with every other piece of
# throwaway output, instead of dropping a `.nox/` at the repo root.
nox.options.envdir = ".artifacts/nox"

# The single definition of where build output goes. Anything that writes or reads
# a throwaway path derives it from here rather than spelling it out again: a path
# written in one place and read in another is how the coverage upload came to name
# a file nothing produced. `tests/test_artifact_paths.py` enforces that.
ARTIFACTS_DIR = Path(".artifacts")
JUNIT_XML = ARTIFACTS_DIR / "junit.xml"
SITE_DIR = ARTIFACTS_DIR / "site"

# Generate list of Python versions from minimum to maximum
ALL_VERSIONS = ["3.11", "3.12", "3.13", "3.14"]
MIN_VERSION = "3.11"
MAX_VERSION = "3.14"
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
        f"--junitxml={JUNIT_XML}",
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
    # Install dependencies. --locked pins the exact uv.lock versions so this matches
    # CI; --extra mlflow lets ty resolve the optional mlflow code paths.
    session.run_install(
        "uv",
        "sync",
        "--locked",
        "--no-default-groups",
        "--extra",
        "mlflow",
        "--group",
        "lint",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Run ruff check
    session.run("ruff", "check", "src", "tests", external=True)

    # Run rumdl markdown linter (resolved from the lint group, not uvx-latest)
    session.run("rumdl", "check", ".", external=True)

    # Run ty (warnings are non-fatal; demoted rules in [tool.ty.rules] stay visible)
    session.run("ty", "check", "--exit-zero-on-warning", "src", external=True)


# Unlike every other session, this one owns no environment. `uv run --locked` resolves
# prek from uv.lock, and each local hook resolves its own tool from that same project
# environment. A nox venv here would be a second environment that only ever holds the
# runner -- which is the redundant install this session used to pay for on every run.
@nox.session(venv_backend="none")
def fix(session: nox.Session) -> None:
    """Format the code base to adhere to our styles, and complain about what we cannot do automatically."""
    # Run at the pre-push stage. A hook with no `stages:` key runs at every stage, so this
    # one pass covers the full suite: the autofixing formatters AND the pre-push gates (ty,
    # interrogate, no-rst-citations), while excluding commitizen (pinned to commit-msg). A
    # plain `prek run` uses the pre-commit stage, which since those gates moved to pre-push
    # would silently skip them -- here and in the CI lint job that runs this session, a
    # green check measuring nothing. --locked pins the exact uv.lock versions, so a stale
    # lock fails loudly and local matches CI, and it keeps prek pinned -- never `uvx prek`.
    session.run(
        "uv",
        "run",
        "--locked",
        "prek",
        "run",
        "--all-files",
        "--show-diff-on-failure",
        "--stage",
        "pre-push",
        *session.posargs,
        external=True,
    )


@nox.session(python=PYTHON_VERSIONS[0], venv_backend="uv")
def build_steps(session: nox.Session) -> None:
    """Run the documentation build steps without building the site.

    Pinned to the lowest supported Python for the same reason ``check_docs`` is:
    an unpinned session takes whatever interpreter the caller happens to have,
    which can sit outside ``requires-python`` and die in ``uv sync`` before any
    step runs. Two projects in this fleet cap at 3.13, so on a machine defaulting
    to 3.14 an unpinned session fails for a reason that has nothing to do with
    the docs.

    ``docs_build/build.py prebuild`` runs these before ``mkdocs build`` (and the
    serve supervisor runs them on a source edit), the explicit commands that
    replaced the mkdocs build hooks no engine but MkDocs executes. None of them
    needs a theme, a server or a markdown renderer -- they read the filesystem and
    write it. This session runs them on their own: to see the generated API pages,
    to re-export the notebooks, or to get a stack trace not buried in a build.

    ``_markdown_export`` (the ``postbuild`` step) is deliberately not run here: its
    input is a site directory a previous build produced, so it has nothing to
    convert until ``build_docs`` has run.
    """
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    session.run("python", "docs_build/_api_pages.py", external=True)


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

    # Generate the API pages and export the notebooks, build, then export the LLM
    # markdown -- the explicit steps that replaced the deleted mkdocs build hooks.
    session.run("python", "docs_build/build.py", "prebuild", external=True)
    session.run("zensical", "build", external=True)
    session.run("python", "docs_build/build.py", "postbuild", str(SITE_DIR), external=True)


@nox.session(python=PYTHON_VERSIONS[0], venv_backend="uv")
def check_docs(session: nox.Session) -> None:
    """Build the docs with warnings fatal, without executing the notebooks.

    Pinned to the lowest supported Python rather than whatever the caller happens
    to have: an unpinned session takes the ambient interpreter, which can sit
    outside requires-python and die in `uv sync` before mkdocs runs. CI only
    passes today because the runner's default happens to be in range -- a runner
    bumped past the ceiling would turn this red for a reason that has nothing to
    do with the docs.

    docs_build/_markers.py warns when a marker resolves to nothing, because a
    placeholder that renders nothing looks exactly like a page that never had one
    -- the warning is the only signal that a page silently lost its content. That
    signal is worthless unless something fails on it, which is what this session is for.

    A full build is too slow to run on every PR: exporting the notebooks executes
    every one of them and dominates the time. MKDOCS_SKIP_NOTEBOOKS skips only the
    export -- the gallery still parses every notebook's source, so sections,
    companions and cards resolve exactly as they do in a real build, which is what
    the markers depend on. build_docs remains the real, notebook-executing build.
    """
    session.run_install(
        "uv",
        "sync",
        "--no-default-groups",
        "--group",
        "docs",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Generate the API pages first (skipping notebook execution) so the markers
    # resolve, then run the strict build. This is what on_pre_build used to do.
    session.run(
        "python",
        "docs_build/build.py",
        "prebuild",
        external=True,
        env={"MKDOCS_SKIP_NOTEBOOKS": "1"},
    )
    session.run(
        "zensical",
        "build",
        "-s",
        external=True,
        env={"MKDOCS_SKIP_NOTEBOOKS": "1"},
    )


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

    # Serve via the supervisor: it regenerates the API pages when src/ changes,
    # so a new class appears without a restart, without relying on a hook.
    session.log("###### Starting local server. Press Control+C to stop server ######")
    session.run("python", "docs_build/serve.py", external=True)


@nox.session(venv_backend="uv")
def link_docs(session: nox.Session) -> None:
    """Check the built documentation for dead links."""
    site_dir = SITE_DIR
    if not site_dir.exists():
        session.error(f"{site_dir}/ not found. Run 'just build' or 'nox -s build_docs' first.")

    session.run(
        "uvx",
        "linkchecker",
        str(site_dir / "index.html"),
        "--no-status",
        "--no-warnings",
        *session.posargs,
        external=True,
    )


KEDRO_SPECS = [
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

    pin_specs = [kedro_spec, dagster_spec, webserver_spec, dg_cli_spec]
    # Re-resolve dagster-mlflow so it matches the pinned dagster version;
    # otherwise the latest dagster-mlflow (installed by --extra mlflow) may
    # be incompatible with the pinned dagster.  dagster-mlflow uses its own
    # version scheme (0.x) so we cannot derive a range from dagster_spec.
    if with_mlflow:
        pin_specs.append("dagster-mlflow")

    session.run_install(
        "uv",
        "pip",
        "install",
        *pin_specs,
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )

    # Unit tests directly (no coverage for version tests)
    session.run(
        "pytest",
        "tests",
        *session.posargs,
    )
