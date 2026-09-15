# Release Checklist

Use this checklist for releases from `main`.

> `main` is the primary release line and publishes both GitHub releases and PyPI packages.
> `1.x-maintenance` is deprecated overall, reserved for critical maintenance only, and should not receive new PyPI releases.
> Historical 2.x release notes remain in Git tags and changelog history; the 4.x release-candidate line ships from `main`; 3.x remains the previously published stable line.

## Pre-Release Preparation

### Version Planning

- [ ] Choose the version with [Semantic Versioning](https://semver.org/):
  - Patch (`X.Y.Z`): bug fixes and small improvements
  - Minor (`X.Y.0`): new features, backward-compatible platform changes
  - Major (`X.0.0`): breaking changes
- [ ] If cutting a prerelease, use a Python-compatible prerelease suffix (`X.Y.ZaN`, `X.Y.ZbN`, or `X.Y.ZrcN`) and plan to publish the final stable cut later as `X.Y.Z`.
- [ ] Confirm the release is intended for `main`, not `1.x-maintenance`.
- [ ] If the release also changes branch policy, docs, or distribution channels, include that in `CHANGELOG.md`.

### Release-Line Sanity

- **P3.4b prerequisite:** `.github/workflows/release.yml` and
  `release-readiness.yml` are deliberately deferred to the P3.4b release-topology
  sibling. Land that sibling before relying on this checklist's automated
  publishing or Release Readiness Check steps.
- [ ] Confirm the default branch is `main`.
- [ ] Confirm `1.x-maintenance` exists and is marked maintenance-only.
- [ ] Confirm open PRs are targeted intentionally:
  - New product work should target `main`.
  - Maintenance-only fixes should target `1.x-maintenance`.
- [ ] Confirm PyPI Trusted Publishing is configured for `spec-kitty-cli` against `.github/workflows/release.yml`.

### Code Quality

- [ ] Run the full test suite:
  ```bash
  pytest tests/ -v
  ```
- [ ] Verify migration registry completeness:
  ```bash
  pytest tests/upgrade/test_migration_robustness.py::TestMigrationRegistryCompleteness -v
  ```
- [ ] Run release validation in branch mode:
  ```bash
  python scripts/release/validate_release.py --mode branch --tag-pattern "v*.*.*"
  ```
- [ ] Run linting and formatting checks appropriate for changed files:
  ```bash
  ruff check .
  ruff format --check .
  ```
- [ ] Build the package and verify metadata:
  ```bash
  python -m build
  twine check dist/*
  ```
- [ ] Verify shared package drift against the release manifest:
  ```bash
  python scripts/release/check_shared_package_drift.py \
    --runtime-pyproject /path/to/spec-kitty-runtime/pyproject.toml
  ```
- [ ] Confirm `.kittify/release/shared-package-compatibility.json` is the
  authoritative 4.0.0 shared-package set and matches `pyproject.toml` plus
  `uv.lock`.
- [ ] Verify the built wheel installs cleanly with plain `pip`:
  ```bash
  python scripts/release/check_exact_install.py --package spec-kitty-cli
  ```

### Release-Candidate Hygiene

The charter requires release-candidate verification to include the full CLI
suite and cross-repo behavior evidence. Run these locally from a trusted runner
before tagging; do not rely on the tag-time publish workflow to run live
canary or cross-repo end-to-end suites.

- [ ] Record the full CLI test-suite result from `pytest tests/ -v`.
- [ ] Run the cross-repo end-to-end suite locally. The suite lives in
  `spec-kitty/EXPERIMENTAL-spec-kitty-end-to-end-testing` (it moved to the
  programme org; clone it beside this checkout):
  ```bash
  cd ../../spec-kitty-end-to-end-testing
  uv sync
  SPEC_KITTY_ENABLE_SAAS_SYNC=1 uv run pytest tests/ -v
  ```
- [ ] Run the live deployed-dev canary from the trusted-runner profile:
  ```bash
  cd ../../spec-kitty-end-to-end-testing
  ./scripts/run-canary.sh --profile local --phase all
  ```
- [ ] Record the e2e and canary result in the release PR, changelog note, or
  release issue. If either fails or is inconclusive, do not tag until the
  product issue is fixed or an explicit maintainer waiver with an issue link is
  recorded.

### Documentation and Metadata

- [ ] Bump `version` in `pyproject.toml`.
- [ ] Add a populated `## [X.Y.Z] - YYYY-MM-DD` section to `CHANGELOG.md`.
- [ ] For prereleases, use the exact prerelease heading (`## [X.Y.ZaN] - YYYY-MM-DD`, etc.).
- [ ] Remove any `tool.uv.override-dependencies` entries for `spec-kitty-*` packages before tagging.
- [ ] Review `README.md` release-track messaging:
  - `main` should be described as the `4.x` release-candidate line until stable acceptance.
  - `1.x-maintenance` should be described as deprecated maintenance-only.
- [ ] Review installation docs if distribution channels changed.
- [ ] If new ADRs were added, verify they are filed under the correct versioned architecture path.

### Upgrade and Migration Checks

- [ ] Test upgrade on a representative existing project:
  ```bash
  spec-kitty upgrade --dry-run
  spec-kitty upgrade
  ```
- [ ] Verify idempotency:
  ```bash
  spec-kitty upgrade
  ```
- [ ] If migrations changed agent assets or templates, smoke-test at least two agent integrations.

## Release Process

### 1. Create the Release Branch

```bash
git checkout main
git pull origin main
git checkout -b release/X.Y.Z
```

### 2. Commit Release Metadata

```bash
git add pyproject.toml CHANGELOG.md README.md RELEASE_CHECKLIST.md
git commit -m "chore(release): prepare X.Y.Z"
```

### 3. Push and Open the Release PR

```bash
git push origin release/X.Y.Z
gh pr create --base main --title "Release X.Y.Z" --fill
```

### 4. Wait for CI and Review

- [ ] `Release Readiness Check` passes for release metadata.
- [ ] `CI Quality` passes for tests, wheel build, lockfile, and exact install,
  or has explicitly accepted non-blocking failures with issue links.
- [ ] `Check Shared Package Drift` passes: `pyproject.toml`, `uv.lock` and the
  release manifest agree on the shared-package ranges and locks.
- [ ] The PR satisfies the active repository policy; do not rely on GitHub
  workflow enforcement — the workflow files run and post check results, but
  nothing requires them to pass before merge.
- [ ] Maintainer approval is recorded.
- [ ] Any release-note or install-doc feedback is resolved.

### 5. Merge the Release PR

- [ ] Use a merge strategy that leaves a PR marker in the main-branch commit
      message so the `Protect Main Branch` workflow can verify provenance.
      Today that means squash-merge for release PRs; do not use `--rebase`
      unless the protection workflow has been updated to recognize rebased PR
      commits.

```bash
gh pr merge --squash --delete-branch
```

### 6. Tag the Release from `main`

```bash
git checkout main
git pull origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

For prereleases, use the exact prerelease tag instead:

```bash
git tag -a vX.Y.ZaN -m "Release vX.Y.ZaN"
git push origin vX.Y.ZaN
```

If this release depends on a newly pinned shared package, release that upstream
package first, verify it is installable from PyPI, and only then tag the CLI.

### 7. Monitor Automated Publishing

- [ ] Watch `.github/workflows/release.yml`:
  ```bash
  gh run watch
  ```
- [ ] Verify the workflow:
  - runs tests
  - validates release metadata
  - checks shared-package drift
  - proves exact wheel installability with plain `pip`
  - builds distributions
  - publishes after tag-time release checks pass
  - creates the GitHub release
  - publishes to PyPI
  - verifies exact installability from PyPI with no local wheel
- [ ] Confirm release-candidate hygiene was already recorded before the tag:
  live canary and cross-repo end-to-end suites are required pre-release
  operator evidence, not tag-time publish workflow jobs.
- [ ] If this is a prerelease, confirm GitHub marks the release as `Pre-release`.
- [ ] Verify the publishing workflow result separately from branch health.
  A successful PyPI/GitHub release proves publication only; it does not prove
  that `main` is green.
- [ ] Verify CI Quality, Check Shared Package Drift, and other release evidence
  checks on the released commit are green, or record every failing check with an
  issue link before using the release as launch-gate evidence:
  ```bash
  gh run list --commit "$(git rev-parse HEAD)" --limit 20
  ```
- [ ] Verify the GitHub release payload:
  ```bash
  gh release view vX.Y.Z
  gh release download vX.Y.Z --dir /tmp/spec-kitty-release-check
  ```

### 8. Open the Next Development Cycle

Do this as soon as the tag is pushed, ahead of routine merges. Branch-mode release
validation (`scripts/release/validate_release.py --mode branch`) requires `main`'s
version to advance beyond the latest tag. It runs in the scheduled Release Readiness
Check on `main` and on every pull request that changes `pyproject.toml`. Right after
tagging, `main` still carries the tagged version, so that check fails with "Version
does not advance beyond latest tag" until this step lands (#4290).

- [ ] Open a pull request to `main` that moves the working version to the next
  development or candidate version (for example `4.0.0rc2` → `4.0.0rc3` on a
  release-candidate line), with no product changes:
  - `version` in `pyproject.toml`
  - the project's own entry in `uv.lock`
  - `.kittify/metadata.yaml`
  - a new `## [Unreleased] - <next version>` heading at the top of `CHANGELOG.md`,
    then refresh the docs retrieval index with `python -m scripts.docs.docs_index --write`
- [ ] Give that pull request priority so it merges ahead of routine work. Changes
  that merge after the tag belong to the next version, not the published one.
- [ ] After it merges, confirm the Release Readiness Check on `main` is green.

## Post-Release Verification

### Package Availability

- [ ] Verify PyPI shows the new version:
  ```bash
  python -m pip index versions spec-kitty-cli
  ```
- [ ] Verify the GitHub release is public and includes the wheel, sdist, and checksums.
- [ ] If this is a prerelease, verify installation with:
  ```bash
  python -m pip install --upgrade --pre "spec-kitty-cli==X.Y.ZaN"
  ```

### Installation and Upgrade

- [ ] Test a fresh install:
  ```bash
  python -m pip install --force-reinstall spec-kitty-cli==X.Y.Z
  spec-kitty --version
  ```
- [ ] Test an exact prerelease install path in a clean virtualenv:
  ```bash
  python -m venv /tmp/spec-kitty-release-check
  /tmp/spec-kitty-release-check/bin/python -m pip install --upgrade pip
  /tmp/spec-kitty-release-check/bin/python -m pip install "spec-kitty-cli==X.Y.ZaN"
  /tmp/spec-kitty-release-check/bin/spec-kitty --version
  ```
- [ ] Test upgrade from the previous stable release on a sample project.

### Communication

- [ ] If this is a minor or major release, publish release notes and migration guidance.
- [ ] If release-track policy changed, call it out explicitly:
  - `main` is the `4.x` release-candidate line until stable acceptance
  - `1.x-maintenance` is deprecated maintenance-only
  - no new `1.x` PyPI releases are planned

## Maintenance-Line Policy

- [ ] Only cut `1.x-maintenance` releases for critical fixes.
- [ ] Do not publish new `1.x` releases to PyPI.
- [ ] If a `1.x-maintenance` release is needed, use GitHub tags/releases only and state clearly that the line is deprecated.

## Rollback Procedure

If a critical issue is discovered after release:

1. Cut a hotfix from `vX.Y.Z` and release `X.Y.(Z+1)` as soon as practical.
2. If the PyPI artifact is broken and no hotfix is ready yet, yank the PyPI release and update the GitHub release notes with the replacement plan.
3. Prefer forward fixes over deleting published tags.

## Common Gotchas

- **Validation fails with "Version does not advance beyond latest tag"**:
  bump `pyproject.toml` to a higher semantic version. On `main` right after a tag
  this is expected until the next cycle is open; see step 8 of the Release Process.
- **Validation fails with "CHANGELOG.md lacks a populated section"**:
  add `## [X.Y.Z]` with real release notes before tagging.
- **PyPI publish fails**:
  check PyPI Trusted Publishing configuration for the workflow and repository, not a legacy token secret.
- **Fresh install still shows the old version**:
  wait a few minutes for package indexes to refresh, then retry with `pip cache purge` if needed.
- **Prerelease install does not resolve**:
  stop and inspect the published dependency metadata, starting with the built
  wheel's `Requires-Dist` and any newly pinned shared packages.

---

**Last Updated**: 2026-09-14
