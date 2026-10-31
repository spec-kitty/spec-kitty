"""Real ``--mission`` scoping for the corpus-walking ``migrate`` commands (#6347).

#5294 / PR #6345 made ``backfill-provenance``, ``charter-encoding`` and
``rebaseline-dossier-hashes`` **reject** ``--mission`` instead of silently
ignoring it. That closed the false-success door but left an operator unable to
re-run one migration against one Mission. This module pins the follow-up: the
three commands accept a real ``--mission`` (mission_id / mid8 / slug, resolved
through the canonical selector resolver) and narrow their walk to that Mission,
while omitting the flag keeps the corpus-wide default and
``rewrite-opposed-by`` / ``repin-hooks`` keep rejecting it.

Every scoping test is a *paired* assertion on the same run — the target
Mission's file changed **and** the sibling Mission's file is byte-identical.
An "it did not crash" assertion would pass on the current reject and proves
nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_A_MID = "01K9AAAABBBBCCCCDDDDEEEEFF"  # 26-char Crockford-base32 ULID shape
_B_MID = "01K9GGGGHHHHJJJJKKKKMMMMNN"
_A_SLUG = f"aaa-mission-{_A_MID}"
_B_SLUG = f"bbb-mission-{_B_MID}"

#: cp1252-encoded prose with curly quotes/accents — unambiguously recoverable
#: under the chokepoint's cp1252 tie-break (an arbitrary high byte is AMBIGUOUS).
_NON_UTF8 = "# Team Charter\n\nWe don\u2019t ship on Fridays \u2014 the \u201cfreeze\u201d rule. Owner: Jos\u00e9 Pe\u00f1a.\n".encode("cp1252")
_NON_CANONICAL_HASH = "0" * 64

_COMMANDS = (
    ("backfill-provenance", "backfill-provenance"),
    ("charter-encoding", "charter-encoding"),
    ("rebaseline-dossier-hashes", "rebaseline-dossier-hashes"),
)
_COMMAND_IDS = [command for command, _ in _COMMANDS]


# ── fixture ─────────────────────────────────────────────────────────────────


def _write_mission(root: Path, *, slug: str, mission_id: str) -> Path:
    """One Mission with every corpus artifact the three commands walk."""
    mission_dir = root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mid8": mission_id[:8],
                "mission_slug": slug,
                "mission_type": "software-dev",
                "topology": "single_branch",
            }
        ),
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# Spec\n\nRequirements here.\n", encoding="utf-8")
    (mission_dir / "plan.md").write_text("# Plan\n\nImplementation plan.\n", encoding="utf-8")
    tasks = mission_dir / "tasks"
    tasks.mkdir()
    (tasks / "WP01-first.md").write_text(
        "---\nwork_package_id: WP01\ntitle: First\ndependencies: []\nsubtasks:\n- T001\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    (mission_dir / "acceptance-matrix.json").write_text(
        json.dumps(
            {
                "negative_invariants": [
                    {
                        "invariant_id": "NI-1",
                        "description": "nope",
                        "verification_method": "grep_absence",
                        "result": "confirmed_absent",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    charter_dir = mission_dir / "charter"
    charter_dir.mkdir()
    (charter_dir / "charter.md").write_bytes(_NON_UTF8)

    dossier_dir = mission_dir / ".kittify" / "dossiers" / slug
    dossier_dir.mkdir(parents=True)
    (dossier_dir / "snapshot-latest.json").write_text(
        json.dumps({"mission_slug": slug, "parity_hash_sha256": _NON_CANONICAL_HASH}, indent=2) + "\n",
        encoding="utf-8",
    )
    return mission_dir


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project with two Missions, a global charter store, and a usable root."""
    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    (root / ".kittify" / "charter").mkdir()
    (root / ".kittify" / "charter" / "charter.md").write_bytes(_NON_UTF8)
    _write_mission(root, slug=_A_SLUG, mission_id=_A_MID)
    _write_mission(root, slug=_B_SLUG, mission_id=_B_MID)
    monkeypatch.chdir(root)
    return root


def _run(project: Path, command: str, *extra: str) -> Any:
    from specify_cli import app

    return CliRunner().invoke(
        app,
        ["migrate", command, "--project-root", str(project), *extra],
    )


def _run_from_root(project: Path, command: str, *extra: str) -> Any:
    """Invoke without ``--project-root`` for commands that resolve it themselves."""
    from specify_cli import app

    return CliRunner().invoke(app, ["migrate", command, *extra])


def _path(project: Path, slug: str, *parts: str) -> Path:
    return project.joinpath("kitty-specs", slug, *parts)


def _matrix_has_provenance(path: Path) -> bool:
    invariants = json.loads(path.read_text(encoding="utf-8"))["negative_invariants"]
    return all("provenance_origin" in invariant for invariant in invariants)


def _is_utf8(path: Path) -> bool:
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _recorded_hash(path: Path) -> str:
    return str(json.loads(path.read_text(encoding="utf-8")).get("parity_hash_sha256", ""))


def _unchanged_checks(command: str, project: Path, slug: str) -> bool:
    """True when the sibling Mission's artifact for *command* is still untouched."""
    if command == "backfill-provenance":
        return not _matrix_has_provenance(_path(project, slug, "acceptance-matrix.json"))
    if command == "charter-encoding":
        return not _is_utf8(_path(project, slug, "charter", "charter.md")) and not _path(project, slug, "charter", "charter.md.bak").exists()
    return _recorded_hash(_path(project, slug, ".kittify", "dossiers", slug, "snapshot-latest.json")) == _NON_CANONICAL_HASH


def _target_changed(command: str, project: Path, slug: str) -> bool:
    """True when the target Mission's artifact for *command* was migrated."""
    if command == "backfill-provenance":
        return _matrix_has_provenance(_path(project, slug, "acceptance-matrix.json"))
    if command == "charter-encoding":
        return _is_utf8(_path(project, slug, "charter", "charter.md"))
    return _recorded_hash(_path(project, slug, ".kittify", "dossiers", slug, "snapshot-latest.json")).startswith("sha256:")


def _invoke(project: Path, command: str, *extra: str) -> Any:
    """Invoke *command* with *extra* args, adding ``--yes`` only where it exists."""
    args = list(extra)
    if command == "charter-encoding" and "--yes" not in args:
        args.append("--yes")
    if command == "rebaseline-dossier-hashes":
        return _run_from_root(project, command, *args)
    return _run(project, command, *args)


# ── SC-001: a scoped run touches one Mission, and only one ──────────────────


@pytest.mark.parametrize("command", _COMMAND_IDS)
def test_scoped_run_touches_only_the_target_mission(command: str, project: Path) -> None:
    """FR-001/FR-002/FR-003, SC-001: the sibling Mission is byte-identical."""
    result = _invoke(project, command, "--mission", _A_SLUG, "--json")
    assert result.exit_code == 0, result.output

    assert _target_changed(command, project, _A_SLUG), f"{command} did not migrate the target Mission"
    assert _unchanged_checks(command, project, _B_SLUG), f"{command} mutated a non-target Mission"


# ── SC-004: every accepted handle form selects the same Mission ─────────────


def _scoped_payload(command: str, project: Path, extra: list[str]) -> dict[str, Any]:
    result = _invoke(project, command, *extra)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    return payload


@pytest.mark.parametrize("command", _COMMAND_IDS)
def test_handle_forms_select_the_same_mission(command: str, project: Path) -> None:
    """FR-005, SC-004: mission_id, mid8 and slug are equivalent. #6798 #6801."""
    base = ["--dry-run", "--json"]
    by_id = _scoped_payload(command, project, ["--mission", _A_MID, *base])
    by_mid8 = _scoped_payload(command, project, ["--mission", _A_MID[:8], *base])
    by_slug = _scoped_payload(command, project, ["--mission", _A_SLUG, *base])

    reports = [json.dumps(payload.get("mission")) for payload in (by_id, by_mid8, by_slug)]
    assert reports == [json.dumps(_A_SLUG)] * 3, reports


# ── FR-008: an unknown handle fails closed and mutates nothing ──────────────


@pytest.mark.parametrize("command", _COMMAND_IDS)
def test_unknown_handle_fails_closed(command: str, project: Path) -> None:
    """A typo must never degrade into a corpus-wide migration."""
    result = _invoke(project, command, "--mission", "ghost")

    assert result.exit_code != 0, result.output
    assert "ghost" in result.output
    assert not _target_changed(command, project, _A_SLUG)
    assert not _target_changed(command, project, _B_SLUG)


# ── FR-006 / SC-003: no ``--mission`` keeps the corpus-wide default ─────────


@pytest.mark.parametrize("command", _COMMAND_IDS)
def test_omitted_mission_reports_a_null_scope(command: str, project: Path) -> None:
    """The payload states the scope, so a scripted caller never has to guess it."""
    result = _invoke(project, command, "--dry-run", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["mission"] is None


@pytest.mark.parametrize("command", _COMMAND_IDS)
def test_omitted_mission_keeps_the_corpus_wide_default(command: str, project: Path) -> None:
    """Same-fixture positive control: the scoped filter must not break the walk."""
    result = _invoke(project, command, "--json")
    assert result.exit_code == 0, result.output

    assert _target_changed(command, project, _A_SLUG)
    assert _target_changed(command, project, _B_SLUG)


# ── NFR-002: dry-run writes nothing, and a second run is a no-op ────────────


@pytest.mark.parametrize("command", _COMMAND_IDS)
def test_dry_run_writes_nothing(command: str, project: Path) -> None:
    result = _invoke(project, command, "--mission", _A_SLUG, "--dry-run", "--json")
    assert result.exit_code == 0, result.output

    assert not _target_changed(command, project, _A_SLUG)
    assert _unchanged_checks(command, project, _B_SLUG)


@pytest.mark.parametrize("command", _COMMAND_IDS)
def test_second_scoped_run_is_a_noop(command: str, project: Path) -> None:
    first = _invoke(project, command, "--mission", _A_SLUG, "--json")
    assert first.exit_code == 0, first.output
    assert _target_changed(command, project, _A_SLUG)

    second = _invoke(project, command, "--mission", _A_SLUG, "--json")
    assert second.exit_code == 0, second.output
    assert not _target_changed_for_second_run(command, project, _A_SLUG)


def _target_changed_for_second_run(command: str, project: Path, slug: str) -> bool:
    """True when a second run would have had more work to do."""
    payload_work = {
        "backfill-provenance": ("summary", "migrated"),
        "charter-encoding": ("normalized",),
        "rebaseline-dossier-hashes": ("summary", "rebaselined"),
    }[command]
    result = _invoke(project, command, "--mission", slug, "--dry-run", "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    for key in payload_work:
        payload = payload[key]
    return bool(payload)


# ── FR-004 / SC-002: the global charter store is excluded and reported ──────


def test_charter_encoding_scoped_run_reports_global_store_exclusion(project: Path) -> None:
    """The store is skipped, reported, and provably untouched (the operator ruling)."""
    global_charter = project / ".kittify" / "charter" / "charter.md"
    before = global_charter.read_bytes()

    result = _run(project, "charter-encoding", "--mission", _A_SLUG, "--yes", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["mission"] == _A_SLUG
    assert payload["global_store_excluded"] is True
    assert global_charter.read_bytes() == before
    assert not (project / ".kittify" / "charter" / "charter.md.bak").exists()


def test_charter_encoding_scoped_run_reports_exclusion_in_human_output(project: Path) -> None:
    global_charter = project / ".kittify" / "charter" / "charter.md"
    before = global_charter.read_bytes()

    result = _run(project, "charter-encoding", "--mission", _A_SLUG, "--yes")

    assert result.exit_code == 0, result.output
    assert "excluded" in result.output.lower()
    assert global_charter.read_bytes() == before


def test_charter_encoding_scoped_run_skips_a_global_store_ambiguity(project: Path) -> None:
    """A pre-existing global-store problem never fails a valid scoped run."""
    # A lone 0x80 byte is undecodable as UTF-8 and unrecoverable as an encoding.
    (project / ".kittify" / "charter" / "charter.md").write_bytes(b"\x80\x81\x82")

    result = _run(project, "charter-encoding", "--mission", _A_SLUG, "--yes", "--json")

    assert result.exit_code == 0, result.output
    assert _is_utf8(_path(project, _A_SLUG, "charter", "charter.md"))


# ── scoped no-op wording: never claim corpus scope for a one-Mission run ────


def test_backfill_provenance_scoped_no_op_names_the_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Mission with no matrix reports that, not "the corpus already carries provenance"."""
    root = tmp_path / "project"
    root.mkdir()
    _write_mission(root, slug=_A_SLUG, mission_id=_A_MID)
    _path(root, _A_SLUG, "acceptance-matrix.json").unlink()
    monkeypatch.chdir(root)

    result = _run(root, "backfill-provenance", "--mission", _A_SLUG)

    assert result.exit_code == 0, result.output
    assert "No acceptance matrix found" in result.output
    assert "corpus" not in result.output.lower()


def test_mission_scoped_summaries_never_claim_corpus_scope(project: Path) -> None:
    """Both human renderers name the Mission when scoped (r2 F4/F5)."""
    provenance = _run(project, "backfill-provenance", "--mission", _A_SLUG)
    assert provenance.exit_code == 0, provenance.output
    scope_lines = [line.strip() for line in provenance.output.splitlines() if line.strip().startswith("Scope")]
    assert scope_lines and scope_lines[0].endswith(_A_SLUG), provenance.output

    encoding = _run(project, "charter-encoding", "--mission", _A_SLUG, "--yes")
    assert encoding.exit_code == 0, encoding.output
    assert f"Mission {_A_SLUG} charter content" in encoding.output
