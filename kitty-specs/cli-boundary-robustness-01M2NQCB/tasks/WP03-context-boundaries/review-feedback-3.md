# WP03 independent review cycle3 — changes requested

Observed at approved HEAD da03c5dad. Independent probe: parent/WP03-workspace-read-repro.py/.log. No product edits. Reviewer Renata freshly resolved. Official invocation edc3f76c50de45a1ae40c72da20b932f; full prompt content unchanged from previously read cycle2 except invocation/topology/cycle metadata.

Create a real directory at `.kittify/workspaces/broken.json` in a temporary project. Registered commands `context info --workspace broken --json` and `context list --json` both exit1 with raw IsADirectoryError, empty stdout and empty stderr. Both human invocations also leak the raw exception. This is an uncovered filesystem-read error, not an empty success. C1/C2/NFR002 promised boundaries remain incomplete.

Owned sites: context.py:93 calls load_context unguarded; context.py:169 calls list_contexts unguarded. The shared workspace/context.py loader catches ValueError/JSON/type/key corruption but not OSError. Independently confirmed list --orphaned has the same raw IsADirectoryError in both modes. All six cases are recorded in the real-file probe log.

Required correction: preserve legitimate empty/missing-workspace behavior and existing exits, but render expected workspace read failures as controlled, named canonical errors in the owned command layer. Real directory-at-file regression fixtures must exercise info, list and orphaned sibling in both modes; assert exact exit, canonical JSON-only stdout, controlled SystemExit, no traceback. Do not silently skip unreadable records or turn failed reads into empty success.

## Canonical workflow and evidence

Initial review claim correctly refused approved state. Parent instructed the documented normal transition; move-task approved→for_review succeeded without force (event01M2P4JM7QV92Z4NMGPEMF44XY). Official review action then claimed cycle3. Prior approval and token-correction evidence remain immutable; this renewed finding invalidates complete boundary coverage, not the prior token fix.

Original R1 token correction remains verified. Existing default-delegation, missing/error/empty/success tests and lint/type/format evidence remain as cycle2; no product delta since da03c5dad. Broad suite intentionally not rerun to demonstrate this narrow real-filesystem counterexample. Shared CLI integration runs independently and is now pre-correction evidence.

## Mandatory checks

| Check | Verdict | Evidence |
|---|---|---|
| Dead code | PASS | Existing command/loader/helper paths live |
| Synthetic-fixture test | PASS | Real directory at workspace JSON path; actual registered commands |
| Silent empty return | PASS | No new empty-return change; required fix must not conceal read failures |
| FR coverage | FAIL | Workspace info/list/orphaned read failure violates FR005/007,NFR002,C1/C2 |
| Frozen surface | PASS | No new source edits; prior owned changes unchanged |
| Locked decision | FAIL | Promised parseable adopted JSON error boundary incomplete |
| Shared ownership | PASS | Required adaptation fits owned context.py/test; no shared-loader rewrite authorized |
| Production fragility | PASS | No newly introduced raw raise; this is an existing failure class missed by adopted boundary |

## Verdict

REQUEST CHANGES, one HIGH finding covering workspace info/list/orphaned read failures. Add tests before correction, preserve previous success/empty semantics and controlled exit1. Parent owns issue-matrix and integration impact; no final issue verdict fabricated.
