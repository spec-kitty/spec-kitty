# Research: Orchestrator error-code prose guard

Mission: `orchestrator-error-code-prose-guard-01M6EJQS` · Issue
[#7035](https://github.com/spec-kitty/spec-kitty) · Grounded on `origin/main`
`9aed3a8012`.

## D-1 — The drift is real, measured, and in the direction the issue says

Read `orchestrator_api.allowed_error_codes` from
`src/specify_cli/core/upstream_contract.json` (80 codes) and diffed each prose
surface against it, parsing only leading enumeration entries (a list item's
leading backticked code; a table row's first cell):

| Surface | Enumerated | Missing from surface | Extra in surface |
|---|---|---|---|
| `docs/api/orchestrator-api.md` → `## Error Codes` bullets | 58 | 22 | 0 |
| `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md` → `## Error Code Summary` table | 57 | 23 | 0 |

The doc's 22: the whole `DESIGN_*` family except `DESIGN_STATUS_EVENT_LOG_UNREADABLE`
(18 names), plus `INVALID_MISSION`, `RUNTIME_BLOCKED`, `RUNTIME_NEXT_FAILED`,
`SAFE_COMMIT_STAGED_TREE_UNCHANGED`, `UNSUPPORTED_CAPABILITY`. The table's 23 are
the same set plus `WORKFLOW_EVIDENCE_REQUIRED`. The 1.12.0 contract-version bullet
does name most `DESIGN_*`/`RUNTIME_*` codes, but as version-history prose — a
reader enumerating the failure surface cannot use it, and nothing checks it.

The naive "scan everything under the heading" parse finds 21 *extra*
ALL-CAPS backticked tokens in the same docs section that are **not** contract
codes: `data.preflight_error_code` values (`LANE_MOVED_AFTER_APPROVAL`,
`APPROVAL_STAMP_MISSING`, `IMPLEMENTATION_UNREADABLE`, the `SINGLE_BRANCH_*`
aliases, …), `data.teardown_error_code` (`COORD_MOVED_AFTER_LANDING`,
`COORDINATION_WORKTREE_UNMATERIALIZED`) and the origin-freshness codes
(`ORIGIN_LANE_STALE`, `ORIGIN_UNREACHABLE`, …). They are a **different code
namespace**: they ride inside `data`, they are not `allowed_error_codes`
entries, and they change on their own schedule. Evidence: the file lists
`APPROVED_CONTENT_MISSING` and `CANCELED_REACHABLE_VIA_DEPENDENCY` in a table the
contract never mentions.

## D-2 — Decision: bound each enumeration explicitly, then compare as a set

Both options the issue offers were considered.

- *Option A, restate the families as list items.* Necessary — it is the user-visible
  fix — but on its own it is the "one-off re-sync" the operator ruled out.
- *Option B, an explicit "documented in prose at X" mapping the test also checks.*
  This is what makes the check durable, but a separate mapping file is a third
  place to drift: the map would say `DESIGN_*` is documented in the 1.12.0 bullet,
  and the test would then pass while a caller still cannot enumerate the codes.

**Chosen: A + B fused, no separate file.** Each surface carries one explicit,
machine-readable anchor pair inside the document that delimits the region the
guard reads:

```
<!-- orchestrator-error-codes:begin -->
...
<!-- orchestrator-error-codes:end -->
```

- The markers *are* the "documented in prose at X" mapping, in the one place that
  cannot drift from the prose itself (the document).
- The region is the *complete* enumeration (option A), so a reader gets the codes
  and the guard gets an exact set.
- The sub-code tables stay outside the region, which is why they need no
  allow-list and cannot make the guard fail when they change (D-1).
- A missing/malformed anchor is a **failure**, not a skip: deleting the anchor
  cannot silently disable the check.

Parsing rules derived from D-1's evidence:

- Docs: a line inside the region matching `^- \`CODE\``; the leading backticked
  token only, so an annotation that mentions another code
  (`SAFE_COMMIT_INDEX_RESIDUE` → `SAFE_COMMIT_RECOVERY_FAILED`) cannot add an entry.
- Table: a row inside the region whose first cell is a single backticked code;
  the description cell is ignored.
- Any non-blank line inside the region that is neither a marker, a matching entry,
  nor an allowed heading/comment is a parsing failure — the region must not
  silently absorb prose the guard cannot read.

## D-3 — Decision: compare the authority at test time, not a copy

The guard reads `orchestrator_api.allowed_error_codes` through the installed
package resource (`importlib.resources.files("specify_cli.core")`, the same seam
`tests/contract/conftest.py` already uses), so the contract file stays the only
authority. No new constant, no second list, no vendored copy — this is what keeps
FR-010 honest and what stops the guard from becoming the next stale surface.

## D-4 — Where the guard lives

`tests/contract/test_orchestrator_api.py`, as a sibling class to
`TestAllowedErrorCodes` (the machine-readable half of the same question). It is
already in the contract shard, already has the contract fixture seam, and is
selected by `-m "contract and fast"`. A separate `scripts/docs/check_*` gate was
rejected: those gates are for stale *generated* surfaces, this is a contract
invariant over hand-written prose, and a new gate needs CI wiring the shard
already provides.

## D-5 — Failure must name surface and codes

The check compares per surface and reports `missing from <path>` and
`not in allowed_error_codes: <path>` with sorted code lists, so the message in a
registration PR is the to-do list. Duplicates within a surface are reported
separately (a multiset check), because set equality is blind to them.

## Open questions

- None blocking. Two noted for the plan's deferral, not this Mission: the skill
  reference's envelope sample still says `contract_version: "1.5.0"` (it is a
  sample, not an enumeration, so out of #7035's scope), and the per-verb
  "Error codes: …" lines remain narrative and unchecked by design (C-005).
