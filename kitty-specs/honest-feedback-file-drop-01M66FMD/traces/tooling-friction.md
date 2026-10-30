# Tooling friction — honest-feedback-file-drop-01M66FMD

- **[2026-10-30][specify] Mission scaffold refused to commit: target branch main is protected.** Expected guard; re-ran on the topic branch `issue-6699-honest-feedback-file-drop`. `finalize-tasks` likewise needed `--target-branch <topic>`; its default target resolution said "main" although planning artifacts were committed on the topic branch. Worked around with the documented flag.
- **[2026-10-30][analyze] `record-analysis` refused on dirty `kitty-ops/lifecycle.jsonl`.** The mission runtime appends ops lines between my commits; committing the ops file first unblocked it. Recurring bookkeeping-vs-dirty-tree friction.
