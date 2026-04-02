# Conflict Resolution Patterns

How to resolve conflicts produced by `copier update --conflict rej` for each file tier and type.

## Table of Contents

- [Why --conflict rej](#why---conflict-rej)
- [Resolution by Tier](#resolution-by-tier)
- [.rej File Format](#rej-file-format)
- [TOML Merge (pyproject.toml)](#toml-merge-pyprojecttoml)
- [YAML Merge (mkdocs.yml, workflows)](#yaml-merge-mkdocsyml-workflows)
- [Markdown Merge (README.md, docs)](#markdown-merge-readmemd-docs)
- [Python Merge (noxfile.py)](#python-merge-noxfilepy)
- [Makefile-like Merge (justfile)](#makefile-like-merge-justfile)
- [Edge Cases](#edge-cases)

---

## Why --conflict rej

`copier update` supports two conflict modes:

| Mode | Behavior | AI suitability |
|------|----------|----------------|
| `--conflict inline` | Inserts `<<<<<<<`/`=======`/`>>>>>>>` markers into files | Harder to parse — markers interleave with file content |
| `--conflict rej` | Keeps local file intact, writes rejected template hunks to `<file>.rej` | Easier — local file is clean, `.rej` shows what template wanted |

Use `--conflict rej`. This produces:
- The **local file** unchanged (what the project currently has)
- A **`.rej` file** containing the diff hunks that copier couldn't apply (what the template wanted to change)

---

## Resolution by Tier

### Tier 1 — Template-managed (template wins)

1. Read the `.rej` file to understand what the template wanted
2. Apply those changes to the local file (the template version is correct)
3. Delete the `.rej` file

If copier updated the file without conflict (no `.rej`), the update is already correct — no action needed.

### Tier 2 — Merge-required (intelligent merge)

1. Read the **local file** (current project state with customizations)
2. Read the **`.rej` file** (what the template wanted to change)
3. Understand the intent of BOTH:
    - Template change: bug fix? dependency bump? structural improvement? new feature?
    - Local state: custom content? extended functionality? project-specific additions?
4. Apply template changes while preserving local additions (see file-type patterns below)
5. Delete the `.rej` file

If copier updated a Tier 2 file without conflict (no `.rej`) BUT the file was classified as customized in Step 2:
- The update may have **overwritten local customizations**
- Compare the updated file against the baseline diff from Step 2
- Restore any lost local additions

### Tier 3 — Local-owned (local wins)

1. If a `.rej` file exists: delete it (ignore template changes)
2. If copier modified the file without conflict: restore from git with `git checkout HEAD -- <file>`

---

## .rej File Format

A `.rej` file contains unified diff hunks that copier couldn't apply:

```diff
--- original
+++ updated
@@ -10,6 +10,8 @@ some context
 existing line
-old template line
+new template line
+added template line
 existing line
```

Each hunk shows:
- **Context lines** (prefixed with space): surrounding content for locating the change
- **Removed lines** (prefixed with `-`): What the template expected the file to have (old template version)
- **Added lines** (prefixed with `+`): What the template now wants (new template version)

Use the context lines to locate the corresponding section in the local file, then decide how to apply the added/removed changes based on the file's tier and merge strategy.

---

## TOML Merge (pyproject.toml)

**Identify sections** by `[bracket.headers]`:

```toml
[project]           # Shared — merge carefully
[build-system]      # Template-owned — accept changes
[tool.ruff]         # Template-owned — accept changes
[tool.hatch.*]      # Template-owned — accept changes
[tool.pytest.*]     # Template-owned — accept changes
[tool.coverage.*]   # Template-owned — accept changes
[dependency-groups]  # Mixed — update template groups, keep custom groups
```

**Merge pattern:**

1. For template-owned sections (`[build-system]`, `[tool.*]`): Apply the `.rej` changes directly
2. For `[project]`:
    - Accept: `requires-python` changes, classifier updates, maintainer format changes
    - Preserve: Custom `dependencies` entries beyond template defaults, custom `[project.scripts]`, custom `[project.urls]` entries
3. For `[dependency-groups]`:
    - Update version pins in template-defined groups (`tests`, `lint`, `docs`, `fix`, `examples`)
    - Preserve entirely custom groups (group names not in the template)
4. For unknown sections: Preserve (they're local additions)

**Example — preserving a custom dependency group:**

Template `.rej` updates the `tests` group versions. Local file also has a custom `benchmarks` group:

```toml
# Accept: updated test dependency versions from template
tests = [
    "pytest>=8.4",        # was >=8.3 — accept bump
    "pytest-cov>=7.1",    # was >=7.0 — accept bump
    ...
]

# Preserve: custom group not in template
benchmarks = [
    "pytest-benchmark>=4.0",
]
```

---

## YAML Merge (mkdocs.yml, workflows)

### mkdocs.yml

**Top-level keys** are the merge units:

- **Template-owned** (accept changes): `theme`, `plugins`, `markdown_extensions`, `extra_css`, `extra_javascript`, `extra`
- **Mixed** (merge): `nav`, `watch`
- **Local additions** (preserve): Any top-level keys not in the template

**Nav merge pattern:**

```yaml
# Template nav structure:
nav:
  - Home: index.md
  - Tutorials:
    - Getting Started: pages/tutorials/getting-started.md
    - Examples: pages/tutorials/examples.md  # conditional
  - How-to Guides:
    - Configure: pages/how-to/configure.md
    - Troubleshooting: pages/how-to/troubleshooting.md
    - Contributing: pages/how-to/contribute.md
  - Reference:
    - API Reference: pages/reference/api.md
  - Explanation:
    - Concepts: pages/explanation/concepts.md

# Local additions to preserve (not in template):
  - FAQ: pages/faq.md                   # KEEP
```

Strategy: Keep template nav items in their updated order. Append local nav items that don't match any template entry.

### GitHub Actions workflows

**Jobs** are the merge units within each workflow file:

1. Identify jobs by their key name under `jobs:`
2. Template-defined jobs: Accept the full `.rej` update (version bumps, matrix changes, new steps)
3. Locally-added jobs: Preserve entirely
4. Within shared jobs: If local adds steps after template steps, keep them appended

**Example — preserving a custom job:**

```yaml
jobs:
  test-fast:     # Template job — accept updates
    ...
  lint:          # Template job — accept updates
    ...
  deploy-staging: # Local job — preserve
    ...
```

---

## Markdown Merge (README.md, docs)

**Sections** (identified by `##` headings) are the merge units:

1. Parse both files into sections by heading level
2. For headings present in both template and local:
    - If section content matches baseline (never customized): Accept template version
    - If section content differs from baseline (customized): Keep local content, but apply template format changes if structural only
3. For headings only in template (new): Insert at the template's position
4. For headings only in local (custom): Preserve at their current position

**Example — preserving custom README sections:**

```markdown
## Features            ← Template heading, local content customized → KEEP LOCAL
## Installation        ← Template heading, matches baseline → ACCEPT TEMPLATE
## Deployment Guide    ← Local-only heading → PRESERVE
## Contributing        ← Template heading → ACCEPT TEMPLATE
```

---

## Python Merge (noxfile.py)

**Functions decorated with `@nox.session`** are the merge units:

1. Parse file for function definitions
2. Template-defined sessions: Accept the `.rej` changes
3. Locally-added sessions: Preserve
4. Import statements: Merge (keep both template and local imports)

---

## Makefile-like Merge (justfile)

**Recipes** (identified by name followed by `:`) are the merge units:

1. Identify recipes by name
2. Template-defined recipes: Accept changes
3. Locally-added recipes: Preserve
4. Variables at the top: Merge (update template vars, keep local vars)

---

## Edge Cases

### New files from template

Files that exist in the new template version but not in the project (template added a new feature):
- **Accept unconditionally** — these are new template features

### Files deleted in template

Files that existed in the previous template version but are removed in the new version:
- **Flag for user review** — do NOT auto-delete
- Report: "Template removed `<file>`. Review whether to delete locally."

### Conditional files changing state

If copier answers change (e.g., `include_examples` toggled):
- New conditional files appearing: Accept (same as new template files)
- Conditional files disappearing: Flag for review (same as deleted files)

### .copier-answers.yml

Always accept the template version — this file is regenerated by copier and is critical for future updates. Never merge or modify manually.

### Files with no .rej but modified by copier

Copier successfully applied the update without conflict. Check:
- If the file is Tier 3 and was customized: Restore with `git checkout HEAD -- <file>`
- If the file is Tier 2 and was customized: Diff against git HEAD to verify no local content was lost
- Otherwise: Accept the update
