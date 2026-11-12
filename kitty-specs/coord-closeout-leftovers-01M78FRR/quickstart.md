# Quickstart: verifying the closeout fixes

1. #7491: `research/repro_7491.py.txt` scenario → `consolidate` exits 76 → commit the listed review cycle on the coordination branch → `consolidate --resume` exits 0.
2. #4041: land and archive a coordination Mission (`spec-kitty archive create <m> --by <you> --reason done`), then `spec-kitty archive reclaim <m>`; `git worktree list` no longer shows `<slug>-coord`.
3. #5867: provoke the squash projection refusal; the output names the paths and `SQUASH_PROJECTION_NOT_LANDED`.
4. #7599: `spec-kitty accept --mode local` on a coordination Mission prints a consolidate step.
5. #7600: dirty a checkout during `consolidate --abort`; the remedy says re-run `--abort`.
