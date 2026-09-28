# Quickstart: red-first reproductions

Run every recipe in a scratch repository with an isolated `HOME`/`XDG_*`. Use `spec-kitty` from this checkout's `.venv/bin`, with a fresh `pip install -e .` so the merge driver subprocess is current. Each recipe must fail on `main` @ `b7ada760` and pass after the fix.

1. **#4919:** `init` → `agent mission create` → `agent decision open` → `agent decision defer` → `agent decision resolve` → `rm kitty-specs/<m>/decisions/index.json` → `doctor decisions --mission <m> --repair`.
   - Today: `malformed_folds:[D]`, count 0, exit 0.
   - Expected: D rebuilt as resolved.
   - Second fixture: the issue's on-disk event pair written directly to `status.events.jsonl`.
   - Third fixture: two `DecisionPointOpened` events for one id. Expected: `clean:false` on diagnose, and exit 1 on repair with the decision kept.
2. **#4900:**
   - Create two missions, then `consolidate` both. Expected: `meta.json` on the target has 1 and 2.
   - Driver unit: `spec-kitty merge-driver-meta` with ours `null`, theirs `1` → `1`; ours `3`, theirs `1` → `3`.
3. **#4933:**
   - Commit `src/app/meta.json` and edit it without committing, then `consolidate`. Expected: exit 1 with `MERGE_UNSAFE_PRIMARY_DIRTY` naming the file, and the edit intact.
   - Repeat inside a lane worktree. Expected: `MERGE_UNSAFE_WORKTREE_DIRTY`.
   - Control: a dirty `kitty-specs/<m>/meta.json` and a dirty `sub/kitty-specs/<m>/meta.json` stay exempt.
4. **#4940:**
   - `agent config set lint_on_edit true`, then write `.claude/settings.json` with permissions, env `"OWNER":"José"`, a user `PreToolUse` hook and the `SessionStart`/`Stop` hooks, encoded as (a) UTF-8 BOM, (b) UTF-16 BOM and (c) cp1252. Run `agent config sync --sync-hooks`.
   - Expected: (a) and (b) are merged with every entry kept and the original bytes backed up; (c) is byte-identical, exit 1.
   - Repeat (c) with `live-work install claude`.
5. **#4998:**
   - Monkeypatch `SkillRegistry.from_package` to CRLF copies of the skill sources, and render CRLF command templates. Install into a scratch project. Expected: byte-identical to the LF install, and `doctor tool-surfaces --kind doctrine-skill --fix` / `doctor skills --fix` / verifier report 0 drifts.
   - Seed a doubled-frontmatter install whose manifest records the corrupted hash, then run `upgrade`. Expected: files restored, and the second run is a no-op.
6. **#4964:** for each registered migrate subcommand, run `migrate --dry-run <sub>` on a legacy fixture. Expected: the tree is unchanged, and `repin-hooks` → exit 2. Also `migrate --force <sub>` → exit 2.
