# Quickstart: see the new refusal

1. On a Mission with an approved work package, move that work package's task file out of `kitty-specs/<mission>/tasks/`.
2. Run `spec-kitty accept --mission <mission> --diagnose`.
3. Expect `OWNERSHIP_UNRESOLVED: WPnn ...` naming the `tasks/` directory, with a recovery line about restoring the task file. Expect no `IMPLEMENTATION_MISSING` for that work package.
4. Run `spec-kitty accept --mission <mission> --attest-no-implementation WPnn --attest-reason "x"`. Expect a refusal; nothing is recorded.
5. Put the task file back. The evidence check now passes, or reports `IMPLEMENTATION_MISSING` only if no owned file changed.
