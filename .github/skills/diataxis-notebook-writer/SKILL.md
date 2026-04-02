---
name: diataxis-notebook-writer
description: Write or rework marimo example notebooks following Diataxis principles. Use when asked to create, edit, or rework interactive notebook examples that serve as tutorial or how-to companions to documentation pages. Triggers on "write a notebook example", "rework notebook", "example notebook", "interactive example", "marimo example", "tutorial notebook", "how-to notebook".
---

# Diataxis Notebook Writer

Write marimo notebook examples that follow Diataxis quadrant conventions for voice, structure, and content boundaries.

Notebooks serve only **tutorials** and **how-to guides** - never explanation or reference. Explanation belongs in markdown pages read away from the keyboard. Reference mirrors code structure, not user tasks.

## Quadrant Decision

Ask two questions to classify the notebook:

1. Does it teach a beginner by guiding them through a learning experience? -> **Tutorial**
2. Does it help a competent user accomplish a specific real-world task? -> **How-to**

If it does neither (conceptual discussion, API description), it should not be a notebook.

## File Placement and Metadata

Place notebooks in `examples/`. Every notebook must define `__gallery__` metadata:

```python
__gallery__ = {
    "title": "How to Stop Optimization Early with Callbacks",  # goal-oriented for how-to
    "description": "Stop unneeded work early by adding Optuna callbacks to your search.",
    "category": "how-to",  # "tutorial" or "how-to"
    "companion": "pages/how-to/use-callbacks.md",  # optional: path to companion doc page
}
```

**Title conventions:**
- Tutorial: descriptive noun phrase - "OptunaSearchCV Quickstart"
- How-to: "How to [verb]..." - "How to Stop Optimization Early with Callbacks"

## Notebook Cell Structure

Both quadrants use **hidden setup cells** (`hide_code=True`) for imports and markdown narrative, with visible code cells for the actions the reader should focus on.

**For quadrant-specific cell patterns, voice, and templates:**
- **Tutorial notebooks**: Read [references/tutorial-notebook.md](references/tutorial-notebook.md)
- **How-to notebooks**: Read [references/howto-notebook.md](references/howto-notebook.md)

## Companion Doc Page Pattern

When a notebook has a companion markdown page, add this admonition near the top of the doc page (after any prerequisites):

```markdown
!!! tip "Interactive version available"
    Try this guide as an interactive notebook:
    [View](/examples/callbacks/) · [Open in marimo](/examples/callbacks/edit/)
```

## Common Anti-Patterns

- **One-size-fits-all structure**: Using "What You'll Learn" + "Key Takeaways" in every notebook regardless of quadrant
- **Embedded explanation in how-to**: "Class imbalance is common because..." belongs in an explanation page, not a how-to notebook
- **Design reasoning in how-to**: "We set refit=False because the outer search doesn't need..." - just say "Set `refit=False`"
- **Tool-centric titles**: "Callbacks" instead of "How to Stop Optimization Early with Callbacks"
- **Tutorial language in how-to**: "What You'll Learn" presumes a learning orientation; how-to readers already know what they want

## Related Skills

- `diataxis-tutorial-writer` - for companion markdown tutorial pages
- `diataxis-howto-writer` - for companion markdown how-to pages
- `marimo-notebook` - for marimo format mechanics (cell syntax, reactivity, script mode)
