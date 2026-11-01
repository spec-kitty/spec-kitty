# Probe recipe — does a slow (but finite) holder red the coexistence ratchet?

This is the reproducible form of the evidence in `research.md` D-3. It is probe evidence,
not a collected test: it lives outside `tests/` on purpose. On the pre-fix harness the
probe **reds**; on the fixed harness it is green.

Copy the block below to `tests/specify_cli/decisions/test_zz_probe_slow_holder.py` (so the
`tests/` conftest chain applies), then run:

```bash
uv run --frozen pytest tests/specify_cli/decisions/test_zz_probe_slow_holder.py -q -n0
```

Delete the file afterwards — it must never be committed under `tests/`.

```python
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands import _decisions_doctor as doctor
from specify_cli.decisions import service
from specify_cli.decisions import store as _store
from specify_cli.decisions.models import OriginFlow
from specify_cli.decisions.service import open_decision, resolve_decision
from specify_cli.status import feature_status_lock, mission_lock_key
from specify_cli.workspace.root_resolver import resolve_status_lock_root

MISSION_ID = "01KTEST_MISSION_ID_000002"
MISSION_SLUG = "concurrency-mission"


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _open(repo_root: Path, key: str) -> str:
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}), encoding="utf-8"
    )
    return str(
        open_decision(
            repo_root,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id=f"step-{key}",
            input_key=key,
            question="How large is the team?",
            options=("1-5", "6-20"),
            actor="alice",
        ).decision_id
    )


class _Worker:
    def __init__(self, fn: Callable[[], Any]) -> None:
        self.error: BaseException | None = None
        self._fn = fn
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        try:
            self._fn()
        except BaseException as exc:
            self.error = exc

    def start(self) -> "_Worker":
        self.thread.start()
        return self

    def finish(self, timeout: float = 30.0) -> None:
        self.thread.join(timeout)
        assert not self.thread.is_alive(), "worker did not finish"
        assert self.error is None, repr(self.error)


@pytest.mark.timeout(120)
def test_probe_slow_holder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d1 = _open(tmp_path, "k1")
    d2 = _open(tmp_path, "k2")
    feature_dir = _mission_dir(tmp_path)
    barrier = threading.Barrier(4, timeout=20.0)

    real_save = _store.save_index

    def slow_save(*a: Any, **k: Any) -> None:
        time.sleep(0.4)  # finite: every holder releases
        real_save(*a, **k)

    monkeypatch.setattr(_store, "save_index", slow_save)
    monkeypatch.setattr(service, "_LOCK_ACQUIRE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(doctor, "_LOCK_ACQUIRE_TIMEOUT_S", 0.2)

    def status_writer() -> None:
        lock_root = resolve_status_lock_root(feature_dir)
        with feature_status_lock(lock_root, mission_lock_key(feature_dir, repo_root=lock_root)):
            pass

    def doctor_repair() -> None:
        doctor._repair(doctor._mission_dir(tmp_path, MISSION_SLUG), doctor._ledger_dir(tmp_path, MISSION_SLUG))

    def gated(fn: Callable[[], Any]) -> Callable[[], Any]:
        def run() -> Any:
            barrier.wait()
            return fn()

        return run

    def resolve_both() -> None:
        resolve_decision(tmp_path, MISSION_SLUG, d1, final_answer="1-5", actor="alice")
        resolve_decision(tmp_path, MISSION_SLUG, d2, final_answer="1-5", actor="alice")

    workers = [
        _Worker(gated(resolve_both)),
        _Worker(gated(lambda: _open(tmp_path, "k3"))),
        _Worker(gated(doctor_repair)),
        _Worker(gated(status_writer)),
    ]
    for w in workers:
        w.start()
    for w in workers:
        w.finish()
```

## Observed

Pre-fix harness (main @ `512567eee7`):

```
tests/specify_cli/decisions/test_zz_probe_slow_holder.py:75: in finish
    assert self.error is None, repr(self.error)
E   AssertionError: DecisionError("Timed out after 0.2s waiting for the decisions lock
    '/tmp/…/kitty-specs/concurrency-mission/decisions/index.json.lock'; another decision
    command is holding it. Nothing was written; retry the command.")
1 failed in 2.04s
```

No deadlock: the four workers all finish; one of them refuses because its peer held the
lock longer than the bound it inherited. That is the mechanism behind a load-shaped red.
