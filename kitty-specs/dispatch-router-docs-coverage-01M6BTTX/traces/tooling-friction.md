# Tooling friction

- **[2026-11-01][specify] `gh issue comment --body` mangles backticks.** A double-quoted
  shell body with unescaped backticks ran `spec-kitty dispatch` as a command substitution
  mid-comment. Fixed by writing the body to a file and PATCHing the comment; noted here
  because the same mistake would silently corrupt a claim comment.
- **[2026-11-01][discovery] `spec-kitty next` query mode reports `preview_step: discovery`
  with `action: null`.** The first `--result success` call is what returns the actionable
  step + `prompt_file`; query mode alone is not enough to know what to do next.
- **[2026-11-01][implement] The pre-review regression gate cannot finish inside its
  300 s budget on a loaded host.** `move-task WP01 --to for_review` ran the repo-declared
  `review.test_command` (`make test-fast`, the whole fast tier) at head and hit its
  300 s timeout, refusing the transition with `gate_timed_out`. The diff was not involved:
  the command is repo-wide and its scope is not derived from the changed files. The
  documented frontmatter escape hatch, `pre_review_test_scope`, is unusable here because
  `WPMetadata.model_validate(..., strict=False)` forbids the key
  (`extra="forbidden"`), so writing it makes the WP file unreadable to the subtask-roster
  resolver. Disposition: candidate tooling gap — the frontmatter override and the strict
  metadata model disagree.
