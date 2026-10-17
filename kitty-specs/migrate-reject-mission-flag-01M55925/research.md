# Research — Reject `--mission` on non-mission-scoped migrate commands (#5294)

Phase 0 consolidation. Sources: the pre-spec grounding squad (opus, profile-loaded:
alignment lens + brownfield/scope lens) and direct code reading on main `7b741a68ed`.

## Decision 1 — The bug is live and not superseded

- **Decision**: Proceed; #5294 is a real, unresolved defect on current main.
- **Rationale**: In-process parse check confirmed all five commands accept `--mission` (exit 0, no "No such option"). Sibling #4964 was closed via PR #5305 but did not touch this mechanism (`git log -S "MissionAgnostic"` / `-S "corpus-wide"` shows only the original #3953 landing, commit `2a072c6d74` / PR #4635, plus unrelated CI churn). No merged PR/ADR makes these commands reject `--mission`.
- **Alternatives considered**: Close as superseded — rejected (evidence shows it is live).

## Decision 2 — Reject (not scope); five commands (not four)

- **Decision**: Make the five commands reject `--mission` with a scope-neutral error. Real per-mission scoping is deferred.
- **Rationale**: Operator triage (2026-10-08) chose the small reject fix; adding real scoping is the larger follow-up. The brownfield lens found `repin-hooks` as a 5th command of the identical class; the operator approved including it (Decision Moment `01M5592YNBAT1PC4P7EB2SP3Y9`, 2026-10-17) to close the whole class at trivial marginal cost.
- **Alternatives considered**: (a) Four only — rejected, leaves `repin-hooks` reproducing the exact defect. (b) Add real `--mission` scoping now — rejected, larger work, explicitly deferred by operator.

## Decision 3 — Seam: `CorpusWideCommand(TyperCommand)` subclass in `migrate_cmd.py`

- **Decision**: A `CorpusWideCommand(TyperCommand)` subclass with a `parse_args` post-check that raises via `_usage_error_class(ctx)` when `_given_on_command_line(ctx, "mission")`; still declares the hidden option through `_with_ignored_mission_option` in `get_params` (so `--help` is unchanged and the flag is parsed, then rejected). The five `@app.command` decorators take `cls=CorpusWideCommand`.
- **Rationale**: Empirically verified by the brownfield lens — a `TyperCommand` *subclass* is left alone by `make_leaf_commands_mission_agnostic` (helpers.py:224 retargets only `cls is None or cls is TyperCommand`), so no walker edit; it is exactly the escape hatch pinned by `test_walker_leaves_custom_command_classes_alone`. Reusing `_given_on_command_line`/`_usage_error_class`/`_COMMANDLINE_SOURCE` solves the two-click-era hazard (typer 0.24.1..0.28) without any new real-`click` class. Home is `migrate_cmd.py` (owns both the commands and the helpers); `cli/helpers.py` stays generic.
- **Alternatives considered**: (a) Per-command runtime guard in each callback — impossible cleanly (`expose_value=False` means the callback never receives `--mission`) and duplicates logic 5× (Sonar S1192). Rejected. (b) Reject-list inside the generic walker — couples the walker to a hardcoded migrate command-name list and fights the left-alone contract. Rejected.

## Decision 4 — Scope-neutral message

- **Decision**: One shared message: "this command is not mission-scoped" + drop-the-flag remedy.
- **Rationale**: The five don't share one scope model — `rewrite-opposed-by` is pack-scoped (`--pack`), `repin-hooks` is repo-repair, the other three walk corpus/mission content. "Corpus-wide" would be inaccurate for two of them; "not mission-scoped" is accurate for all five and reconciles the "pass `--mission` everywhere" skill instruction by telling the agent to drop it here.

## Decision 5 — Blast radius / whack-a-field

- **Decision**: Amend the two tree-wide invariant tests; add positive reject tests; confirm no doc regen.
- **Rationale**: `test_every_leaf_command_accepts_mission` and `test_reregistration_keeps_the_invariant` (tests/cli/test_mission_agnostic_flag.py) assert the whole tree accepts `--mission`; because the rejecting class still *declares* the hidden option they may stay mechanically green yet become intent-lies — amend to carve out the five and assert they reject. `tests/architectural/test_json_contract_enumeration.py` invokes the five with `--dry-run`/`--json` only (default source, not rejected) → must stay green. `--help` is byte-identical (option stays hidden) → no `docs/api/cli-commands.md` regen, no docs-freshness run needed for this change. No `packs/**/prompt.md` names these commands specifically.

## Supply-chain posture

No dependency added/upgraded/removed → `DIRECTIVE_051` / `supply-chain-install-safety` controls are **N/A** for this mission. Recorded here per the plan step contract (silence is not compliance).

## Adversarial evidence

Pre-spec grounding squad (2 opus lenses) ran before spec; no contested finding dropped. The 5th-command finding (`repin-hooks`) was escalated to an operator decision and resolved (include). A post-tasks adversarial anti-laziness squad is planned before implement.
