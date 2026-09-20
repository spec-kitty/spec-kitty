"""WP04 T018 — end-to-end repair-fidelity capstone (REAL objects, no mocks).

This is the cross-lane integration gate for the doctor-mission-state repair
mission. Unlike the WP02/WP03 CLI characterization tests (which mock
``repair_repo`` / ``teamspace_dry_run`` and only assert the *shell's* exit codes
and rendering), this suite drives the **real** ``repair_repo`` and
``teamspace_dry_run`` objects over a seeded git repository, closing the WP02
reviewer's note that the report json shape was only ever mock-verified.

The seeded repo carries two missions:

* ``legacy-change-mode-mission`` (a) — ``meta.json`` has ``change_mode: regular``
  (a legacy value this codebase never writes). Fully repairable: ``--fix``
  normalizes the value away and the mission completes successfully.
* ``audit-blocking-mission`` (b) — a genuinely audit-blocking shape (a corrupt,
  non-JSON ``status.events.jsonl``). ``run_audit`` flags it ``CORRUPT_JSONL``,
  which is a TeamSpace blocker; the repair cannot heal it, so it stays invalid.

The suite asserts, against the real objects:

* SC-001 — ``--fix`` repairs (a): status ``updated``, stored ``change_mode``
  gone, ``meta_actions`` records ``normalized_change_mode:regular`` (the
  dropped value, fidelity #4780), no ``ValueError``, no validation error (the
  pre-fix behavior aborted the mission).
* SC-002/003 — the real ``RepairReport.to_json()`` and
  ``TeamspaceDryRunReport.to_json()`` carry per-mission records, so triage is
  possible from the command's own output WITHOUT reading the git-ignored
  ``.kittify/migrations/`` manifest.
* SC-004 — ``--audit`` and ``--fix`` agree that (a) is repairable, not fatal
  (audit raises no finding for the legacy value; fix heals it), and both agree
  that (b) is invalid.
* SC-005 — re-running ``--fix`` after a successful repair is idempotent.
* CRITICAL (additive-only guarantee) — ``teamspace_dry_run`` on the repo with
  (b) STILL returns ``valid=False`` (would exit 1), before AND after ``--fix``.

Tactic references:
- ``atdd-adversarial-acceptance`` / ``function-over-form-testing``: assert the
  observable end-to-end outcome of the real objects, never mocked internals.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from packaging.version import Version

from specify_cli.audit import run_audit
from specify_cli.audit.models import AuditOptions
from specify_cli.migration.mission_state import (
    MissionRepairResult,
    RepairReport,
    repair_repo,
    teamspace_dry_run,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

LEGACY_SLUG = "legacy-change-mode-mission"
BLOCKED_SLUG = "audit-blocking-mission"
_LEGACY_MISSION_ID = "01KWNP7Q8R9TVWXY2Z3A4B5C00"
_BLOCKED_MISSION_ID = "01KWNP7Q8R9TVWXY2Z3A4B5C11"
_CORRUPT_STATUS_ROW = "this is not valid json{{{\n"


def _has_events_5() -> bool:
    import spec_kitty_events

    return Version(spec_kitty_events.__version__) >= Version("5.0.0")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _meta(slug: str, mission_id: str, *, change_mode: object | None = None) -> str:
    meta: dict[str, object] = {
        "slug": slug,
        "mission_slug": slug,
        "friendly_name": slug,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-07-03T10:00:00+00:00",
        "mission_id": mission_id,
    }
    if change_mode is not None:
        meta["change_mode"] = change_mode
    return json.dumps(meta, indent=2, sort_keys=True) + "\n"


def _seed_repo(tmp_path: Path) -> Path:
    """Return a committed git repo seeded with the legacy + audit-blocking missions."""
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-q", "-b", "main")
    _git(primary, "config", "user.email", "wp04-e2e@spec-kitty.test")
    _git(primary, "config", "user.name", "wp04 e2e")

    # (a) legacy change_mode — fully repairable.
    legacy = primary / "kitty-specs" / LEGACY_SLUG
    legacy.mkdir(parents=True)
    (legacy / "meta.json").write_text(
        _meta(LEGACY_SLUG, _LEGACY_MISSION_ID, change_mode="regular"),
        encoding="utf-8",
    )

    # (b) genuinely audit-blocking — a corrupt, non-JSON status.events.jsonl that
    # ``run_audit`` flags CORRUPT_JSONL (a TeamSpace blocker) and the repair
    # cannot heal, so the dry-run must keep refusing it.
    blocked = primary / "kitty-specs" / BLOCKED_SLUG
    blocked.mkdir(parents=True)
    (blocked / "meta.json").write_text(
        _meta(BLOCKED_SLUG, _BLOCKED_MISSION_ID),
        encoding="utf-8",
    )
    (blocked / "status.events.jsonl").write_text(_CORRUPT_STATUS_ROW, encoding="utf-8")

    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "baseline")
    return primary


def _result_for(report: RepairReport, slug: str) -> MissionRepairResult:
    return next(m for m in report.missions if m.mission_slug == slug)


# ── SC-001: --fix repairs the legacy mission instead of aborting ────────────


def test_fix_repairs_legacy_change_mode_e2e(tmp_path: Path) -> None:
    """SC-001: the real ``repair_repo`` heals (a) — no ValueError, exit-0 shape."""
    primary = _seed_repo(tmp_path)

    # Pre-fix behavior aborted this mission with a ValueError; the repair must
    # now complete without raising.
    report = repair_repo(primary)

    legacy = _result_for(report, LEGACY_SLUG)
    assert legacy.status == "updated", f"legacy change_mode mission should repair, got {legacy.status!r} with validation_errors={legacy.validation_errors!r}"
    # "exit 0 / not fatal" for the legacy mission: no validation error recorded.
    assert legacy.validation_errors == []
    assert "normalized_change_mode:regular" in legacy.meta_actions

    persisted = json.loads((primary / "kitty-specs" / LEGACY_SLUG / "meta.json").read_text(encoding="utf-8"))
    assert "change_mode" not in persisted

    summary = report.to_dict()["summary"]
    assert isinstance(summary, dict)
    assert summary["missions_updated"] >= 1


# ── SC-002/003: real report json carries per-mission triage, no manifest read ─


def test_repair_report_json_carries_per_mission_records_e2e(tmp_path: Path) -> None:
    """SC-002: the REAL ``RepairReport.to_json()`` carries per-mission triage.

    The operator can identify what changed for (a) — slug, status, meta_actions,
    validation_errors — by parsing the command's own ``--json`` output, with no
    read of the git-ignored ``.kittify/migrations/`` manifest.
    """
    primary = _seed_repo(tmp_path)

    report = repair_repo(primary)

    payload = json.loads(report.to_json())
    by_slug = {m["mission_slug"]: m for m in payload["missions"]}

    assert LEGACY_SLUG in by_slug
    legacy_record = by_slug[LEGACY_SLUG]
    assert legacy_record["status"] == "updated"
    assert legacy_record["meta_actions"] == ["normalized_change_mode:regular"]
    assert legacy_record["validation_errors"] == []

    # (b) is surfaced per-mission with its own reason — not a bare count.
    assert BLOCKED_SLUG in by_slug
    blocked_record = by_slug[BLOCKED_SLUG]
    assert blocked_record["status"] == "error"
    assert blocked_record["validation_errors"], "the audit-blocking mission must carry its reason"

    # NFR-003: the triage detail lives in the serialized report itself.
    serialized = report.to_json()
    assert "normalized_change_mode:regular" in serialized
    assert LEGACY_SLUG in serialized and BLOCKED_SLUG in serialized


@pytest.mark.skipif(not _has_events_5(), reason="TeamSpace dry-run requires spec-kitty-events >= 5.0.0")
def test_dry_run_report_json_carries_per_mission_records_e2e(tmp_path: Path) -> None:
    """SC-002/003: the REAL ``TeamspaceDryRunReport.to_json()`` carries per-mission
    error records (dry-run parity), obtainable without a git-ignored manifest read.
    """
    primary = _seed_repo(tmp_path)

    report = teamspace_dry_run(primary)

    assert report.valid is False
    payload = json.loads(report.to_json())
    errors = payload["errors"]
    assert errors, "dry-run must surface per-mission errors[]"
    blocked = [e for e in errors if e.get("mission_slug") == BLOCKED_SLUG]
    assert blocked, f"expected a per-mission record for {BLOCKED_SLUG}, got {errors!r}"
    entry = blocked[0]
    # Each record names the mission, its error code, and a human reason.
    assert entry["mission_slug"] == BLOCKED_SLUG
    assert "error" in entry
    assert "message" in entry
    # NFR-003: triage detail is present in the serialized dry-run output.
    assert BLOCKED_SLUG in report.to_json()


# ── SC-004: audit and fix agree on the legacy value (and on genuine invalidity) ─


def test_audit_and_fix_agree_on_legacy_change_mode_e2e(tmp_path: Path) -> None:
    """SC-004: ``--audit`` and ``--fix`` classify (a) consistently (repairable).

    The read-only audit raises NO finding for the legacy ``change_mode`` (it is a
    writer-derived known key, not a blocker), while ``--fix`` heals it — so the
    two modes do not contradict each other on the same field. Both modes also
    agree that (b) is genuinely invalid.
    """
    primary = _seed_repo(tmp_path)

    audit = run_audit(AuditOptions(repo_root=primary))
    audit_by_slug = {m.mission_slug: m for m in audit.missions}

    # Audit does not flag the legacy change_mode mission at all — no finding it
    # would treat as valid-and-final that fix treats as unrecoverably fatal.
    legacy_codes = {f.code for f in audit_by_slug[LEGACY_SLUG].findings}
    assert legacy_codes == set(), f"audit unexpectedly flagged the legacy mission: {legacy_codes!r}"

    # ...and fix heals it (repairable, not fatal) — the two modes agree.
    report = repair_repo(primary)
    assert _result_for(report, LEGACY_SLUG).status == "updated"

    # Both modes agree the audit-blocking mission is invalid, for the same reason.
    blocked_codes = {f.code for f in audit_by_slug[BLOCKED_SLUG].findings}
    assert blocked_codes, "audit must flag the genuinely-invalid mission"
    assert _result_for(report, BLOCKED_SLUG).status == "error"


# ── SC-005: idempotency ─────────────────────────────────────────────────────


def test_fix_is_idempotent_e2e(tmp_path: Path) -> None:
    """SC-005: a second ``repair_repo`` run makes no further change to (a)."""
    primary = _seed_repo(tmp_path)

    first = repair_repo(primary)
    assert _result_for(first, LEGACY_SLUG).status == "updated"

    # Commit the healed tree so the second run starts from a clean checkout.
    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "post-repair")

    second = repair_repo(primary)
    legacy = _result_for(second, LEGACY_SLUG)
    assert legacy.status == "unchanged"
    assert legacy.meta_actions == []

    persisted = json.loads((primary / "kitty-specs" / LEGACY_SLUG / "meta.json").read_text(encoding="utf-8"))
    assert "change_mode" not in persisted


# ── CRITICAL: the dry-run refusal is preserved (additive-only guarantee) ─────


@pytest.mark.skipif(not _has_events_5(), reason="TeamSpace dry-run requires spec-kitty-events >= 5.0.0")
def test_dry_run_still_refuses_audit_blocking_mission_e2e(tmp_path: Path) -> None:
    """CRITICAL: ``teamspace_dry_run`` STILL refuses (b) — before AND after --fix.

    The repair-fidelity change is additive-only: healing the legacy
    ``change_mode`` must NOT weaken the dry-run's refusal of a genuinely-broken
    mission. The dry-run must return ``valid=False`` (the CLI would exit 1) with
    (b) named, both before any fix and after a ``--fix`` that heals (a) but
    cannot heal (b).
    """
    primary = _seed_repo(tmp_path)

    before = teamspace_dry_run(primary)
    assert before.valid is False, "dry-run must refuse the audit-blocking mission before --fix"
    assert BLOCKED_SLUG in {e.get("mission_slug") for e in before.errors}

    # Run the real repair (heals (a), leaves (b) broken), commit the healed tree.
    repair_repo(primary)
    _git(primary, "add", ".")
    _git(primary, "commit", "-q", "-m", "post-repair")

    after = teamspace_dry_run(primary)
    assert after.valid is False, "dry-run refusal must be preserved after --fix heals the legacy mission"
    assert BLOCKED_SLUG in {e.get("mission_slug") for e in after.errors}
