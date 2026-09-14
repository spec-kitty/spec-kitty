# Implementation Plan: GitHub Actions Sonar hardening (validatable workflows)

**Branch**: `fix/ghactions-sonar-hardening` | **Spec**: kitty-specs/ghactions-sonar-hardening-01M2FYX1/spec.md
**Issue**: #4342 (epic #1928, milestone 4.0.0)

## Summary

Harden the eight PR-CI-validated GitHub Actions workflows per the live SonarCloud
`githubactions` findings, behavior-identically (NFR-001), and adjudicate the safe-as-written
`uv sync --frozen` hotspots + false-positives without editing them (C-001). Four remediation
families over disjoint file sets, plus one edit-free adjudication dossier. Release-critical and
non-PR-exercised workflows are out of scope (NFR-002).

## Technical Context

**Language/Version**: GitHub Actions workflow YAML (schema per actionlint); no application code.
**Primary Dependencies**: none new — edits are to `.github/workflows/*.yml` + `.github/actions/warmup/action.yml` (warmup not in the actionable set). Validation via `actionlint` (or YAML parse) + the PR's own CI run.
**Storage**: N/A.
**Testing**: the eight in-scope workflows are exercised by the PR's own CI run — that green run IS the acceptance signal (no workflow can be fully validated locally). Plus `actionlint`/YAML-parse per edited file. No unit tests (declarative YAML).
**Target Platform**: GitHub-hosted Actions runners.
**Project Type**: single (CI configuration).
**Performance Goals**: none (no runtime change).
**Constraints**: no CI behavior change (NFR-001); SHA-pin each action to its own current version (C-002); enumerate jobs before relocating permissions (C-003); never `--no-build` the hatchling self-install (C-004); code change vs hotspot review are separate actions (C-001).
**Scale/Scope**: ~25 actionable edits across 8 files + a ~53-finding adjudication dossier; 5 work packages.

## Constitution Check
Charter Sonar expectations apply: code change and hotspot review are separate actions; every edit
behavior-identical; PR body must call out remaining Sonar UI hotspot work (FR-005). No gate violations.

## Parallel Work Analysis

### Dependency Graph
```
WP01 (S7630 injection, module-tests.yml)            ─┐
WP02 (S7637 SHA-pin, ci-quality.yml + ci-windows.yml)─┤
WP03 (S8264/S8233 perms + installs, ci-aggregate.yml + ci-fleet-verdict.yml)─┼─ disjoint files → parallel → integrate
WP04 (installs, ci-modules.yml + events-alignment.yml + packs.yml)          ─┤
WP05 (adjudication dossier, NO owned workflow files)                        ─┘
```

### Work Distribution (file-partitioned — no owned_files overlap)
- **WP01** — S7630 input-injection env-indirection. owned_files: `.github/workflows/module-tests.yml` (9 sites; care with `inputs.test_dirs`/`cov_target` JSON argv).
- **WP02** — S7637 action SHA-pinning. owned_files: `.github/workflows/ci-quality.yml` (setup-uv ×4), `.github/workflows/ci-windows.yml` (paths-filter ×1 + its S8264 perm + S8544). Single-owned so ci-windows's multiple rules land together.
- **WP03** — least-privilege + ci-aggregate installs. owned_files: `.github/workflows/ci-aggregate.yml` (S8264 perms + pyyaml/diff-cover/defusedxml pins), `.github/workflows/ci-fleet-verdict.yml` (S8233 perm).
- **WP04** — 3rd-party install hardening. owned_files: `.github/workflows/ci-modules.yml` (pyyaml), `.github/workflows/check-spec-kitty-events-alignment.yml` (packaging), `.github/workflows/packs.yml` (claude-code S8543 pin; S6505 npm = adjudicate note in body, no edit).
- **WP05** — adjudication dossier (FR-005). owned_files: `kitty-specs/ghactions-sonar-hardening-01M2FYX1/adjudication.md` (a mission artifact) — the won't-fix rationale for the 46 `uv sync --frozen` hotspots, S8544 self-bootstrap/drift, S6505 npm/npx, and the ~6 FPs. NO workflow edits.

### Coordination Points
- **Integration**: the PR's own CI run over the eight edited workflows must be green (NFR-001). Each WP verified individually by actionlint/YAML parse; the PR run is the behavioral gate.

### Out of scope (deferred)
`release.yml`, `release-readiness.yml`, `ci-nightly.yml` (not PR-exercised — separate follow-up + manual dry-run), `docs-pages.yml` (PR #4286).
