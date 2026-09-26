# Contract: Nightly Integration Lane, Escalation, and Release Gate

## Nightly integration lane (`ci-nightly.yml`, FR-006) (REVISED post-squad)

- New job runs `pytest tests/integration tests/next` (directory selection, NOT `-m integration` alone — 843/1015 are integration-marked but no nightly marker suite selects them). **Both** roots are covered because the dead `integration_tests_next` special tier declared both; wiring only integration would leave `tests/next/**` (24 files) dark.
- **Retire the dead `integration_tests_next` special tier** in `ci-module-registry.yml` in the same change (mandatory — GAP-3; closes #4729 honestly).
- `if: always()` run-all-regardless; exit captured into env; terminal fail-loud step surfaces red (existing #4212 pattern). PWHEADLESS=1 + per-worker HOME isolation as elsewhere.
- **Add the job to `nightly-summary.needs`** or its red won't surface in the aggregator.
- **Measurement**: `capture_shard_timings.py --module` KeyErrors on a non-row dir, so measure via `pytest tests/integration tests/next --durations=0` (or add a `--test-dirs` override to the tool). Shard only if the monolith overruns the per-shard timeout (NFR-004).
- Does NOT add a `modules[]` row (C-003 — no per-PR promotion; that's #5037).

## Escalation helper (`scripts/ci/nightly_escalation.py`, FR-007)

CLI: `nightly_escalation.py --suite-key <key> --conclusion <success|failure> [--repo <owner/repo>] [--run-url <url>]`

- `failure` → find open issues containing `<!-- nightly-escalation-key: <key> -->`; if one exists, comment/update it; else create a `priority:P0` issue with that marker in the body + a link to the failing run. INV-5: at most one open per key.
- `success` → if an open issue with the key exists, close it (suite recovered).
- No token / API error → print a warning, exit 0 (degrade to fail-loud only), never echo the token (C-005).
- Unit-tested in `tests/ci/test_nightly_escalation.py` with a mocked GitHub client: covers create, update-existing (dedup), close-on-green, and token-absent degrade.

## Release nightly gate (`scripts/ci/release_nightly_gate.py` + `release.yml`, FR-008) (REVISED post-squad)

CLI: `release_nightly_gate.py --tag <release_tag> [--dispatch] [--timeout <s>]`

- Resolve `<release_tag>` → `release_sha`. Query `ci-nightly.yml` runs for `head_sha == release_sha`.
- If a `success` run exists → exit 0 (gate passes).
- Else if `--dispatch` → `workflow_dispatch` `ci-nightly.yml` **by the tag ref** (`ref=<release_tag>` — workflow_dispatch **cannot** take a bare SHA; the tag points at the release SHA so the run's `head_sha` matches), input `mode=full`; poll to terminal; exit 0 only if it concluded `success`, else non-zero.
- In-flight nightly for the SHA → wait for terminal result (don't race), then decide.
- **Token**: the dispatch uses `RELEASE_NIGHTLY_DISPATCH_TOKEN` (PAT or GitHub App) — the default `GITHUB_TOKEN` does NOT trigger a nested run (recursion guard). The `nightly-gate` job declares `permissions: actions: write`. **Operator prerequisite: create this secret** (call out in the PR body).
- `release.yml`: new `nightly-gate` job; `build-release` gains `needs: [nightly-gate]` (and thus `publish-pypi` transitively). Fail closed (no publish) on any non-success. Token/secret absent on a real release ⇒ failure, never a silent pass.
- Unit-tested in `tests/ci/test_release_nightly_gate.py` with a mocked GitHub client: green-exists→pass, none→dispatch(by tag)→green→pass, none→dispatch→red→fail, in-flight→wait, token-absent→fail-closed.
