# Mission Specification: Record the `pr:pause-ci` pin's disposition and refresh the derived pinning inventory

**Mission Branch**: `issue-6998-pinning-inventory-pause-ci-disposition-01M6BTSJ`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue [#6998](https://github.com/spec-kitty/spec-kitty/issues/6998) — "Pinning inventory stale on main: `tests/release/pinning_rule_inventory.json` lacks a row for `test_pause_ci_label._REQUIRED_GATES` (needs a disposition)". Found while running the blast radius of #6915; reproduces on a clean `origin/main` checkout, so it is not caused by that work.

## Intent Summary (confirmed)

- **Primary actor**: a Spec Kitty maintainer whose PR reds the `CI Modules` shard on a stale, undispositioned pin that has nothing to do with their change — and the reviewer who then has to adjudicate a `disposition: null` row under time pressure.
- **Trigger**: `tests/ci/test_pause_ci_label.py::_REQUIRED_GATES` entered the tree with `eb099b70b1` (the `pr:pause-ci` change, #6961). The derivation now discovers it as a `retiring-host` + `set-equality` rule — a claim about `ci-quality.yml`'s contents — so it must carry an adjudicated disposition. Nothing adjudicated it, and nothing re-derives the artefact per PR, so the committed inventory is stale on `main` today.
- **Desired outcome**: the human decision for that rule is recorded in the deriver's `DISPOSITIONS` map with a stated reason, `tests/release/pinning_rule_inventory.json` is byte-exactly what the derivation now produces, and both gates that own this artefact are green.
- **Invariant**: no gate is weakened. `test_inventory_is_reproducible_by_rerunning_the_derivation` still asserts byte-identity (strict mode unchanged), and `test_every_entry_carries_a_disposition_from_the_vocabulary_and_a_reason` still fails closed per PR on an undispositioned row. The new evidence is that the disposition is *recorded*, not that the check is bypassed.
- **Not in scope** (named in the PR's `## Deferred`): why this landed unnoticed — the freshness gate is warn-only per PR by operator ruling 2026-10-18, and hard-gating it on `main` pushes is the still-open #4845. That is a CI-policy decision, not this defect.

### Grounding (current `main` @ `287a226cfe`)

| Check | Result |
|---|---|
| Issue reproduces | Yes. `PYTHONPATH=src python scripts/ci/derive_pinning_inventory.py --check` → "is stale — re-run", exit 1. |
| Superseded? | No. `eb099b70b1` introduced the pin; `git log` over the deriver, the artefact and the test shows no adjudication commit after it. The artefact was last refreshed 2026-10-18 (`7604688425`). |
| Blast radius from #6915? | None. The failure is on the untouched base, as the issue states. |
| Only difference in the derivation? | Exactly one added row, `tests/ci/test_pause_ci_label.py::_REQUIRED_GATES`, `subjects: ["retiring-host"]`, `form: "set-equality"`, `dependency: true`, `disposition: null`. Zero rows removed. |
| Blind regeneration? | Passes `--check`, then reds `test_every_entry_carries_a_disposition_from_the_vocabulary_and_a_reason` with `disposition None not in ['none', 'relocate', 'retire-as-moot', 'rewrite']` — the issue's diagnosis, reproduced. |

### The adjudication, and why it is `none`

`is_dependency` derives `true` here by clause 3: the rule names only the **host** (`ci-quality.yml`, which survives the sonarcloud retirement — only the job inside it left), but it does so in a `set-equality` form, i.e. a claim about that file's contents rather than a lookup of it. So the derivation correctly refuses to clear it on its own and fails closed.

The claim it makes is real but unchanged: the `pr:pause-ci` contract requires `ci-quality.yml`'s `clean-install-verification` job to *run* and *fail* under the label, because a skipped required check passes. That job survives untouched, and the rule's membership list is still exactly right. It asserts nothing about the retired `sonarcloud` job, which the file never names. So the recorded decision is `none` — the vocabulary's "adjudicated, nothing it asserts changes" — not `rewrite` (no edit is made) and not `relocate` (nothing moved).

`none` under `dependency: true` is the established shape for exactly this case: 26 of the 114 derived rows already carry it (e.g. `scripts/ci/fleet_main.py::main_workflows`, `tests/release/test_release_ci_ownership.py::RESTORED_WORKFLOWS`), each with a reason naming the surviving host.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The recorded decision travels with the derivation (Priority: P1)

As a maintainer, the `pr:pause-ci` required-gate pin carries a recorded disposition and reason in the deriver itself, so no future reader has to re-adjudicate it and no reviewer meets a bare `disposition: null`.

**Why this priority**: without it the artefact cannot be regenerated at all — regenerating reds the blocking completeness gate. This is the whole defect.

**Independent Test**: load `scripts/ci/derive_pinning_inventory.py`, look up `tests/ci/test_pause_ci_label.py::_REQUIRED_GATES` in `DISPOSITIONS`, and assert the entry is `("none", <reason ≥ 60 chars>)`; the derivation for that rule then emits a non-null disposition that is inside `DISPOSITIONS_VOCABULARY` and carries that reason.

**Acceptance Scenarios**:

1. **Given** the deriver on the branch, **When** the derivation runs, **Then** the row for `tests/ci/test_pause_ci_label.py::_REQUIRED_GATES` has `disposition: "none"` and a reason naming the surviving host job — not `null`.
2. **Given** that row, **When** `test_every_entry_carries_a_disposition_from_the_vocabulary_and_a_reason` runs, **Then** it passes without the test being modified.
3. **Given** the `DISPOSITIONS` entry, **When** it is deleted and the derivation re-run, **Then** the completeness gate reds again — the entry is load-bearing, not decorative.

### User Story 2 - The committed inventory is what the derivation produces (Priority: P1)

As a maintainer, `tests/release/pinning_rule_inventory.json` is byte-identical to a fresh derivation, so the freshness check the issue names exits 0 and the artefact stops being a standing debt on every PR.

**Why this priority**: the issue's literal symptom. It also clears the line-number drift accumulated since 2026-10-18, which is the same staleness.

**Independent Test**: run `PYTHONPATH=src python scripts/ci/derive_pinning_inventory.py --check`; re-run the strict freshness gate with `SPEC_KITTY_STRICT_PINNING_INVENTORY=1`.

**Acceptance Scenarios**:

1. **Given** the branch, **When** `derive_pinning_inventory.py --check` runs, **Then** it exits 0 and prints no staleness message.
2. **Given** the branch, **When** the strict freshness gate runs, **Then** it passes and emits no `PinningInventoryDriftWarning`.
3. **Given** the artefact, **When** it is hand-edited by one line, **Then** the freshness gate reds — byte-identity is still the assertion.
4. **Given** the derivation is re-run on the branch, **When** the output is diffed against the committed artefact, **Then** the diff is empty (the commit is the derivation's own output, not a hand-edit).

### User Story 3 - The adjudication is explained where a maintainer will look (Priority: P2)

As a reviewer, the changelog records that an undispositioned pin was adjudicated and the inventory refreshed, with the before/after, so the next staleness report is recognised as the same class rather than re-diagnosed from scratch.

**Why this priority**: this is the second occurrence of the class (#4334 built the ledger; `7604688425` refreshed it; #4845 remains open). The decision belongs in the record.

**Independent Test**: read the `[Unreleased]` entry; it names #6998, leads with the impact, and states before/after under 1,200 characters; `test_validate_changelog_entry.py` and `test_changelog_fragments.py` pass.

**Acceptance Scenarios**:

1. **Given** the branch, **When** the changelog validators run, **Then** they pass.
2. **Given** the entry, **When** it is read alone, **Then** a maintainer can tell that no behaviour and no gate changed — only a recorded decision and a regenerated artefact.

### Edge Cases

- **The `none` choice is challenged.** If a reviewer argues the rule is a real dependency on the retired job, the refutation is in the file: `tests/ci/test_pause_ci_label.py` never mentions `sonarcloud`; the subject is `retiring-host` only.
- **Regeneration churn.** The refresh carries ~36 line-number blocks accumulated since 2026-10-18. That is the correct derived output, not unrelated editing; the diff must contain no non-derived change, and the only added row is the `_REQUIRED_GATES` one.
- **A sibling PR regenerates the same artefact.** Another mission touching the same pin could conflict. Resolution rule: the artefact is never hand-merged — take either side, re-run the derivation, and commit its output. Base drift in line numbers is resolved by re-deriving, never by editing the JSON.
- **Interpreter divergence.** The artefact must be byte-identical across supported interpreters (the module docstring's PEP 701 note). The derivation is checked under the default interpreter; a divergence would be a separate defect, reported not silently absorbed.
- **Strict mode is not a per-PR blocker** by operator ruling 2026-10-18. This mission does not change that: it fixes the data, not the switch.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Recorded disposition | As a maintainer, I want `DISPOSITIONS["tests/ci/test_pause_ci_label.py::_REQUIRED_GATES"]` set to `("none", <reason>)` so that the pin is adjudicated in the deriver, not in a commit message. | High | Open | [build] | no — red without it: the row derives `disposition: null` |
| FR-002 | Reason names the surviving subject | As a reviewer, I want that reason (≥ 60 chars, the gate's own floor) to state that the host file and its `clean-install-verification` job survive and the file never names the retired job so that the `none` is checkable rather than asserted. | High | Open | [build] | no |
| FR-003 | Regenerated artefact | As a maintainer, I want `tests/release/pinning_rule_inventory.json` committed exactly as the derivation emits it (the new row plus accumulated line drift) so that `--check` exits 0. | High | Open | [build] | no — `--check` is red before |
| FR-004 | Both owning gates green | As a maintainer, I want the strict freshness gate and the blocking completeness gate green on the branch with neither test modified, so that the fix is data and the gates keep their teeth. | High | Open | [ratchet] | no — pairing: reverting FR-001 reds completeness, reverting FR-003 reds freshness |
| FR-005 | Changelog record | As a reviewer, I want an `[Unreleased]` entry naming #6998 with impact-first lead and before/after under 1,200 characters so that the adjudication is in the record. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Minimal source diff | The only executable change is one entry added to `DISPOSITIONS`; no deriver logic, top-level constant, or test assertion changes. Verified by `git diff --stat` over `scripts/` and `tests/` showing one file with one added block. | Maintainability | High | Open |
| NFR-002 | Deterministic artefact | Two consecutive derivations on the branch produce byte-identical output (`sha256` equal), and the committed artefact equals the derivation's output. | Reliability | High | Open |
| NFR-003 | Fast gate runtime | The two pinning gates together complete well inside the `fast` marker budget on a developer laptop (observed ≈ 3.5 s of call time; the one-off import cost is not part of this requirement). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No gate weakening | `tests/release/test_pinning_inventory_fresh.py` is not modified. No `xfail`, `skip`, env-var default change, vocabulary widening, or `_MIN_REASON_CHARS` relaxation. `DISPOSITIONS_VOCABULARY` stays `{relocate, rewrite, retire-as-moot, none}`. | Process | High | Open |
| C-002 | No hand-edit of the artefact | `tests/release/pinning_rule_inventory.json` is produced only by `python3 scripts/ci/derive_pinning_inventory.py`; its `_comment` says "DERIVED — do not hand-edit". Any line-number conflict is resolved by re-deriving. | Technical | High | Open |
| C-003 | Classifier unchanged | The derivation's `set-equality` classification (the `_string_form` collection catch-all) is not special-cased for `pytest.mark.parametrize` sources. An over-approximating derivation plus a human disposition is the contract's design; changing it would silently re-adjudicate 26 existing rows. | Technical | High | Open |
| C-004 | Issue workflow state | #6998 keeps `status:claimed` and `taken-by-human`; the PR carries `taken-by-human`, `ready-for-squad` and the operator's `pr:pause-ci` throttle label. | Process | High | Open |

### Key Entities

- **Pinning rule**: a named construct (`<relpath>::<scope>`) in the scanned Python surface that references a subject. `_REQUIRED_GATES` is one.
- **Subject**: a literal token of the retirement — `retiring-job` (`sonarcloud`), `retiring-host` (`ci-quality.yml`), `retiring-step` (`make test-fast`).
- **Disposition**: the recorded human decision for a live dependent rule — `relocate`, `rewrite`, `retire-as-moot`, or `none` (adjudicated, nothing changes).
- **Artefact**: `tests/release/pinning_rule_inventory.json`, the committed `derived` + `executed` ledger that the freshness gate re-derives and diffs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `PYTHONPATH=src python scripts/ci/derive_pinning_inventory.py --check` exits 0 on the branch (exit 1 before). — [build] · no-op passable: no
- **SC-002**: Zero rows in the artefact carry `disposition: null`; all 114 derived rows plus the executed ledger carry a vocabulary disposition and a reason ≥ 60 chars. — [ratchet] · no-op passable: no — positive control: reverting FR-001 reintroduces exactly one `null` row and reds the gate
- **SC-003**: `tests/release/test_pinning_inventory_fresh.py` passes in full with `SPEC_KITTY_STRICT_PINNING_INVENTORY=1`, and `git diff` over that file is empty. — [ratchet] · no-op passable: no
- **SC-004**: `git diff --stat origin/main -- scripts/ tests/` reports exactly one source file changed (`scripts/ci/derive_pinning_inventory.py`) plus the regenerated artefact. — [ratchet] · no-op passable: no
