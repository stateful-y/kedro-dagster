---
name: diataxis-howto-writer
description: Generate task-oriented how-to guide documentation for Python packages following Diátaxis principles. Use when asked to write a how-to guide, cookbook entry, recipe, procedure, troubleshooting guide, or any documentation that helps an already-competent user accomplish a specific real-world task. Triggers on "write a how-to", "how to configure", "how to deploy", "how to integrate", "troubleshooting guide", "cookbook", "recipe", "procedure for".
---

# Diátaxis How-to Guide Writer

Generate how-to guides — task-oriented documentation that helps already-competent users accomplish specific goals.

A how-to guide is a **recipe**. It addresses a real-world problem and provides practical directions to solve it. The reader already knows what they want to do.

## File Placement

Place how-to guides in `docs/pages/how-to/`. Example: `docs/pages/how-to/configure.md`.

## What a How-to Guide Is

- Directions that guide the reader through a problem or towards a result
- Addresses an already-competent user who knows what they want to achieve
- Concerned with **work**, not study
- Like a recipe: a professional chef still uses recipes to ensure correctness

A how-to guide is NOT a tutorial. Tutorials serve learning; how-to guides serve work. See the distinction section below.

## Generation Workflow

### Step 1: Identify the Task

- What real-world problem or goal does the user have?
- Frame it from the **user's perspective**, not the tool's capabilities
- Good: "How to configure logging for production" (user need)
- Bad: "Using the LogConfig class" (tool-centric, not a need)

### Step 2: Determine Prerequisites

- What should the user already know or have set up?
- List these briefly at the top — do not teach them (that is a tutorial's job)

### Step 3: Write the Guide

Structure as a sequence of actions toward the goal. Apply all key principles below.

## Key Principles

### Address real-world complexity

A guide useless for any purpose except exactly the narrow case described is rarely valuable. Remain open to the range of possibilities so users can adapt guidance to their needs.

Use conditional steps: "If you are using X, do Y instead."

### Omit the unnecessary

Practical usability over completeness. A how-to guide should start and end in some reasonable place, requiring the reader to join it up to their own work. Unlike a tutorial, it does not need to be end-to-end.

### Provide a set of instructions

The steps are in the form of actions — including thinking and judgement, not just physical acts. Address how the user thinks as well as what the user does.

### Describe a logical sequence

The fundamental structure is a sequence that implies logical ordering in time. If one step sets up the environment for another, put it first even if the ordering is not strictly required.

### Seek flow

Ground sequences in the user's activity patterns. A workflow that has the user repeatedly switching contexts is clumsy. Consider:

- What are you asking the user to think about?
- How long must they hold a thought before resolving it in action?
- Does the guide require unnecessary back-and-forth?

At its best, a how-to guide anticipates the user — the helper who has the tool ready before you reach for it.

### Pay attention to naming

Titles must say exactly what the guide shows:

- Good: "How to integrate application performance monitoring"
- Bad: "Integrating application performance monitoring" (could be about whether to, not how)
- Worse: "Application performance monitoring" (could be anything)

### No digression, explanation, or teaching

Anything beyond action dilutes the guide. Do not explain concepts inline — link to explanation pages. Do not teach basics — that is a tutorial's job. Do not provide exhaustive reference — link to reference pages.

## Language Patterns

- **"This guide shows you how to…"** — Describe the problem and what will be solved
- **"If you want x, do y. To achieve w, do z."** — Conditional imperatives
- **"Refer to the X reference guide for a full list of options."** — Don't pollute with every option

## Python Package How-to Template

````markdown
# How to [Accomplish Specific Goal]

This guide shows you how to [goal description]. Use this when you need to
[real-world scenario].

## Prerequisites

- <package-name> installed ([Getting Started](../tutorials/getting-started.md))
- [Other requirement]

## Steps

### 1. [First Action]

```python
from <package_name> import <thing>

<configuration or setup code>
```

### 2. [Second Action]

If you are [condition A]:

```python
# approach for condition A
```

If you are [condition B] instead:

```python
# approach for condition B
```

### 3. [Verify / Complete]

```python
# verification step
```

## Common Variations

- **[Variation 1]**: [Brief guidance]
- **[Variation 2]**: [Brief guidance]

## Troubleshooting

**Problem: [common issue]**
: [Solution]

**Problem: [another issue]**
: [Solution]

## See Also

- [API Reference for X](../reference/api.md) — full list of options
- [About Y architecture](../explanation/architecture.md) — understanding the design
```text

## Typical How-to Guides for Python Packages

- **How to install** — pip, uv, conda, Docker, from source variations
- **How to configure <feature>** — settings, env vars, config files
- **How to integrate with <library>** — using alongside pytest, FastAPI, Django, etc.
- **How to deploy to production** — WSGI, Docker, cloud platforms
- **How to write a plugin / extension** — for extensible packages
- **How to migrate from vX to vY** — upgrade path with breaking changes
- **How to test your code** — patterns for testing code that uses the package
- **How to troubleshoot <category>** — common problems and solutions
- **How to contribute** — development setup, workflow, conventions

## Distinction from Tutorials

| Aspect | Tutorial | How-to Guide |
|--------|----------|-------------|
| User state | At study | At work |
| User skill | Beginner | Already competent |
| Goal | Learning experience | Task completion |
| Path | Single, managed | Branching, real-world |
| Setting | Contrived, safe | Real world, unpredictable |
| Choices | None — pick for them | Conditional alternatives |
| Responsibility | Teacher's | User's |
| Explanation | Minimal, inline | None — link out |

A tutorial teaches general skills through a specific exercise. A how-to guide helps accomplish a specific task using existing skills.

## Anti-Patterns to Avoid

- **Teaching basics** — Do not explain what a function is; the user is competent
- **Exhaustive options** — List 2-3 variations, link to reference for the rest
- **Tool-centric framing** — "How to use the X class" is not addressed to a human need
- **Missing conditionals** — Real-world tasks branch; acknowledge this with if/then guidance
- **Burying the action** — Lead with what to do, not why
