---
name: diataxis-explanation-writer
description: Generate understanding-oriented explanation documentation for Python packages following Diátaxis principles. Use when asked to write conceptual docs, architecture overview, design decisions, "about" pages, "why" docs, background context, or any documentation that helps the reader understand a topic through reflection and discussion. Triggers on "write an explanation", "conceptual docs", "architecture overview", "design decisions", "why did we choose", "background", "about the design", "explain the architecture".
---

# Diátaxis Explanation Writer

Generate explanation documentation — understanding-oriented discussion that helps the reader make sense of a topic through reflection.

Explanation is like reading **On Food and Cooking** by Harold McGee: it does not teach you to cook or give you recipes, but it places cooking in context of history, science, and society, deepening your understanding of the craft.

## File Placement

Place explanation pages in `docs/pages/explanation/`. Example: `docs/pages/explanation/concepts.md`.

## What Explanation Is

- Discursive treatment of a subject that permits reflection
- Deepens and broadens understanding by providing context, connections, and perspective
- An answer to "Can you tell me about…?"
- The only documentation you might read in the bath — away from the keyboard

Explanation serves the user's **study**, not their work. It is the counterpart to reference (which also contains propositional knowledge but serves work).

## Generation Workflow

### Step 1: Identify the Topic

- What concept, decision, or aspect of the package would benefit from deeper understanding?
- Frame it as an implicit "About…": "About the plugin architecture", "About authentication design"
- Choose a topic that can be meaningfully bounded — not the entire package, but a coherent area

### Step 2: Gather Context

- Read the source code to understand the design
- Check git history or ADRs for decision rationale
- Look at `README.md` and existing docs for hints about design philosophy
- Identify connections to other systems, concepts, or alternatives

### Step 3: Write the Explanation

Structure as a discussion that circles around the topic from different angles. Apply all key principles below. Target 500-2000 words.

## Key Principles

### Make connections

Weave a web of understanding. Connect the topic to other things — even outside the immediate subject — if it helps comprehension.

"The event system works similarly to browser DOM events, where handlers are registered for specific event types and called when those events fire."

### Provide context

Explain **why** things are the way they are: design decisions, historical reasons, technical constraints. Draw implications. Mention specific examples.

"We chose SQLite as the default backend because it requires zero configuration and ships with Python's standard library. For production workloads exceeding 100 concurrent writers, see the PostgreSQL backend."

### Talk about the subject

Explanation guides are **about** a topic — they circle around it. The title should allow an implicit "about": "About user authentication", "About the caching strategy".

Discuss:
- The bigger picture
- History and evolution
- Choices, alternatives, possibilities
- Why: reasons and justifications

### Admit opinion and perspective

All human creation is invested with opinion. Explanation can and must consider alternatives, counter-examples, and multiple approaches. It is a discussion, not a decree.

"Some teams prefer a monolithic configuration file while others split settings by concern. Both approaches have trade-offs…"

### Keep explanation closely bounded

One risk of explanation is absorbing other things. The urge to include instruction (how-to) or technical description (reference) is strong. Resist it — those have their own places. Allowing them in interferes with the explanation and removes them from where they belong.

## Language Patterns

- **"The reason for X is because historically, Y…"** — Explain origins
- **"W is better than Z, because…"** — Offer judgements where appropriate
- **"An X in this system is analogous to a Y in…"** — Provide context through analogy
- **"Some users prefer W (because Z). This can be a good approach, but…"** — Weigh alternatives
- **"X interacts with Y as follows:…"** — Unfold internal workings to build understanding

## Python Package Explanation Template

```markdown
# About [Topic]

[Opening paragraph that frames the topic and why it matters to the reader's
understanding of the package.]

## Overview

[High-level description of the concept, system, or decision being explained.
Connect it to the reader's existing knowledge.]

## Why [This Approach]

[Explain the reasoning behind the design. What problem does it solve? What
alternatives were considered? What constraints shaped the decision?]

For example, [concrete example that illustrates the concept].

## How It Works

[Describe the mechanism at a conceptual level — not a step-by-step procedure
(that would be a how-to), but the logic and flow of the system.]

[Diagrams or analogies are valuable here.]

## Trade-offs and Alternatives

[Discuss what was gained and what was given up. Mention alternative approaches
and why they were not chosen — or when they might be better.]

| Approach | Pros | Cons |
|----------|------|------|
| Current approach | ... | ... |
| Alternative A | ... | ... |
| Alternative B | ... | ... |

## Connections

[Link this topic to related concepts, other parts of the system, or broader
patterns in the ecosystem.]

- [Related concept in the package](other-explanation.md)
- [API Reference for this system](../reference/api.md)
- [How to configure this feature](../how-to/configure.md)
```

## Typical Explanation Pages for Python Packages

- **Architecture Overview** — How the package is structured, the component graph, data flow
- **Design Decisions** — Why certain approaches were chosen (ADR-style or narrative)
- **Key Concepts** — Domain terminology, mental models, glossary with depth
- **Plugin/Extension Model** — How extensibility works and why it is designed this way
- **Performance Characteristics** — Complexity analysis, caching strategy rationale, benchmarks with context
- **Security Model** — Trust boundaries, threat model, why certain security choices were made
- **Comparison with Alternatives** — How this package differs from similar tools, when to choose which
- **History and Evolution** — How the package got to its current state (for mature projects)

## Distinction from Reference

| Aspect | Explanation | Reference |
|--------|------------|-----------|
| Purpose | Illuminate a topic | Describe the machinery |
| User mode | At study | At work |
| Tone | Discursive, reflective | Austere, neutral |
| Content | Context, reasons, opinions | Facts, specifications |
| Structure | Circles around a topic | Mirrors code structure |
| When read | Away from the keyboard | While coding |
| Test | "Could I read this in the bath?" → explanation | "Is this boring?" → reference |

## Anti-Patterns to Avoid

- **Disguised reference** — Lists of parameters or API details belong in reference
- **Disguised how-to** — Step-by-step procedures belong in how-to guides
- **No clear topic** — Every explanation must be "about" something bounded
- **Too abstract** — Ground discussion in concrete examples from the actual package
- **Missing the "why"** — If it does not answer "why", it is probably reference, not explanation
- **Unbounded scope** — Explanation that tries to cover everything covers nothing well
