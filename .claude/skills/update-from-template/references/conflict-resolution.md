# Conflict Resolution Patterns

How to resolve conflicts from `copier update` for each file tier and type.

## Table of Contents

- [Use the default inline merge](#use-the-default-inline-merge-not---conflict-rej)
- [Resolution by Tier](#resolution-by-tier)
- [.rej File Format](#rej-file-format)
- [TOML Merge (pyproject.toml)](#toml-merge-pyprojecttoml)
- [YAML Merge (mkdocs.yml, workflows)](#yaml-merge-mkdocsyml-workflows)
- [Markdown Merge (README.md, docs)](#markdown-merge-readmemd-docs)
- [Python Merge (noxfile.py)](#python-merge-noxfilepy)
- [Makefile-like Merge (justfile)](#makefile-like-merge-justfile)
- [Edge Cases](#edge-cases)

---

## Use the default inline merge, NOT --conflict rej

**Do not pass `--conflict rej`. Use copier's default, which is a three-way inline merge.**

This file used to prescribe `--conflict rej` on the grounds that a `.rej` is easier for an
assistant to parse than markers interleaved with content. That reasoning is about *reading*
the outcome and ignores what the two modes do to the file. They are not two presentations of
the same result. Measured on one repository, one release, the same commit, only the flag
differing:

| | `--conflict rej` | default (inline) |
|---|---|---|
| `.rej` files | 5 | **0** |
| digest-pinned `uses:` lines | 49 → **26** | 49 → **49** |
| local `exclude:` block in `tests.yml` | **destroyed** | intact |
| tracked files changed | 7 | **2** |

`--conflict rej` applies hunks with `git apply --reject`, which is all-or-nothing **per hunk**
and has no knowledge of the merge base. A hunk carrying the template's change plus context
lines the project has legitimately edited fails as a unit, and what lands is the template's
version of everything that did apply. The inline mode performs a real three-way merge, so
where base, local and template agree it simply keeps the agreement, and it only marks genuine
divergence.

The damage is not limited to things you would think to recount. In one repository the reject
mode also replaced a live `Compat tests` pin set with the template's **disabled** placeholder,
and dropped `lfs: true` from a checkout step. A digest recount would have reported those files
clean.

If an inline conflict does appear, it is a real one. Resolve it in place: the markers sit
exactly where the two sides genuinely disagree, which is far less than `--conflict rej`
rejects.

### If you inherit a --conflict rej run

The **local file** already contains every hunk that applied — *not* the untouched original.
So deleting the `.rej` does not restore the project's version. Use
`git checkout HEAD -- <file>` to undo them, and check with `git diff HEAD -- <file>` whenever
a `.rej` exists: a non-empty diff means the file was partially updated. Better still, discard
the whole run and redo it without the flag.

---

## Resolution by Tier

With the default inline merge a conflict appears as `<<<<<<<` / `=======` / `>>>>>>>` markers
**in the file**, at exactly the lines where the two sides genuinely disagree. There is no
`.rej` to read. The tier rules below decide which side of each marker block to keep. Where
this section says "the template's side", read the block between `=======` and `>>>>>>>`.

Sweep for markers with `^(<<<<<<<|>>>>>>>|=======)( |$)` before committing. The anchored form
without that trailing group misses `<<<<<<< HEAD` and `>>>>>>> theirs`.

### Tier 1 — Template-managed (template wins)

1. Keep the template's side of every marker block.
2. If the file updated with no conflict, it is already correct — no action.

Verify by diffing against a fresh `copier copy` at the same ref: a Tier 1 file should end
byte-identical to the pristine render.

### Tier 2 — Merge-required (intelligent merge)

1. Read both sides of each marker block, and understand the intent of each:
    - Template change: bug fix? dependency bump? structural improvement? new feature?
    - Local state: custom content? extended functionality? project-specific additions?
2. Apply the template's change while preserving the local addition (see file-type patterns
   below). Both sides usually want to survive; that is what makes it Tier 2.

If a Tier 2 file updated with **no** conflict but you classified it as customized, do not
assume it was left alone. Take a whole-file pre/post diff and confirm the only changes are the
template's intended ones.

### Tier 3 — Local-owned (local wins)

1. Keep the local side of every marker block.
2. If copier modified the file with no conflict, restore it: `git checkout HEAD -- <file>`.

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
    - Examples: pages/examples/index.md  # conditional
  - How-to Guides:
    - Configure: pages/how-to/configure.md
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
- **Exception — a file the template MOVED:** see below.
- **Exception — a dropped config another tool still reads:** delete it explicitly and confirm it is gone, do not just flag it. `copier update` does not reliably remove such a file, and the leftover keeps working. When `renovate.json` replaced `.github/dependabot.yml`, a surviving `dependabot.yml` runs Dependabot alongside Renovate and opens duplicate PRs. Run `git rm .github/dependabot.yml`; the update is not complete while it remains.


#### Old build output stops being ignored

The `.gitignore` entries for `site/`, `htmlcov/`, `coverage.xml`, `.coverage`, `.nox/`, `.pytest_cache/` and `.ruff_cache/` are replaced by a single `.artifacts/`. Anything a previous build already left at the project root therefore stops being ignored and appears as untracked the moment the update lands.

That is the intended behaviour, not a defect: the point is that stale output becomes visible instead of sitting ignored forever. Delete it (`rm -rf site htmlcov coverage.xml .coverage .nox .pytest_cache .ruff_cache`) rather than re-adding ignore entries. New runs write under `.artifacts/`.

Watch for it when staging: a plain `git add -A` immediately after the update will otherwise commit a whole built site.

#### A relocated file destroys local content, silently

When the template moves a file it ships, `copier update` writes it at the new path **and deletes the old one for you** — no conflict, no `.rej`, no prompt. Any local edits the old copy carried are gone from the working tree at that moment.

Measured on a real update: a project's two curated prose edits in `CONTRIBUTING.md` were destroyed by the move and had to be recovered with `git show HEAD:CONTRIBUTING.md`. Nothing in the update's output mentioned it.

So the instruction is **not** "carry the content over before deleting" — there is no delete of yours to precede. It is:

1. After the update, diff the new path against the old file's pre-update content: `git show HEAD:<old-path> | diff - <new-path>`.
2. Re-apply anything local that the template's copy does not carry.
3. Only then stage the move.

Copier does not always delete, either — an earlier release left both copies in place. Verify which happened rather than assuming, and if the old copy survived, remove it: for these files the consuming tool reads exactly one of the two and ignores the other without a word.

| Moved to | Read by | The ignored copy |
|---|---|---|
| `.github/CODEOWNERS` | GitHub code-owner review | a root `CODEOWNERS` is never consulted |
| `.github/renovate.json` | Renovate | only one config is loaded |

Both are Tier 1 (template-managed), but do not assume a project's copy matches the template's — verify before discarding anything. The danger is that everything looks right: the new file is present, the tool is configured, CI is green, and the copy the maintainer keeps editing is the one nothing reads.

Do not trust `git status` to reveal a leftover. If an unresolved `.gitignore` conflict still lists a path, git omits the file from status entirely and copier exits 0 with no `.rej` — the delivery looks clean while the stale file sits there. Grep for the content instead.

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
