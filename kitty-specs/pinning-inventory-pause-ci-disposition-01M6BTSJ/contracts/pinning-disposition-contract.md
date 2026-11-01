# Contract — the pinning-disposition decision for `_REQUIRED_GATES`

**Mission**: `pinning-inventory-pause-ci-disposition-01M6BTSJ` · **Issue**: #6998
**Governing contract**: `kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/contracts/gate-disposition-contract.md` (the derivation, the disposition vocabulary, and the three prohibitions). This document does not restate it; it records the one decision that contract leaves to a human, and the invariants this mission must not break while recording it.

## The rule in question

`tests/ci/test_pause_ci_label.py::_REQUIRED_GATES` — a literal list of `(workflow, job)` pairs consumed by `@pytest.mark.parametrize`. It existed in no form before `eb099b70b1` (#6961, the `pr:pause-ci` label contract).

## Derived classification (not a decision — this is what the derivation emits)

| Field | Value | Why |
|---|---|---|
| `subjects` | `["retiring-host"]` | the list names `ci-quality.yml`; it never names the retired job |
| `form` | `set-equality` | `_string_form`'s collection catch-all: a literal inside a list/tuple/dict is a claim about that collection, not a lookup through it. Deliberately over-approximating |
| `dependency` | `true` | `is_dependency` clause 3 — host reference + `set-equality`/`exact-string` form |
| `disposition` before this mission | `null` | fail-closed: no recorded decision, so the freshness/completeness pair refused to let the artefact be regenerated |

## The decision

**`disposition: "none"`**, with a stated reason, keyed in `DISPOSITIONS` (not `EXECUTED_LEDGER` — the rule resolves in the post-change tree).

The four vocabulary values, and why this is the only correct one here:

| Value | Claims | True here? |
|---|---|---|
| `relocate` | the property still matters and moved to a new host | No. Nothing moved. |
| `rewrite` | the property matters but its expression no longer can, so it was re-expressed | No. The expression is still correct; no edit was made. |
| `retire-as-moot` | the subject genuinely ceased to exist | No. `ci-quality.yml`'s `clean-install-verification` job is present (`build-wheel`, `clean-install-verification`, `lint`, `quality-gate`, `uv-lock-check`). |
| `none` | adjudicated: the derived dependency is not real — nothing the rule asserts changes | **Yes.** The rule requires that gate to *run* and *fail* under the `pr:pause-ci` label (a skipped required check passes). The gate still runs and still fails, and the retired job was never a member of the list. |

`none` under `dependency: true` is the established shape, not an invention: 26 of the 114 derived rows already carry it, each with a reason naming the surviving host.

## Invariants this mission must preserve

1. **The artefact is derived, never written.** `tests/release/pinning_rule_inventory.json` must equal `derive_pinning_inventory.py --stdout` byte for byte. Conflicts are resolved by re-deriving.
2. **The completeness gate stays fail-closed and blocking per PR.** No `null` disposition may survive; the vocabulary and the 60-character reason floor are unchanged. The evidence is a *recorded* disposition, never a widened check.
3. **The freshness gate keeps its teeth.** `test_inventory_is_reproducible_by_rerunning_the_derivation` still asserts byte-identity and still runs strict under `SPEC_KITTY_STRICT_PINNING_INVENTORY=1`. Its test file is unmodified by this mission.
4. **The classifier is untouched.** `_string_form` is not special-cased for `pytest.mark.parametrize` sources: that would silently re-adjudicate 26 existing rows and make the artefact pass without recording a human decision.
5. **Prohibited, per the governing contract:** deleting a rule with no disposition; leaving a justification that describes something no longer true; weakening an assertion to make it pass.
