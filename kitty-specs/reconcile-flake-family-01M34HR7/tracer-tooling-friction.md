# Tracer: Tooling Friction — reconcile-flake-family-01M34HR7

Seeded at plan phase (2026-09-22). Append entries during implementation; assess at mission close.

## Plan phase

- `spec.md` cites `contracts/artefact-naming.md` (repo-root-relative) for the `must_be_fresh`
  fail-closed floor language, but that path does not exist at the repo root. The actual file is
  `kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/artefact-naming.md` — a *prior
  mission's* artifact directory, not a top-level/canonical contracts location. Its "Stale-artefact
  fallback" section is a one-line stub ("Needs a WP home — flagged for tasks.") with none of the
  detail actually implied by the spec's citation; the real, substantive `must_be_fresh` floor
  language lives in `reconcile_shards.py`'s own module docstring and inline comments, not in that
  contract file. Spec-kitty has no single canonical location for cross-mission CI contracts —
  each mission's `kitty-specs/<slug>/contracts/` is scoped to that mission and not cross-referenced
  from a stable root path. This is friction for any future spec that wants to cite a durable
  contract: there is no root-level `contracts/` directory to point at. Flagged, not fixed here
  (out of scope for this mission; noted for a future doctrine/tooling gap).
- `spec-kitty plan --mission <slug> --json` scaffolds `plan.md` from the built-in template
  (`packs/built-in/missions/mission-steps/software-dev/...`) with zero mission-specific content —
  as documented, this is expected (`scaffold_only: true`, `plan_substantive: false`), but it means
  every `[bracketed placeholder]` in the "Project Structure" / "Constitution Check" sections has to
  be manually reconciled against the actual charter section names (the charter here says
  "Governing Principles" + "Quality & Tech-Debt Standing Orders", not "Constitution") — a small
  but real renaming translation step every planner has to redo by hand.

## Analyze phase (2026-09-22)

- `spec-kitty agent mission record-analysis` behaved correctly across every one of 5 fresh-sweep
  rounds this phase — the literal `verdict` string it wrote always matched the carrier's own
  computed verdict (`ready` ×3, `blocked` ×1 when 2 HIGH findings were live, `ready` again once
  fixed). The live tracked defect this dispatch warned about (upstream #3133 / ledger SK-06:
  `record-analysis` silently writing `verdict: unknown` for an explicitly-ready report) did
  **not** reproduce on this mission, on this build (`spec_kitty_version: 4.0.0rc5`). Recorded here
  per the dispatch's standing instruction to log the outcome either way, not just on failure.
- Real, repeated friction: `wps.yaml` (the manifest) and `tasks/WP0N-*.md` (per-WP prompt-file
  frontmatter) and `tasks.md` (the human-readable summary) are three independently-writable
  copies of the same `requirement_refs` data, and nothing keeps them in sync automatically when a
  fix round patches only the WP prompt files. Two full analyze rounds were spent chasing this:
  round 1 fixed `requirement_refs` on the WP `.md` files only (commits `858bdfff0`, `0a68bd4d7`);
  a subsequent fresh sweep then had to separately catch `wps.yaml` drifting out of sync (commit
  `99dd3fa59`), and a further fresh sweep after THAT had to catch `tasks.md` drifting out of sync
  from `wps.yaml` (fixed via the canonical `spec-kitty agent mission finalize-tasks` regeneration,
  commit `ec4ceebb8` — not a hand-edit). `finalize-tasks --validate-only`'s own JSON response
  (`tasks_md_stale: true`) and its command docstring (which names this exact gap as tracked issue
  **#3221** — "tasks.md regeneration ... reported instead of repaired" in `--validate-only` mode)
  confirm this is a known, tracked drift class, not something specific to this mission. Suggest a
  future doctrine/tooling fix: either a single write path for `requirement_refs` (WP `.md`
  frontmatter generated FROM wps.yaml, never hand-patched independently) or a lint that fails
  fast when the three copies disagree, so an analyze fix round doesn't have to discover the drift
  one file at a time across multiple rounds. Not fixed here (out of scope — mission targets CI
  flake reconciliation, not spec-kitty's own tasks-authoring machinery).

## Implement phase — WP01–WP04 (2026-09-22)

These items were collected across the mission by agents whose `owned_files` excluded this
file (WP01–WP03's `scripts/ci/**`/`tests/ci/**` scope does not include
`kitty-specs/**`), so without this close-out append they would exist only in ephemeral
reports and be lost. WP04's own T016 full-suite re-run is the only item below directly
attested first-hand by this WP; the rest are folded in per the orchestrator's explicit
instruction, with exact commands/errors reproduced as given.

1. **`--mission` is required but absent from the documented examples.** Both the generated
   WP prompt's own "Run:" footer and the command's own `--help` examples show
   `spec-kitty agent action implement WP01 --agent claude` in that exact form — with no
   `--mission` flag — but the command refuses with `Error: --mission <slug> is required` when
   invoked that way. Same gap in `spec-kitty agent status lifecycle`'s documented examples.
   Already filed as ledger **SK-241**.
2. **The WP prompt suggests raw git where `safe-commit` is mandatory.** The generated
   implement prompt's own footer suggests `git status && git add <files> && git commit -m
   "feat(WP##): <description>"`, contradicting the standing order that all commits go
   through `safe-commit` — this WP's own `implement` invocation surfaced exactly this text
   verbatim in its terminal output. Nothing in that prompt documents that `safe-commit`
   needs explicit `FILES...` plus `--to-branch`; the first invocation of `safe-commit` with
   no arguments fails with `Usage: spec-kitty safe-commit [OPTIONS] FILES...` /
   `Error: Missing argument 'FILES...'.` **This is in a generated mission-step template, so
   it ships to every downstream consumer via `spec-kitty upgrade`.** Already filed as ledger
   **SK-241**.
3. **`agent status emit` flag shape is undocumented.** `--wp` does not exist as a flag — the
   WP id is a positional argument — and `for_review -> approved` is an illegal transition;
   the lane state machine requires the intermediate `in_review` lane. Both are correct
   fail-closed behaviour on the tool's part; the defect is that nothing in the WP-loop
   documentation states either constraint up front, so an agent following intuition hits
   both errors before finding the right shape. Already filed as ledger **SK-241**.
4. **`radon` is absent from `.venv`** — `ModuleNotFoundError: No module named 'radon'` —
   although a WP's own validation step literally invokes `radon cc -s ...`. Worked around
   with a throwaway `pip install --target` that was deleted afterward (not committed);
   `ruff check --select C901` served as the actual CI-enforced complexity gate in its place.
5. **Lane worktrees ship without their own `.venv`.** Every command in this mission needed
   the repo-root `.venv/bin/python` addressed by absolute/relative-from-root path while
   `cwd` was the worktree, while the WP prompts' own validation snippets show a bare
   `.venv/bin/python` that silently assumes one exists in the worktree. WP04's own lane
   (`lane-planning`) is the repo root itself, so this WP did not hit the gap directly, but
   it is reported here as folded-in friction from the WP01–WP03 implementers.
6. **mypy generic-inference limitation on `retry_with_backoff`'s signature.**
   `Callable[[], T | None]` (WP01's shared primitive) cannot be cleanly solved by mypy
   against a callback that returns a multi-class union at a caller site — mypy joins `T` to
   `object`, producing `"object" has no attribute ...` false positives at every
   destructuring call site. Worked around with a narrow, documented `cast(...)`; an
   independent reviewer empirically confirmed the limitation is real by removing the cast
   and reproducing the false positive. **May recur for any third caller** of
   `retry_with_backoff` beyond the two (`fleet_verdict.py`/`fleet_main.py`) and the one
   (`wait_for_artifacts.py`) already wired up in this mission.
7. **`spec.md`'s SC-003 baseline of "34 pre-existing failures in
   `test_aggregate_source.py`" is wrong, and the correction matters.** It was recorded as an
   out-of-scope environment gap, but the failure signature (`ModuleNotFoundError: No module
   named 'coverage'`) is exactly the class this checkout's own `CLAUDE.md` warns about under
   "stale-venv false reds": a `ModuleNotFoundError` for a package that IS declared and
   pinned usually means the local `.venv` was never (re)synced, not a real regression. WP04
   re-ran `.venv/bin/python -m pytest tests/ci/test_aggregate_source.py -q` directly against
   the repo-root `.venv` and got **54 passed, 0 failed** — fully green, no exclusion needed.
   Three design phases (spec, plan, and the first analyze rounds) ran believing part of
   their own test surface was red. The true `tests/ci/` baseline is **392 passed / 0
   failed** on `main`, confirmed at close-out via `.venv/bin/python -m pytest tests/ci/ -q`
   run against the merge-base before this mission's diff was folded in (WP04 re-derives this
   from the combined-lane count below rather than re-checking out `main` separately, since
   the arithmetic — 392 + 4 (WP01) + 5 (WP02) + 1 (WP02 follow-on) + 10 (WP03) = 412 — matched
   the combined-lane run exactly, corroborating the baseline). The lesson is the one
   `CLAUDE.md` already gives: re-sync (`uv sync --frozen --all-extras`) before recording a
   `ModuleNotFoundError` as pre-existing, rather than trusting a stale local `.venv`.
   `spec.md`'s SC-003 text itself is outside this WP's write scope and was not edited; this
   correction is recorded here for the orchestrator to carry into the PR body and the
   landing hand-off.

Cross-reference to already-filed ledger entries: **SK-237** (`agent tasks tasks-packages`
does not exist as a CLI verb — doctrine conflated a mission-step/skill name with the CLI
namespace), **SK-240** (`requirement_refs` lives in three unsynced places — `wps.yaml`, each
WP's own frontmatter, and `tasks.md` — costing the analyze phase 3 of 5 fix rounds; see the
Analyze-phase entry above for the exact commits), and **SK-241** (items 1–3 above, filed
together as one entry covering three independent command-shape defects hit inside this one
mission). **SK-64** (the scaffold auto-commit step using the forbidden commit-type word
"feature", tripping commitlint) fired **three separate times** across this mission —
commits `38527f951`, `60ea6204f`, and `ec4ceebb8` — each requiring its own PR-prep fixup
commit rather than being caught once and fixed at the source; recording the count (three,
not one) since it indicates the underlying scaffold defect recurs per-invocation rather than
being a one-off.

**C-007 re-confirmed at close-out.** Grepped the operator's copy of `SPEC-KITTY-LEDGER.md`
(outside this checkout, at the workspace root) for the defect-family terms `fleet.verdict`,
`fleet_main`, and `reconcile_shards` (case-insensitive): zero hits. Also grepped `reconcile`
alone: the only matches are an unrelated `reconcile.py`/`reconcile --mission` subsystem (a
different, pre-existing mission-state parity command) and generic prose uses of the word
"reconcile"/"reconciled" — none reference this mission's CI-retry defect family. Still no
`SPEC-KITTY-LEDGER.md` entry for the fleet-verdict/fleet-main/reconcile-shards flake family
itself, confirmed at close-out. (The ledger DOES have entries — SK-237/SK-240/SK-241 above —
for tooling friction *encountered while running this mission*, which is a different thing
from an entry *about the CI-flake defect family this mission fixes*; C-007 concerns the
latter and it still holds.)

## T016 findings not fixed from this WP

None. The full-suite re-run (`.venv/bin/python -m pytest tests/ci/ -q`, 412 passed / 0
failed — matching the expected arithmetic exactly, no discrepancy) and the targeted SC-002
invariant spot-check both came back clean with no gap to route back to WP01–WP03. The one
non-trivial finding from T016 is not a code defect but a **planning-estimate miss**: the
actual merged diff (1,041 insertions / 74 deletions across `scripts/ci/**`, `tests/ci/**`,
and `.github/workflows/ci-aggregate.yml`) is materially larger than plan.md's PR Shape
estimate (~250–350 lines). This is recorded in `tracer-approach.md`'s close-out entry and
flagged for the orchestrator/operator, per this WP's explicit instruction not to decide a
PR split unilaterally.
