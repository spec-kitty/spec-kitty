# Quickstart: what changes for an operator

```bash
# A work package approved with nothing committed to its owned files is refused:
spec-kitty agent tasks move-task WP03 --to approved --agent claude --note lgtm
#  -> IMPLEMENTATION_MISSING: WP03 ... no implementation commit touching its owned_files ...

# The implementer approving its own work is refused (same tool:model:profile):
#  -> REVIEW_NOT_INDEPENDENT: WP03 ...

# accept and consolidate refuse the same way, whatever --force or --lenient was used.

# A docs-only work package that owes no deliverable:
spec-kitty accept --mission <slug> --attest-no-implementation WP04 --attest-reason "docs-only; nothing to ship"
spec-kitty consolidate --mission <slug>
#  -> "WP04: IMPLEMENTATION_MISSING lifted by operator attestation (...)"
```
