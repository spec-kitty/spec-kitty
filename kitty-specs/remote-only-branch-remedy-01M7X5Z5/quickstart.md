# Quickstart: verifying the remote-only remedy

1. Clone a repository whose coordination Mission's coordination branch you have no local head for.
2. `spec-kitty agent tasks status --mission <m> --json` → exits 1, code `STATUS_SURFACE_REF_REMOTE_ONLY`, message lists:
   - `git -C <root> fetch <remote> <b>` (only when `refs/remotes/<remote>/<b>` is absent),
   - `git -C <root> branch <b> <remote>/<b>`,
   - `spec-kitty doctor coordination --mission <m> --fix`.
3. Run the `git branch` step; re-run the status board → it succeeds.
4. `spec-kitty doctor coordination --mission <m>` prints the same steps.
