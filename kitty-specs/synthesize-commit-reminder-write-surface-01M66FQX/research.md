# Research — synthesize-commit-reminder-write-surface-01M66FQX

Grounding for spec-kitty/spec-kitty#6631, recorded before planning.

## Reproduction on current main (512567eee7, 2026-10-30)

Confirmed by reading the current `main` (the reporter's build was `1a0c8b467`;
`git log` since then shows no change to the reminder, the record writer or the
skill references):

1. `_print_synthesis_commit_reminder` renders `_SYNTHESIS_ARTIFACT_PATHS`
   (`src/specify_cli/cli/commands/charter/_synthesis.py:763-782`), a fixed
   tuple of exactly three paths: `.kittify/charter/synthesis-manifest.yaml`,
   `.kittify/charter/provenance/`, `.kittify/charter-packs/`.
2. The same run calls `append_synthesized_activations`
   (`src/specify_cli/cli/commands/charter/synthesize.py:556-562`;
   `resynthesize.py:216-221`), which writes
   `.kittify/charter/synthesized-artifacts.yaml`
   (`CREATED_ARTIFACTS_PATH`, `reach_only.py:45`) whenever a participating
   kind's recorded set changes, and writes the activation write target
   (`.kittify/charter/activation.yaml` on a ledger project, or the pointed-at
   `charter.yaml` / `.kittify/config.yaml` on a legacy project) through
   `_promote` when a first-time slug joins an explicit `activated_<kind>s`
   list (`reach_only.py:272-316`).
3. The governance skill's step 7
   (`src/charter/offering/skills/spk-charter-governance/references/charter-governance-workflow.md:186-191`)
   commits the same three paths. `charter-artifact-structure.md` does not list
   the record in its authority table (line ~63) nor its Git-tracking table
   (line ~185-190).
4. The existing reminder test
   (`tests/agent/cli/commands/test_charter_synthesize_cli.py:275`) asserts the
   three paths as a substring, so a fourth path would keep it green — it
   cannot catch the omission (confirmed: the substring assertion is not an
   exhaustive list assertion).

The real-pipeline entry point for a reproduction test already exists:
`tests/charter/synthesizer/test_synthesize_activation_append.py` drives the
real `charter synthesize` (only evidence collection and request derivation are
patched) on a `tmp_path` project with an explicit `activated_tactics` list, and
the run creates tactic `how-we-apply-directive-003` and writes the record.

## Not superseded

- No commit since `1a0c8b467` touches `_SYNTHESIS_ARTIFACT_PATHS`,
  `_print_synthesis_commit_reminder`, `CREATED_ARTIFACTS_PATH` handling or the
  skill references (`git log --since=2026-10-20` on those paths shows only
  #6510/#6453/#6454/#6496 work, none changing the reminder's path list).
- The changelog has no entry saying the record is intentionally uncommitted.
- Related but distinct: #6453 (concurrent runs losing record entries — fixed
  by the synthesis lock), #6454 (unreadable manifest fail-closed). Neither
  covers the reminder.
- `charter bundle validate` leaves the record out of bundle-manifest scope
  (`charter_bundle.py:83-87`) — that concerns the bundle manifest, not git
  tracking; out of scope here (C-005).

## Decisions

- **D1 — Derive the reminder from the write surface, not a longer fixed
  list.** The issue's own analysis: the record and the activation file are
  written only on some runs, so a fixed list either misses them or names a
  path that does not exist (which would make the printed `safe-commit` command
  fail). The activation-append step is the single writer that knows what it
  wrote; it will report the repo-relative paths it wrote, and the reminder
  renders base paths + those.
- **D2 — Report through the return value of `append_synthesized_activations`.**
  Its current `list[str]` warnings return gains a structured shape (warnings +
  written paths). Callers: `synthesize.py`, `resynthesize.py`, and the
  reach-only/append test files. This is an internal seam (pre-GA 4.0.0rc line),
  not a public CLI contract; the JSON envelopes are unchanged (C-003).
- **D3 — Pin the invariant generically with an end-to-end regression test.**
  Run the real synthesize on the canonical fixture, extract the printed
  safe-commit line, execute it in the test repo, assert
  `git status --porcelain .kittify/` is empty. The assertion is over the whole
  `.kittify/` tree, so any future written-but-unnamed artifact fails it — the
  test is the anti-drift pin the issue asks for.
- **D4 — Skill/doc text updated in the committed source.**
  `src/charter/offering/skills/spk-charter-governance/references/` is tracked
  in core and is the source of the rendered `~/.agents/skills/` copy (verified
  identical today). No pack pin bump is needed: the references are not part of
  the fetched `packs/built-in` / `packs/internal` trees (verified: no
  `charter-governance-workflow.md` under `packs/` after `make sync-packs`).

## Evidence

- `git check-ignore` on this repository: `.kittify/charter-packs/**` is
  ignored here, but `synthesis-manifest.yaml`, `provenance/` and
  `synthesized-artifacts.yaml` are not — consumer projects differ; the
  reminder's job is to name what the run wrote regardless.
- `tests/specify_cli/cli/commands/test_safe_commit_cli.py` shows the
  in-process `CliRunner` pattern for executing a `safe-commit` invocation and
  the git-repo setup needed (init on a non-protected branch, identity config).

## Open questions (resolved in the spec)

- None blocking. The spec fixes: report shape (FR-001), reminder derivation
  (FR-002), regression test (FR-003), docs (FR-004), changelog (FR-005).
