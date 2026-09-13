# Quickstart: Operator Config & Install Ergonomics

## For the operator (target experience)

```bash
# One-time: put all your knobs in one gitignored file (located via SPEC_KITTY_HOME).
# ~/.spec-kitty/.kitty.env  (machine-wide) — or <repo>/.kittify/.kitty.env (per-repo override)
cat > ~/.spec-kitty/.kitty.env <<'EOF'
SPEC_KITTY_ENABLE_SAAS_SYNC=1
SPEC_KITTY_SAAS_URL=https://team.spec-kitty.ai
SPEC_KITTY_SAAS_TOKEN=...        # secret — file is gitignored + claudeignored
SPEC_KITTY_PRERELEASE=1          # opt into rc catfooding (default off)
EOF

# No more per-shell exports. The CLI seeds these before anything reads them.
spec-kitty sync opt-in
spec-kitty sync now
spec-kitty upgrade --agent-check     # now offers the latest rc (pinned) because PRERELEASE is on

# config.yaml carries just the pointer (committed, no secrets):
#   env_file: ${SPEC_KITTY_HOME}/.kitty.env

# Health:
spec-kitty doctor            # reports env-file health (names only), rc channel, and 0 absolute pack paths
```

## Verifying the mission (acceptance walkthrough)

1. **Portable provenance** (US1): compile the charter on an editable checkout and on a wheel install → `charter.yaml` byte-identical, only `${SPEC_KITTY_PACKS_ROOT}/built-in/...` tokens; export `SPEC_KITTY_PACKS_ROOT=/tmp/x` and re-compile → still byte-identical.
2. **One-file opt-in** (US2): unset all sync vars in the shell, put them in `.kitty.env`, run `sync doctor` → vars seen (by name); `sync now` reaches drain without a config error.
3. **Precedence** (US2.3): same var in real-env/per-repo/home → real-env wins, per-repo beats home.
4. **rc channel** (US3): `SPEC_KITTY_PRERELEASE` unset → no rc advisory; set → newest rc offered as `spec-kitty-cli==<rc>`.
5. **Self-heal** (US4): a project with absolute provenance + no `.kitty.env` → `spec-kitty upgrade` heals paths, creates `.kitty.env`, adds pointer + ignore lines; re-run = no changes.
6. **Secrets** (US2.6): `doctor`/`sync status` never print `SPEC_KITTY_SAAS_TOKEN`'s value; `.kitty.env` is gitignored + claudeignored.
7. **Docs** (US5): a Team Kitty (SaaS) architecture section with the opt-in→sync interaction diagram exists; two ADRs under `docs/adr/3.x/`.
