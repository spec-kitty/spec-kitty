---
affected_files: []
cycle_number: 1
mission_slug: readme-rename-and-docs-audit-01M78WZM
reproduction_command:
reviewed_at: '2026-11-13T01:08:22Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP02
---

# WP02 review, cycle 1: changes requested

Reviewer: `claude-reviewer::reviewer-renata` (independent; did not write this code).

The retired-list move is behaviour-identical, every red test was red at its own commit, the gate
is green on the tree and red on a planted mention and a stale entry, ruff, format and
`mypy --strict` are clean, and the generated surfaces are untouched. Two defects make the
inventory and the gate under-report the exact things #7520 exists to find, so the snapshot and
the page lists posted to #7522–#7528 would be wrong. Both are small to fix.

## Issue 1 (high): on a shallow clone the inventory reports the graft commit as a content change

`GitHistory.last_content_change` (`scripts/docs/staleness_audit.py`, the `before is None` branch)
reads a missing parent blob as "page created here". This checkout is shallow
(`git rev-parse --is-shallow-repository` → `true`); its boundary commit `47cc8f3b2` (2026-08-10,
15,780 files added) is the graft, not a content change. In the committed snapshot
`audit/inventory.json`, **61 of 340 pages** carry `last_content_change: 2026-08-10` /
`last_content_commit: 47cc8f3b2…` (for example every `context/audience/**` page, `context/dossier.md`,
`context/lexical.md`). Those are the pages whose content is *oldest*, and the inventory presents
them as recently changed — the opposite of what the section passes need. CI checkouts are often
shallow too.

Fix: detect a shallow repository (or a commit in `.git/shallow` / with no reachable parent) and
either refuse with a clear message (`git fetch --unshallow` first) or record the field as unknown
(`null` plus a `history_truncated` / "before <date>" marker) instead of a date. Add a test on a
`git clone --depth 1` fixture. Regenerate `audit/inventory.json` and `audit/page-lists.md` from a
full-history clone.

## Issue 2 (high): the retired `/spec-kitty.merge` slash command is invisible to the gate and the inventory

`spec-kitty merge` is matched only as the CLI phrase (`_command_pattern(("merge",))` in
`scripts/retired_surfaces.py`). The agent-facing form of the same retired command, the
`/spec-kitty.merge` slash command and its `spec-kitty.merge.md` command file, was replaced by
`consolidate` (`HISTORICAL_COMMANDS` in
`src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_antigravity_workflows.py`;
`CANONICAL_COMMANDS` in `src/specify_cli/skills/command_installer.py` has no `merge`). It is named on
**22 living pages the gate does not flag**, among them `guides/how-to/missions/accept-and-merge.md`,
`guides/tutorials/claude-code-integration.md`, all ten `guides/how-to/harnesses/*.md`, seven
`guides/how-to/scenarios/*.md`, `api/file-structure.md` and `architecture/documentation-mission.md`.
Planting ``Run `/spec-kitty.merge`.`` on `docs/guides/README.md` leaves the gate green.
The same applies to `/spec-kitty.dashboard` (retired #5530; today only on a page the gate already
flags for `spec-kitty dashboard`).

Fix: give the retired slash commands a surface (`spec-kitty.merge`, `spec-kitty.dashboard`, matched
as `/spec-kitty.<cmd>` and `spec-kitty.<cmd>.md`, never a prefix of a live name), add matcher cases
(found and not-found, for example `/spec-kitty.consolidate` stays clean), add the new pairs to the
burn-down with their section issue in the same landing, set the `_baselines.yaml` count to the
new landing total with the justification, and regenerate the snapshot and page lists.

## Issue 3 (medium): the size ratchet lets the burn-down be swapped or regrown

`tests/architectural/test_ratchet_baselines.py` fails only on growth above the recorded 64; a
shrink only warns. After a section pass fixes a page (live 63, baseline still 64), a new
(page, surface) pair can be added to `retired_surface_burndown.yaml` and both the gate and the
ratchet stay green; a same-size swap is never caught. Pin the set, not only its size: for example a
test that every burn-down pair is in the frozen landing set (a literal in the test, or a digest),
so entries can only leave. This keeps C-003 ("no silent allowlist") true after the first fix lands.

## Issue 4 (low): smaller points, fix while you are here

- `check()` / `scan()` read the body only (`body_of`), but `title` and `description` are published.
  Nothing hits there today; say so in the docstring or scan them too.
- `_entry` and `load_burndown` branches without a test: a non-mapping entry, a missing field,
  `entries` not a list. A duplicate `page:` entry merges silently; refuse it.
- For the 85 code-list surfaces the finding reads "retired by removed from the code tree
  (tests/architectural/...)", while the hint says the note names the replacement. Reword one of them.
- `docs-lint` job `name:` in `ci-router.yml` still says "spelling + changelog style".
- Non-`src/` entries of `RETIRED_PATHS` (`tests/`, `scripts/`, `.github/workflows/*.yml`) are not
  docs surfaces; state that choice in the module docstring.

## What is fine (no change needed)

- Retired lists moved verbatim: the 79 paths and 5 CLI prefixes at the base equal
  `RETIRED_PATHS` / `RETIRED_CLI_PREFIXES` exactly; the arch gate passes.
- Not extending `check_docs_freshness.py` was right: no CI job runs that orchestrator, the gate
  belongs in the always-on `docs-lint` job, and the page set and retired set each keep one source
  (plan D-6 revision records it).
- Inventory output is byte-reproducible (two runs identical; the regenerated pages match the
  committed snapshot except the commit header). The 145 KB snapshot in the Mission directory is
  reasonable (under the 200 KB budget, history-only, not under `docs/`), once regenerated per
  Issue 1.
- No model identifiers in commits or code; code commits carry no bookkeeping files; no
  bot-owned surface edited.
