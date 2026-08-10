# Available commands for Kedro-Dagster

# Throwaway build output lives under one directory instead of scattering across the
# repo root. `site_dir` must agree with `site_dir` in mkdocs.yml, which is what
# actually decides where the site is written; these recipes only read it.
# `tests/test_artifact_paths.py` asserts the two agree.
artifacts_dir := ".artifacts"
site_dir := artifacts_dir / "site"

# Show all available commands
default:
    @just --list

# Install dependencies and git hooks
install:
    uv sync --group dev
    # -f matters twice over. It overwrites an existing shim instead of chaining it:
    # without it prek finds a pre-v0.27.0 shim, moves it to `.git/hooks/pre-commit.legacy`
    # and CHAINS it -- both run on every commit. And it re-wires the hook set on an
    # existing clone, which is how a clone that installed before `pre-push` was added
    # picks up the pre-push gate instead of leaving it declared-but-never-run.
    uv run prek install -f

# Run tests and doctests with parallel execution
test:
    uv run pytest tests src/kedro_dagster --doctest-modules --doctest-continue-on-failure -n auto -v

# Run fast tests (excludes slow and integration tests)
test-fast:
    uv run pytest -m "not slow and not integration" -n auto -v

# Run slow tests (includes integration tests)
test-slow:
    uv run pytest -m "slow or integration" -n auto -v

# Run tests with coverage
test-cov:
    uv run pytest --cov=kedro_dagster --cov-report=html --cov-report=term -n auto

# Run docstring examples
test-docstrings:
    uv run pytest --doctest-modules --doctest-continue-on-failure --no-cov src/kedro_dagster

# Run fast tests after pinning dependency versions (e.g. just test-compat some-package==1.0.0)
test-compat +PINS='':
    uvx nox -s test_compat -- {{PINS}}

# Run linters and type checkers (read-only; same lock-pinned tools as 'just fix')
lint:
    uv run --locked ruff check src tests
    uv run --locked rumdl check .
    uv run --extra mlflow --locked ty check --exit-zero-on-warning src

# Format and fix code (via prek)
fix:
    uv run prek run --all-files --show-diff-on-failure

# Build documentation (prebuild generates API pages + notebooks; postbuild exports LLM markdown)
build:
    uv run python docs_build/build.py prebuild
    uv run zensical build
    uv run python docs_build/build.py postbuild {{ site_dir }}

# Serve documentation locally with live API regeneration on source edits
serve:
    @echo "###### Starting local server. Press Control+C to stop server ######"
    uv run python docs_build/serve.py

# Check built docs for dead links (build first with 'just build')
link:
    uvx linkchecker {{ site_dir }}/index.html --no-status --no-warnings

# Clean build artifacts
clean:
    rm -rf {{ artifacts_dir }}
    rm -rf build dist *.egg-info
    rm -rf .ty_cache .rumdl_cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete

# Run all quality checks (fix, test)
all: fix test
