# Research: Truthful software-dev discovery step and finalize shim cleanup

Sources: grounding squad and post-spec adversarial squad, main 4e81f4d5, 2026-09-28.

## Decision 1 — Rewrite the discovery prompt; do not ship a software-dev scaffold
- **Decision**: The mission-step `research` prompt tells the agent to author `kitty-specs/<mission>/research.md` directly (create or extend it). `spec-kitty research --mission <handle>` is described only for mission types that ship research templates, after their plan is filled.
- **Rationale**: The software-dev plan prompt (`plan/prompt.md:320-360`) already owns `research.md` / `data-model.md`. `expected-artifacts.yaml` marks both as optional and non-blocking for discovery. A second scaffold would be a parallel authority (charter: single canonical authority). The `discovery` step runs before `plan.md` exists, while `research.py:222-236` exits 1 without a filled plan.
- **Alternatives**: (A) ship a software-dev research scaffold. Rejected: it duplicates the plan step and still hits the plan-filled gate.
- **Decision record**: DM-01M3KAD2G6HZMB6TF4W049WCB9.

## Decision 2 — Canonical resolver for research templates
- **Decision**: `research.py` resolves through `specify_cli.runtime.resolver.resolve_template`, mapping destination → template: `research.md` → `research-template.md`, `data-model.md` → `data-model-template.md`, CSVs → `research/<name>.csv`. The legacy `core.project_resolver.resolve_template_path` is retired, since `research.py:76` is its only caller.
- **Rationale**: The legacy 5-tier resolver has no package-default tier, so a fresh install only finds templates if `~/.kittify` is populated. It also asks for filenames the pack does not ship, so `research.md` / `data-model.md` never scaffold for any type. Verified: `resolve_template('research-template.md', mission='research')` resolves, and `mission='software-dev'` raises `FileNotFoundError`.
- **Behaviour change**: the canonical resolver no longer reads `.kittify/missions/<type>/templates/` or project-root `templates/`. It adds `.kittify/overrides/templates/`, org packs and the package default. This is documented in the changelog.
- **Alternatives**: rename only at `research.py:264-265` and keep the legacy resolver. Rejected: it keeps a parallel resolution authority and still misses the package default.

## Decision 3 — #5233 shim removal
- **Decision**: Delete `_ensure_branch_checked_out` (`agent/mission.py:352-354`), drop the three patches in the same commit, and remove the dead `fire_dossier_sync` test patch. Keep the public `specify_cli.status` import shim. Rebuild the validate-only read-only fixture so HEAD is on a branch that differs from the mission target, the #1861 shape.
- **Rationale**: Nothing calls the shim; checkout positioning goes through `commit_for_mission`, which the tests already patch. The read-only test's fixture checks out the target branch today (`:128`, `:145`), so its "divergent branch" claim is untested.

## Open questions / risks
- Prompt-invariant tests may pin the old text; they are updated with a justification (NFR-001).
- The doctrine pack manifest may hash skills; regenerate if the gate trips.
