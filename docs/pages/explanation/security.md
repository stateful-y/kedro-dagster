# Security

Kedro-Dagster is built on a hardened, security-first release pipeline. This page
explains the measures that protect you as a *user* of the package and what each one means
in practice, so you can depend on it with confidence.

## How releases reach you safely

**Trusted publishing (OIDC).** Releases are published to PyPI through GitHub's OpenID
Connect trusted-publishing flow. No long-lived PyPI API token exists anywhere to be stolen
and used to push a malicious release: a release can only originate from this project's own
audited release workflow.

**Signed artifacts (PEP 740 attestations).** Every published distribution carries a
cryptographic attestation, produced with Sigstore, binding the artifact to the exact
workflow run that built it. You can verify that what you install is what this project
actually released, not a tampered copy.

**A software bill of materials (SBOM).** Each release ships a CycloneDX SBOM enumerating
every dependency it resolves. When a vulnerability is disclosed in a transitive
dependency, you can tell in seconds whether a given release is affected.

**Immutable, monitored dependencies.** Third-party GitHub Actions and Python dependencies
are pinned, and Renovate keeps them current as reviewable pull requests. A dependency
cannot be swapped out from under a release, and updates arrive as visible changes rather
than silent drift.

## How the code is checked

**Static security analysis.** Every change is scanned with ruff's flake8-bandit (`S`)
ruleset, which flags insecure patterns (unsafe subprocess use, weak hashing, hardcoded
credentials, unsafe deserialization) before they can merge.

**Deep analysis (CodeQL).** GitHub's CodeQL runs data-flow analysis on every change and on
a weekly schedule, catching vulnerability classes such as injection and path traversal that
line-level linting cannot see.

**Secret scanning.** gitleaks runs both as a pre-commit hook and as a CI check that cannot
be bypassed, so credentials and keys never enter the codebase or a release.

## How the pipeline itself is hardened

**Least privilege.** Every automation workflow runs with a read-only token by default;
only the specific jobs that must write are granted more. A compromised step cannot quietly
rewrite the repository.

**A single merge gate.** No change lands on the main branch until the full test suite and
the security checks above all pass, enforced as one required status check.

**Untrusted input never becomes code.** Values an outsider controls -- a pull request
title, an issue body, a fork's branch name -- reach a workflow's shell only as environment
variables. Workflow expressions are substituted into a script *before* the shell parses
it, so interpolating one directly turns a crafted pull request title into commands that
run with the release job's privileges. Quoting does not help; passing the value through
`env:` does, because the runner then hands it over as data. A test asserts no workflow
interpolates such a value into a `run:` or `script:` body.

**Scoped automation identity.** Release automation authenticates with a short-lived,
narrowly-scoped GitHub App token rather than a broad personal access token, so there is no
long-lived automation credential to leak.

## Transparency and disclosure

**An independent security grade.** This repository is scored weekly by the
[OpenSSF Scorecard](https://securityscorecards.dev/), an external automated audit of its
security practices (pinned dependencies, token permissions, branch protection, and more).
The result is public, so the posture is verifiable rather than merely asserted.

**Responsible disclosure.** If you find a vulnerability, the
[security policy](https://github.com/stateful-y/kedro-dagster/security/policy)
explains how to report it privately, before any public disclosure.

**Reviewed changes.** Code ownership is declared in `CODEOWNERS`, so changes are reviewed
before they merge.
