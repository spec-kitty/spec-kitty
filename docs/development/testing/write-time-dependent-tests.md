---
title: Write Time-Dependent Tests
description: Inject stable clocks in tests and avoid wall-clock reads inside assertions.
doc_status: active
updated: '2026-06-15'
audience:
- profile: internal/lead-developer
  guidance_text: Written for the Lead Developer reader.
type: how-to
---
# Write Time-Dependent Tests

Time-dependent behavior must be tested with a stable reference time wherever the production API can accept one.

Prefer this pattern:

```python
from datetime import UTC, datetime


def test_lifecycle_state_is_active(tmp_path):
    now = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result = derive_mission_lifecycle(feature_dir, now=now)

    assert result.state == "active"
```

For new code, expose a `now=` keyword argument or a small clock dependency at the boundary that owns the timestamp. Tests should pass a fixed `datetime` or date through that boundary and assert against the fixed value.

Do not read the wall clock inside an `assert` expression:

```python
assert payload["created_at"][:10] == date.today().isoformat()
assert emitted.year == datetime.now(UTC).year
assert expires_at > time.time()
```

Pytest collection fails on direct `datetime.now()`, `datetime.utcnow()`, `datetime.today()`, `date.today()`, `datetime.datetime.now()`, `datetime.datetime.utcnow()`, `datetime.datetime.today()`, `datetime.date.today()`, and `time.time()` calls inside `assert` expressions.

When the behavior is explicitly “mint a fresh timestamp now,” capture a bounded window outside the assertion:

```python
before = datetime.now(UTC)
event = emitter.emit_wp_status_changed(...)
after = datetime.now(UTC)

emitted = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
assert before <= emitted <= after
```

Use the bounded-window pattern only for code whose public contract is freshness. For calendar logic, expiry logic, lifecycle classification, and generated files, inject `now=` instead.
