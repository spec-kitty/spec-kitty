"""#4926 regression: `research` must never fabricate a 0-byte "ready"
artifact when no template resolves, and `--force` must never truncate an
existing user-authored research asset to empty — for ALL FOUR assets
(`research.md`, `data-model.md`, `research/evidence-log.csv`,
`research/source-register.csv`). (WP02, FR-002/FR-005, US2)

RED-first (C-011): against the base `_copy_asset` / CSV-loop destroyer
(`if dest_path.exists(): dest_path.unlink(); dest_path.touch()`), every test
below fails — a fresh `research` run touches all four assets to 0 bytes and
reports them "ready", and `research --force` over real user content unlinks
then re-touches it to empty. Post-fix (T021), the write is routed through
``guard_destructive_overwrite`` and the skip decision is taken BEFORE any
filesystem mutation, so the destroyer never fabricates or truncates.

Driven through the pre-existing entry point (the real ``research`` command),
mirroring ``test_research_read_surface.py``'s harness (NFR-002 discipline):
``find_repo_root`` / ``get_project_root_or_exit`` are patched to the fixture
root and the seam resolves for real against the on-disk fixture.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import research as research_mod

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

# The real, shipped CSV templates (only the `research` mission type ships
# research.md/data-model.md-adjacent CSV templates with real content — no
# mission type ships a research.md/data-model.md template at all).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_RESEARCH_MISSION_CSV_TEMPLATES = _REPO_ROOT / "packs" / "built-in" / "missions" / "research" / "templates" / "research"

# Production-shaped identity: a 26-char Crockford-alphabet ULID + its 8-char mid8.
MISSION_ID = "01KVW9RSRCHPRESERVE0TESTAB"
MID8 = MISSION_ID[:8]
assert len(MISSION_ID) == 26
SLUG = "research-preservation"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"

# A substantive, FILLED plan (no template markers) so `validate_plan_filled`
# clears the gate ahead of `research`'s own scaffold work.
FILLED_PLAN = """\
# Implementation Plan — Research Preservation

## Technical Context
Language/Version: Python 3.11
Primary Dependencies: typer, rich
Storage: filesystem

## Architecture
Regression fixture for #4926 — no research/data-model template resolves for
this mission type, and no CSV template resolves for `software-dev` either.
"""

# The four research assets under test (relative to the mission dir).
RESEARCH_MD = Path("research.md")
DATA_MODEL_MD = Path("data-model.md")
EVIDENCE_LOG_CSV = Path("research") / "evidence-log.csv"
SOURCE_REGISTER_CSV = Path("research") / "source-register.csv"
ALL_FOUR_ASSETS = (RESEARCH_MD, DATA_MODEL_MD, EVIDENCE_LOG_CSV, SOURCE_REGISTER_CSV)


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True)


def _init_repo(repo_root: Path) -> None:
    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "research-preservation@example.test")
    _git(repo_root, "config", "user.name", "Research Preservation")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    from specify_cli.migration.backfill_topology import _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _seed_mission(repo_root: Path, *, mission_type: str = "software-dev") -> Path:
    """Seed a flattened (SINGLE_BRANCH) mission with a FILLED primary plan and
    no research artifacts yet. Returns the primary mission dir."""
    from mission_runtime import MissionTopology

    _init_repo(repo_root)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "mission_type": mission_type,
        "topology": MissionTopology.SINGLE_BRANCH.value,
    }
    primary_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)
    (primary_dir / "plan.md").write_text(FILLED_PLAN, encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "seed mission")
    return primary_dir


def _run_research(repo_root: Path, *, force: bool = False):  # type: ignore[no-untyped-def]
    """Invoke the REAL ``research`` command (pre-existing entry point) — a
    minimal single-command app so the root callback's global preflight never
    runs, mirroring ``test_research_read_surface.py``'s harness."""
    app = typer.Typer()
    app.command(name="research")(research_mod.research)
    runner = CliRunner()
    args = ["--mission", SLUG_WITH_MID8]
    if force:
        args.append("--force")
    with (
        patch.object(research_mod, "find_repo_root", return_value=repo_root),
        patch.object(research_mod, "get_project_root_or_exit", return_value=repo_root),
    ):
        return runner.invoke(app, args, catch_exceptions=False)


# --------------------------------------------------------------------------- #
# Acceptance Scenario 1 (spec.md US2): no template resolves anywhere for a
# `software-dev` mission → no 0-byte fabrication, no false "ready" claim, for
# ANY of the four assets — a plain (no --force) fresh run.
# --------------------------------------------------------------------------- #
def test_plain_research_does_not_fabricate_any_asset(tmp_path: Path) -> None:
    primary_dir = _seed_mission(tmp_path)

    result = _run_research(tmp_path)

    assert result.exit_code == 0, result.output
    for rel in ALL_FOUR_ASSETS:
        dest = primary_dir / rel
        assert not dest.exists(), f"{rel} was fabricated (0-byte 'ready' artifact) though no template resolves"
    # Honest reporting (T022): a clear "no template" outcome, not a false
    # green "N artifacts ready" success claim.
    assert "no research template" in result.output.lower(), result.output


# --------------------------------------------------------------------------- #
# Acceptance Scenario 2: an existing user-authored asset with real content and
# NO resolvable template — `research --force` must preserve it, not truncate
# to 0 bytes. The skip decision is taken BEFORE any unlink (never
# unlink-then-fabricate). Parametrized over all four assets (#4926 — all four
# share the same destroyer, so all four need the same regression coverage).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("asset_rel", ALL_FOUR_ASSETS, ids=lambda p: str(p))
def test_force_does_not_truncate_existing_user_content(tmp_path: Path, asset_rel: Path) -> None:
    primary_dir = _seed_mission(tmp_path)
    dest = primary_dir / asset_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    original_content = f"# User-authored {asset_rel.name}\n\nReal findings, not a stub.\n"
    dest.write_text(original_content, encoding="utf-8")

    result = _run_research(tmp_path, force=True)

    assert result.exit_code == 0, result.output
    assert dest.exists(), f"{asset_rel} vanished under --force"
    final_bytes = dest.read_bytes()
    assert len(final_bytes) > 0, f"{asset_rel} was truncated to 0 bytes under --force (#4926)"
    assert final_bytes.decode("utf-8") == original_content, f"{asset_rel}'s user-authored content was altered under --force"


# --------------------------------------------------------------------------- #
# Acceptance Scenario 3 (control, existing behavior — no regression): a plain
# (no --force) re-run over an existing user-authored asset preserves it
# unchanged.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("asset_rel", ALL_FOUR_ASSETS, ids=lambda p: str(p))
def test_no_force_rerun_preserves_existing_user_content(tmp_path: Path, asset_rel: Path) -> None:
    primary_dir = _seed_mission(tmp_path)
    dest = primary_dir / asset_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    original_content = f"# User-authored {asset_rel.name}\n\nReal findings, not a stub.\n"
    dest.write_text(original_content, encoding="utf-8")

    result = _run_research(tmp_path, force=False)

    assert result.exit_code == 0, result.output
    assert dest.read_text(encoding="utf-8") == original_content, f"{asset_rel} changed on a plain (no --force) re-run"


# --------------------------------------------------------------------------- #
# Acceptance Scenario 4 (control, NFR-002/R1 — legitimate templated path):
# the `research` mission type ships REAL CSV templates (evidence-log.csv,
# source-register.csv) — a mission of that type must still copy real content,
# never refuse the legitimate path. (research.md/data-model.md carry no
# template for ANY mission type in the shipped packs, so they are excluded
# from this control — their coverage is Scenario 1/2/3 above.)
# --------------------------------------------------------------------------- #
def test_csv_template_resolves_for_research_mission_type_copies_real_content(tmp_path: Path) -> None:
    primary_dir = _seed_mission(tmp_path, mission_type="research")
    # Materialize the real shipped CSV templates at the tier-1 (project
    # mission-specific) resolution path a real `spec-kitty init` + charter
    # activation would populate — this fixture doesn't run `init`, so the
    # template must be placed explicitly for `resolve_template_path` to find it.
    project_templates = tmp_path / ".kittify" / "missions" / "research" / "templates" / "research"
    project_templates.mkdir(parents=True, exist_ok=True)
    for csv_name in ("evidence-log.csv", "source-register.csv"):
        shutil.copy2(_RESEARCH_MISSION_CSV_TEMPLATES / csv_name, project_templates / csv_name)

    result = _run_research(tmp_path)

    assert result.exit_code == 0, result.output
    for rel in (EVIDENCE_LOG_CSV, SOURCE_REGISTER_CSV):
        dest = primary_dir / rel
        assert dest.exists(), f"{rel} was not created though the 'research' mission type ships a real template"
        content = dest.read_text(encoding="utf-8")
        assert len(content) > 0
        assert "smith" in content.lower() or "source_id" in content.lower() or "timestamp" in content.lower(), (
            f"{rel} does not look like the real shipped template content: {content[:200]!r}"
        )


# --------------------------------------------------------------------------- #
# Acceptance Scenario 5 (#4926 reporting-honesty regression, the common
# re-run path): a mission type whose CSV templates DO resolve (`research`) —
# create the artifacts once, then re-run WITHOUT `--force`. The second run's
# headline must NOT claim "No research template for mission type" (a template
# demonstrably resolved on the first run) — it must instead convey that the
# existing artifacts were preserved and that `--force` re-authorizes the
# overwrite. Pre-fix, the headline is keyed solely on `created_paths` being
# empty, which is also true on this re-run (nothing NEW was created because
# the existing CSVs are correctly preserved), so it prints the same false
# "no template" claim as the genuine no-template case.
# --------------------------------------------------------------------------- #
def test_rerun_without_force_reports_preserved_not_no_template(tmp_path: Path) -> None:
    primary_dir = _seed_mission(tmp_path, mission_type="research")
    project_templates = tmp_path / ".kittify" / "missions" / "research" / "templates" / "research"
    project_templates.mkdir(parents=True, exist_ok=True)
    for csv_name in ("evidence-log.csv", "source-register.csv"):
        shutil.copy2(_RESEARCH_MISSION_CSV_TEMPLATES / csv_name, project_templates / csv_name)

    first = _run_research(tmp_path)
    assert first.exit_code == 0, first.output
    for rel in (EVIDENCE_LOG_CSV, SOURCE_REGISTER_CSV):
        assert (primary_dir / rel).exists(), f"{rel} was not created on the first run"

    second = _run_research(tmp_path)  # no --force

    assert second.exit_code == 0, second.output
    lowered = second.output.lower()
    assert "no research template for mission type" not in lowered, (
        f"re-run falsely claimed 'no research template' though a template resolved and created "
        f"real artifacts on the first run — #4926 reporting-honesty regression:\n{second.output}"
    )
    assert "preserved" in lowered and "--force" in lowered, (
        f"re-run must convey that existing artifacts were preserved and that --force re-authorizes overwrite:\n{second.output}"
    )
    for rel in (EVIDENCE_LOG_CSV, SOURCE_REGISTER_CSV):
        assert (primary_dir / rel).exists(), f"{rel} vanished on the unauthorized re-run"
