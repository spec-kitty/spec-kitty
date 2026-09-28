"""#5254 (FR-005/FR-006/FR-007, US2/SC-002): `spec-kitty research` must scaffold
`research.md` and `data-model.md` for a research-type mission from the research
pack's SHIPPED templates, resolved through the canonical 6-tier resolver
(`specify_cli.runtime.resolver.resolve_template`) — not the legacy 5-tier
`core.project_resolver.resolve_template_path`, which has no package-default
tier and asks for filenames the pack does not ship.

RED-first (ADR 2026-07-17-1): against the pre-fix `research.py` (asking the
legacy resolver for `research.md` / `data-model.md` verbatim, which no tier —
including `~/.kittify` — ships under those names), this test's positive
control fails: `research.md` / `data-model.md` are never created for ANY
mission type.

Driven through the pre-existing entry point (the real `research` command),
mirroring `test_research_preservation.py`'s harness.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import research as research_mod

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_REPO_ROOT = Path(__file__).resolve().parents[4]
_RESEARCH_PACK_TEMPLATES = _REPO_ROOT / "packs" / "built-in" / "missions" / "research" / "templates"

# Production-shaped identity: a 26-char Crockford-alphabet ULID + its 8-char mid8.
MISSION_ID = "01KVW9RSRCHTEMPLATES0TESTA"
MID8 = MISSION_ID[:8]
assert len(MISSION_ID) == 26
SLUG = "research-templates"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"

FILLED_PLAN = """\
# Implementation Plan — Research Templates

## Technical Context
Language/Version: Python 3.11
Primary Dependencies: typer, rich
Storage: filesystem

## Architecture
Regression fixture for #5254 — research.md/data-model.md must scaffold from
the research pack's shipped templates via the canonical resolver.
"""

RESEARCH_MD = Path("research.md")
DATA_MODEL_MD = Path("data-model.md")
EVIDENCE_LOG_CSV = Path("research") / "evidence-log.csv"
SOURCE_REGISTER_CSV = Path("research") / "source-register.csv"


@pytest.fixture(autouse=True)
def _empty_global_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the global tier at an empty directory. The per-worker isolated
    HOME can already hold a seeded ``~/.kittify/missions/`` from an earlier
    test on the same worker, which would win over the package default and
    make these assertions depend on test order."""
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path_factory.mktemp("empty-kittify-home")))


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True)


def _init_repo(repo_root: Path) -> None:
    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "research-templates@example.test")
    _git(repo_root, "config", "user.name", "Research Templates")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    from specify_cli.migration.backfill_topology import _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _seed_mission(repo_root: Path, *, mission_type: str = "research") -> Path:
    """Seed a flattened (SINGLE_BRANCH) mission with a FILLED primary plan and
    no research artifacts yet. Returns the primary mission dir. The global
    tier is empty (``_empty_global_home``), so absent a project override only
    the package-default tier can satisfy a resolution."""
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
    runs, mirroring ``test_research_preservation.py``'s harness."""
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
# Positive control (SC-002): a research mission scaffolds all 4 advertised
# artifacts from the shipped templates, each non-empty and byte-identical to
# the pack default.
# --------------------------------------------------------------------------- #
def test_research_mission_scaffolds_all_four_shipped_templates(tmp_path: Path) -> None:
    primary_dir = _seed_mission(tmp_path, mission_type="research")

    result = _run_research(tmp_path)

    assert result.exit_code == 0, result.output

    expectations = {
        RESEARCH_MD: _RESEARCH_PACK_TEMPLATES / "research-template.md",
        DATA_MODEL_MD: _RESEARCH_PACK_TEMPLATES / "data-model-template.md",
        EVIDENCE_LOG_CSV: _RESEARCH_PACK_TEMPLATES / "research" / "evidence-log.csv",
        SOURCE_REGISTER_CSV: _RESEARCH_PACK_TEMPLATES / "research" / "source-register.csv",
    }
    for dest_rel, template_path in expectations.items():
        dest = primary_dir / dest_rel
        assert dest.exists(), f"{dest_rel} was not created"
        dest_bytes = dest.read_bytes()
        assert len(dest_bytes) > 0, f"{dest_rel} is empty"
        assert dest_bytes == template_path.read_bytes(), f"{dest_rel} does not match the shipped template {template_path}"


# --------------------------------------------------------------------------- #
# Negative control (SC-003): a software-dev mission creates 0 files and
# reports truthfully that no template exists.
# --------------------------------------------------------------------------- #
def test_software_dev_mission_creates_nothing(tmp_path: Path) -> None:
    primary_dir = _seed_mission(tmp_path, mission_type="software-dev")

    result = _run_research(tmp_path)

    assert result.exit_code == 0, result.output
    for rel in (RESEARCH_MD, DATA_MODEL_MD, EVIDENCE_LOG_CSV, SOURCE_REGISTER_CSV):
        assert not (primary_dir / rel).exists(), f"{rel} was fabricated for a software-dev mission"
    assert "no research template" in result.output.lower(), result.output


# --------------------------------------------------------------------------- #
# #4926 guard, sharing the positive control's fixture: a pre-existing
# authored research.md is untouched without --force.
# --------------------------------------------------------------------------- #
def test_preexisting_research_md_untouched_without_force(tmp_path: Path) -> None:
    primary_dir = _seed_mission(tmp_path, mission_type="research")
    dest = primary_dir / RESEARCH_MD
    original_content = "# Authored research\n\nReal findings.\n"
    dest.write_text(original_content, encoding="utf-8")

    result = _run_research(tmp_path)

    assert result.exit_code == 0, result.output
    assert dest.read_text(encoding="utf-8") == original_content, "research.md changed on a plain (no --force) re-run"
