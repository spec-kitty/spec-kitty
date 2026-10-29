---
affected_files: []
cycle_number: 1
mission_slug: owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5
reproduction_command:
reviewed_at: '2026-10-29T06:10:09Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback (reviewer-renata), cycle 1

Verdict: changes requested. There is one required change, and it is small. The code, tests and CHANGELOG are otherwise sound (see "Verified" below).

## Required changes

1. **ADR `docs/adr/4.x/2026-10-27-1-owned-refusals-use-the-c2-error-contract.md` now contradicts the shipped behaviour.**
   - Decision 7 (line 36) says: "Only the ownership resolution is routed through the renderer; their other errors keep the `{error, code}` payload on stderr."
   - Since `76620461`, `decision.py::_handle_action_context_error(exc, owned)` (`src/specify_cli/cli/commands/decision.py:248-265`) also routes the decision ledger's write-containment `OWNED_MISSION_PATH_REFUSED`, and any registered `OwnedRefusalCode` raised after resolution on an owned run, through `emit_owned_refusal` on stdout.
   - The CHANGELOG entry (`docs/changelog/CHANGELOG.md:35`) states the new behaviour and points readers at this ADR. As a result the ADR, which is the authority for the rule, says the opposite.
   - Fix: amend Decision 7 to say that an `agent decision` verb prints, as C2 on stdout, both its ownership-resolution refusal and a registered `OwnedRefusalCode` raised after resolution on an owned run (the ledger write-containment `OWNED_MISSION_PATH_REFUSED`). Every other code, and every error on a non-owned run, keeps `{error, code}` on stderr.
   - Also widen the Context definition (line 23: "the typed `ActionContextError` a command raises when its `--owned-checkout` claim, or a flagless adoption, is refused"). It should cover owned refusals raised after resolution on an owned run (write containment, staged index), which this Mission now renders as C2.
   - Add the decision ledger refusal to the Negative consequences list beside the spec-commit and finalize lines.
   - Follow the house style: either edit in place with the `updated:` date bumped, or add an `## Amendment 2026-10-29` section, as other 4.x ADRs do.
   - This edit is outside WP04's owned files (the ADR is WP02's), but it follows from the coordinator's scope widening. Record it with `add-history` as before.

## Non-blocking notes

- **Golden fixture.** A regeneration tool exists: `SPEC_KITTY_REGEN_GOLDEN=1 pytest tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py -n0`, documented in that module's docstring (lines 30-36) and implemented at lines 104-122. I ran it on a copy of the lane at HEAD. The regenerated `mission_create_cli.json` is byte-identical to the hand-edited commit (`git diff` is empty), so nothing needs to change. Next time, use the tool and say so in the history.
- **Residual arms (no change needed).**
  - In `spec_commit_cmd.py`, the generic `except ActionContextError` arm, after `_commit_spec_files`, cannot see a registered owned code on an owned run. The SPEC kind is primary, so `_owned_commit_target_for_kind` returns `owned.write_branch` without a coordination probe. The commit router wraps `write_dir` `ActionContextError`s into `_OwningSurfaceRefused`, which is not an `ActionContextError`.
  - In finalize, the commit-time `owned.files` calls (`mission_finalize_commit.py:404` and `mission_finalize_planning_pin.py:552`) come after the minter's `follow_links=True` screen of every top-level mission entry (`core/owned_mission.py:414`) and the `non_planning` guard.
  - I tested it. Real symlink escapes (`tasks`, `tasks.md`, `lanes.json`, `meta.json`, `spec.md`) are refused upfront as C2 `OWNED_MISSION_PATH_REFUSED` with `spec_kitty_version`.
  - The arm at `mission_finalize_commit.py:967` is therefore reachable only through a time-of-check-to-time-of-use race (a symlink planted mid-run). Forced with a monkeypatch, it prints `{stale_repository_root_copy, error, spec_kitty_version}` with no code. Optionally name it as a residual in the same ADR amendment.
