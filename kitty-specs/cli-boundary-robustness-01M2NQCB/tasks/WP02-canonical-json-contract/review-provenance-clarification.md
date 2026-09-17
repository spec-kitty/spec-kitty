# WP02 review provenance clarification

Audience: mission reviewers and maintainers auditing approval evidence.

Approval event `01M2P0BCKE0YCE4WCM9CFBFH17` incorrectly attributes the review to the configured Git user. **No human review or human approval took place at this step.** The immutable event has not been edited.

The actual independent reviewer was agent `/root/task_author`, with the loaded `reviewer-renata` profile, distinct from implementation agent `/root/validation_map`. It reviewed implementation HEAD `105ef7167`, ran 125 passing focused checks, and committed its review evidence in `9579f8749` (`review-evidence-1.md`). Canonical approval artifacts were committed in `e6e805152`.

The review claim supplied `codex:gpt-6:reviewer-renata:reviewer`. The generated completion command omitted `--agent`; following that command defaulted the verdict actor to the Git user and discarded the claimed model/profile. This is tracked in [#4670](https://github.com/spec-kitty/spec-kitty/issues/4670). Subsequent transitions must pass the complete agent identity explicitly.

This document clarifies the erroneous provenance field; it is not a second verdict and does not replace event-sourced status authority. The genuine independent review supports the WP approval. The final implementation PR still awaits the requested human review.
