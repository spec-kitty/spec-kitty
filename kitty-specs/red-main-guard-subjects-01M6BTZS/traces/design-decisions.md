# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · D-1: no guard is touched — neither the forbidden-pattern tuple nor the SafeCommitError descendant walk. D-2: the reworded docs sentence keeps `main` (as a branch) and drops the instruction form, which is what the charter's Branch-Intent Terminology Governance asks for; a synonym swap that still reads as an instruction would be a grep dodge. D-3: SAFE_COMMIT_DIRECTORY_ARGUMENT is documented as a pre-mutation refusal carrying offending_path, never as a SAFE_COMMIT_RECOVERY_FAILED refinement, because that family means the commit may have landed. D-4: docs-facing parity between the full contract and the prose enumerations is out of scope (22 registered codes are documented in prose form elsewhere) and is recorded for a follow-up.
