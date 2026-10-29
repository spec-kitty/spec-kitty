"""#6715: ``consolidate --attest-no-implementation`` lifts ``IMPLEMENTATION_MISSING`` for the named work package only.

A work package that legitimately owes no implementation (its deliverable already exists, it was
docs-only and landed elsewhere) refuses with ``IMPLEMENTATION_MISSING`` like a hollow approval.
The operator records why with ``--attest-no-implementation <WP> --attest-reason "<why>"``: a
forced operator self-transition with ``policy_metadata.attestation = "no_implementation"``,
recorded before the claim is built.

* :func:`test_the_attestation_lifts_implementation_missing_for_an_independently_reviewed_wp` --
  WP02 (approved by ``bob``, implemented by ``claude``) with no owned change refuses; a request
  without a reason exits 2 and one naming a work package outside the claim exits 1, both
  recording nothing; with the attestation the Mission consolidates at exit 0, WP02 lands
  ``done`` and the output names WP02's lifted refusal.
* :func:`test_the_attestation_never_lifts_review_not_independent` -- a self-approved hollow WP02
  plus the attestation still refuses ``REVIEW_NOT_INDEPENDENT``: the attestation is never the
  approving actor.

Drives the REAL CLI end to end on a coord Mission, reusing the WP01 fixture helpers.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.integration.test_6715_consolidate_lane_evidence import _BANNER, _Mission, _git, _sk, accept, drive, lanes_of, setup_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]

_RESEARCH = "research/notes.md"
_ATTESTATION = '"attestation": "no_implementation"'


def _flat(proc: subprocess.CompletedProcess[str]) -> str:
    """The run's stdout and stderr with every whitespace run collapsed (the console wraps long lines)."""
    return " ".join((proc.stdout + proc.stderr).split())


def _drive_mission(mission: _Mission, *, wp02_reviewer: str) -> None:
    drive(mission, "WP01", "T1", implementer="alice", reviewer="bob", owned_path="src/m1/real.py")
    drive(mission, "WP02", "T2", implementer="claude", reviewer=wp02_reviewer, owned_path=None)
    drive(mission, "WP03", "T3", implementer="claude", reviewer="bob", owned_path="src/m3/real.py")
    drive(mission, "WP04", "T4", implementer="alice", reviewer="bob", owned_path=f"kitty-specs/{mission.slug}/{_RESEARCH}")
    before = lanes_of(mission)
    assert all(before.get(wp) == "approved" for wp in ("WP01", "WP02", "WP03", "WP04")), f"fixture: every WP must reach approved; lanes={before}"
    accept(mission)


def _attestation_mentions(mission: _Mission) -> int:
    """Mentions of a no-implementation attestation on every status log of the Mission, working copies and committed (0 means none recorded)."""
    relpath = f"kitty-specs/{mission.slug}/status.events.jsonl"
    logs = [*mission.repo.glob(relpath), *mission.repo.glob(f".worktrees/*/{relpath}")]
    return sum(log.read_text(encoding="utf-8").count(_ATTESTATION) for log in logs) + _committed_attestations(mission)


def _committed_attestations(mission: _Mission) -> int:
    """Attestations committed on any branch's status log (the coordination branch holds it under coord topology)."""
    count = 0
    for ref in _git(mission.repo, "for-each-ref", "--format=%(refname)", "refs/heads").splitlines():
        shown = _git_show(mission, f"{ref}:kitty-specs/{mission.slug}/status.events.jsonl")
        count += shown.count(_ATTESTATION)
    return count


def _git_show(mission: _Mission, spec: str) -> str:
    proc = subprocess.run(["git", "show", spec], cwd=mission.repo, capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else ""


def test_the_attestation_lifts_implementation_missing_for_an_independently_reviewed_wp(tmp_path: Path) -> None:
    mission = setup_mission(tmp_path, "coord")
    _drive_mission(mission, wp02_reviewer="bob")

    refused = _sk(mission, "consolidate", "--mission", mission.slug)
    refused_output = refused.stdout + refused.stderr
    assert refused.returncode != 0 and "IMPLEMENTATION_MISSING: WP02" in refused_output, refused_output[-3000:]

    no_reason = _sk(mission, "consolidate", "--mission", mission.slug, "--attest-no-implementation", "WP02")
    assert no_reason.returncode == 2, (no_reason.stdout + no_reason.stderr)[-2000:]
    assert "--attest-no-implementation requires --attest-reason" in _flat(no_reason)
    outside = _sk(
        mission,
        *("consolidate", "--mission", mission.slug, "--attest-no-implementation", "WP02", "--attest-no-implementation", "WP09"),
        *("--attest-reason", "docs-only"),
    )
    assert outside.returncode == 1, (outside.stdout + outside.stderr)[-2000:]
    assert "not approved: WP09" in _flat(outside)
    assert _attestation_mentions(mission) == 0, "a refused request records nothing, for any work package of it"

    landed = _sk(mission, "consolidate", "--mission", mission.slug, "--attest-no-implementation", "WP02", "--attest-reason", "docs-only")
    output = _flat(landed)

    assert landed.returncode == 0, f"an attested no-implementation WP with an independent review must consolidate. output:\n{output[-3000:]}"
    assert "WP02: IMPLEMENTATION_MISSING lifted by operator attestation (docs-only)" in output, output[-3000:]
    assert _BANNER in output, output[-3000:]
    after = lanes_of(mission)
    assert all(after.get(wp) == "done" for wp in ("WP01", "WP02", "WP03", "WP04")), f"every WP must land done; lanes={after}"
    # Only the other work packages' content reached the target: WP02 (attested, no implementation) brought none.
    landed_paths = set(_git(mission.repo, "ls-tree", "-r", "--name-only", "main").splitlines())
    assert "tools/check.sh" not in landed_paths, "nothing of WP02 may reach the target"
    assert {"src/m1/real.py", "src/m3/real.py", f"kitty-specs/{mission.slug}/{_RESEARCH}"} <= landed_paths, sorted(landed_paths)


def test_the_attestation_never_lifts_review_not_independent(tmp_path: Path) -> None:
    mission = setup_mission(tmp_path, "coord")
    _drive_mission(mission, wp02_reviewer="claude")
    main_before = _git(mission.repo, "rev-parse", "main")

    refused = _sk(mission, "consolidate", "--mission", mission.slug, "--attest-no-implementation", "WP02", "--attest-reason", "docs-only")
    output = refused.stdout + refused.stderr

    assert refused.returncode != 0, f"a self-approved WP must not consolidate, attested or not. output:\n{output[-3000:]}"
    assert "REVIEW_NOT_INDEPENDENT: WP02" in output, output[-3000:]
    assert "IMPLEMENTATION_MISSING: WP02" not in output, "the attestation lifted IMPLEMENTATION_MISSING only"
    assert _BANNER not in output
    assert _git(mission.repo, "rev-parse", "main") == main_before
    status = json.loads(_sk(mission, "agent", "tasks", "status", "--mission", mission.slug, "--json").stdout)
    assert {w["id"]: w["lane"] for w in status["work_packages"]}.get("WP02") == "approved"
