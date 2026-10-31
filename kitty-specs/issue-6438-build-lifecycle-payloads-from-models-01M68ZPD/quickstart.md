# Quickstart — verify the model-built lifecycle payloads

Everything here runs from the repository root checkout of the branch under test.

## 1. Confirm the pre-change behaviour (red) and the post-change behaviour (green)

```bash
# On origin/main (pre-change): an empty reason is written.
uv run pytest tests/specify_cli/status/test_model_built_payloads_6438.py -q
# On this branch: green.
```

## 2. Read the three emitters

```bash
sed -n '860,1040p' src/specify_cli/status/lifecycle_events.py
```

Each of `emit_reviewer_self_approval`, `emit_mission_reopened` and
`emit_follow_up_recorded` now constructs its payload model and persists
`model_dump(mode="json", exclude_none=False)`; the guards and the
`append_lifecycle_event` call are unchanged.

## 3. Prove it by hand

```bash
uv run python - <<'PY'
import json, pathlib, tempfile
from specify_cli.status import lifecycle_events as le

feat = pathlib.Path(tempfile.mkdtemp()) / "001-demo"
feat.mkdir()
(feat / "meta.json").write_text(json.dumps({
    "created_at": "2026-04-01T10:00:00+00:00",
    "merged_at": "2026-04-02T10:00:00+00:00",
    "mission_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
    "mission_number": 1,
    "mission_slug": feat.name,
    "target_branch": "main",
}))

# Rejected: the model requires a non-empty reason. Nothing is appended.
try:
    le.emit_mission_reopened(feat, mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
                             mission_slug=feat.name, reason="", reopened_by="me")
except Exception as exc:
    print("refused:", type(exc).__name__)

# Accepted: the payload is the model dump.
ev = le.emit_mission_reopened(feat, mission_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
                              mission_slug=feat.name, reason="regression", reopened_by="me")
from spec_kitty_events.lifecycle import MissionReopenedPayload
print(ev["payload"] == MissionReopenedPayload(**{k: v for k, v in ev["payload"].items()}).model_dump(mode="json", exclude_none=False))
PY
```

## 4. Run the blast radius

```bash
uv run pytest tests/specify_cli/status/ -q -m "fast or unit"
uv run pytest tests/architectural/test_events_tracker_public_imports.py -q
uv run ruff check src/specify_cli/status/lifecycle_events.py tests/specify_cli/status/test_model_built_payloads_6438.py
uv run mypy src/specify_cli/status/lifecycle_events.py
```

## 5. What a reviewer should refuse

- Any change to `_build_envelope`, `append_lifecycle_event`,
  `persist_lifecycle_event_local`, the event-type constants or the dedup keys.
- Any emitter that still assigns its payload from a dict literal.
- A "fix" that wraps or swallows `ValidationError`, which would restore the
  silent-write behaviour under a different name.
