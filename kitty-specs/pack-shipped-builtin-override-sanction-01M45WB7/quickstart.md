# Quickstart: verify the pack-shipped sanction

```bash
# 1. In an org pack, move the legacy template to the pack root
git mv templates/setup/replaceable-builtins.yaml replaceable-builtins.yaml
spec-kitty doctrine pack validate .        # FR-014: errors on bad entries

# 2. In a consumer with that pack configured (no consumer allowlist edits)
spec-kitty doctrine fetch                  # git/https packs keep the pack-root file
spec-kitty doctor doctrine                 # RC=0; "Sanctioned built-in override(s)" lists pack sources
spec-kitty doctor doctrine --json | jq '.profile_health.org_drg.sanctioned_overrides'

# 3. Withdraw a pack's sanction (consumer side)
cat >> .kittify/doctrine/replaceable-builtins.yaml <<'YAML'
revoked_pack_sanctions:
  - urn: directive:MINUTES_STAND_ALONE
YAML
spec-kitty doctor doctrine                 # RC=1; finding names the revocation
```
