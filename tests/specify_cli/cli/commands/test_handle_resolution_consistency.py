"""WP06 (mission-handle-resolution-consistency, FR-013): the cross-command
handle-resolution regression net.

This is the mission's adversarial safety net. It proves the promise the mission
makes — *a bad ``--mission`` handle reads the same, truthful way across the FIXED
commands* — holds end to end, AND that the two deliberately-EXCLUDED envelopes
are NOT collateral-damaged by the unification.

Scope of the four assertions (see
``kitty-specs/mission-handle-resolution-consistency-01M2TPWG/contracts/cli-behavior.md``):

* **T028 — canonical message across the fixed commands.** For ``research``,
  ``plan`` (``setup-plan``), ``tasks`` (``check-prerequisites``) and ``merge``
  (fresh), a nonexistent handle in a ≥2-mission repo yields the single canonical
  ``Mission not found: <handle>`` (WP01's
  :func:`mission_not_found_message` constant) and NONE of the pre-fix defect
  strings (``"to disambiguate"``, ``"lanes.json is required"``).
* **T029 — NFR-001 snapshot invariance.** Each fixed command leaves
  ``kitty-specs/`` byte-for-byte unchanged on the nonexistent-handle path (the
  ``research`` phantom-scaffold guard, generalized to every fixed command via a
  content-hash snapshot).
* **T030 — FR-013 correct-commands-stay-correct.** The two PRESERVED envelopes
  are still intact, NOT flattened onto the bare constant: the identity resolver
  (:class:`MissionNotFoundError`, ``context/mission_resolver.py``) still names
  the handle AND still carries the ``spec-kitty migrate backfill-identity``
  remediation; ``reconcile --mission <bad>`` still speaks of a "dossier not
  found". Regressing either — collapsing it to ``Mission not found: <handle>`` —
  fails this test.
* **T031 — legacy-mission count agreement.** In a repo that includes a legacy
  (no ``mission_id``) mission, ``next``'s discovery population equals the
  plan/tasks auto-detect population (both see the legacy mission). Guards the
  mission's shared-population decision.

T032 (whole suite green + full ``tests/architectural/`` green + union blast
radius) is executed by the implementing agent, not encoded as an in-file test.

All assertions drive the real CLI in-process via :class:`typer.testing.CliRunner`
over real git repositories — no subprocess ``run_cli`` (≈90 s slower, prone to
stale-install false-reds) and no source mocking, so this stays a true
integration net.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app
from specify_cli.context.mission_resolver import (
    MissionNotFoundError,
    mission_not_found_message,
    resolve_mission,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

# A single handle that matches no mission in any staged repo below.
_HANDLE = "zznope"
_CANONICAL = f"Mission not found: {_HANDLE}"
# The pre-fix, misleading strings each fixed command used to emit. None may
# survive on the nonexistent-handle path (T028).
_OLD_DEFECT_STRINGS = ("to disambiguate", "lanes.json is required")

# Two syntactically valid, distinct ULIDs for the identity-bearing missions.
_ULID_A = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
_ULID_B = "01BX5ZZKBKACTAV9WEVGEMMVRZ"

# The FIXED commands, each as a full argv for the top-level ``app``. ``plan`` and
# ``tasks`` surface through the ``agent mission`` group (``setup-plan`` /
# ``check-prerequisites``); ``merge`` is the fresh entry (not ``--resume`` /
# ``--abort``). Human output is asserted for all four (only ``next`` / the plan
# and tasks agent commands / materialize carry ``--json``; research is
# human-only and merge's ``--json`` is dry-run-only — see FR-011).
_FIXED_COMMANDS = [
    pytest.param(["research", "--mission", _HANDLE], id="research"),
    pytest.param(["agent", "mission", "setup-plan", "--mission", _HANDLE], id="plan"),
    pytest.param(["agent", "mission", "check-prerequisites", "--mission", _HANDLE], id="tasks"),
    pytest.param(["merge", "--mission", _HANDLE], id="merge-fresh"),
]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _seed_mission(specs_dir: Path, slug: str, *, mission_id: str | None = None) -> None:
    """Create a minimal but real mission dir (legacy when *mission_id* is None)."""
    mission_dir = specs_dir / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text(f"# {slug}\n", encoding="utf-8")
    meta: dict[str, object] = {
        "mission": "software-dev",
        "mission_type": "software-dev",
        "mission_slug": slug,
        "friendly_name": slug,
    }
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _init_repo(repo_root: Path) -> None:
    """Initialise a real git repo so main-repo / preflight detection works."""
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "wp06-net@example.invalid")
    _git(repo_root, "config", "user.name", "WP06 Consistency Net")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / ".kittify").mkdir()


def _commit_all(repo_root: Path) -> None:
    """Commit the seeded tree so ``merge``'s git preflight sees a clean worktree."""
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "seed missions")


def _snapshot(specs_dir: Path) -> list[tuple[str, str]]:
    """Byte-for-byte listing of ``kitty-specs/``: (relpath, sha256) per entry.

    Directories contribute a trailing-slash entry with an empty hash so a
    phantom *empty* directory (the pre-fix ``research`` failure mode) is caught
    even before any file lands in it.
    """
    entries: list[tuple[str, str]] = []
    for path in sorted(specs_dir.rglob("*")):
        rel = str(path.relative_to(specs_dir))
        if path.is_dir():
            entries.append((rel + "/", ""))
        else:
            # noqa TID251: raw SHA-256 of file bytes is a file-integrity check
            # (the NFR-001 byte-for-byte snapshot invariant), not charter content
            # hashing — charter.hasher.hash_content normalizes BOM/newlines and
            # would silently mask a whitespace-only phantom write.
            entries.append((rel, hashlib.sha256(path.read_bytes()).hexdigest()))  # noqa: TID251
    return entries


@pytest.fixture
def two_mission_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A committed repo with two genuine, identity-bearing missions (no ``zznope``)."""
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    specs = repo_root / "kitty-specs"
    _seed_mission(specs, "001-alpha-mission", mission_id=_ULID_A)
    _seed_mission(specs, "002-beta-mission", mission_id=_ULID_B)
    _commit_all(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root


@pytest.fixture
def legacy_mission_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A committed repo whose two missions include one legacy (no ``mission_id``)."""
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    specs = repo_root / "kitty-specs"
    _seed_mission(specs, "001-identity-mission", mission_id=_ULID_A)
    _seed_mission(specs, "002-legacy-mission")  # no mission_id -> legacy
    _commit_all(repo_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    return repo_root


@pytest.fixture
def _bypass_dashboard_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the charter preflight hooks so ``next`` reaches discovery listing.

    Mirrors ``tests/next/test_next_missing_mission_discovery.py``'s bypass; only
    ``next`` (query mode) runs the dashboard preflight, so this is scoped to the
    T031 test that invokes it.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    ok = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_a, **_kw: ok,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_for_dashboard",
        lambda *_a, **_kw: ok,
    )


# ---------------------------------------------------------------------------
# T028 — one canonical message across every FIXED command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", _FIXED_COMMANDS)
def test_nonexistent_handle_yields_canonical_message(two_mission_repo: Path, argv: list[str]) -> None:
    """Every fixed command reads ``Mission not found: <handle>`` for a bad handle."""
    result = runner.invoke(app, argv)

    assert result.exit_code != 0, result.output
    assert _CANONICAL in result.output, f"{argv} did not emit the canonical message; output:\n{result.output}"
    for defect in _OLD_DEFECT_STRINGS:
        assert defect not in result.output, f"{argv} leaked the pre-fix defect string {defect!r}:\n{result.output}"


# ---------------------------------------------------------------------------
# T029 — NFR-001: the not-found path writes nothing (phantom-write guard)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", _FIXED_COMMANDS)
def test_nonexistent_handle_leaves_specs_byte_identical(two_mission_repo: Path, argv: list[str]) -> None:
    """A bad handle must leave ``kitty-specs/`` byte-for-byte unchanged."""
    specs = two_mission_repo / "kitty-specs"
    before = _snapshot(specs)

    result = runner.invoke(app, argv)

    assert result.exit_code != 0, result.output
    after = _snapshot(specs)
    assert after == before, f"{argv} mutated kitty-specs/; symmetric diff: {sorted(set(after) ^ set(before))}"
    # The specific phantom the pre-fix ``research`` scaffold produced must be absent.
    assert not (specs / _HANDLE).exists(), f"{argv} scaffolded a phantom kitty-specs/{_HANDLE}/"


# ---------------------------------------------------------------------------
# T030 — FR-013: the two EXCLUDED envelopes stay intact (not flattened)
# ---------------------------------------------------------------------------


def test_identity_resolver_envelope_is_preserved(two_mission_repo: Path) -> None:
    """The identity resolver keeps its handle + ``backfill-identity`` remediation.

    ``MissionNotFoundError`` is deliberately NOT unified onto the bare
    ``Mission not found: <handle>`` constant — collapsing it would erase the
    FR-005 legacy-mission remediation. This pins that it still names the handle,
    still points at ``spec-kitty migrate backfill-identity``, and is distinct
    from the canonical constant.
    """
    with pytest.raises(MissionNotFoundError) as excinfo:
        resolve_mission(_HANDLE, two_mission_repo)

    message = str(excinfo.value)
    assert _HANDLE in message
    assert "backfill-identity" in message
    assert "No mission found for handle" in message
    # NOT flattened: the richer envelope is not the bare unified constant.
    assert message != mission_not_found_message(_HANDLE)
    assert _CANONICAL not in message


def test_reconcile_envelope_is_preserved(two_mission_repo: Path) -> None:
    """``reconcile`` keeps its semantically-distinct "dossier not found" wording.

    A dossier is not a mission directory; the mission left ``reconcile`` out of
    the unification on purpose. Flattening it to ``Mission not found: <handle>``
    fails here.
    """
    result = runner.invoke(app, ["reconcile", "--mission", _HANDLE])

    assert result.exit_code != 0, result.output
    assert _HANDLE in result.output
    assert "dossier not found" in result.output
    # NOT flattened onto the capital-M unified constant.
    assert _CANONICAL not in result.output


# ---------------------------------------------------------------------------
# T031 — legacy-mission population agreement across discovery surfaces
# ---------------------------------------------------------------------------


def test_legacy_mission_population_agrees_across_next_and_plan_tasks(legacy_mission_repo: Path, _bypass_dashboard_preflight: None) -> None:
    """``next`` discovery and plan/tasks auto-detect see the SAME missions.

    Including the legacy (no ``mission_id``) one — the shared-population
    decision the mission committed to. A regression that hid legacy missions
    from one surface but not the other would break the set equality below.
    """
    next_res = runner.invoke(app, ["next", "--json"])
    assert next_res.exit_code != 0, next_res.output
    next_payload = json.loads(next_res.stdout)
    next_slugs = {row["mission_slug"] for row in next_payload["available_missions"]}

    plan_res = runner.invoke(app, ["agent", "mission", "setup-plan", "--json"])
    assert plan_res.exit_code != 0, plan_res.output
    plan_payload = json.loads(plan_res.stdout.strip().split("\n")[0])
    plan_slugs = set(plan_payload["available_missions"])

    tasks_res = runner.invoke(app, ["agent", "mission", "check-prerequisites", "--json"])
    assert tasks_res.exit_code != 0, tasks_res.output
    tasks_payload = json.loads(tasks_res.stdout.strip().split("\n")[0])
    tasks_slugs = set(tasks_payload["available_missions"])

    assert next_slugs == plan_slugs == tasks_slugs
    assert "002-legacy-mission" in next_slugs, "the legacy mission must be visible to every discovery surface"
    # golden-count: cardinality-is-contract (exactly the two staged missions).
    assert len(next_slugs) == 2
