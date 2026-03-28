---
name: diataxis-tutorial-writer
description: Generate learning-oriented tutorial documentation for Python packages following Diátaxis principles. Use when asked to write a tutorial, getting started guide, first steps page, quickstart, onboarding guide, or any documentation that teaches a beginner by walking them through hands-on steps. Triggers on "write a tutorial", "getting started page", "quickstart guide", "first steps", "beginner guide", "onboarding docs", "teach how to use".
---

# Diátaxis Tutorial Writer

Generate tutorials — learning-oriented documentation where the reader acquires skills through hands-on practice under guidance.

A tutorial is a **lesson**. The reader does things, and learns by doing. The author is the teacher; the reader is the student.

## File Placement

Place tutorial pages in `docs/pages/tutorials/`. Example: `docs/pages/tutorials/getting-started.md`.

## What a Tutorial Is

- A practical activity where the student learns by doing something meaningful
- Designed around an encounter the learner can make sense of
- The teacher is responsible for the learner's safety and success
- Purpose: help them **learn**, not help them **get something done**

A tutorial is like a driving lesson: the purpose is to develop skills and confidence, not to get from A to B.

## Generation Workflow

### Step 1: Understand the Package

- Read `pyproject.toml` for package name, description, key features
- Scan `src/<package>/` for the simplest useful public API
- Check `examples/` for existing usage patterns
- Identify the **single most impressive thing** a beginner can achieve quickly

### Step 2: Design the Learning Journey

Choose a concrete goal the learner will achieve. Structure it as:

1. **Setup** — Install the package, verify installation
2. **First contact** — Import, call the simplest function, see a result
3. **Build** — Incrementally add complexity, one concept at a time
4. **Completion** — Arrive at a meaningful, visible result
5. **Next steps** — Link to how-to guides and explanation (not more tutorials)

Every step should produce a **visible, verifiable result**.

### Step 3: Write the Tutorial

Apply all key principles below. Use the language patterns. Target 500-1500 words.

## Key Principles

### Show the learner where they are going

Open with what they will achieve: "In this tutorial, we will create a [concrete thing]. Along the way we will [encounter X, Y, Z]."

Never say "In this tutorial you will learn…" — that is presumptuous.

### Deliver visible results early and often

Every step must produce something the user can see. Start with the smallest possible success, then build.

```python
# Step 1: Verify installation
import my_package
print(my_package.__version__)
# Output: 1.0.0
```

### Maintain a narrative of the expected

Tell the user what will happen before it happens: "You will notice that…", "After a moment, you should see…", "The output should look something like…"

Show exact expected output. Flag likely mistakes: "If you see X instead, you probably forgot to Y."

### Point out what the learner should notice

Close learning loops: "Notice that the prompt changed to…", "See how the output now includes…"

Observing is an active skill. Prompt it.

### Ruthlessly minimise explanation

A tutorial is not the place for explanation. One sentence is enough: "We use HTTPS because it is more secure." Link to explanation pages for depth.

Explanation distracts the learner's attention and blocks learning. Resist the urge to teach by telling.

### Focus on the concrete

Focus on *this* problem, *this* action, *this* result. Lead the learner from step to concrete step. General patterns will emerge naturally from concrete examples — the mind does this automatically.

### Ignore options and alternatives

There may be many interesting diversions — ignore them. Stay on the path to the conclusion. Every option adds cognitive load. Save alternatives for how-to guides.

### Encourage and permit repetition

Where possible, make steps repeatable. Learners often repeat a step just to confirm "the same thing really does happen again."

### Aspire to perfect reliability

Every step must produce the stated result for every user, every time. A learner who does not get the expected result loses confidence immediately. Test the tutorial end-to-end.

## Language Patterns

Use these templates:

- **"We…"** — First-person plural affirms the teacher-learner relationship
- **"In this tutorial, we will…"** — Describe what the learner will accomplish
- **"First, do x. Now, do y. Now that you have done y, do z."** — No ambiguity
- **"The output should look something like…"** — Set expectations
- **"Notice that…"**, **"Remember that…"**, **"Let's check…"** — Confirm they are on track
- **"You have built a…"** — Celebrate the accomplishment at the end

## Python Package Tutorial Template

````markdown
# Getting Started

In this tutorial, we will [concrete achievement]. Along the way, we will
[encounter key concepts].

## Prerequisites

- Python [version]+ installed
- A terminal or command prompt

## Installation

=== "pip"

    ```bash
    pip install <package-name>
    ```

=== "uv"

    ```bash
    uv add <package-name>
    ```

Verify the installation:

```python
import <package_name>
print(<package_name>.__version__)
```

The output should look something like:

```text
x.y.z
```

## Your First [Thing]

Now let's [do the first meaningful action].

```python
from <package_name> import <main_thing>

result = <main_thing>(<simple_args>)
print(result)
```

You should see:

```text
[expected output]
```

Notice that [observation about the result].

## [Building On It]

Now that we have [previous result], let's [next step].

[... continue building incrementally ...]

## What We Built

You have [accomplished concrete thing]. Along the way, you:

- [Learned concept 1]
- [Used tool/function X]
- [Saw how Y works]

## Next Steps

- [How-to guide for a related task](../how-to/something.md)
- [Explanation of a concept encountered](../explanation/concept.md)
- [API reference for the functions used](../reference/api.md)
```text

## Anti-Patterns to Avoid

- **Starting with explanation** — Do not open with "X is a framework that…"; open with what they will do
- **Offering choices** — "You can use either A or B" forces a decision; just pick one
- **Assumed knowledge** — Do not skip steps because they seem obvious
- **Wall of code** — Break into small steps, each with visible output
- **Missing output examples** — Every code block needs its expected output
- **Teaching by telling** — Show, do not explain; link to explanation pages instead

## What a Tutorial Is NOT

- Not a how-to guide (serves work, not study)
- Not a reference (describes machinery, doesn't guide action)
- Not an explanation (discusses topics, doesn't guide action)
- Not "the basics" — tutorials can be advanced; the distinction is study vs. work
