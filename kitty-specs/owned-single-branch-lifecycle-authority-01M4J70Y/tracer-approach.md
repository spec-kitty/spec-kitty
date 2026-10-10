# Tracer: Approach — owned single-branch lifecycle authority

Seeded at planning (2026-10-10). Append during implementation; assess at close.

## Strategy
- Thread the one validated `OwnedCheckout` (minted by `resolve_owned_mission`) as `owned=` through each broken surface, mirroring the sibling owned arms. No second resolver; no `core/paths.py` change.
- Land-and-verify the existing codex repair branches: rebase each issue's fix+test onto current `main`, confirm it still fits the seam, re-run its targeted regression RED→GREEN. Rewrite minimally only where a branch drifted or was incomplete (#5874 orchestrator-api extension; #5947 new).
- Sequential single_branch WPs (one per surface) — all converge on the shared seam; sequential avoids collisions and dogfoods the owned path.

## Per-WP plan
WP01 #5874 decision host + orchestrator-api · WP02 #5877 prerequisites · WP03 #5878 map-requirements · WP04 #5880+#5892 finalize · WP05 #5893 recording+authority · WP06 #5947 review/cycle verify+harden.

## Running notes
- (append during implement)

## Running notes (implement)
- WP01 (#5874): adopted codex/5874 test f606dc110 (RED: 7 fail) + fix 8f4a49ea1 (host). Adaptation to current main: `_ledger_dir` containment → follow_links=True (post-#5671 files() keeps link leaf; escaped-ledger refusal was the only residual fail, 4 tests); `owned=owned` instead of `**({"owned":owned})` spread at typed call sites (mypy --strict). EXTENDED orchestrator_api/decision_verbs.py open/resolve/defer/cancel (operator D2) via shared _resolve_owned_decision_context + _fail_from_owned_error degrade (contract-preserving). New test tests/specify_cli/orchestrator_api/test_decision_verbs_owned.py (3 pass). Host 12/12 green. Independent review (reviewer-renata): APPROVE, no blocking findings. Nit deferred: cmd_verify/cmd_list still use spread for _resolve_ledger_dir (cosmetic).
