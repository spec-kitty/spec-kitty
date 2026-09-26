# `runtime_bridge` parity-oracle fixture layout (WP01, #2531)

The parity oracle (`tests/runtime/test_bridge_parity.py` +
`tests/runtime/_bridge_oracle.py`) is the BLOCKING safety net every extraction
WP (WP03–WP10) re-runs as its acceptance gate. It drives the three real public
entry points of `src/runtime/next/runtime_bridge.py`
(`decide_next_via_runtime`, `query_current_state`, `answer_decision_via_runtime`)
against realistic on-disk mission repos.

## Snapshots are built programmatically, not stored on disk

There are no committed golden repos here. Each fixture's frozen snapshot is
**built fresh in a temp dir** by a `_build_*` function, which stays in the oracle
module `test_bridge_parity.py`. The builders use the shared real-mission
scaffolds (`scaffold_software_dev`, `advance_to_step` and the git / WP-seeding
helpers), which live in `tests/runtime/_next_mission_scaffold.py`, plus the
oracle-local `scaffold_research` / `scaffold_documentation` helpers (real
`git init`, `kitty-specs/<slug>/meta.json`, `tasks/WP*.md`, a canonical
`status.events.jsonl` seed, and — where the scenario needs an advanced run — a
REAL engine walk via `advance_to_step`, never a stub). The `ledger_results`
module fixture then `copytree`s each snapshot **twice** into independent per-run
roots and drives the owning entry once per copy, so masking soundness and
determinism are proven together.

To regenerate / inspect a scenario, call its `_build_*` function with a `tmp_path`
and read the returned `(snapshot_dir, drive_kwargs)`.

The board-authority P0 tests (#4980 / #4975) live in
`tests/runtime/test_next_board_authority.py`; they reuse the same scaffold module
but never import the oracle or set up the `ledger_results` fixture.

## Per-entry sub-ledgers

Fixtures are partitioned by the public entry that owns them (`FixtureSpec.sub_ledger`):

- **`decide_next`** — the happy loop (specify→plan→tasks→implement→review→accept),
  each CLI/composed guard branch (software-dev / research / documentation,
  including the `tasks` legacy-union), plus the error / `decision_required` arms:
  `dn_input_mission_decision_required` (`_map` decision-required, `bridge:3629`),
  `dn_corrupt_run_state` (engine-error, `:2965`),
  `dn_missing_canonical_status` (WP-iteration `CanonicalStatusNotFoundError`, `:2639`),
  `dn_block_policy_unreadable_state` (pre-state OSError under a blocking
  retrospective policy, `:2936`), and
  `dn_wp_done_no_action_mapped` (`_map` WP-step no-action, `:3659`).
- **`query`** — the four `_build_*_query_decision` sites, incl.
  `q_input_mission_decision_required` (`_build_decision_required_query`, `:3147`).
- **`answer`** — `answer_input_mission` drives the answer-path's own emit/commit.

## Coverage floor (binding)

`test_coverage_floor_is_met` tallies the Decision sites and guard branches
actually reached across the whole ledger and asserts `>= floor` (17 sites / 18
branches). This is a checkable count, not a fixture count:
`test_hollow_ledger_fails_coverage_floor` proves the same helper trips on a
sparse ledger. The two composed-guard fail-closed defaults are exercised by
direct unit calls (`test_{research,documentation}_fail_closed_default_direct_call`)
rather than through an entry, because a valid charter-resolved `action_sequence`
never routes an unknown action to them from a public entry.

## Non-determinism masking

`_bridge_oracle.canonical()` MASKs ULIDs/timestamps, PATH-NORMALIZEs
repo-root-relative fields (`workspace_path`, `reason`, `origin.mission_path`) to
each run's own root, and PROMPT-NORMALIZEs `prompt_file` to its stable basename
stem (prompt files live in the shared `spec-kitty-prompts/<hash>/` namespace
outside repo_root, and composed markers carry an `mkstemp` random suffix).
`test_reason_normalizer_meta_test` guards against the normalizer over-collapsing
a genuine semantic delta. Side-effect payloads (sync emit, coord commit, and the
IC-02 engine mutations `_append_event`/`_write_snapshot`/`_read_snapshot` plus the
retrospective gate) are canonicalized the same way (`canonical_side_effects`) and
asserted binding-equal across the two runs.

## Scope — not a standalone golden characterization

Every assertion compares two independent runs of the **current** code (no stored
golden baselines). The oracle catches non-determinism, coverage-floor
regressions, and side-effect-payload breaks — but NOT a *consistent* behavior
change across an extraction (both runs shift identically). The compensating
control is that each extraction WP (WP03–WP10) also re-runs the full existing
runtime suite (`tests/next/*`, `tests/integration/test_*_runtime_walk.py`), which
pins concrete decide_next/query/answer outputs. Run both; do not over-trust a
green oracle alone.
