---
name: diataxis-reference-writer
description: Generate and structure information-oriented reference documentation for Python packages following Diátaxis principles. Use when asked to write API reference docs, CLI reference, configuration reference, error code reference, or any documentation that provides austere technical description of the machinery. Triggers on "write reference docs", "API documentation", "document the API", "CLI reference", "configuration reference", "error reference", "describe the interface".
---

# Diátaxis Reference Writer

Generate reference documentation — information-oriented technical descriptions of the machinery, meant to be consulted, not read.

Reference material is like a **map**: it describes the territory accurately so the user can navigate it confidently while working. It is austere, authoritative, and free of interpretation.

## File Placement

Place reference pages in `docs/pages/reference/`. Example: `docs/pages/reference/api.md`.

## What Reference Is

- Technical description of the machinery and how to operate it
- Propositional knowledge the user looks to while working
- Led by the **product structure**, not by user needs
- Purpose: describe, as succinctly as possible, in an orderly way

Reference is what the user needs while they are at work — applying their existing skills.

## Generation Workflow

### Step 1: Map the API Surface

- Scan `src/<package>/` for all public modules
- Within each module, identify public classes, functions, constants, type aliases
- Note the module hierarchy: package → subpackages → modules → classes → methods
- Check `__all__` exports if defined
- Identify CLI entry points from `pyproject.toml` `[project.scripts]`
- Find configuration schemas, settings classes, env var definitions

### Step 2: Mirror the Code Structure

The documentation structure must reflect the code structure — like a map reflects territory. If a method belongs to a class in a module, the docs should show the same hierarchy.

```text
reference/
  api.md              # or split per module:
  api/
    module_a.md       # mirrors src/<package>/module_a.py
    module_b.md       # mirrors src/<package>/module_b.py
  cli.md              # mirrors CLI commands
  configuration.md    # mirrors settings/config
```

### Step 3: Write the Reference

Apply all key principles below. For API docs, prefer mkdocstrings auto-generation with well-written docstrings over hand-written reference.

## Key Principles

### Describe and only describe

Neutral description is the key imperative. Do not explain, instruct, discuss, or opine. These run counter to reference needs which demand accuracy, precision, completeness, and clarity.

If instruction or explanation feels necessary, link to how-to guides or explanation pages instead.

### Adopt standard patterns

Reference is useful when it is consistent. Use the same format for every function, every class, every CLI command. Standard patterns let users scan rapidly.

No creative vocabulary or varied styles — reference is not the place.

### Respect the structure of the machinery

The documentation structure mirrors the code structure. If the code organizes functionality into modules and classes, the reference should do the same. This lets the user navigate code and docs in parallel.

### Provide examples

Short usage examples illustrate without distracting. An example of a command invocation or function call is a succinct way to show context without falling into explanation.

```python
# Example: Create a client with custom timeout
client = MyClient(timeout=30)
```

Keep examples minimal — just enough to illustrate, not to teach.

## Language Patterns

- **"<Class> provides…"**, **"<Function> returns…"** — State facts about the machinery
- **"Parameters: a, b, c"** — List inputs, outputs, options
- **"You must use X. You must not apply Y unless Z."** — Warnings where appropriate
- **"See [How to configure X] for usage guidance."** — Link out

## mkdocstrings Integration

For Python packages using MkDocs with mkdocstrings, generate reference via docstrings:

### Docstring Format (NumPy style)

```python
def process(data: list[float], *, normalize: bool = False) -> Result:
    """Process the input data and return a Result.

    Parameters
    ----------
    data : list[float]
        The input data points to process.
    normalize : bool, optional
        Whether to normalize values to [0, 1] range, by default False.

    Returns
    -------
    Result
        The processed result containing summary statistics.

    Raises
    ------
    ValueError
        If `data` is empty.

    Examples
    --------
    >>> process([1.0, 2.0, 3.0])
    Result(mean=2.0, std=0.816)

    >>> process([1.0, 2.0, 3.0], normalize=True)
    Result(mean=0.5, std=0.408)
    """
```

### MkDocs Page Using mkdocstrings

```markdown
# API Reference

::: package_name
    options:
      show_root_heading: true
      show_source: true
      members_order: source
```

Or per-module:

```markdown
# module_name

::: package_name.module_name
    options:
      show_root_heading: true
      show_source: true
      members_order: source
```

## CLI Reference Template

```markdown
# CLI Reference

## `command-name`

```
command-name [OPTIONS] ARGUMENT
```text

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `ARGUMENT` | Description | Yes |

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--verbose` | `-v` | Enable verbose output | `false` |
| `--output` | `-o` | Output file path | stdout |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

### Examples

```bash
command-name --verbose input.txt
command-name -o result.json input.txt
```
```text

## Configuration Reference Template

```markdown
# Configuration Reference

## Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PACKAGE_DEBUG` | `bool` | `false` | Enable debug mode |
| `PACKAGE_LOG_LEVEL` | `str` | `"INFO"` | Logging level |

## Configuration File

The configuration file is read from `~/.config/package/config.toml`.

### `[section]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `key` | `str` | `""` | Description |
```

## Distinction from Explanation

| Aspect | Reference | Explanation |
|--------|-----------|-------------|
| Purpose | Describe the machinery | Illuminate a topic |
| User mode | At work | At study |
| Tone | Austere, neutral | Discursive, reflective |
| Content | Facts, specifications | Context, reasons, connections |
| When read | While doing something | When stepping back to think |
| Test | "Is this boring and unmemorable?" → reference | "Could I read this in the bath?" → explanation |

## Anti-Patterns to Avoid

- **Creeping explanation** — Examples that expand into "why" discussions; keep examples terse
- **Missing structure** — Flat lists of functions with no hierarchy; mirror the code
- **Incomplete coverage** — Every public API surface must be documented, no gaps
- **Stale content** — Reference must match the current version; automate where possible
- **Instruction mixed in** — "To use this, first do X" is a how-to; reference just describes
