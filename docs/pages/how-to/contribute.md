# Contributing to Kedro-Dagster

Thank you for your interest in contributing to Kedro-Dagster! This document provides guidelines for contributing to the project.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and considerate in all interactions.

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended)
- [just](https://github.com/casey/just) (optional, for task automation)
- Git

### Development Setup

1. Fork the repository on GitHub

2. Clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/kedro-dagster.git
cd kedro-dagster
```

3. Install dependencies:

```bash
uv sync --group dev
```

4. Install the git hooks (required):

```bash
uv run prek install -f
```

## Development Workflow

### Making Changes

1. Create a new branch:

```bash
git checkout -b feature/my-feature
```

2. Make your changes

3. Run tests:

=== "just"

    ```bash
    just test
    ```

=== "nox"

    ```bash
    uvx nox -s test
    ```

=== "uv run"

    ```bash
    uv run pytest
    ```

4. Format and fix code:

=== "just"

    ```bash
    just fix
    ```

=== "nox"

    ```bash
    uvx nox -s fix
    ```

=== "uv run"

    ```bash
    uv run ruff format src tests
    uv run ruff check src tests --fix
    uv run ty check src
    ```

5. Commit your changes:

```bash
git add .
git commit -m "feat: add my feature"
```

We follow [Conventional Commits](https://www.conventionalcommits.org/) for commit messages. The format is enforced by a commitizen commit-msg hook, which validates your commit messages automatically.

**Valid commit message examples:**

- `feat: add new feature`
- `fix: resolve bug in calculation`
- `docs: update installation guide`
- `chore: update dependencies`
- `test: add tests for new feature`

### Running Tests

Kedro-Dagster uses pytest with markers to categorize tests into different types:

- **Fast tests**: Unit tests that run quickly without subprocess calls or heavy I/O
- **Slow tests**: Tests marked with `@pytest.mark.slow` that take longer to execute
- **Integration tests**: Tests marked with `@pytest.mark.integration` that run subprocesses or test multiple components together

#### Test Commands

Run fast tests only (recommended during development):

=== "just"

    ```bash
    just test-fast
    ```

=== "nox"

    ```bash
    uvx nox -s test_fast
    ```

=== "uv run"

    ```bash
    uv run pytest -m "not slow and not integration"
    ```

Run slow and integration tests:

=== "just"

    ```bash
    just test-slow
    ```

=== "nox"

    ```bash
    uvx nox -s test_slow
    ```

=== "uv run"

    ```bash
    uv run pytest -m "slow or integration"
    ```

Run all tests:

=== "just"

    ```bash
    just test
    ```

=== "nox"

    ```bash
    uvx nox -s test
    ```

=== "uv run"

    ```bash
    uv run pytest
    ```

Run tests with coverage:

=== "just"

    ```bash
    just test-cov
    ```

=== "nox"

    ```bash
    uvx nox -s test_coverage
    ```

=== "uv run"

    ```bash
    uv run pytest --cov=kedro_dagster --cov-report=html
    ```


Run tests across multiple Python versions:

=== "nox"

    ```bash
    uvx nox -s test
    ```


#### When to Mark Tests as Slow or Integration

Mark your tests appropriately to help maintain fast feedback during development:

- Use `@pytest.mark.slow` for tests that:
    - Take more than a few seconds to run
    - Perform heavy computations
    - Make network requests
    - Access external resources

- Use `@pytest.mark.integration` for tests that:
    - Run subprocess commands
    - Test multiple components working together
    - Require complex setup or teardown
    - Exercise end-to-end workflows


Example:

```python
import pytest

@pytest.mark.slow
def test_large_computation():
    # Long-running test
    pass

@pytest.mark.integration
@pytest.mark.slow
def test_end_to_end_workflow():
    # Complex integration test
    pass
```

#### Test Organization

Follow these conventions when writing tests:

**Class-based test structure**: Group related tests into classes using the `Test<Component><Scenario>` naming pattern.

**Fixture usage**: Prefer fixtures from `conftest.py` over module-level data. See `tests/conftest.py` for available factories.

**Property-based testing**: [Hypothesis](https://hypothesis.readthedocs.io/) is available for property-based testing of edge cases and invariants.

#### CI Test Strategy

The CI pipeline uses a two-tier testing strategy optimized for fast feedback:

1. **Fast tests** (`test-fast` job): Runs on minimum and maximum Python versions (3.11, 3.14) only:
    - **Draft PRs**: Ubuntu only - Quick feedback in ~2-3 minutes
    - **Ready PRs/Main**: All OS - Ubuntu, Windows, macOS - Cross-platform validation

2. **Full test suite** (`test-full` job): Runs all tests (fast + slow + integration) on Ubuntu across all Python versions (3.11-3.14) when the PR is not in draft mode or on the main branch. This comprehensive validation includes coverage reporting on the minimum supported Python version.

### Code Quality

Run linters and type checkers:

=== "just"

    ```bash
    just lint
    ```

=== "nox"

    ```bash
    uvx nox -s lint
    ```

=== "uv run"

    ```bash
    uv run ruff check src tests
    uv run ty check src
    ```

Format code and fix issues:

=== "just"

    ```bash
    just fix
    ```

=== "nox"

    ```bash
    uvx nox -s fix
    ```

=== "uv run"

    ```bash
    uv run ruff format src tests
    uv run ruff check src tests --fix
    uv run ty check src
    ```

Run all quality checks:

=== "just"

    ```bash
    just check
    ```

=== "uv run"

    ```bash
    just fix && just test
    ```

### Docstring Standards

All public functions, methods, and classes require **NumPy-style** docstrings. Coverage is enforced at 100% by `interrogate`.

**Check docstring coverage:**

```bash
uvx interrogate src
```

**Required sections** (as applicable):

- `Parameters` - All function/method parameters with types and descriptions
- `Returns` - Return value type and description
- `Raises` - Exceptions raised
- `See Also` - Related classes/functions
- `References` - Academic references for algorithms or methods used
- `Notes` - Implementation details, mathematical background
- `Examples` - Usage examples (tested via `pytest --doctest-modules`)

**`See Also` format:**

Use standard numpydoc format with short names:

```python
See Also
--------
OtherClass : One-line description of how it relates.
other_function : Another related object.
```

Names are linked to their API pages automatically, whether or not you wrap them
in backticks. Names that cannot be resolved (a private helper, or a concept
rather than an API object) are left as plain text rather than failing the
build, so you can reference anything that reads well.

Fully qualified names work too (`kedro_dagster.module.OtherClass`), and
resolve to the same page as the short form. A member reference
(`OtherClass.method`) links to that member on its class page. A name from
another project (for example `sklearn.linear_model.Ridge`) links to that
project's documentation when its inventory is configured in `mkdocs.yml`.

For hyperlinks, always use Markdown syntax: `[text](url)`.

### Glossary

A glossary is optional. Create `docs/pages/explanation/glossary.md` and define
terms as a definition list, giving each one an explicit anchor:

```markdown
Memory buffer { #memory-buffer .autolink }
:   The internal store of recent rows a stateful component maintains.

Step { #step }
:   One timestep.
```

A term marked `.autolink` has its **first** occurrence on every other page
turned into a link to its definition. The glossary page is the only place terms
are listed, so a definition and its links cannot drift apart.

Opting in is per term because defining a word and advertising it everywhere are
different decisions. A glossary is free to define short, common words such as
`step` above, and auto-linking those wherever prose happens to use them is
noise. Text inside code, headings and existing links is never touched.

### Documentation

Build documentation:

=== "just"

    ```bash
    just build
    ```

=== "nox"

    ```bash
    uvx nox -s build_docs
    ```

=== "uv run"

    ```bash
    uv run python docs_build/build.py prebuild && uv run zensical build
    ```

Serve documentation locally. `just serve` and `nox -s serve_docs` run the
preview supervisor (`docs_build/serve.py`), which watches `src/` and regenerates
the API pages when you add or change a public symbol, so it appears in the
preview without a restart. Raw `zensical serve` still works but is a **static**
preview: it does not regenerate the API pages on a source edit, because that
regeneration is not tied to the documentation engine.

=== "just"

    ```bash
    just serve
    ```

=== "nox"

    ```bash
    uvx nox -s serve_docs
    ```

=== "uv run (static preview)"

    ```bash
    uv run zensical serve
    ```

!!! warning "Empty site with no error? Check your inotify limits"

    If `just build`/`just serve` finishes successfully but produces an **empty**
    site (no pages, no error), the documentation engine could not register the
    source files to watch: your machine's inotify instances are exhausted, which
    is common on a desktop running an editor plus other file watchers. Raise the
    limit and rebuild:

    ```bash
    sudo sysctl fs.inotify.max_user_instances=512
    sudo sysctl fs.inotify.max_user_watches=524288
    ```

    Continuous integration and Read the Docs run in fresh environments and are
    not affected; this only bites busy local machines.

View all available commands:

```bash
just --list
```


## Before You Open a PR

- [ ] Run `just test-fast` - all fast tests pass
- [ ] Run `just fix` - code is formatted and linted
- [ ] Write or update tests for your changes
- [ ] If you changed docs, run `just serve` and verify they render
- [ ] Use conventional commit messages
- [ ] Keep the PR focused on a single concern

## Submitting Changes

1. Push your changes to your fork:

```bash
git push origin feature/my-feature
```

2. Open a Pull Request on GitHub

3. Ensure all CI checks pass

4. Wait for review and address any feedback

## Pull Request Guidelines

- Write clear, descriptive PR titles following Conventional Commits
- Include a description of the changes
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass
- Keep PRs focused and atomic

## Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/) enforced by commitizen:

- `feat:` - New features (triggers minor version bump)
- `fix:` - Bug fixes (triggers patch version bump)
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks
- `perf:` - Performance improvements
- `ci:` - CI/CD changes

**Breaking changes:** Add `!` after the type or add `BREAKING CHANGE:` in the footer to trigger a major version bump.

**Example with scope:**
```bash
git commit -m "feat(api): add new endpoint for user data"
```

**Example with breaking change:**
```bash
git commit -m "feat!: redesign authentication system

BREAKING CHANGE: authentication now requires API keys instead of passwords"
```

The commit-msg hook validates your commit messages and prevents commits that don't follow the
convention. CI validates them again on single-commit PRs, which is the case where your commit
message, not the PR title, becomes the squash commit and lands in the changelog. On a multi-commit
PR the PR title ships instead, and the individual commit messages are free-form.

## Release Process

!!! note "Maintainers only"
    The release process is managed by project maintainers. Contributors do not need to create releases. Open PRs and a maintainer will handle versioning and publishing.

Releases are fully automated through GitHub Actions when a new tag is pushed, with a **manual approval gate** before publishing to PyPI to ensure quality control.

```mermaid
graph LR
    A[Push Tag<br/>v*.*.*] --> B[changelog.yml]
    B --> C[Generate<br/>CHANGELOG.md]
    B --> D[Build Package<br/>validation]
    C --> E[Create PR]
    E --> F[Review & Merge<br/>PR]
    F --> G[publish-release.yml]
    G --> H[Create GitHub<br/>Release]
    H --> I{Manual<br/>Approval}
    I -->|Approve| J[Publish to PyPI]
    style I fill:#f59e0b,stroke:#333,stroke-width:2px,color:#fff
    style J fill:#10b981,stroke:#333,stroke-width:2px,color:#fff
```

### How It Works

1. **Tag a release:**

    ```bash
   git tag v0.2.0 -m "Release v0.2.0"
   git push origin v0.2.0
    ```

2. **Automated changelog workflow** (`changelog.yml`):
    - Generates changelog from conventional commits using git-cliff
    - Creates a **Pull Request** with the updated CHANGELOG.md
    - Builds the package distributions (wheels and sdist) for **immediate validation**
    - Stores distributions as workflow artifacts (reused later to avoid rebuilding)

3. **Review and merge the changelog PR:**
    - A maintainer reviews the generated changelog
    - Once approved, merge the PR to main

4. **Automated release workflow** (`publish-release.yml`):
    - Creates a GitHub Release with generated release notes
    - Attaches distribution files to the release
    - **Waits for manual approval** before proceeding to PyPI

5. **Manual approval for PyPI publishing:**
    - Designated reviewers receive a notification
    - Review the GitHub Release to verify everything is correct
    - Approve the deployment to publish to PyPI
    - Package is published using Trusted Publishing (OIDC, no tokens needed)

6. **Release notes generation:**
    - All commits since the last tag are analyzed
    - Commits are grouped by type (Added, Fixed, Documentation, etc.)
    - Only commits following conventional format are included
    - Breaking changes are highlighted

### Version Numbering

This project uses [Semantic Versioning](https://semver.org/):

- **Major** (1.0.0): Breaking changes
- **Minor** (0.1.0): New features (backward compatible)
- **Patch** (0.0.1): Bug fixes (backward compatible)

Use conventional commits to communicate the type of change, and select the appropriate version number when tagging.

## Questions?

If you have any questions, feel free to:

- [Open an issue on GitHub](https://github.com/stateful-y/kedro-dagster/issues/new)
- [Start a discussion in the repository](https://github.com/stateful-y/kedro-dagster/discussions)

Thank you for contributing! 🎉
