# Contract: `scripts/ci/source_eligibility.py`

## Pure decision (unit-tested, no network, no git)

```text
resolve_source(trigger: TriggerMeta, candidates: list[CandidateRun], default_branch: str) -> SourceDecision
```

- Deterministic function of its arguments only. No I/O, no `subprocess`, no clock.
- Applies, in order: dispatch → `NoFallback`; `event=pull_request` or `conclusion=failure` → `NotAMainSource`; else pick the most-recent `conclusion=success` candidate whose `headBranch == trigger.head_branch`, else whose `headBranch == default_branch` → `EligibleSource`; none → `NoEligibleSource`.
- Raises `ValueError` ONLY on malformed input (missing required field, non-int `databaseId`). A legitimate absence of source is a `No*` variant, never an exception.

## Edge (`main()`)

- Args mirror `select_source_artifacts.py`: read injected JSON files/args; the `gh api|jq`/`gh run list --json` call lives in the workflow, not the module.
- Emits to stdout / `$GITHUB_OUTPUT`, exactly two keys:

```text
run-id=<databaseId or empty>
eligibility=<slug>
```

- MUST NOT emit `complete`, `missing`, or `coverage` (those belong to `reconcile_shards.py`).
- MUST exit 0 for every `SourceDecision` variant (including the empty ones). Non-zero exit only on malformed input.

## Workflow wiring (`.github/workflows/ci-aggregate.yml`, `last-success` step)

- The step's `run:` invokes `python3 scripts/ci/source_eligibility.py ...` — no inline `gh run list ... || true` decision logic remains.
- The step still emits `run-id` to `$GITHUB_OUTPUT` under the same output name the downstream `download-previous` step reads (`steps.last-success.outputs.run-id`), so no downstream step changes.
- The `workflow_dispatch` guard (`if: github.event_name != 'workflow_dispatch'`) is preserved (belt-and-braces with `NoFallback`).

## Frozen boundaries (assert unchanged)

```yaml
# round-trip: skip: illustrative contract anchors, not a parseable mission artifact
frozen:
  - path: .github/workflows/ci-aggregate.yml
    step: "Fail loudly if the reconciled shard set is incomplete"  # ~:292-299
    rule: run-block byte-identical (pinned by test)
  - path: scripts/ci/reconcile_shards.py
    symbol: must_be_fresh
    rule: unchanged; a SELECTED shard absent from current stays fatal
  - path: .github/workflows/ci-router.yml        # #4347, Stage 1
    rule: not touched
  - path: .github/workflows/ci-fleet-verdict.yml # #4371, Stage 1
    rule: not touched
```

## Test obligations

1. Red-first unit cases (assert the REJECTIONS, not a happy string): `pr-head-trigger`, `failed-trigger`, `dispatch-no-fallback`, `eligible push-main`, `eligible source-branch`, `no-success-source`, plus `unrelated-branch success rejected` and `red source-branch run rejected`.
2. Execution-grounded wiring guard (mirror `tests/ci/test_aggregate_source.py:146-153,309-327`): extract the real `last-success` step from `ci-aggregate.yml`, assert it invokes `scripts/ci/source_eligibility.py`, execute it against a stubbed no-eligible-source inventory, assert `run-id=""` + a named `eligibility` slug.
3. Guard-preservation pin: assert the fail-closed step's `run:` text is byte-identical.
