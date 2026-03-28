---
name: diataxis-docs-planner
description: Audit, plan, and structure Python package documentation following the Diátaxis framework (tutorials, how-to guides, reference, explanation). Use when asked to plan documentation, audit existing docs, identify documentation gaps, restructure docs, create a documentation roadmap, or organize documentation for a Python package. Triggers on "plan docs", "audit documentation", "structure docs", "documentation roadmap", "what docs do I need", "organize documentation".
---

# Diátaxis Documentation Planner

Audit existing documentation and produce a structured plan following the Diátaxis framework — four quadrants of documentation that serve distinct user needs.

## The Four Quadrants

| Quadrant | Orientation | User mode | Serves | Question answered |
|----------|-------------|-----------|--------|-------------------|
| **Tutorial** | Learning | Study | Acquisition of skill | "Can you teach me to…?" |
| **How-to guide** | Task | Work | Application of skill | "How do I…?" |
| **Reference** | Information | Work | Application of skill | "What is…?" |
| **Explanation** | Understanding | Study | Acquisition of skill | "Why…?" |

## Compass Decision Tree

Classify any content by asking two questions:

1. **Action or cognition?** Does it guide what the user *does*, or inform what the user *knows*?
2. **Acquisition or application?** Does it serve *study* (learning) or *work* (applying skills)?

| Informs… | Serves… | → Quadrant |
|----------|---------|------------|
| Action | Acquisition (study) | Tutorial |
| Action | Application (work) | How-to guide |
| Cognition | Application (work) | Reference |
| Cognition | Acquisition (study) | Explanation |

## Audit Workflow

### Step 1: Analyze the Codebase

Examine the package to understand what needs documenting:

- Read `pyproject.toml` for package name, description, dependencies, entry points, CLI tools
- Scan `src/<package>/` for public modules, classes, functions (the API surface)
- Check for CLI entry points, configuration files, plugin systems
- Look at `tests/` for usage patterns and features exercised
- Check `examples/` if present

### Step 2: Inventory Existing Documentation

Read all files in `docs/` and classify each page by quadrant using the compass:

- For each page, note: file path, current title, actual quadrant, intended quadrant
- Flag pages that mix quadrants (e.g., a "getting started" that is half tutorial, half reference)
- Flag pages that are misclassified (e.g., an "explanation" page that is really a how-to)

### Step 3: Identify Gaps

For a well-documented Python package, expect at minimum:

**Tutorials** (at least 1):
- Getting Started / First Steps — install, import, first meaningful result

**How-to Guides** (varies by feature count):
- One per common task/problem users face
- Installation/setup variations (different platforms, configs)
- Integration with other tools/libraries
- Configuration for common scenarios
- Troubleshooting guide

**Reference** (comprehensive):
- API reference (all public modules, classes, functions)
- CLI reference (if applicable)
- Configuration reference (all settings/options)
- Error codes / exceptions (if applicable)

**Explanation** (at least 1-2):
- Architecture / design overview
- Key concepts and terminology
- Design decisions / "why" docs
- Comparison with alternatives (when useful)

### Step 4: Produce the Plan

Output a structured documentation plan:

1. **Gap analysis table** — what exists, what is missing, what needs reclassification
2. **Recommended pages** — organized by quadrant, with title, purpose, priority (high/medium/low)
3. **MkDocs nav structure** — ready to paste into `mkdocs.yml`
4. **Implementation order** — tutorials and key how-tos first (highest user impact)
5. **Skill recommendations** — name the specific writer skill for each page:
   - Tutorial pages → `diataxis-tutorial-writer`
   - How-to pages → `diataxis-howto-writer`
   - Reference pages → `diataxis-reference-writer`
   - Explanation pages → `diataxis-explanation-writer`

## MkDocs Nav Patterns

Canonical Python package nav structure using `pages/` folder-per-quadrant:

```yaml
nav:
  - Home: index.md
  - Tutorials:                                    # tutorial
    - Getting Started: pages/tutorials/getting-started.md
  - How-to Guides:                                # how-to
    - How to Configure X: pages/how-to/configure-x.md
    - How to Integrate with Y: pages/how-to/integrate-y.md
    - Contributing: pages/how-to/contribute.md
  - Reference:                                    # reference
    - API Reference: pages/reference/api.md
    - CLI Reference: pages/reference/cli.md
    - Configuration: pages/reference/configuration.md
  - Explanation:                                  # explanation
    - Architecture: pages/explanation/architecture.md
    - Design Decisions: pages/explanation/design-decisions.md
```

For complex packages with multiple user types or deployment targets, see [references/compass-and-patterns.md](references/compass-and-patterns.md) for multi-layer hierarchy and two-dimensional structure guidance.

## Common Anti-Patterns to Flag

- **The mega-README**: Everything in one file — split by quadrant
- **Tutorial-reference hybrid**: "Getting Started" that is actually an API walkthrough — separate
- **How-to disguised as explanation**: "Understanding X" that is really step-by-step instructions
- **Missing tutorials entirely**: Only reference docs (common with auto-generated docs)
- **Explanation scattered everywhere**: Bits of "why" sprinkled across how-to guides — consolidate

## Quality Signals

When auditing, also note:

- **Functional quality**: accuracy, completeness, consistency, precision
- **Deep quality**: flow, fit to user needs, anticipation of the user
- Use the `mkdocs` skill for site configuration and build concerns — this skill focuses on content structure

## Output Format

```markdown
## Documentation Audit: <package-name>

### Current State

| Page | File | Current Quadrant | Issues |
|------|------|-----------------|--------|
| ... | ... | ... | ... |

### Gap Analysis

| Quadrant | Existing | Missing | Priority |
|----------|----------|---------|----------|
| Tutorial | ... | ... | ... |
| How-to | ... | ... | ... |
| Reference | ... | ... | ... |
| Explanation | ... | ... | ... |

### Recommended Pages
#### Tutorials (use `diataxis-tutorial-writer`)
1. **Getting Started** — Install, first use, verify result [HIGH]

#### How-to Guides (use `diataxis-howto-writer`)
1. **How to configure X** — ... [HIGH]

#### Reference (use `diataxis-reference-writer`)
1. **API Reference** — Full public API [HIGH]

#### Explanation (use `diataxis-explanation-writer`)
1. **Architecture Overview** — ... [MEDIUM]

### Proposed MkDocs Nav
nav:
  ...
```
