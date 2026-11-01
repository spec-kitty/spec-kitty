# Tooling friction

- **[2026-11-01][grounding] No DocFX in the cloud container.** `dotnet-sdk-8.0` came from the Ubuntu archive and `docfx` from NuGet. `www.plantuml.com` is unreachable, so the local site walk rewrote the five `plantuml` fences to `text` in a throwaway worktree (diagram render only, not page set). Workaround.
- **[2026-11-01][grounding] Shallow clone hides #3914's base commit.** `rename_reconcile.py --base a60425c…` fails on a 50-commit clone; the forward gate needs no git, so it was run directly. Workaround.
- **[2026-11-01][specify] `charter context` reported `packs/internal` missing.** `make sync-packs` had not run in this checkout (the setup script does not run it). Fixed by running it; candidate gap: `scripts/dev/cloud-session-setup.sh` could sync packs.
- **[2026-11-01][specify] `mission create` scaffold commit carries no co-author trailer.** The CLI's own commit cannot take the operator-required trailer. Candidate gap.
- **[2026-11-01][implement] `tests/docs` collection costs ~55 s of session setup in this container.** Any single docs test file pays it; the ledger tests themselves run under 1 s. Not investigated (not this Mission's surface).
- **[2026-11-01][implement] `rename_reconcile.py` needs ruamel, so it cannot run under bare system `python3`.** Pre-existing; run it with `.venv/bin/python`. `bulk_ref_rewrite.py --dry-run` over the whole repo exceeds 10 minutes with 298 substitutions; scope it with `--root`. Candidate gaps, not fixed here.
- **[2026-11-01][implement] `sed -i` on `CLAUDE.md` replaced the symlink to `AGENTS.md` with a regular file.** Caught by `git status` (`T`); restored. Edit `AGENTS.md` only.
