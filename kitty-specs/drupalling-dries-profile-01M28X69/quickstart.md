# Quickstart: Drupalling Dries Agent Profile

**Mission**: `drupalling-dries-profile-01M28X69`
**Branch**: `feat/drupalling-dries-profile`

For the implementer picking up a work package on this mission. Read `plan.md` for the why;
this is the operational path.

---

## 0. Environment first — this is not optional

This checkout has **no `.venv`**, and the repository's own code does not currently import without
one. Before anything else:

```bash
cd /Users/nicolas/Projects/spec-kitty
make dev-setup          # or: uv sync --frozen --all-extras
```

**Why it comes first.** A globally installed `spec-kitty` operates on the pack bundled inside its
own venv, not this repository's. Verified during Phase 0:

```
$ spec-kitty doctrine regenerate-graph --check
DRG graph is fresh:
/Users/nicolas/.local/pipx/venvs/spec-kitty-cli/lib/python3.14/site-packages/packs/built-in
```

That green says nothing about your changes. Every command below must run against repository source.

---

## 1. Establish the baseline before touching anything

```bash
uv run spec-kitty doctrine regenerate-graph --check   # expect: exit 0, repo path
uv run spec-kitty doctor doctrine --json | head -40   # expect: 0 skipped profiles
```

If either is already red on `main`, that is a **pre-existing condition to report**, not to absorb
into this mission's diff. Record it in the WP and continue.

---

## 2. Read the precedents before writing

Do not invent shapes. Three files define everything you need:

```bash
packs/built-in/agent_profiles/java-jenny.agent.yaml            # profile shape (185 lines)
packs/built-in/styleguides/python-conventions.styleguide.yaml  # patterns + anti-patterns (170)
packs/built-in/toolguides/maven-review-checks.toolguide.yaml   # descriptor shape
```

The distillation source is fetched fresh from
`https://raw.githubusercontent.com/amazeeio/drupal-agents-md/main/Vanilla/AGENTS.md` —
1,492 lines. Section map in `research.md`.

---

## 3. The one non-obvious step

Lineage is **not** in the YAML. Add to `_CURATED_ARTIFACT_EDGES` in
`src/charter/offering/drg/migration/extractor.py` (~line 267), beside the four existing specialists:

```python
(
    "agent_profile:drupalling-dries",
    _AGENT_PROFILE_IMPLEMENTER_IVAN,
    Relation.SPECIALIZES_FROM,
),
```

A `specializes-from` field in the profile YAML is **rejected by the model** — it will not work.

---

## 4. Regenerate; never hand-edit a graph fragment

```bash
uv run spec-kitty doctrine regenerate-graph        # writes the fragments
uv run spec-kitty doctrine regenerate-graph --check # proves them fresh
git diff --stat packs/built-in/*.graph.yaml        # expect: only your 4 nodes + their edges
```

`--check` regenerates into a temp directory and compares. A hand-edit is indistinguishable from
staleness — both go red.

---

## 5. Verify

```bash
make test-fast                                             # baseline
uv run pytest tests/doctrine/agent_profiles/ -q            # profile load/resolution
uv run pytest tests/doctrine/styleguides/ -q               # styleguide models
uv run pytest tests/doctrine/ tests/charter/ -q            # both — src/charter/offering/ was touched
uv run pytest tests/architectural/test_no_legacy_terminology.py -q   # ~0.1s, prose gate
uv run ruff check . && uv run ruff format --check .        # format is a SEPARATE gate from lint
```

`ruff check` passing says nothing about formatting — CI runs `ruff format --check` over the whole
repo and an unformatted file reds regardless.

**Before recording any failure as pre-existing**, classify it against the baseline-red categories in
CLAUDE.md — known-P0 reds, CI-environment failures, stale-install, stale-venv. A `ModuleNotFoundError`
for a pinned package means step 0 was skipped, not that something regressed.

---

## 6. Definition of done for the mission

- [ ] 8 files: 5 new pack artifacts, 2 edits, 1 regenerated fragment set
- [ ] `regenerate-graph --check` green against the **repository** pack
- [ ] `doctor doctrine --json` reports 0 skipped profiles
- [ ] All 14 source anti-patterns carried (SC-003)
- [ ] Boundary reciprocal in both profiles, with the verification/authorship distinction (R-006)
- [ ] Provenance credited in every delivered artifact (FR-010)
- [ ] Profile within 140-215 lines (NFR-001)
- [ ] No invented PHPStan level, coverage number, or threshold (NFR-006)
- [ ] Only `avoidance-boundary` changed in `frontend-freddy.agent.yaml` (NFR-007)
- [ ] Test commands and pass/fail counts recorded in the PR's *Tests run* section

---

## Traps, collected

| Trap | Symptom | Fix |
|------|---------|-----|
| Global CLI checks the wrong pack | `--check` green, pointing at a pipx path | Run via `uv run` from the repo |
| Hand-editing a `*.graph.yaml` | `--check` red, "stale" | Regenerate instead |
| `specializes-from` in profile YAML | Rejected at load | Use the extractor table |
| `ModuleNotFoundError: spec_kitty_events.diary` | Import fails | `uv sync --frozen --all-extras` |
| Lint green, CI red | Format gate | `uv run ruff format --check .` |
| Inventing a PHPStan level | Passes tests, violates NFR-006 | Use the project's configured level |
| Editing `.claude/` or another agent copy | Change vanishes on upgrade | Edit `packs/built-in/` only (C-001) |
