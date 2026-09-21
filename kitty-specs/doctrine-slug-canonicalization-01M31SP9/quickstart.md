# Quickstart: verifying the canonical slug fix end to end

The mission's acceptance gate is the field-report scenario reproduced with the **real** engine (not hand-written sidecars), covering both #4832 and #4833.

## Go-forward (Stories 1 & 2)
```bash
# In a fixture project repo (pytest tmp_path drives this in the suite):
spec-kitty charter new directive LOVE_THY_ENEMY          # → love-thy-enemy.directive.yaml, id: LOVE_THY_ENEMY inside
# author a project agent profile under .kittify/doctrine/agent_profiles/<id>.agent.yaml
spec-kitty charter activate directive LOVE_THY_ENEMY
spec-kitty charter activate agent-profile <profile-id>
spec-kitty charter bundle validate                       # EXPECT: 0 errors (no "unknown kind", no sidecar mismatch)
```
Expected: exit 0. Before the fix: 2 errors for the directive (#4832) + 1 "unknown kind 'agent_profile'" (#4833).

## Existing SCREAMING-filename repo (Story 3 — no migration)
```bash
# Repo already has LOVE_THY_ENEMY.directive.yaml (SCREAMING), registered by the real engine
# (manifest slug = love-thy-enemy). NO rename is performed.
spec-kitty charter bundle validate                       # EXPECT: 0 errors — validator trusts the manifest slug
ls kitty-specs/.../LOVE_THY_ENEMY.directive.yaml          # EXPECT: file UNCHANGED (still SCREAMING)
```

## Corruption honesty (NFR-001 guard — both directions)
```bash
# (a) orphan sidecar, no backing artifact:
#   .kittify/charter/provenance/agent_profile-ghost.yaml   (no ghost.agent.yaml)
spec-kitty charter bundle validate                       # EXPECT: still errors "references non-existent artifact"
# (b) orphan artifact, absent from manifest, no sidecar:
#   .kittify/doctrine/directive/orphan.directive.yaml      (not registered)
spec-kitty charter bundle validate                       # EXPECT: still errors "has no provenance sidecar"
```

## Test entry points
- `tests/charter/synthesizer/test_bundle_validate_extension.py` — 5-kind coverage, manifest-driven resolution, orphan-still-caught.
- `tests/charter/...` — `slug_for` unit + convergence, `_registration_records` path-update, migration idempotency/no-clobber, kind-set parity guard.
- `tests/specify_cli/cli/commands/test_doctrine_new.py` — scaffolder emits kebab filename with authored id preserved.
- Baseline: `make test-fast` plus the two owning subsystem dirs `tests/charter/` and `tests/doctrine/`.
