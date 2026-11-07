# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-05 · pi-claude · The refusal in #7201 is correct; the defect is the destination the terminus asks for. safe_commit's HEAD/destination check stays untouched; the fix hands the terminus the consolidate run's already-resolved lanes_manifest.target_branch via commit_merge_bookkeeping(destination_ref_override=...), the same override the merge executor's own bookkeeping commit uses (#4985/#4991).
