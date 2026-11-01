---
title: 2.1 Main-Branch Cutover Checklist
description: Checklist for promoting the 2.x line to main, parking the old line as 1.x-maintenance, and shipping 2.1.0 as the first stable PyPI release on the new main.
doc_status: deprecated
updated: '2026-06-03T00:00:00Z'
kind: How-To
---
> Migration note: This page documents a migration path or historical transition. It is not the current 3.2 happy path.

# 2.1 Main-Branch Cutover Checklist

Use this checklist to promote the `2.x` line to `main`, park the old line as `1.x-maintenance`, and ship `2.1.0` as the first stable PyPI release on the promoted line.

## Desired End State

- `main` points at the former `2.x` history and is the stable `2.x` line.
- `1.x-maintenance` points at the former `main` history and is clearly deprecated.
- `2.1.0` publishes both GitHub release artifacts and the PyPI package.
- Install and docs messaging consistently describe `1.x-maintenance` as maintenance-only.

## Phase 0: Freeze and Confirm

- [ ] Freeze non-release merges during the cutover window.
- [ ] Confirm the cutover is a branch rename/cutover, not a merge.
- [ ] Confirm the intended open-PR outcome:
  - PRs targeting `2.x` should land on the future `main`.
  - PRs targeting current `main` should either stay on `1.x-maintenance` or be explicitly rebased.
- [ ] Confirm the release version is `2.1.0`.

## Phase 1: Repo and Distribution Prep

- [ ] Merge the release-preparation changes for `2.1.0`:
  - version bump
  - changelog entry
  - README/docs release-track update
  - release workflow with PyPI publish
  - release-readiness targeting `main` (and temporarily `2.x`)
- [ ] Configure PyPI Trusted Publishing for `spec-kitty-cli`:
  - owner/repo: `Priivacy-ai/spec-kitty`
  - workflow: `.github/workflows/release.yml`
  - environment: `pypi`
- [ ] Verify GitHub environment settings for `pypi` if environment protection rules are used.
- [ ] Confirm branch protections are defined for both current `main` and `2.x` before rename.

## Phase 2: Pre-Cutover Verification

- [ ] Confirm latest `2.x` HEAD is the intended release candidate.
- [ ] Confirm `CI Quality` is green on that commit.
- [ ] Confirm `Release Readiness Check` passes for the `2.1.0` PR.
- [ ] Confirm `gh pr list` shows the expected open PRs and bases.
- [ ] Confirm docs and metadata now describe:
  - `main` as stable `2.x`
  - `1.x-maintenance` as deprecated maintenance-only
  - PyPI publication starting with `2.1.0`

## Phase 3: Branch Cutover on GitHub

Do these steps in GitHub settings/UI during the freeze window.

1. [ ] Temporarily change the default branch from current `main` to `2.x`.
2. [ ] Rename current `main` to `1.x-maintenance`.
3. [ ] Rename current `2.x` to `main`.
4. [ ] Set `main` back as the default branch.
5. [ ] Verify branch protection rules carried over correctly after rename.
6. [ ] Verify open PR retargeting:
   - current `2.x` PRs should now target `main`
   - current `main` PRs should now target `1.x-maintenance`

## Phase 4: Post-Cutover Repository Checks

- [ ] Verify the repository homepage and default-branch badge point at the new `main`.
- [ ] Verify raw `main` asset URLs still resolve as expected.
- [ ] Verify docs contribution/edit links point at `main`.
- [ ] Verify workflows trigger on the right branches after the rename.
- [ ] Verify `README.md` on GitHub clearly marks `1.x-maintenance` as deprecated.
- [ ] Add a short deprecation note or pinned issue for `1.x-maintenance` if desired.

## Phase 5: Release `2.1.0`

1. [ ] Check out the new `main` locally and pull latest.
2. [ ] Confirm `pyproject.toml` and `CHANGELOG.md` still show `2.1.0`.
3. [ ] Tag the release:
   ```bash
   git checkout main
   git pull origin main
   git tag -a v2.1.0 -m "Release v2.1.0"
   git push origin v2.1.0
   ```
4. [ ] Watch `.github/workflows/release.yml`.
5. [ ] Verify:
   - tests passed
   - distributions built
   - PyPI publish succeeded
   - GitHub release was created with artifacts and notes

## Phase 6: Release Verification

- [ ] Verify GitHub release `v2.1.0` exists.
- [ ] Verify PyPI shows `2.1.0` as the latest version.
- [ ] Verify `pipx install spec-kitty-cli` installs `2.1.0`; optionally verify
      `python -m pip install spec-kitty-cli` inside a virtual environment.
- [ ] Smoke-test `spec-kitty --version` and `spec-kitty init` from the PyPI install.
- [ ] Verify upgrade behavior on a representative existing project.

## Phase 7: Follow-Through

- [ ] Announce `2.1.0` as the new stable line.
- [ ] State clearly that `1.x-maintenance` is deprecated and maintenance-only.
- [ ] Update any external docs or pinned install instructions that still mention the old split-track model.
- [ ] Close or retarget any stale PRs/issues that still refer to the old branch setup.

## Current PRs to Check During Cutover

At the time this checklist was prepared:

- `#305` targets `2.x` and should end up on the new `main`.
- `#277` targets `2.x` and should end up on the new `main`.
- `#265` targets current `main` and should end up on `1.x-maintenance` unless intentionally rebased.

## Rollback Plan

If the branch rename causes unexpected automation or protection issues:

1. Pause tagging and PyPI publication.
2. Fix branch protection and workflow targeting on GitHub first.
3. Re-verify PR bases and default branch behavior.
4. Only tag `v2.1.0` after the branch model is stable.
