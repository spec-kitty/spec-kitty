"""Shared helpers for the ``consolidate --target <b> --retarget`` end-to-end tests (#7692, WP04).

The arms live in ``test_consolidate_retarget*.py``; see ``test_consolidate_retarget.py`` for the scenario.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from specify_cli.status.reducer import reduce
from specify_cli.status.store import read_event_stream
from tests.terminus.conftest import CoordMission, _cli_env, blob_present_at, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.rollback_harness import flat, state_path
from tests.terminus.test_target_override_recorded_target_unwritable import _branches, _merge_records, _reflogs

OLD = "main"
NEW = "develop"
REASON = "e2e"
RETARGET = ("--target", NEW, "--retarget")
PREFLIGHT_LINE = "Consolidation refused before any branch moved."
CODE_FILE = "src/pkg/wp01.py"
RETARGET_RECORD_UNWRITABLE = "RETARGET_RECORD_UNWRITABLE"

# The commit subjects the run writes (the sources' message templates).
RETARGET_SUBJECT = "chore({slug}): retarget main -> develop"
DONE_SUBJECT = "chore({slug}): record done transitions for merged WPs"
RETRO_SUBJECT = "chore({slug}): capture mission retrospective"
FLATTEN_SUBJECT = "chore({slug}): flatten coordination metadata after branch deletion (#3086)"

# Rebinds ONE module-level callable of the consolidation family before ``main()``. ``raise`` models
# a failure inside the rollback door (the door rolls back); ``kill`` models a SIGKILL (nothing
# runs after it, so the record and the branches stay exactly as the interrupt left them).
PATCHED_CLI = """
import os, signal, sys
import specify_cli
from specify_cli.consolidation import {module}

def _interrupt(*_args, **_kwargs):
    if {kill!r}:
        sys.stdout.flush()
        sys.stderr.flush()
        os.kill(os.getpid(), signal.SIGKILL)
    raise RuntimeError("injected")

{module}.{name} = _interrupt
sys.argv = ["spec-kitty", *sys.argv[1:]]
specify_cli.main()
"""


def run_patched(mission: CoordMission, module: str, name: str, *extra: str, kill: bool) -> subprocess.CompletedProcess[str]:
    """Run the REAL CLI with ``<module>.<name>`` rebound to raise (``kill=False``) or SIGKILL itself."""
    script = PATCHED_CLI.format(module=module, name=name, kill=kill)
    args = ["consolidate", "--mission", mission.slug, "--yes", *extra]
    return subprocess.run([sys.executable, "-c", script, *args], cwd=str(mission.repo), env=_cli_env(mission.home), capture_output=True, text=True, check=False)


def tip(mission: CoordMission, ref: str) -> str:
    return git(mission.repo, "rev-parse", ref).stdout.strip()


def meta_at(mission: CoordMission, ref: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(git(mission.repo, "show", f"{ref}:kitty-specs/{mission.slug}/meta.json").stdout)
    return payload


def log_subjects(mission: CoordMission, rev_range: str) -> list[str]:
    """Commit subjects of *rev_range*, oldest first."""
    return git(mission.repo, "log", "--reverse", "--format=%s", rev_range).stdout.splitlines()


def retarget_commits(mission: CoordMission, rev_range: str) -> int:
    return log_subjects(mission, rev_range).count(RETARGET_SUBJECT.format(slug=mission.slug))


def events_at(mission: CoordMission, ref: str) -> list[dict[str, Any]]:
    out = git(mission.repo, "show", f"{ref}:kitty-specs/{mission.slug}/status.events.jsonl").stdout
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def lanes_at(mission: CoordMission, ref: str, scratch: Path) -> dict[str, str]:
    """Each WP's lane reduced from *ref*'s event log (the CLI's own reducer)."""
    feature_dir = scratch / ref.replace("/", "_")
    feature_dir.mkdir(parents=True, exist_ok=True)
    blob = git(mission.repo, "show", f"{ref}:kitty-specs/{mission.slug}/status.events.jsonl").stdout
    (feature_dir / "status.events.jsonl").write_text(blob, encoding="utf-8")
    stream = read_event_stream(feature_dir)
    snapshot = reduce(stream.transitions, stream.annotations)
    return {wp: str(state.get("lane")) for wp, state in snapshot.work_packages.items()}


def merge_record(mission: CoordMission) -> dict[str, Any] | None:
    path = state_path(mission)
    if path is None:
        return None
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def kitty_specs_status(mission: CoordMission) -> str:
    return git(mission.repo, "status", "--porcelain", "--", "kitty-specs").stdout


def assert_refused_cleanly(
    mission: CoordMission,
    result: subprocess.CompletedProcess[str],
    code: str,
    before: dict[str, str],
    reflogs_before: dict[str, list[str]],
    *,
    status_before: str = "",
) -> None:
    """The #5783 invariant set with the refusal code as a parameter (NFR-001)."""
    output = flat(result)
    assert result.returncode == 1, f"the retarget must be refused. output={output}"
    assert code in output, f"the refusal must carry {code}. output={output}"
    assert PREFLIGHT_LINE in output, f"the refusal must come before any branch moved. output={output}"
    assert "Traceback" not in result.stderr, f"a refusal is not a crash. stderr={result.stderr}"
    assert _branches(mission) == before, f"no branch tip may move. output={output}"
    assert _reflogs(mission) == reflogs_before, f"no branch may move and come back either. output={output}"
    assert _merge_records(mission) == [], f"no merge record may be written. output={output}"
    assert not blob_present_at(mission.repo, NEW, CODE_FILE), f"nothing lands on the new target. output={output}"
    assert kitty_specs_status(mission) == status_before, f"a refusal leaves kitty-specs/ as it was. output={output}"


def dry_run(mission: CoordMission, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    result = run_terminus(mission, ["consolidate", "--dry-run", "--json", "--mission", mission.slug, *extra])
    payload: dict[str, Any] = json.loads(result.stdout.strip().splitlines()[-1])
    return result, payload


def assert_landed_on_new_target(mission: CoordMission, result: subprocess.CompletedProcess[str], pre_new: str) -> None:
    output = flat(result)
    assert result.returncode == 0, output
    assert "Traceback" not in result.stderr, result.stderr
    assert blob_present_at(mission.repo, NEW, CODE_FILE), output
    assert not blob_present_at(mission.repo, OLD, CODE_FILE), output
    landed = f"{pre_new}..{NEW}"
    assert retarget_commits(mission, landed) == 1, f"NFR-002: exactly one retarget commit. log={log_subjects(mission, landed)}"
    assert meta_at(mission, NEW)["target_branch"] == NEW


def protect(mission: CoordMission, protection: str) -> None:
    config = mission.repo / ".kittify" / "config.yaml"
    config.write_text(protection, encoding="utf-8")
    git(mission.repo, "add", str(config))
    git(mission.repo, "commit", "-qm", "chore: protection config")


def clear_stale_global_lock(mission: CoordMission) -> None:
    """Remove the global merge lock a SIGKILLed run leaves, as the operator is told to (``characterization_support``)."""
    (mission.repo / ".kittify" / "runtime" / "merge" / "__global_merge__" / "lock").unlink(missing_ok=True)


def kill(mission: CoordMission, module: str, name: str, *extra: str) -> subprocess.CompletedProcess[str]:
    """SIGKILL a real ``consolidate`` at ``<module>.<name>``; the stale global lock is then cleared."""
    result = run_patched(mission, module, name, *extra, kill=True)
    clear_stale_global_lock(mission)
    return result
