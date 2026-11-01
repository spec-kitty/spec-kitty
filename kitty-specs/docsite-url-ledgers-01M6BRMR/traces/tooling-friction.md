# Tooling friction

- **[2026-11-01][grounding] No DocFX in the cloud container.** `dotnet-sdk-8.0` came from the Ubuntu archive and `docfx` from NuGet. `www.plantuml.com` is unreachable, so the local site walk rewrote the five `plantuml` fences to `text` in a throwaway worktree (diagram render only, not page set). Workaround.
- **[2026-11-01][grounding] Shallow clone hides #3914's base commit.** `rename_reconcile.py --base a60425c…` fails on a 50-commit clone; the forward gate needs no git, so it was run directly. Workaround.
- **[2026-11-01][specify] `charter context` reported `packs/internal` missing.** `make sync-packs` had not run in this checkout (the setup script does not run it). Fixed by running it; candidate gap: `scripts/dev/cloud-session-setup.sh` could sync packs.
- **[2026-11-01][specify] `mission create` scaffold commit carries no co-author trailer.** The CLI's own commit cannot take the operator-required trailer. Candidate gap.
- **[2026-11-01][implement] `tests/docs` collection costs ~55 s of session setup in this container.** Any single docs test file pays it; the ledger tests themselves run under 1 s. Not investigated (not this Mission's surface).
