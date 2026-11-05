---
affected_files: []
cycle_number: 1
mission_slug: landed-worktree-cleanup-01M6KZNP
reproduction_command:
reviewed_at: '2026-11-05T08:20:49Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP06
---

# WP06 review — changes requested (reviewer-renata)

The CLI reference blocks match the real help byte for byte (doctor workspaces from lane-d,
upgrade from lane-e). The changelog fragment passes style and spelling with no warning. Most
runbook claims check out against the lane-d and lane-e code. One real inaccuracy blocks approval.

## Issue 1 (blocking): `--prune` removes nothing on macOS or Windows, and the runbook says it will

`process_probe.processes_with_cwd_under` returns `available=False` when there is no `/proc`
(any non-Linux platform). `landed_worktrees._after_probe` then gives every candidate
`unproven` / `PROCESS_PROOF_UNAVAILABLE`, so `--prune` removes nothing. `plan.md` line 16 names
this: "process proof unavailable there and on macOS: report-only". macOS is a target platform.

The runbook does not say so, and two statements are false there:

- "A merge that happens after the session ends": "the next `git fetch origin` and
  `spec-kitty doctor workspaces --prune` ... finds it landed and removes it." On macOS it is
  reported as unproven and kept.
- The "Known gaps" list omits the largest gap.

The changelog fragment also says `--prune` "removes only worktrees whose commits are on the
local `origin/<primary>`" with no platform caveat.

**Fix:** add a "Known gaps" bullet to `pr-landing.md` section 12, in plain words. For example:
"On macOS and Windows, running processes cannot be checked. Every worktree is then reported as
unproven, and `--prune` removes nothing. Remove it by hand with `git worktree remove` (no
`--force`) and `git branch -d`." Qualify the "merge after the session ends" paragraph to match
("On Linux, ..."). Add a short clause to the changelog fragment, such as "Linux only; on macOS
and Windows it reports and removes nothing."

## Issue 2 (blocking, same class, small): squash and rebase detection needs git 2.38 or newer

`is_absorbed` uses `git merge-tree --write-tree` for a non-ancestor tip. On git older than 2.38
it raises `AbsorptionUnsupported`, and the verdict is `unproven` (`ABSORPTION_UNSUPPORTED`).
The runbook says "Merge commits, rebase and squash merges all count" with no condition. The
changelog says "(squash and rebase merges count)". Add "with git 2.38 or newer" to both, or
add a Known-gaps bullet.

## Non-blocking notes (fix if cheap; not required for approval)

1. **Remote name.** The runbook fetches PRs and rebases against `upstream` (steps 2 and 3).
   Section 12 and the code read `origin/<primary>`. When `origin` is a fork, `git fetch origin`
   does not bring in the merge, and the worktree stays "not landed" (safe, but surprising). One
   sentence would help: "`origin` must be the canonical repository; the check does not read
   `upstream`."
2. **Restore section.** The kept ref is `refs/spec-kitty/discarded/<branch>@<short-sha>` when an
   earlier, different tip already holds `refs/spec-kitty/discarded/<branch>` (`discarded_ref`).
   "Use the ref printed on the `tip kept at` line" would cover that case.
3. **Upgrade help.** The `upgrade --help` exit-code and mutual-exclusion paragraph does not list
   the new exit-2 refusals (`--cli` or `--no-worktrees` with an opt-in flag, unknown
   `--include-worktree` path). That text lives in lane-e code, so it is a follow-up, not a
   WP06 defect. The doc copy faithfully reflects the current help.
4. **Closeout items (known, not WP06 defects).** The `docs-retrieval-index.yaml` slug still
   says `12-follow-up-hygiene`, and the doctor help freshness check needs the lane-d code to
   be consolidated.

## Verified accurate

- `cli-commands.md` doctor workspaces block equals `COLUMNS=80 spec-kitty doctor workspaces --help` (lane-d).
- `cli-commands.md` upgrade options box equals `COLUMNS=80 spec-kitty upgrade --help` (lane-e).
- Landed definition, "never removes" list (dirty or untracked, locked, content not on primary, own-uid process, Mission lane and coordination, main and current worktree), never `--force`, re-check before removal, `--fix` unchanged.
- Gaps: other-uid and unreadable processes (counted and printed), ignored files and in-progress rebase or merge deleted, detached tip not kept under a ref.
- Recreate commands (`git branch <b> <sha>`, `git worktree add --detach <path> <sha>`), the `refs/spec-kitty/discarded/` rule (only when commits exist on no other ref), and the output format all match `_render_outcome`.
- Upgrade: default selects none, `--include-worktree` (repeatable), `--all-worktrees`, Mission and detached skipped, escaping symlink never selectable, `--cli` / `--no-worktrees` with opt-in exit 2, preview and post-run lists.
- Only owned files changed. No `packs/`, `src/` or `tests/` edits. Fragment, not a `CHANGELOG.md` edit. Link `../development/how-to/pr-landing.md#12-...` resolves from `docs/changelog/`. TOC renumbered; no other inbound links to the old `#12-follow-up-hygiene` anchor except the retrieval index.

## Tests run

- `uv run --frozen pytest tests/architectural/test_docs_cli_reference_parity.py tests/docs/test_changelog_style.py tests/architectural/test_no_legacy_terminology.py -q`: 262 passed
- `uv run --frozen pytest tests/docs -q -k "spelling or link or changelog"`: 377 passed, 1 skipped
- `uv run --frozen python -m scripts.docs.check_changelog_style`: 0 errors, no warning for 7173
- `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`: 0 findings
