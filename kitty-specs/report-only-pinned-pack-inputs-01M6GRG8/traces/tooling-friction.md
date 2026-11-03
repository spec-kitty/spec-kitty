# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · spec-kitty specify on a protected target branch creates the mission scaffold on disk but refuses the scaffold commit, leaving kitty-specs/<slug>/ untracked and the mission unusable; agent mission create --start-branch/--target-branch is the working path for issue-bound missions.

2026-11-03 · python-pedro · Two host-specific traps. (1) The implement work landed before spec-kitty agent action implement WP01 recorded the claim, so move-task --to for_review refused with 'no implementation commit since claim' and the only escape the CLI offers is --force; the honest remedy was a genuine follow-up commit after the claim. Ordering: claim, then implement, then commit. (2) record-analysis computes package:built-in from the running installation, so a report recorded with uv run (editable) is immediately stale under the global ~/.local/bin/spec-kitty that runs next; record with the same CLI that advances the runtime.
