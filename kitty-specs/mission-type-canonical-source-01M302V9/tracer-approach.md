# Tracer: Approach

Seeded at planning; append during implementation.

## Strategy

Converge mission-type resolution onto the single canonical charter `ResolvedMissionType`
source; retire the org-blind `specify_cli/mission.py` resolver rather than band-aid it.
Strangler order:

1. **Tidy-first / campsite** the seam (behavior-preserving) before the functional change.
2. **Add the new home** — `path_conventions` doctrine slot + move `VALID_PATH_KEYS` into `charter`;
   author the ADR alongside.
3. **Rewire consumers** (acceptance path-conventions + optional-artifacts, worktree sparse-checkout,
   validators, dashboard) onto `ResolvedMissionType` / dossier `ManifestRegistry`.
4. **Route the loader** through the org-aware chain; preserve the typeless→software-dev *template* default.
5. **Migration + doctor audit** for consumer projects carrying legacy `mission.yaml` overrides.

## Red-first

Each of #3831 and #4088 lands an issue-pinned `@pytest.mark.regression` repro that is RED through the
pre-existing entry point before the fix, then relaxes to a focused unit/functional test after.

## Notes (append during implement)
-
