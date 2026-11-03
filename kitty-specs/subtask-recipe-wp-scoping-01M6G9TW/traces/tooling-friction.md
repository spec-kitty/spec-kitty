# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · claude-opus-4-5 · The mission's own generated prompts prove the defect: the implement prompt for WP01 and the `agent action implement` runbook both end with `spec-kitty agent tasks mark-status T001 T002 T003 --status done --mission <slug>` — no `--wp`. On this mission, whose WP files each author T001..T003 (the normal case), that printed command is refused by mark-status ("T001 is a subtask of WP01, WP02, WP03; pass --wp to select one."), so the operator has to hand-edit the advice or reach for --force. Exactly the #7108 dead end, observed on the mission that fixes it.

2026-11-03 · python-pedro · The mission had to be re-created on the topic branch: specify on main reaches the coord topology and the protected-branch refusal rejects the planning write there, so the second attempt ran specify on issue-7108-subtask-recipe-wp-scoping from the start. Also inherited on resume: the previous run added a pyproject.toml mypy-override entry for the new module, which no gate reads (mypy runs only via make typecheck over two named files) and which is outside every WP's owned files — reverted, and mypy --strict on the module is clean without it.
