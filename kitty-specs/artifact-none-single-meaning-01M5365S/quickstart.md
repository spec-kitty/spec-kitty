# Quickstart: Verify the #5697 fix

How to confirm the mission's behaviour end to end. All commands run from the
repository root with the project venv (`.venv/bin/python`), never a bare
`uv run` that re-syncs the hand-built venv.

## 1. Classification — every mission file resolves (except the four excluded)

```bash
.venv/bin/python - <<'PY'
from mission_runtime import kind_for_mission_file as k, is_primary_artifact_kind as p
m = "m"
def show(rel):
    kind = k(f"kitty-specs/{m}/{rel}", mission_slug=m)
    primary = kind is not None and p(kind)
    print(f"{rel:28} -> {kind} (primary={primary})")
for rel in ["research/notes.md","research/code-grounding.md","research/evidence.py",
            "findings.md","report.md","methodology.md","synthesis.md","literature-review.md",
            "gap-analysis.md","audit-report.md","occurrence_map.yaml","goals.md","release.md","meta.json"]:
    show(rel)
print("--- excluded (must stay None) ---")
for rel in ["lint-report.json","docs/x.md","answers.yaml","mission-events.jsonl"]:
    show(rel)
PY
```

**Expected**: every file in the first block resolves to a non-`None` PRIMARY kind
(`research/*` → RESEARCH; `findings/report/methodology/synthesis/literature-review`
→ RESEARCH_OUTPUT; `gap-analysis`/`audit-report` → ANALYSIS_REPORT; `occurrence_map.yaml`
→ OCCURRENCE_MAP; `goals.md` → MISSION_GOALS; `release.md` → RELEASE_RECORD; `meta.json`
→ PRIMARY_METADATA). Every excluded path stays `None`.

## 2. One meaning for None — both consumers agree

```bash
.venv/bin/python -m pytest \
  tests/consolidation/test_projection_excludes_plan_outputs.py \
  tests/mission_runtime/ -q
```

**Expected**: green. The projection selects only coordination-kind paths; an
unclassified path is primary-bound in `_partition_paths_by_primary_kind` and is
not projected by `_post_checkpoint_mission_paths`.

## 3. Partition invariant holds with the new kinds

```bash
.venv/bin/python -c "from mission_runtime.artifacts import assert_partition_invariant; assert_partition_invariant(); print('P-1 OK')"
```

**Expected**: `P-1 OK` (total + disjoint over all members incl. the four new).

## 4. The #5697 refuse is gone (regression repro)

```bash
.venv/bin/python -m pytest -m regression tests/consolidation/test_projection_excludes_plan_outputs.py -q
```

**Expected**: the issue-pinned repro that is RED on `main` is GREEN after the fix —
a squash projection over byte-identical unclassified `research/**` content passes
instead of refusing.

## 5. No local None→coord re-derivation remains

```bash
.venv/bin/python -m pytest tests/architectural/ -k "coordination_kind or none_meaning or projection" -q
```

**Expected**: green — the architectural guard confirms the two former dissenters
consume `is_coordination_kind_file` and retain no local `None → coord` branch.
