# Research memo — upgrade and Windows drift

Brief for plan and tasks. Grounding at `fb7c92d6f0` (`skupstream/main`). Lenses: prior art, seam census, CRLF predicate. No product code was changed in this pass.

## Decisions taken without the operator

- No new public command flag. Genuine edits keep the existing "do not overwrite user edits unless the operator asks to repair" guarantee. Consent is the repair request that already overwrites agent profiles in the same state. The internal overwrite switch that comments call `--repair-drift=overwrite` stays unexposed.
- #5574 and #5575 do not require the broader Codex skill-drift programme or the still-open doctrine-skill drift issue.
- A stored-copy versus working-copy line-ending difference is not a content change. A real text change stays uncommitted even when line endings also differ. Comparison uses the same clean-filter Git would use on add. Proceed.

## WP cut

| WP | Owns | Depends |
|----|------|---------|
| WP01 | False drift: bytes that match the current canonical rendering are fresh, and the recorded install hash is refreshed. Unattended upgrade of that case succeeds. | none |
| WP02 | Consent: a genuine edit is preserved unless the operator asks to repair. Repair of command skills then overwrites, matching agent profiles. Unattended upgrade still reports and does not write. | WP01 for the false-positive volume; real-edit consent is independent |
| WP03 | Planning artifacts Git considers clean do not block implement when auto-commit is off, and do not produce an empty commit. A real text change is still staged. | none |

## Contract versus code

Drift policy (proposed, `kitty-specs/agent-profile-projection-plugin-production-01KV3NGS/contracts/drift-policy.md`): drifted means the on-disk hash matches neither the recorded install hash nor the current canonical rendering. Present means it matches the current rendering.

| Surface | What the code does today | Anchor |
|---------|--------------------------|--------|
| Command-skill verify | Drift is on-disk hash versus manifest hash only | `src/specify_cli/skills/command_installer.py` `verify` ~1098, `preserve` ~715 |
| Manifest repair | Fingerprint versus `content_hash`; no canonical check | `src/specify_cli/skills/manifest_store.py` `repair_stale_manifest` ~446 |
| Command-skill probe | Drift when on-disk hash ≠ recorded hash; finding has no repair command | `src/specify_cli/tool_surface/providers/command_skills.py` `probe` ~216 |
| Doctrine skill assessment | Disk matching expected catalog bytes skips consent | `src/specify_cli/skills/installer.py` `_prepare_project_skills` ~757, `_preserve_project_path` ~839 |
| Upgrade | Always passes `repair_drift=False`; non-interactive drift exits 1 and points at `doctor tool-surfaces` | `src/specify_cli/cli/commands/upgrade.py` ~449 and ~508 |
| Doctor tool-surfaces | `--fix` repairs via `SurfaceRepairService`; `ok` ignores warnings | `doctor.py` `tool_surfaces` ~298; `repair.py` `SurfaceRepairService.repair` ~144 |
| Command-skill repair | Automatic consent only; `consent_required` fails the write | `command_skills.py` `repair` ~364 |
| Agent-profile repair | Sets overwrite paths for drifted files, then applies | `agent_profiles.py` ~444 |
| Doctor skills `--fix` | Any drift refuses the whole repair | `_command_surface_doctor.py` `_repair_refusal` ~304 |
| Planning filter | Raw blob bytes versus working-tree bytes | `implement_cores.py` `_files_changed_vs_ref` ~471, compare ~493 |
| Implement refusal | `--no-auto-commit` exits 1 when planning artifacts look uncommitted | `implement.py` ~432, entered from ~887 |

`show_blob` (`implement_cores.py` ~98) is `git show <ref>:<path>` with no line-ending conversion. The predicate is byte-identical on rc5 and this main (hash `bdb321bc3c17…` from the function through `return changed`).

## Red-first shape

- WP01: a command skill whose bytes equal the current render and whose manifest hash is older is not drift, and unattended project upgrade exits 0. Extend the existing render tests (`tests/specify_cli/skills/test_crlf_skill_render_4998.py`, the expected-hash gap noted around the #5281 marker).
- WP02: a genuine edit is unchanged and reported when upgrade is unattended; the same edit is overwritten when the operator runs the repair that already overwrites agent profiles. Doctor guidance names a repair the operator can run.
- WP03: home is `tests/specify_cli/cli/commands/test_implement_coord_idempotency.py` (real git repo). Seed `.gitattributes` `* text=auto eol=crlf`, check the files out so Git's status is empty, then `resolve_planning_artifact_staging(..., auto_commit=False)` yields an empty `files_to_commit`. A second test writes one revised token in CRLF and expects only that path staged. Re-pin `tests/architectural/test_trio_seam_only.py` if the working-tree read token inside `_files_changed_vs_ref` changes. Add the port method; do not change `show_blob`.

## Out of scope

- #2527 (open): doctrine skills stay drifted from the manifest hash, and stray plugin dist files. Adjacent to the doctor story, not the command-skill canonical-render gap.
- #702 and the Codex skill-drift programme.
- #4998 (closed): line endings at skill install time. Distinct.
- spec-kitty-qa #760 and docs PR #765: register rows for the planning-artifact false positive. Not a product change.
- Exposing a new overwrite flag on upgrade.
