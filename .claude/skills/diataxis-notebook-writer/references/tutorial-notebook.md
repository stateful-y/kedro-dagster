# Tutorial Notebook Patterns

Cell patterns for marimo notebooks classified as `"category": "tutorial"` in `__gallery__`.

A tutorial notebook is a **lesson**. The reader acquires skills through guided hands-on practice. The notebook is the classroom - every cell produces visible output the learner can verify.

## Voice

Use first-person plural throughout: **"we"**, **"our"**, **"let's"**.

- "We create a classification dataset"
- "Now we define the search space"
- "Let's run the search and inspect the results"

Never use "you will learn" - that is presumptuous. Use "we will [do concrete thing]" instead.

## Cell Structure

### Title cell (hidden, first narrative cell)

```python
@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # OptunaSearchCV Quickstart

        In this notebook, we will run a hyperparameter search using
        `OptunaSearchCV` and inspect the best parameters and score.
        Along the way, we will define search spaces with Optuna
        distributions and see how the results API works.

        **Prerequisites:** Basic familiarity with scikit-learn's
        fit/predict API.
        """
    )
```

Key points:
- State what **we will do**, not what "you will learn"
- Mention concrete outcomes, not abstract learning objectives
- Prerequisites in a single line, not a bulleted list

### Section cells (hidden, between code cells)

```python
@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## 1. Prepare Data and Estimator

        We start by creating a classification dataset and
        initializing a LogisticRegression estimator.
        """
    )
```

Key points:
- Number the sections for clear progression
- One sentence of context - what we do, not why
- No explanation of concepts - link to explanation page if needed

### Observation cells (hidden, after code output)

```python
@app.cell(hide_code=True)
def _(mo, search):
    mo.md(
        f"""
        **Best params:** {search.best_params_}
        **Best score:** {search.best_score_:.3f}

        Notice that `best_params_` returns the same format as
        scikit-learn's `GridSearchCV`. The score is the mean
        cross-validated score from the best trial.
        """
    )
```

Key points:
- Show exact expected output
- "Notice that..." closes the learning loop
- One sentence of observation, not a paragraph of explanation

### Closing cell (hidden, final cell)

```python
@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## What We Built

        We ran a hyperparameter search with `OptunaSearchCV` and found
        the best regularization parameter for a LogisticRegression. Along
        the way, we:

        - Defined a search space with `FloatDistribution`
        - Ran the search with `OptunaSearchCV.fit()`
        - Inspected `best_params_` and `best_score_`

        **Next steps:**

        - How to resume optimization from prior trials:
          [View](/examples/study_management/) · [Open in marimo](/examples/study_management/edit/)
        - How to stop optimization early with callbacks:
          [View](/examples/callbacks/) · [Open in marimo](/examples/callbacks/edit/)
        """
    )
```

Key points:
- "What We Built" - celebrate accomplishment, don't summarize theory
- Brief bullet list of concrete things done, not concepts learned
- Link to how-to notebooks, not more tutorials

## Principles Checklist

- [ ] Every code cell produces visible output (no silent cells)
- [ ] "We" language throughout, never "you will learn"
- [ ] Title says what we will do, not what you will learn
- [ ] "Notice that..." observations after key outputs
- [ ] One-sentence max explanation per concept; link out for depth
- [ ] Single path - no branching, no CategoricalDistribution choices unless essential
- [ ] All code cells are re-runnable with deterministic results
- [ ] Ends with "What We Built", not "Key Takeaways"
- [ ] Numbered sections guide sequential progression
- [ ] No options or alternatives - just one clear path
