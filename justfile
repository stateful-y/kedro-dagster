# Available commands for Kedro-Dagster

# Show all available commands
default:
    @just --list

# Install dependencies and git hooks
install:
    uv sync --group dev
    # -f matters: without it prek finds a pre-v0.27.0 shim, moves it to
    # `.git/hooks/pre-commit.legacy` and CHAINS it -- both hooks then run on
    # every commit. `-f` overwrites instead. Measured; the migration notice
    # prek prints names this flag, and this is the command people actually run.
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
    uv run mkdocs build --clean
    uv run python docs_build/build.py postbuild site

# Serve documentation locally with live API regeneration on source edits
serve:
    @echo "###### Starting local server. Press Control+C to stop server ######"
    uv run python docs_build/serve.py

# Check built docs for dead links (build first with 'just build')
link:
    uvx linkchecker site/index.html --no-status --no-warnings --ignore-url 'material/overrides'

# Clean build artifacts
clean:
    rm -rf .nox
    rm -rf build dist *.egg-info
    rm -rf .pytest_cache .ty_cache .ruff_cache
    rm -rf htmlcov .coverage coverage.xml
    rm -rf site
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete

# Run all quality checks (fix, test)
all: fix test
