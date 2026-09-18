# Quickstart: Verifying Consistent Mission-Handle Resolution

Manual verification recipe. Automated equivalents live in the mission's test
battery (see `plan.md` → Project Structure → `tests/`).

## Setup

```bash
# In an isolated sandbox project (never $HOME):
git init -b main && spec-kitty init --ai claude
spec-kitty specify a-b-c        # creates a real mission
spec-kitty specify etc-passwd   # creates a second real mission
ls kitty-specs/                 # note the two real mission dirs
```

## Verify C1 — nonexistent handle, no phantom write

```bash
BEFORE=$(ls kitty-specs/ | sort)

spec-kitty research --mission zznope   # expect: "mission not found: zznope", non-zero
spec-kitty plan     --mission zznope   # expect: "mission not found: zznope" (NOT "disambiguate")
spec-kitty tasks    --mission zznope   # expect: "mission not found: zznope" (NOT "disambiguate")
spec-kitty merge    --mission zznope   # expect: "mission not found: zznope" (NOT "lanes.json required")

AFTER=$(ls kitty-specs/ | sort)
[ "$BEFORE" = "$AFTER" ] && echo "OK: specs tree unchanged (no kitty-specs/zznope)" || echo "FAIL: phantom write"
```

## Verify C4 — merge --abort stays tolerant

```bash
spec-kitty merge --abort --mission zznope   # expect: tolerant cleanup, NOT a hard "mission not found"
```

## Verify C5 — bare `next` discovery

```bash
# >1 mission present:
spec-kitty next          # expect: a list "a-b-c-<mid8> (<mid8>) — <friendly name>" etc., "re-run with --mission", non-zero, NOT "Invalid value"

# Reduce to exactly one mission, then:
spec-kitty next          # expect: auto-selects the sole mission and proceeds

# Zero missions (fresh project):
spec-kitty next          # expect: "no missions found" + points to specify, non-zero
```

## Verify C2/C3 — unchanged distinct errors

```bash
spec-kitty research --mission ../x   # expect: path-safety refusal (distinct from not-found)
```

## JSON parity spot-check

```bash
spec-kitty plan --mission zznope --json | jq '.'   # structured error, handle: "zznope"
spec-kitty next --json | jq '.available_missions'  # present when >1 mission
```
