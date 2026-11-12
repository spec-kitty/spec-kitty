# Approach

- **[2026-11-12][research] Read-only squad before specify.** Three parallel agents (code grounding, evidence mining, fold discovery) plus a fresh-context challenger. The challenger corrected three claims and found why most approvals carry `auto-approval:` (`auto_commit: false` + unreleased #3933).
- **[2026-11-12][plan] Close the class by deletion, not by a gate.** Remove the git-user and auto-approval fallbacks and route every identity field through one resolver; an end-to-end test with a distinctive git `user.name` pins the absence.
