# Release Scripts

This directory contains helper scripts that keep local release checks aligned with the
automated release pipeline for stable and prerelease releases from `main`.

## Stable Release Scope

- Branch: `main`
- Versioning: stable releases use `X.Y.Z` in `pyproject.toml`
- Tags: `vX.Y.Z`
- Publication targets: GitHub Releases and PyPI

## Prerelease Publish Scope

- Branch: `main`
- Versioning: prereleases use `X.Y.ZaN`, `X.Y.ZbN`, or `X.Y.ZrcN`
- Tags: `vX.Y.ZaN`, `vX.Y.ZbN`, or `vX.Y.ZrcN`
- Publication targets: GitHub Releases and PyPI
- Installer behavior: users must pass `--pre` (or pin the exact prerelease) to `pip`

Branch-mode readiness checks accept both stable and prerelease versions.
Tag-mode publish checks now accept matching prerelease tags as well, and GitHub
marks those releases as prereleases automatically.

## Scripts

### `validate_release.py`

Validates release readiness by checking version alignment, changelog completeness, and
version progression relative to existing tags.

#### Usage

```bash
# Branch mode (for PRs and local development)
python scripts/release/validate_release.py --mode branch --tag-pattern "v*.*.*"

# Tag mode (for release workflow)
python scripts/release/validate_release.py --mode tag --tag v3.0.1 --tag-pattern "v*.*.*"
```

#### What it validates

- `pyproject.toml` version is a valid stable or prerelease version
- `CHANGELOG.md` contains populated section for that version
- Version advances beyond latest existing release tag
- In tag mode: tag matches version (for example `v3.0.1` <-> `3.0.1`, `v3.1.0a0` <-> `3.1.0a0`)

### `changelog_fragments.py`

Pull requests add their changelog entries as fragments in `docs/changelog/unreleased/<id>.<section>.md`
instead of editing `CHANGELOG.md`. At release time this folds them into `## [Unreleased]`
and deletes them. In tag mode `validate_release.py` refuses while any fragment remains.

```bash
python -m scripts.release.changelog_fragments check             # names and shape
python -m scripts.release.changelog_fragments assemble          # preview the section
python -m scripts.release.changelog_fragments assemble --write  # fold in, delete fragments
```

### `extract_changelog.py`

Extracts a version section from `CHANGELOG.md` for GitHub Release notes.

```bash
python scripts/release/extract_changelog.py 2.0.0
```

### `check_shared_package_drift.py`

Validates that `.kittify/release/shared-package-compatibility.json` is the
release authority for the CLI's compatible shared-package ranges and exact
`uv.lock` versions, that no emergency `tool.uv` override remains in CLI
metadata, and that retired `spec-kitty-runtime` is not a CLI dependency.

```bash
python scripts/release/check_shared_package_drift.py
```

### `check_exact_install.py`

Builds a clean temporary virtualenv, installs the built wheel with plain
`pip`, and can run an installed console script so release-time dependency
metadata and entrypoint imports are exercised exactly as users will see them
from PyPI.

```bash
python scripts/release/check_exact_install.py \
  --package spec-kitty-cli \
  --console-script spec-kitty \
  --console-arg=--version

# After PyPI publish, verify the exact public artifact with no local wheel.
python scripts/release/check_exact_install.py \
  --package spec-kitty-cli \
  --version X.Y.Z \
  --from-index \
  --console-script spec-kitty \
  --console-arg=--version
```

## Workflow Integration

- PR release metadata validation: `.github/workflows/release-readiness.yml`
- PR/package CI: `.github/workflows/ci-quality.yml`
- PR shared-package pin drift: `.github/workflows/check-spec-kitty-events-alignment.yml`
- Tag releases: `.github/workflows/release.yml` (triggers on stable and prerelease `v*.*.*` tags)

Release PR check ownership:

1. `Release Readiness Check` validates release metadata only: version, changelog, and tag progression.
2. `CI Quality` owns tests, wheel build, lockfile checks, and exact install verification.
3. `Check Shared Package Drift` owns shared-package pin drift evidence.

Live canary and cross-repo end-to-end runs are release-candidate hygiene, not
tag-time publish jobs. The charter still requires them before a release
candidate is tagged; the release owner must run them locally from a trusted
runner and record the pass, product failure, inconclusive result, or explicit
maintainer waiver.

Tag-time publish workflow sequence:

1. run tests
2. validate release metadata
3. build the wheel candidate
4. verify shared-package drift
5. verify exact installability from the built wheel
6. verify artifacts and extract changelog notes
7. create GitHub Release
8. publish to PyPI
9. verify exact installability from PyPI with `pip install spec-kitty-cli==X.Y.Z`

## Local Release Workflow

```bash
# 1) prepare version + changelog
git checkout main
git pull origin main
git checkout -b release/3.1.0a0
vim pyproject.toml   # version = "3.1.0a0" for prerelease, "3.1.0" for stable
vim CHANGELOG.md     # add ## [3.1.0a0] - YYYY-MM-DD (or final ## [3.1.0])

# 2) validate
python scripts/release/validate_release.py --mode branch --tag-pattern "v*.*.*"
python -m pytest
python scripts/release/check_shared_package_drift.py
python -m build
python scripts/release/check_exact_install.py --package spec-kitty-cli
twine check dist/*

# 3) release-candidate hygiene (local trusted-runner evidence, before tagging)
pushd ../../spec-kitty-end-to-end-testing
uv sync
SPEC_KITTY_ENABLE_SAAS_SYNC=1 uv run pytest tests/ -v
./scripts/run-canary.sh --profile local --phase all
popd

# 4) clean build artifacts
rm -rf dist/ build/

# 5) commit, push, and merge the release metadata through a PR
spec-kitty safe-commit --message "chore(release): prepare 3.1.0a0" pyproject.toml CHANGELOG.md
git push origin release/3.1.0a0
gh pr create --base main --title "Release 3.1.0a0" --fill

# 6a) prerelease publish from updated main
git checkout main
git pull origin main
git tag v3.1.0a0 -m "Release 3.1.0a0"
git push origin v3.1.0a0

# 6b) stable publish from updated main
#     Edit pyproject.toml to "3.1.0" and rename the changelog heading to [3.1.0]
git tag v3.1.0 -m "Release 3.1.0"
git push origin v3.1.0
```

Treat publish success and branch health as separate evidence. The tag-time
publish workflow proves PyPI/GitHub release publication; release summaries
should only call `main` green after CI Quality and Check Shared Package Drift
on the same commit have also passed.

## Troubleshooting

### Version does not advance

```bash
git tag --list 'v*.*.*' --sort=-version:refname | head -1
```

Then bump `pyproject.toml` to a higher stable or prerelease version.

### Missing changelog entry

Add:

```markdown
## [3.0.1] - 2026-03-31
```

with non-empty notes below the heading.

### Tag/version mismatch

If tag and `pyproject.toml` do not match:

```bash
git tag -d v3.0.1
git push origin :refs/tags/v3.0.1
git tag v3.0.1 -m "Release 3.0.1"
git push origin v3.0.1
```

### Installing a prerelease from PyPI

```bash
python -m pip install --upgrade --pre spec-kitty-cli
# or pin an exact build
python -m pip install --upgrade "spec-kitty-cli==3.1.0a0"
```

If exact install fails locally but the repo still resolves under `uv`, stop and
fix the published dependency metadata first. Do not reintroduce
`tool.uv.override-dependencies` for `spec-kitty-*` packages as a release
workaround.

## Testing

```bash
python -m pytest tests/release -v
```

## Reference

- `RELEASE_CHECKLIST.md`
- `.github/workflows/release.yml`
- `.github/workflows/release-readiness.yml`
