# Mission Specification: GitHub Actions Sonar hardening (validatable workflows)

**Mission**: ghactions-sonar-hardening-01M2FYX1
**Issue**: #4342 (GitHub Actions hardening cluster) — epic #1928, milestone 4.0.0
**Origin**: current-profile SonarCloud debt cluster on `spec-kitty_spec-kitty` (analysis 2026-09-14), replacing the retired pre-migration code-smell tickets.

## Intent Summary

Harden the project's **PR-CI-validated** GitHub Actions workflows per the live SonarCloud
`githubactions` findings, **without changing any CI behavior**. Primary actor: the CI/security
maintainer. Trigger: SonarCloud flags 99 `githubactions` findings; ~25 in the validatable
workflows are genuine hardening, the rest are safe-as-written (hotspot review) or false-positive.
Desired outcome: the exposed inputs, unpinned actions, over-broad permissions, and unpinned
3rd-party installs in the eight PR-exercised workflows are hardened; the safe-as-written
`uv sync --frozen` self-install hotspots and false-positives are adjudicated (no edit) with
rationale. Invariant that must always hold: **every edited workflow remains functionally
identical** — this is security hardening only, and the PR's own CI run (which exercises all
eight in-scope workflows) must stay green.

**Release-critical workflows are OUT of scope** (`release.yml`, `release-readiness.yml`,
`ci-nightly.yml`): they are not exercised by PR CI, so hardening edits there cannot be validated
before merge — deferred to a separate follow-up with a manual dry-run. `docs-pages.yml` is
excluded (under change in PR #4286).

Grounding (opus classification pass, read-only) established the load-bearing facts: the project
self-installs via `build-backend = hatchling.build`, so `uv sync --frozen` **must** build — a
`--no-build`/`--only-binary` "fix" would break every run; the lock carries 1420 sha256 hashes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Workflow inputs can no longer be script-injected (Priority: P1)
A `run:` block interpolates `${{ inputs.X }}` directly, so a crafted input could inject shell.
After this mission those interpolations are routed through step `env:` vars referenced as `"$VAR"`,
closing the injection class without changing what the step does.
**Acceptance**: every S7630 site in the eight in-scope workflows uses `env:`-indirection; the
workflow's observable behavior (same commands, same args) is unchanged; PR CI green.

### User Story 2 - Third-party actions and installs are pinned (Priority: P2)
Flagged third-party actions run at a moving tag, and a few 3rd-party `pip`/`npm` installs are
unpinned. After this mission each flagged action is pinned to **its own current tag's** full-length
commit SHA (same version, `# vX` trailing comment) and the bare 3rd-party installs get exact pins /
`--only-binary :all:`.
**Acceptance**: each S7637/S8544/S8543 in-scope site is pinned to a SHA/version that resolves to
the same code it ran before; `uv sync --frozen` self-install steps are untouched; PR CI green.

### User Story 3 - Workflow permissions follow least privilege (Priority: P2)
Workflow-level `permissions` grant more than a single job needs. After this mission the grant is
relocated to the specific job(s) that require it, every needing job retaining its access.
**Acceptance**: each S8264/S8233 in-scope workflow declares permissions at job scope; no job that
needed a permission loses it; PR CI green.

### User Story 4 - Safe-as-written findings are adjudicated, not churned (Priority: P1)
The 46 `uv sync --frozen` S8541 hotspots (self-install must build), the self-bootstrap/drift
S8544 sites, the S6505 npm-lifecycle sites, and the ~6 false-positives are **not** edited; they
are recorded with won't-fix rationale for Sonar UI + the PR body.
**Acceptance**: an adjudication dossier lists each safe-as-written/FP finding with its rationale;
zero code edits are made for them.

### Edge Cases
- SHA-pinning a moving tag must resolve the CURRENT tag SHA (no silent version bump).
- Permission relocation must enumerate every job first — a missed job silently loses access.
- `module-tests.yml` inputs (`test_dirs`, `cov_target`) feed a heredoc Python script as argv;
  env round-tripping must preserve JSON quoting.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-001 | Move every in-scope S7630 `${{ inputs.* }}` interpolation out of `run:` into a step `env:` var referenced as `"$VAR"` (module-tests.yml ×9), behavior-identical. | Proposed |
| FR-002 | Pin each in-scope S7637 third-party action to its OWN current tag's full-length commit SHA with a `# vX` comment, no version change (ci-quality.yml setup-uv ×4; ci-windows.yml paths-filter ×1). | Proposed |
| FR-003 | Relocate in-scope S8264/S8233 workflow-level permissions to the specific job(s) needing them (ci-aggregate.yml, ci-fleet-verdict.yml, ci-windows.yml), every needing job retaining access. | Proposed |
| FR-004 | Harden bare in-scope 3rd-party installs with exact pins and/or `--only-binary :all:` and pin the claude-code npm tool (ci-modules.yml pyyaml; check-spec-kitty-events-alignment.yml packaging; ci-aggregate.yml pyyaml + diff-cover/defusedxml; packs.yml claude-code S8543). MUST NOT touch `uv sync --frozen` self-install steps. | Proposed |
| FR-005 | Produce an adjudication dossier (won't-fix rationale, no code edit) for the in-scope safe-as-written hotspots (46 `uv sync --frozen` S8541, S8544 self-bootstrap/drift, S6505 npm/npx) and the ~6 false-positives, for Sonar UI + PR body. | Proposed |

### Non-Functional Requirements

| ID | Requirement | Threshold / Measure | Status |
|----|-------------|---------------------|--------|
| NFR-001 | No CI behavior change. | The eight in-scope workflows remain functionally identical; the PR's own CI run (which exercises them) is green. | Proposed |
| NFR-002 | Scope boundary respected. | Zero edits to release.yml, release-readiness.yml, ci-nightly.yml, docs-pages.yml. | Proposed |
| NFR-003 | Workflow YAML validity. | actionlint / YAML parse clean on every edited file. | Proposed |

### Constraints

| ID | Constraint | Status |
|----|-----------|--------|
| C-001 | Code change and hotspot review are SEPARATE actions (charter Sonar expectations). Safe-as-written/FP findings get NO code edit — only adjudication. | Active |
| C-002 | SHA-pin to each action's OWN current version SHA — never unify versions (a version change is out of scope). | Active |
| C-003 | Permission relocation MUST enumerate every job that uses the grant before moving it; never drop a needed permission. | Active |
| C-004 | `uv sync --frozen` (hatchling self-install) MUST NOT receive `--no-build`/`--only-binary`; it must build the project. | Active |

### Key Entities
- **In-scope workflow** — one of the eight PR-CI-validated files: ci-quality, ci-windows, module-tests, ci-aggregate, ci-fleet-verdict, ci-modules, check-spec-kitty-events-alignment, packs.
- **Adjudication finding** — a safe-as-written or false-positive Sonar finding recorded with rationale, not edited.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- Every in-scope S7630/S7637/S8264/S8233/real-install finding is remediated with a behavior-identical edit; PR CI green.
- The 46 `uv sync --frozen` S8541 hotspots + FPs are adjudicated with rationale and receive zero edits.
- No edits to any out-of-scope (release-critical / deferred) workflow.
