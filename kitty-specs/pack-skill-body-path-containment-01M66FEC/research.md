# Discovery research — pack-skill body_path containment (issue #6734)

## Decisions

1. **The issue is real and reproduces on `main` (512567ee).** Two read paths,
   two different behaviours:
   - `src/charter/offering/pack_skills/validation.py::_read_body` hand-rolls
     containment (`base.resolve()` + `body_file.is_relative_to(base)`), so the
     *validation* path does refuse absolute/symlink escapes today — but by a
     hand-rolled check that is also **looser** than the primitive: a
     string-level `..` that resolves back inside (`sub/../body.md`) passes.
   - `src/charter/offering/pack_skills/repository.py::body_text` reads
     `source.parent / skill.body_path` with **no containment**: repros on
     pristine `main` show `body_text` returning the content of a file outside
     the skill directory after the body symlink was repointed (load-time
     validation passed because the link still resolved inside at load), and
     likewise for an injected record with an absolute or `..` `body_path`.
     The escaped body reaches `skill_preparation.py`, which projects
     `SKILL.md` into users' agent folders.
2. **Mission boundary: one small software-dev mission.** Route both read paths
   through `charter.offering.drg.org_pack_config.resolve_relative_path_within_root`
   (the shared containment primitive introduced for #6418), anchored at the
   skill file's directory (today's anchor), raise `PackSkillViolation` on a
   read-time escape, add tests proving absolute/`..`/symlink escapes are
   refused identically on both paths, correct containment-authority claims.
   No overlaps with sibling #6418 follow-ups #6733/#6731 (org-fragment and
   pack-root plumbing surfaces, disjoint modules).
3. **Not superseded.** `git log -S resolve_relative_path_within_root --
   src/charter/offering/pack_skills/` is empty; `_read_body` is unchanged
   since its introduction (566a62a43f). PR #6756 (closed #6418) touched the
   org-DRG fragment / asset-sidecar surfaces, not `pack_skills/`. The
   `docs/changelog/CHANGELOG.md` `[Unreleased]` entry covers DRG fragment
   nodes and asset sidecars only. #6734 had no comments and no linked PR.
4. **The org-DRG `body_path` contract is a different rule and stays out of
   scope.** `find_body_path_escapes` (org_pack_loader.py, #6418) anchors
   authored DRG node `body_path`s at the *pack root*; pack-skill `body_path`
   is anchored at the *skill file's directory*. The mission keeps the
   skill-directory anchor (issue: "Keep today's skill-directory-relative
   semantics" = same anchor and trust stance; the primitive's stricter
   `..`-component rule replaces the hand-roll's looser edge).
5. **Read-time escape behaviour: fail-closed raise.** `body_text` raises
   `PackSkillViolation` naming the escape, consistent with load-time
   validation ("refused identically on both paths"). A contained-but-missing
   body keeps the separate "not found" load-time finding.

## Evidence

- Independent grounding review (reviewer-renata profile loaded), 2026-10-30:
  supersession verdict OPEN; both claims confirmed with reproduction
  (`body_text` served an outside file via symlink swap and via an injected
  `..` record; a fresh load after the swap skips the file, so the
  already-loaded catalog serves content a fresh load rejects).
- The primitive's contract (`resolve_relative_path_within_root`): refuses
  absolute (POSIX/Windows/UNC), string-level `..` components, and
  symlink-resolved escapes; `resolve_rejecting_loops` handles symlink loops.
- Existing pack-skill test surface: `tests/charter_offering/pack_skills/`
  (`test_validation.py` already covers a `..` escape on the validation path;
  `test_repository.py` covers tiers/conflicts/augmentations but no
  containment).
- Claim-correction sites found: `org_pack_config.py` ("a single canonical
  escape-detection implementation…"), `pack_validator.py:1441` ("rather than a
  **sixth** hand-rolled…"), `pack_layout.py:39-44` (accurate after the fix).
  The merged mission spec `kitty-specs/doctor-body-path-containment-01M5ZD3C/`
  is a historical immutable snapshot — not edited.
- `docs/development/how-to/create-a-pack-skill.md` documents the
  "must stay inside that directory" rule; optional one-line clarification
  that enforcement also holds at read time.

## Open questions (resolved during specify)

- What should `body_text` raise on an escape? → `PackSkillViolation` with a
  message naming the escape (see decision 5).
- Does routing through the primitive change accepted inputs? → Yes, at the
  edges: string-level `..` (`sub/../body.md`) and symlink-loop bodies that the
  hand-roll accepted become refused. Adopted deliberately (single authority);
  recorded in the spec's edge cases and the changelog.
