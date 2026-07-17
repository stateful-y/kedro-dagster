# Diátaxis Compass and Documentation Patterns

## Full Compass Table

| Content characteristic | Tutorial | How-to Guide | Reference | Explanation |
|----------------------|----------|-------------|-----------|-------------|
| **What they do** | Introduce, educate, lead | Guide | State, describe, inform | Explain, clarify, discuss |
| **Answers the question** | "Can you teach me to…?" | "How do I…?" | "What is…?" | "Why…?" |
| **Oriented to** | Learning | Goals | Information | Understanding |
| **Purpose** | Provide a learning experience | Help achieve a particular goal | Describe the machinery | Illuminate a topic |
| **Form** | A lesson | A series of steps | Dry description | Discursive explanation |
| **Analogy** | Teaching a child to cook | A recipe in a cookbook | Info on a food packet | Article on culinary history |

## Boundary Blur Risks

Adjacent quadrants share affinities that cause content to bleed across boundaries:

| Shared trait | Quadrants at risk | Common mistake |
|-------------|------------------|----------------|
| Guide action | Tutorial ↔ How-to | Conflating "getting started" with "how to configure" |
| Serve application of skill | Reference ↔ How-to | Stuffing procedures into API docs |
| Contain propositional knowledge | Reference ↔ Explanation | Expanding reference examples into explanations |
| Serve acquisition of skill | Tutorial ↔ Explanation | Overloading tutorials with background context |

## Python Package Page Patterns

### Typical Tutorial Pages
- **Getting Started** — Install via pip/uv, import, call a function, verify output
- **Your First <Feature>** — Build something small end-to-end
- **Tutorial Series Part N** — Multi-part progressive learning path

### Typical How-to Pages
- **How to install** (with variations: pip, uv, conda, Docker, from source)
- **How to configure <feature>** — Settings, env vars, config files
- **How to integrate with <library>** — Using the package alongside another tool
- **How to deploy** — Production setup, CI/CD integration
- **How to extend / write plugins** — For extensible packages
- **How to migrate from vX to vY** — Upgrade guides
- **Troubleshooting** — Common problems and solutions

### Typical Reference Pages
- **API Reference** — Auto-generated via mkdocstrings (modules → classes → methods)
- **CLI Reference** — Commands, flags, options, exit codes
- **Configuration Reference** — All settings with types, defaults, descriptions
- **Error Reference** — Exception classes, error codes, meanings
- **Changelog** — Version history (auto-generated via git-cliff or similar)

### Typical Explanation Pages
- **Architecture Overview** — How the package is structured and why
- **Design Decisions** — Why certain approaches were chosen
- **Key Concepts** — Domain terminology and mental models
- **Comparison with Alternatives** — How this package differs from similar tools
- **Performance Characteristics** — Complexity, benchmarks, trade-offs
- **Security Model** — Trust boundaries, threat model (when applicable)

## Complex Hierarchy Patterns

### Single Product, Multiple User Types

```text
docs/
  getting-started.md                    # tutorial (all users)
  how-to/
    users/                              # how-to for end users
      configure.md
      troubleshoot.md
    developers/                         # how-to for integrators
      extend.md
      write-plugins.md
    contributors/                       # how-to for maintainers
      development-setup.md
      release-process.md
  reference/
    api.md                              # reference (shared)
    cli.md
    config.md
  explanation/
    architecture.md                     # explanation (shared)
    design-decisions.md
```

### Single Product, Multiple Deployment Targets

```text
docs/
  getting-started.md                    # tutorial (generic)
  how-to/
    install-pip.md                      # how-to per target
    install-docker.md
    install-from-source.md
    deploy-aws.md
    deploy-gcp.md
  reference/                            # reference (shared)
    api.md
    config.md
  explanation/                          # explanation (shared)
    architecture.md
```

## Contents Page Guidelines

- Landing pages should read as overviews, not bare lists
- Keep lists under 7 items per group; break into sub-sections if longer
- Use headings with brief introductory text to provide context
- Each landing page should help the user quickly find what they need

## Quality Checklist

### Functional Quality (measurable)
- [ ] Accurate — code examples run, commands produce stated output
- [ ] Complete — all public API surface documented
- [ ] Consistent — terminology, formatting, style uniform across pages
- [ ] Up-to-date — matches current version of the package

### Deep Quality (experiential)
- [ ] Flow — reader progresses naturally without jarring transitions
- [ ] Fit to needs — each page serves a clear user need
- [ ] Anticipation — docs address questions before they arise
- [ ] Minimal friction — no unnecessary detours or digressions
