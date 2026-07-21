from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from kedro_dagster.config import KedroDagsterConfig

DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"

# Fenced ```yaml blocks, keeping the indentation so nested fences (inside
# MkDocs tabs) are dedented correctly.
YAML_BLOCK = re.compile(r"^([ \t]*)```+[ \t]*yaml[ \t]*$(.*?)^\1```+[ \t]*$", re.M | re.S)

# Opt-out marker placed on the line before a fence. Fences carry no attributes
# in these docs, so an HTML comment is the escape hatch; it renders as nothing.
SKIP_MARKER = "<!-- dagster-config-test: skip -->"

# A block is treated as dagster.yml configuration when its top-level keys are a
# non-empty subset of the config's fields. This keeps catalog.yml,
# credentials.yml and parameter snippets out of scope without marking each one.
CONFIG_FIELDS = set(KedroDagsterConfig.model_fields)


def _iter_config_examples() -> list[tuple[str, int, str]]:
    """Collect dagster.yml examples from the documentation.

    Returns
    -------
    list[tuple[str, int, str]]
        Tuples of relative path, 1-indexed line of the opening fence, and the
        dedented YAML body.
    """
    examples = []
    for path in sorted(DOCS_ROOT.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in YAML_BLOCK.finditer(text):
            indent, body = match.group(1), match.group(2)
            line_no = text.count("\n", 0, match.start()) + 1

            preceding = text[: match.start()].rstrip().rsplit("\n", 1)[-1].strip()
            if preceding == SKIP_MARKER:
                continue

            if indent:
                body = "\n".join(line.removeprefix(indent) for line in body.splitlines())

            try:
                parsed = yaml.safe_load(body)
            except yaml.YAMLError:
                # Malformed YAML is reported by the dedicated test below.
                parsed = None

            if isinstance(parsed, dict) and parsed and set(parsed) <= CONFIG_FIELDS:
                examples.append((str(path.relative_to(DOCS_ROOT.parent)), line_no, body))
    return examples


CONFIG_EXAMPLES = _iter_config_examples()


def test_documentation_contains_config_examples():
    """The collector finds dagster.yml examples, so a passing suite is not vacuous."""
    assert CONFIG_EXAMPLES, "No dagster.yml examples found in docs. The collector is likely broken."


@pytest.mark.parametrize(
    ("source", "line_no", "body"),
    CONFIG_EXAMPLES,
    ids=[f"{source}:{line_no}" for source, line_no, _ in CONFIG_EXAMPLES],
)
def test_documented_config_example_parses(source, line_no, body):
    """Every documented dagster.yml example validates against KedroDagsterConfig."""
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        pytest.fail(f"{source}:{line_no} is not valid YAML: {exc}")

    try:
        KedroDagsterConfig(**parsed)
    except ValidationError as exc:
        pytest.fail(
            f"{source}:{line_no} does not validate against KedroDagsterConfig.\n"
            f"Mark it with '{SKIP_MARKER}' if it is intentionally partial.\n{exc}"
        )
