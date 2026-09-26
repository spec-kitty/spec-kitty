# Review Action — Governance Guidelines

These guidelines govern the quality and correctness standards for work package review in the software-dev mission. They are injected at runtime via the charter context bootstrap.

---

## Dependency Verification

- Before reviewing a WP, confirm each WP listed in its `dependencies` frontmatter field has been merged into the mission's target branch or otherwise incorporated into the current review base.
- Identify any WPs that list the current WP as a dependency and note their current lanes.
- If you request changes AND dependents exist, warn those agents to rebase and provide a concrete rebase command.
- Confirm that dependency declarations match actual code coupling (imports, shared modules, API contracts).

---

## Review Intent

- Assess intent and risk first before diving into line-level details.
- Verify that the implementation satisfies the acceptance criteria defined in the WP task file.
- Check that test coverage is adequate for the changes introduced.
- Verify that no deliverable files were written to the repository root checkout instead of the worktree.

---

## Outcome Actions

- Approve: move WP to `approved` with a summary note. Merge later records `done`.
- Reject: write structured feedback to the temp file path shown in the prompt, then move WP back to `planned`.
- Use the exact temp file path provided by the prompt to avoid conflicts with other review agents.
