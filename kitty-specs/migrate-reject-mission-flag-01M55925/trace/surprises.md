# Mission Trace — Surprises / Gotchas

Append-only. Seeded at planning; appended during implement.

- **Known collision (not a bug)**: `tests/cli/test_mission_agnostic_flag.py::test_every_leaf_command_accepts_mission` and `::test_reregistration_keeps_the_invariant` assert the whole tree accepts `--mission`. Because the rejecting class still *declares* the hidden option (it intercepts at `parse_args`), these two may stay mechanically green yet become intent-lies for the five — they MUST be actively amended to carve out the reject-set, with positive assertions that the five reject.
- **Two-click-era hazard**: typer 0.24.1..0.28 spans real `click` and vendored `typer._click`. Any new Option/Command must be typer-native; the `UsageError` must come from the ctx's own click universe (`_usage_error_class`), or exit 2 degrades to a traceback. Do not hand-roll.
- **Bare `--mission` (no value)** errors at typer's parser ("requires an argument", exit 2) before the scope post-check — still loud, different message. Acceptable.

- **Scope-neutral message is load-bearing (post-tasks squad, 2026-10-17)**: the reject message must NOT say "runs across the whole corpus/repository" — inaccurate for `rewrite-opposed-by` (pack-scoped) and `repin-hooks` (repo-repair). Since the tests assert only the `not mission-scoped` substring, an over-specific message would ship green. Keep it scope-neutral.
- **#4964 sibling test in the blast radius**: `tests/cli/test_migrate_group_flags_4964.py` forwards group flags into these five subs via `ctx.default_map`. `CorpusWideCommand.parse_args` wraps `super().parse_args`, so a default_map regression surfaces only there — run it.
- **No real-app retarget-count assertion**: the five move outside the walker's count; don't add a real-app `make_leaf_commands_mission_agnostic` total assertion (synthetic-app count tests are unaffected).
- **Group-position `--mission`** (before the subcommand) fails via click's own "No such option" at the group — loud, distinct message, not a regression.
