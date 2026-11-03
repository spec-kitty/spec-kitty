# Research: Report-only pinned pack inputs (#7128)

Discovery findings gathered before `plan`. Everything here is measurement on
`origin/main` @ `f1e860a17f` in this clone (`spec-kitty-cli 4.0.0rc8`).

## D1 — The defect reproduces, and the refusal comes from one rule

`record_report_transaction` (`src/specify_cli/git/report_transaction.py:305-321`) computes four
sources of "dirty material input". Measured on this clone, with `make sync-packs` done and a clean
worktree:

| Probe | Result |
| --- | --- |
| `_dirty_paths(repo)` (index/worktree dirt) | `set()` — ignored files are not status entries |
| `collect_material_inputs(mission, repo)` keys | 708 total, **110** pack-relative |
| `material_paths ∩ dirty` | empty |
| untracked-but-present material paths (`... is_file() and path not in tracked_paths`) | **67**, all `packs/internal/*` |

So the refusal is produced by line 317 alone: "a material input exists on disk but has no committed
state". 67 matches the issue's "66 paths, all under `packs/internal/`" (this clone's pin carries one
extra file); the issue's count is not a discrepancy to chase.

**Decision:** the reported `DIRTY_ANALYSIS_INPUT` is caused by that rule, not by index dirt, not by
the charter-dirt rule, and not by an unsafe git state.

## D2 — The rule is load-bearing and must survive

`tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py::test_unsafe_state_refuses_without_report_write[ignored_input]`
adds an ignored file under `.kittify/templates/` via `.git/info/exclude` and asserts the transaction
refuses. That is the same rule firing on an operator-authored, gitignored input — exactly the case
that must keep refusing.

**Decision:** rejecting the "exclude ignored paths from the dirty set" arm of the issue's
"Expected" section. It would open a hole: any gitignored material input would become recordable,
so a report could be qualified over authority that has no committed state at all. The issue's
second arm — "treat a fetched-and-pin-verified pack tree as clean by construction" — is the one to
take.

## D3 — A pin-verified tree genuinely has committed state

Evidence, from the pack machinery already in the tree:

- `packs/internal.source.yaml` and `packs/built-in.source.yaml` are **tracked**
  (`git ls-files packs` lists them; only the fetched trees are ignored, `.gitignore:251-252`).
- `charter.offering.packs.pack_pin.PackPin` records `repository`, `commit` (40-hex, tag never
  persisted), `subtree`, `tree_digest{algorithm,value,level}` and `snapshot_sha256`.
- `verify_pack_pin(pin, pack_root)` returns `True` only when **both** the level-aware clean-tree
  digest and the raw full-tree digest equal the pin's, and refuses when the algorithm is unknown or
  `snapshot_sha256` is absent (`pack_pin.py:168-176`).
- `scripts/sync_packs.py --check` uses the same pair (`check_pack`) and reports `internal: ok` here.

Measured cost of `verify_pack_pin(PackPin(packs/internal.source.yaml), packs/internal)` on this
clone: **0.008 s**, 67 files, no network, no git subprocess.

**Decision:** the exemption is `verify_pack_pin(pin, root)` on the pin read from the *committed*
authority, plus `pin.subtree == <root relative to repo>`, so a tree can only be exempted by the pin
that names it.

## D4 — Where the exemption must be computed, and from which copy of the pin

`packs/built-in/` never reaches the rule: `_package_inputs()` digests the built-in tree as a single
`package:built-in` entry with `path: null`, so no per-file path enters `material_paths`. Only the
registry-declared org pack (`charter_packs.org.packs[0].local_path: packs/internal`,
`.kittify/config.yaml`) contributes paths. The fix therefore has to generalise over
`load_pack_registry(root).packs` → `effective_root(root)`, not hard-code `packs/internal`.

Reading the pin: `load_pack_pin` takes a `Path` and parses it. Reading it from `HEAD` would need a
second parser (rejected by C-002). The equivalent, and stricter in one direction, is: exempt only
when the pin file is **tracked and unmodified** (present in `tracked_paths`, absent from
`_dirty_paths`), so the on-disk pin *is* the committed pin, then `load_pack_pin` + `verify_pack_pin`
on it. A dirty or untracked pin file then grants nothing — FR-003.

**Decision:** no new pin parser, no `git show` plumbing; "committed pin" is proved by the file being
tracked and clean.

## D5 — Prior art and non-supersession

- `git log -S DIRTY_ANALYSIS_INPUT` → one commit, `45ee988d0f` (#4228), which introduced the rule
  with the sibling `ignored_input` case. Nothing since touched this seam.
- #5125 (relocate `report_transaction` out of `git/`) and #5380 (a different report-only refusal)
  are open and orthogonal.
- #7106 (analysis freshness) observed this defect and recorded without `--report-only` as a
  workaround; it did not fix it.
- No ADR governs the analysis-input closure; the relevant authority is the code comment at
  `src/specify_cli/analysis_inputs.py:1-5` ("Runtime/status/cache outputs are deliberately not
  inputs") plus the charter's Proof Trail and Quality Gates sections.

**Decision:** #7128 is live, unsuperseded, and in scope for this Mission.

## D6 — Test surface that already exists (red-first target)

`tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py` builds a real git fixture
and drives the real CLI (`CliRunner().invoke(app, ["record-analysis", ...])`), which is exactly the
production entry point the non-vacuity tactic requires. The new cases belong there: one fixture,
with the pack tree and its pin added, plus the existing refusal cases as controls.

## Open questions for plan

- Whether the `packs/<name>.source.yaml` sibling naming (`<pack root>.source.yaml`) is the right
  discovery convention, or whether the pin should be located through
  `kernel.pack_tiers.pin_filename` + the repo `packs/` directory. `scripts/sync_packs.py` uses
  `root / "packs" / pin_filename(name)` — the plan must pick one and justify it.
- Whether `packs/internal.source.yaml` should also become a material input (today it is not, so a
  pin bump alone does not invalidate a report; the tree content does). Out of scope if it changes
  the manifest shape.
