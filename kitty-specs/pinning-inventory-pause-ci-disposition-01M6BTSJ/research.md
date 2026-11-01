# Research: recording the `pr:pause-ci` pin's disposition

**Mission**: `pinning-inventory-pause-ci-disposition-01M6BTSJ`
**Issue**: [#6998](https://github.com/spec-kitty/spec-kitty/issues/6998)
**Written**: 2026-11-01, after implementation and both review rounds (discovery recorded post-hoc; the evidence below was gathered before the first edit and is reproduced in the PR's `## Tests run`).

## Grounding evidence (gathered on `main` @ `287a226cfe`, before any edit)

| Claim | How it was checked | Result |
|---|---|---|
| The issue still reproduces on current `main` | `PYTHONPATH=src python scripts/ci/derive_pinning_inventory.py --check` | exit 1, "tests/release/pinning_rule_inventory.json is stale — re-run …" |
| Not superseded | `git log` over the deriver, the artefact and `tests/ci/test_pause_ci_label.py`; the artefact's last refresh is `7604688425` (2026-10-18) | no adjudication commit after `eb099b70b1`; nothing superseding |
| The pin came from the `pr:pause-ci` change | `git log -S'_REQUIRED_GATES' -- tests/ci/test_pause_ci_label.py` | exactly one commit, `eb099b70b1` (#6961) |
| The derivation adds exactly one row, removes none | `--stdout` diffed against the committed artefact, field by field, excluding `lines` | one added row, zero removed; 35 rows line-only drift; `executed` and `subjects` byte-identical |
| Blind regeneration is the trap the issue names | regenerated, then ran the blocking gate | `_REQUIRED_GATES: disposition None not in ['none', 'relocate', 'retire-as-moot', 'rewrite']` — reproduced exactly |
| The rule's form and subject | derived row | `subjects: ["retiring-host"]`, `form: "set-equality"`, `dependency: true` |
| The asserted job still exists | parsed `.github/workflows/ci-quality.yml` | jobs are `build-wheel`, `clean-install-verification`, `lint`, `quality-gate`, `uv-lock-check` — the pinned job survives |
| The file never names the retired job | `grep -c sonarcloud tests/ci/test_pause_ci_label.py` | `0` |
| The issue's cited base reproduces too | the issue states `origin/main` @ `dc9a09d3` in a separate worktree | consistent with the above; not independently re-run, unnecessary given the current-tip reproduction |

## Decisions

### D1 — the disposition is `none`, recorded in `DISPOSITIONS`

`is_dependency` returns `true` by its clause 3: the rule references only the **host** (`ci-quality.yml`, which survives — the job inside it was removed, the file was not) but does so in a `set-equality` form, i.e. a claim about that file's contents rather than a lookup of it. The derivation therefore refuses to clear it on its own and fails closed. That is correct behaviour: the classifier over-approximates on purpose, and the adjudication is the human seam.

The verdict is `none` because:

- No edit is made → `rewrite` would claim one.
- Nothing moved → `relocate` would claim that.
- The subject did not cease to exist → `retire-as-moot` is false. `ci-quality.yml`'s `clean-install-verification` job is still there, and it *must* still run and fail under the label (a skipped required check passes), which is exactly what the rule asserts.

`none` under `dependency: true` is the established shape: 26 of the 114 derived rows already carry it, each with a reason naming the surviving host (e.g. `scripts/ci/fleet_main.py::main_workflows`, `tests/release/test_ci_ownership.py::RESTORED_WORKFLOWS`). This row joins them.

Rejected alternative: teaching `_string_form` to recognise `pytest.mark.parametrize` sources so this list would classify as `derived-relation` and clear automatically. Rejected because it re-adjudicates 26 existing rows, changes the meaning of a contract-bearing gate to make data pass, and needs no human decision to be recorded — which is the opposite of what the contract asks for. See `plan.md` C-003.

### D2 — the artefact is regenerated whole, including the line-number drift

The freshness gate asserts byte-identity, so the artefact must be the derivation's output. That carries the line-number drift accumulated since 2026-10-18: 35 rows change only their `lines`, and one row is added. Trimming the drift by hand would make the freshness gate red and is forbidden by the artefact's own `_comment` ("DERIVED — do not hand-edit"). Precedent: `7604688425`, "chore(ci): refresh stale pinning-rule inventory line numbers".

### D3 — no new test

The defect is missing **data**, not missing coverage. The invariant is already owned by `tests/release/test_pinning_inventory_fresh.py`:

- `test_inventory_is_reproducible_by_rerunning_the_derivation` (byte-identity; strict under `SPEC_KITTY_STRICT_PINNING_INVENTORY=1`),
- `test_every_entry_carries_a_disposition_from_the_vocabulary_and_a_reason` (fail-closed, per-PR blocking).

A third test asserting this one row would duplicate the second. Non-vacuity is shown by reverting each half instead (below), which `acceptance-criteria-non-vacuity` accepts as the half-by-half proof for a compound fix. `DIRECTIVE_041` forbids the extra test.

### D4 — the changelog entry is a per-PR fragment

`docs/changelog/unreleased/6998.fixed.md`, not an edit to `docs/changelog/CHANGELOG.md`. #6988 introduced fragments precisely so parallel PRs never conflict on the shared changelog, and this batch runs roughly twenty concurrent missions. WP02's `owned_files` was corrected to the fragment path after the guard reported `ACTIVE_WP_SCOPE_VIOLATION`. The release-time `changelog_fragments assemble` folds it into `[Unreleased]`.

## Non-vacuity: half-by-half revert evidence

| Reverted half | Result |
|---|---|
| Remove the `DISPOSITIONS` entry, re-derive | `test_every_entry_carries_a_disposition_from_the_vocabulary_and_a_reason` reds: `_REQUIRED_GATES: disposition None not in [...]` |
| Hand-edit one artefact `lines` value, keep the disposition | `test_inventory_is_reproducible_by_rerunning_the_derivation` reds under strict mode |

Both restored; the committed tree is the derivation's own output (artefact `sha256` == `--stdout` `sha256`, `d1630675618e02e4a077611393abf1cb56435fa67a3e2a5fd07b9b7c77390902`).

## Open questions for follow-up (not resolved here)

1. **Why this landed unnoticed.** The freshness gate warns per PR and asserts only nightly (operator ruling 2026-10-18), so a stale artefact can reach `main` without a red. Hard-gating the check on `main` pushes is **#4845** — a CI-policy decision for the operator, recorded as `deferred-with-followup` in the issue matrix.
2. **The gate validates the ledger structurally, not semantically.** A disposition word could later be changed to another vocabulary value without a red. Pinning one row's meaning would need an edit to `test_pinning_inventory_fresh.py`, which this mission's C-001 forbids and which would be inconsistent with the 44 other adjudicated rows that carry no per-row pin. Raised in the WP01 review note; not a blocker.
3. **Line-number churn is inherent** to storing `lines` in a byte-identity-checked artefact. Each `main` commit that shifts a scanned rule creates the same drift. Not addressed; #4845 is the closest tracked owner.
4. **The pre-review regression gate cannot scope this WP.** Its census auto-scope resolved no targets for a write scope of `scripts/ci/*.py` plus `tests/release/*.json`, so it fell back to `make test-fast` and timed out at 300 s twice; `pre_review_test_scope` cannot be set because `WPMetadata` is `extra=forbid`. Traced in `traces/tooling-friction.md`; operator decision tracked by #6865.
