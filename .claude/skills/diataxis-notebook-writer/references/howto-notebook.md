# How-to Notebook Patterns

Cell patterns for marimo notebooks classified as `"category": "how-to"` in `__gallery__`.

A how-to notebook is a **recipe**. The reader already knows what they want to accomplish and needs practical directions to get there. The notebook lets them adapt the recipe to their real-world case.

## Voice

Use imperative and conditional language. Address the reader directly when needed, but focus on actions.

- "This notebook shows how to stop optimization early using Optuna callbacks."
- "Wrap Optuna's `MaxTrialsCallback` using the `Callback` wrapper."
- "If you need multiple stopping criteria, pass a dictionary of callbacks."

Never use "What You'll Learn" - the reader already knows what they want to achieve.

## Cell Structure

### Title cell (hidden, first narrative cell)

```python
@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # How to Stop Optimization Early with Callbacks

        This notebook shows how to stop optimization early by
        adding Optuna callbacks to `OptunaSearchCV`.

        **Prerequisites:** Familiarity with the
        OptunaSearchCV quickstart
        ([View](/examples/quickstart/) · [Open in marimo](/examples/quickstart/edit/)).
        """
    )
```

Key points:
- Title starts with "How to [verb]..."
- One-sentence description of the goal
- Prerequisites as a single line linking to prior knowledge

### Step cells (hidden, between code cells)

```python
@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## 1. Wrap the Callback

        Wrap Optuna's `MaxTrialsCallback` with the `Callback`
        wrapper for sklearn compatibility.
        """
    )
```

Key points:
- Numbered steps with action verbs
- One to two sentences max - what to do, not why
- No conceptual explanation; link to explanation page if context is needed

### Verification cells (hidden, after result)

```python
@app.cell(hide_code=True)
def _(mo, n_trials_run):
    mo.md(
        f"""
        Requested trials: 20
        Actual trials run: {n_trials_run}
        """
    )
```

Key points:
- Show the result that proves the task succeeded
- No interpretation beyond the facts

### Conditional guidance (when variations exist)

```python
@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## 3. Multiple Callbacks

        If you need multiple stopping criteria, pass a dictionary
        of callbacks. Each callback is invoked at the end of every trial.
        """
    )
```

Key points:
- "If you need X, do Y" - conditional imperatives
- Present variations as branches the user can follow or skip
- Don't explain why they might need it

### No closing summary

How-to notebooks end after the final verification step. Do not add:
- "Key Takeaways" sections
- "What We Learned" summaries
- "Next Steps" sections (these are optional; include only if directly relevant)

The task is done. The reader moves on.

## Principles Checklist

- [ ] Title is "How to [verb]..." - goal-oriented
- [ ] `__gallery__` title matches the goal format
- [ ] No "What You'll Learn" section
- [ ] No "Key Takeaways" or summary section
- [ ] Markdown cells contain only directional action prose
- [ ] No embedded explanation - link out for "why" content
- [ ] No design reasoning - just show what to do
- [ ] Conditional imperatives for variations ("If you need X, do Y")
- [ ] Verification step shows the task succeeded
- [ ] Numbered steps for clear progression
- [ ] Assumes competence from prerequisites
