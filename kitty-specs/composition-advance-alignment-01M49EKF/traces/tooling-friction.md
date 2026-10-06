# Tooling-friction tracer

- `spec-kitty spec-commit` refuses a directory argument (`decisions/`). The individual files have to be passed instead.
- The first pytest run in a fresh container spends about 22 s in a session fixture that pip-installs the package into a scratch venv.
- Commits made by the spec-kitty CLI itself (`safe-commit`, `spec-commit`, `move-task`, `implement`) are unsigned under `commit.gpgsign=true`, so the branch had to be re-signed with `git rebase --exec "git commit --amend --no-edit --reset-author -S"`.
- That re-sign rewrote the recorded planning commit, and `implement WP02` refused with an orphaned planning commit until `finalize-tasks --refresh-planning-commit --allow-orphaned` ran.
- A container restart lost the in-flight WP02 reviewer. Its verdict had already been recorded through `move-task`, so the event log survived as the source of truth.
