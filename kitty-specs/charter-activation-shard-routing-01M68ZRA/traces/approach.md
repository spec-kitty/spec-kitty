# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude-code/opus · Reproduced the #6336 gap through the production entry point (scripts.ci.gate_selection.select_modules, the same call ci-modules.yml makes): .kittify/charter/charter.yaml, .kittify/charter/activation.yaml and packs/internal.source.yaml each select zero modules; src/kernel/activation_ledger_store.py selects {core_misc,kernel,unit} with charter absent.

2026-10-31 · claude-code/opus · Aggregate-diff review before landing (self-review; the ready-for-squad label is the independent squad hand-off): the combined diff is 5 files of substance -- ci-router.yml (new non-src group + outputs row; one added charter glob), gate_selection.py (one hand-authored fan-out table consulted by select_modules), the scrub charter root, the registry charter row, the new test module -- plus one changelog line. Cross-WP integration check: WP01's non-src group and WP02's src root never overlap (no src glob in the new group, so it stays out of the unmatched union and no job gates on it); the charter group's three transcription sites all moved together, verified by both ordered verbatim guards; the module set/shard counts/test dirs are untouched. LAND.
