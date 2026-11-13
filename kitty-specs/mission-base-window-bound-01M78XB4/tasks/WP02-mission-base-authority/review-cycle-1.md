---
affected_files: []
cycle_number: 1
mission_slug: mission-base-window-bound-01M78XB4
reproduction_command:
reviewed_at: '2026-11-12T22:57:52Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review (reviewer-renata) -- changes requested

Passing: 125 tests (WP tests + tests/core/test_mission_creation_family.py), create-path blast radius 19/19, layer/cold-import gates 83/83, ruff/format/mypy/C901 clean. Recording is write-once and failure-tolerant and the tests drive the real `agent mission create`. Two problems need fixing.

**Issue 1 (blocking, soundness): the derived base can sit ABOVE Mission work when the Mission directory was renamed.**
`_earliest_scaffold_commit` limits `git log` to `kitty-specs/<slug>/`, so a commit that renames the Mission directory into `<slug>/` shows as `A` (the rename source is outside the pathspec, so git cannot pair the rename). Reproduction (git 2.43):
```
base -> scaffold (kitty-specs/old/spec.md) -> work (app.py) -> rename (git mv kitty-specs/old kitty-specs/new) -> plan
git log --first-parent --diff-merges=first-parent --reverse --diff-filter=A --format=%H mb -- kitty-specs/new/
  => first line = the rename commit
```
The derived base is then `rename^1` = `work`, which is above the scaffold commit and the Mission's own `work` commit. WP03 would exempt both as pre-Mission history. The WP's rule is "never a guessed sha; failures are UNAVAILABLE".
Fix: fail closed on a rename into the Mission directory. For example, read the earliest first-parent commit touching the directory with rename detection over the parent dir (`git log --first-parent --diff-merges=first-parent --no-patch --reverse -M --name-status --format=%H <branch> -- kitty-specs/`). If its entry for `<slug>/` is an `R` from another path, return UNAVAILABLE with a reason, or follow the rename to the source directory's earliest add. Add a test with this exact shape, and keep the NFR-002 budget statement accurate (it covers only the recorded case).

**Issue 2 (should fix, layering): `specify_cli.core` now imports `specify_cli.consolidation`.**
Before this WP, no module under `src/specify_cli/core/` imported `specify_cli.consolidation`. `consolidation` imports `core` (`core.git_ops`, `core.constants`), so this WP adds a core<->consolidation package cycle. It also means `mission_creation_meta` and `mission_creation_protected_mint` now run `consolidation/__init__.py` on every create, which eagerly imports baseline, conflict_resolver, mission_number.bake, state and workspace. No architectural gate pins this today, which is why it passes, but it points the wrong way.
`record_mission_base_sha` is a pure meta.json write helper, so it belongs with the meta key. Move it into `src/specify_cli/mission_metadata.py` or `src/specify_cli/meta_keys.py` (both owned by this WP). The two core call sites then import it from there. `consolidation/mission_base.py` keeps only the read/derive authority (it may re-export nothing). Update `tests/specify_cli/core/test_mission_base_recording.py` to import the helper from its new home. Re-run `tests/core/test_mission_creation_family.py`.

**Issue 3 (minor): `--diff-merges=first-parent` makes git emit full patches.**
On git 2.43 the log output carries a patch for every commit that adds files under the Mission directory. `_earliest_scaffold_commit` still returns the right sha only because the first output line happens to be the first `%H`. Add `--no-patch` (I verified it selects the same commits), so the parse is not coupled to patch layout and the output stays small.

**Non-blocking note:** a recorded `mission_base_sha` is trusted after the ancestry check alone, so a hand-edited value above Mission work would be accepted. That matches the WP contract and DM 01M78XBQS8NE8PPMSTZHMDJ610. If cheap, consider stating in the module docstring that the recorded value is trusted as tool-written and write-once.

Anti-pattern checklist: dead code N/A (the WP says WP03 is the caller; the recording helper is live), synthetic fixture PASS, silent empty return PASS (`()` and `None` are documented), FR coverage PASS, frozen surface PASS, locked decision PASS, shared-file ownership PASS, production fragility PASS (GitProbeError propagation from `pre_mission_history` is documented).
