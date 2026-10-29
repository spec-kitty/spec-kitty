# Quickstart: verify the mission by hand

```bash
spec-kitty init --ai claude --non-interactive . && spec-kitty charter interview --defaults && spec-kitty charter generate --from-interview

# #6557
printf 'this: is not: a valid charter\n\t- broken\n:::\n' > .kittify/charter/charter.yaml
spec-kitty charter status          # Error (ACTIVE_CHARTER_CONFIG_INVALID): ... Remediation: ...  (exit 1)
spec-kitty charter status --json   # {"ok": false, "error": {"code": "ACTIVE_CHARTER_CONFIG_INVALID", ...}}
printf -- '- a\n- b\n' > .kittify/charter/charter.yaml
spec-kitty charter status          # same code, no "Bundle schema version" text
git checkout .kittify/charter/charter.yaml   # or regenerate

# #6525 (local)
spec-kitty charter activate directive <id> --cascade all --json | python -m json.tool
spec-kitty charter deactivate directive <id> --json | python -m json.tool
spec-kitty charter activate nonsense x --json     # ACTIVATION_KIND_UNKNOWN, exit 1

# #6526 (local)
spec-kitty charter status --json | python -c "import json,sys; print(json.load(sys.stdin)['activation'])"
```
