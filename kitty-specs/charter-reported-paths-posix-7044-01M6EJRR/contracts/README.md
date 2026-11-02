# Contracts

This mission introduces no contract and changes no existing one.

`charter generate --json` and `charter interview --json` keep their field names, field sets,
ordering guarantees, printable-JSON behaviour and exit codes (NFR-001); only the *spelling* of
two existing string values changes, from the host separator to POSIX. On a POSIX host the value
is byte-identical to what it was, so no consumer needs a compatibility gate.

The registry-level contract this change leans on is already defined elsewhere and is quoted
rather than restated here:

- `kernel.paths.to_posix()` — the single separator-normalisation seam (#2836).
- `kernel.charter_pack_paths.repo_relative_posix()` — the one helper that decides *what* a
  reported repository-relative path looks like (#6277, #7044).
