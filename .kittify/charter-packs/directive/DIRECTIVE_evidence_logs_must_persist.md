## DIRECTIVE_evidence_logs_must_persist

Investigation-mode missions whose WPs produce evidence logs under
`kitty-specs/<mission>/research/*.log` MUST ensure those logs are
committed to the mission's PR branch. The project-level `.gitignore`
rule `*.log` silently excludes them under default `git add` semantics.

Two acceptable remediation paths (either satisfies the directive):

1. **Whitelist** in the top-level `.gitignore`:

   ```
   !kitty-specs/**/research/*.log
   ```

2. **Explicit `-f`** at commit time: the implementer must use
   `git add -f kitty-specs/<mission>/research/*.log` and verify via
   `git status` that all expected log files appear in the index before
   commit.

The mission-review post-merge audit MUST surface any evidence log that
is referenced by a `research/comment-*.md`, `research/outcome-*.md`, or
`acceptance-matrix.json` but is absent from the merge commit. This rule
exists to protect the NFR-003 reproducibility contract: a reviewer
following the comment alone must be able to compare the cited log
output against the on-disk artifact.

Reference cases:
- spec-kitty PR #1160 (caught during mission-review, fixed in-PR)
- Filed as spec-kitty#1161 (remediation tracking)
