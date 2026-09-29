# Review Workflow Checklist

Operational checklist for executing the Spec Kitty review workflow surface.

## 1. Claim and Context

- [ ] Loaded charter context: `spec-kitty charter context --action review --json`
- [ ] Claimed WP: `spec-kitty agent action review WP## --agent <name>`
- [ ] Noted the review prompt file path from command output

## 2. Read the Review Prompt

- [ ] Read the generated review prompt file
- [ ] Identified acceptance criteria listed in the prompt
- [ ] Identified the correct git diff commands (base branch from prompt, not hardcoded)

## 3. Inspect Changes

- [ ] Ran the git diff commands from the review prompt
- [ ] Compared each acceptance criterion against the diff
- [ ] Checked for unrelated changes outside the WP scope

## 4. Issue Verdict

- [ ] **If all acceptance criteria met**: `spec-kitty agent tasks move-task WP## --to approved --note "..."`
- [ ] **If criteria not met**: wrote feedback to temp file, ran `spec-kitty agent tasks move-task WP## --to planned --review-feedback-file <path> --agent <your reviewer id>` without forcing the move

## 5. Post-Review

- [ ] If rejected and WP has downstream dependents: checked `spec-kitty agent tasks status` and warned in feedback
- [ ] Confirmed WP lane updated correctly
