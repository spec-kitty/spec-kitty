# Quickstart — verifying this mission locally

**Mission**: `sonar-per-pr-coverage-reuse-01M2FR32` · **Date**: 2026-09-14

How to reproduce the mission's evidence and check your work. Every command here was run during
planning; the numbers are what they actually produced on 2026-09-14 at base `73f7ba61da`.

## 0. Environment

```bash
uv sync --frozen --all-extras          # a stale .venv is indistinguishable from real breakage
unset GITHUB_TOKEN                     # use keyring auth for gh; OAuth lacks the needed scopes
```

The Bash tool here runs **zsh**: an unquoted `$VAR` holding several paths is passed as ONE argument.
Use `${=VAR}`, `xargs`, or explicit paths.

## 1. Reproduce the duplicate-cost measurement (NFR-002, SC-003)

Do **not** quote a single run — the population is wide (12m50s–23m15s, median 22m32s, n=12).

```bash
gh run list --repo spec-kitty/spec-kitty --workflow ci-quality.yml \
  --limit 40 --json databaseId,event,headBranch,createdAt \
  --jq '.[] | select(.event=="pull_request") | .databaseId'
# then, per run, read the step timings:
gh api "repos/spec-kitty/spec-kitty/actions/runs/<id>/jobs?per_page=100" \
  --jq '.jobs[] | select(.name|startswith("SonarCloud")) | {conclusion, steps:[.steps[]|{n:.name,s:.started_at,c:.completed_at}]}'
```

A job whose steps are all `skipped` after the credential check is a **fork** PR, not evidence of an
absent credential. Mistaking one for the other produced a wrong conclusion during research.

## 2. Reproduce the coverage-breadth defect (FR-013, NFR-009, SC-004)

```bash
# The matrix's own reconciled set, from a real PR run:
gh run download <ci-aggregate-run-id> -n ci-aggregate-reconciled-coverage -D recon/

# The retiring step's measurement, locally:
.venv/bin/python -m pytest tests/unit tests/status tests/cli tests/specify_cli/runtime \
    tests/architectural/test_no_retired_subsystems.py \
  -m "(fast or unit) and not slow and not e2e and not integration and not regression \
      and not distribution and not live_adapter and not stress and not windows_ci and not platform_darwin" \
  -n auto --dist loadfile \
  --cov=specify_cli --cov=charter --cov=glossary --cov=kernel --cov=mission_runtime --cov=runtime \
  --cov-report=xml:fast-coverage.xml
```

Then diff covered-line sets per file. Expected before the fix: matrix union 71,070 covered (55.15%);
retiring step 42,933 (33.31%); **4,391 fast-only**, of which **2,808** survive adding the two rows.

Confirm the mechanism directly — 16 of 17 rows are narrow:

```bash
python3 -c "
import yaml
for m in yaml.safe_load(open('.github/ci-module-registry.yml'))['modules']:
    print(f\"{m['module']:20s} {m['cov_targets']}\")"
```

**Acceptance for WP01**: after broadening, no file's covered-line set shrinks.

## 3. Check the directories being declared (FR-006, A-003)

```bash
.venv/bin/python -m pytest tests/unit tests/specify_cli/runtime -n auto --dist loadfile -q
# expected: 531 passed

# what the retiring step actually selected (479), vs everything (531):
.venv/bin/python -m pytest tests/unit tests/specify_cli/runtime --collect-only -q | tail -1
```

The 52-test difference is one file carrying markers that exclude it from **every** selection,
including the scheduled sweep. That is a **pre-existing** gap: report it, do not absorb it.

## 4. Registry changes — the gates that will stop you (WP01)

```bash
.venv/bin/python -m pytest tests/architectural/test_module_shard_registry.py -q
```

Two will red first, by design:
- module names must be **bijective** with the retirement scrub — add the group names too;
- every row needs **measured** durations — a length mismatch silently degrades shard balancing to a
  test-count split, and the skew guard passes vacuously because it reads the committed file.

So: refresh the timings, and record the measuring run id.

## 5. Blast-radius test surface

```bash
make test-fast                                   # baseline
.venv/bin/python -m pytest tests/architectural tests/release tests/ci -q   # topology is cross-cutting
```

`ruff check .` and `ruff format --check .` are **separate** gates; format is whole-repo and clean
lint says nothing about it.

## 6. What you cannot verify locally

Honesty boundary — do not claim these from a local run:

| Claim | Why not |
|---|---|
| the reporting job runs at all | a `workflow_run` handler executes only the default-branch copy; it cannot run on the PR that introduces it |
| the credential-bearing context behaves as expected on fork-origin runs | needs a live run; the guard is required regardless |
| real CI cost of broadened targets | local→CI ratio observed ≈2.2×, single-point; fixture overhead is undercounted |
| the report publishes | blocked by an external service setting this mission does not change |

For each, the mission records a **post-integration observation** rather than a pre-merge claim.
