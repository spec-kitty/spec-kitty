"""NFR-006 / AC-9 / FR-132 — subprocess-based CLI visibility test.

WP05 (reframed via spec commit 25066955) delivers **deterministic Rich-formatted
output** for catalog-miss warnings.  This is a cosmetic UX improvement that
is particularly valuable under Slice F's multiplied catalog sources (FR-132).

Before the CLI logging bootstrap (FR-130 + FR-131) is installed, Python's
built-in defaults already make the raw warning text visible in stderr — so
asserting on ``"Charter catalog miss"`` alone is a false-positive RED
(cycle-1 reviewer finding, review-cycle-1.md).  The key distinguishing
marker is the **Rich-formatted level prefix**: RichHandler writes

    WARNING  Charter catalog miss for …

(``WARNING`` followed by exactly TWO spaces, NO colon) whereas Python's raw
``logging.lastResort`` handler writes

    Charter catalog miss for …

(no level prefix at all) and ``warnings.warn`` writes

    source.py:N: WarningClass: Charter catalog miss for …

(source-location prefix, single colon).  Neither raw format matches
``r"WARNING\\s{2,}Charter catalog miss"``.

This test is the executable specification for AC-9: it MUST fail at the
pre-bootstrap commit and MUST pass only after the bootstrap installs the
RichHandler.

**ATDD discipline (C-011):**
- Cycle-1 RED commit (47389d40): test used plain marker — was a
  FALSE-POSITIVE RED (passed before bootstrap).
- Cycle-2 RED (this file at pre-bootstrap parent): assertion now targets
  Rich format — FAILS before bootstrap, PASSES after.

Scenario 5 / AC-9 pinned by ``test_typoed_styleguide_produces_visible_stderr_warning``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]

# The warning text fragment that MUST appear in stderr (or stdout) when a
# charter selects a styleguide ID that is not present in the doctrine catalog.
# This string appears in ``charter.activation._catalog_miss.emit_catalog_miss_warning``
# as the common prefix of every catalog-miss message.
_CATALOG_MISS_MARKER: str = "Charter catalog miss"

# The typo'd styleguide ID we inject into the fixture charter.  Using a name
# that is obviously absent from the built-in catalog avoids false positives.
_TYPO_ID: str = "does-not-exist-typo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source_version() -> str:
    with open(_REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def _git_init(repo: Path) -> None:
    """Initialise a minimal git repo so the charter resolver accepts the path."""
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "atdd@example.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "ATDD"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo, check=True, capture_output=True,
    )


def _write_minimal_kittify(repo: Path) -> None:
    """Write the bare-minimum .kittify scaffold so schema gate passes."""
    kittify = repo / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)

    # metadata.yaml — schema_version 3 satisfies the migration gate
    (kittify / "metadata.yaml").write_text(
        textwrap.dedent("""\
            spec_kitty:
              version: 3.2.0
              initialized_at: '2026-01-01T00:00:00'
              schema_version: 3
            """),
        encoding="utf-8",
    )

    # config.yaml — minimal agents block; charter_packs.org block absent (no org layer)
    (kittify / "config.yaml").write_text(
        textwrap.dedent("""\
            agents:
              available:
                - claude
            """),
        encoding="utf-8",
    )

    # kitty-specs/ directory satisfies the assert_initialized check
    (repo / "kitty-specs").mkdir(exist_ok=True)


def _write_charter_with_typo(repo: Path, typo_id: str) -> None:
    """Seed a charter that selects a deliberately typo'd styleguide ID.

    #2773 consolidated the compiled bundle into the authoritative
    ``.kittify/charter/charter.yaml``; doctrine selections are now read from
    ``governance.charter.selected_<kind>`` (via
    ``charter.activation.sync.load_governance_config``), NOT from a fenced YAML block in
    the curated ``charter.md``. The typo'd ID therefore lives in
    ``charter.yaml`` so the catalog-miss warning path is exercised end-to-end.
    A minimal ``charter.md`` companion is still written because the bootstrap
    charter-context path requires the curated ``charter.md`` to exist.
    """
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)

    charter_md = textwrap.dedent("""\
        # Test Project Charter

        > Version: 1.0.0

        ## Purpose

        Integration-test charter whose authoritative doctrine selection (in
        the sibling charter.yaml) names a deliberately typo'd styleguide so the
        catalog-miss warning path is exercised end-to-end.
        """)
    (charter_dir / "charter.md").write_text(charter_md, encoding="utf-8")

    charter_yaml = textwrap.dedent(f"""\
        schema_version: '2.0.0'
        governance:
          doctrine:
            selected_styleguides:
              - {typo_id}
        """)
    (charter_dir / "charter.yaml").write_text(charter_yaml, encoding="utf-8")


def _run_cli(project_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Invoke the Spec Kitty CLI in a subprocess against *project_path*.

    Environment is isolated to the source tree (no installed package
    interference) — mirrors the ``run_cli`` fixture in conftest but
    written inline so this test file is self-contained and clearly
    pinned to the subprocess contract mandated by NFR-006.
    """
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONPATH"] = str(_REPO_ROOT / "src")
    env["SPEC_KITTY_CLI_VERSION"] = _source_version()
    env["SPEC_KITTY_TEST_MODE"] = "1"
    env["SPEC_KITTY_TEMPLATE_ROOT"] = str(_REPO_ROOT)
    # Prevent the upgrade-check notice from polluting stderr
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    # Prevent the Rich live-display from failing in headless mode
    env["PWHEADLESS"] = "1"

    command = [sys.executable, "-m", "specify_cli.__init__", *args]
    return subprocess.run(
        command,
        cwd=str(project_path),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_with_typo_charter(tmp_path: Path) -> Path:
    """Minimal Spec Kitty project whose charter has a typo'd styleguide ID."""
    repo = tmp_path / "typo-charter-project"
    repo.mkdir()
    _git_init(repo)
    _write_minimal_kittify(repo)
    _write_charter_with_typo(repo, _TYPO_ID)
    return repo


# ---------------------------------------------------------------------------
# AC-9 / Scenario 5 — the pinned test
# ---------------------------------------------------------------------------


def test_typoed_styleguide_produces_visible_stderr_warning(
    project_with_typo_charter: Path,
) -> None:
    """FR-132 / AC-9 / NFR-006 — catalog-miss MUST appear as Rich-formatted WARNING.

    A charter that selects a styleguide ID that does not exist in the
    catalog MUST cause a ``CharterCatalogMissWarning`` to be emitted via
    ``warnings.warn``.  After WP05's CLI logging bootstrap (FR-130 + FR-131),
    that warning is routed through ``logging.captureWarnings(True)`` →
    root logger → a RichHandler stderr handler.

    **Why the assertion targets the Rich format (cycle-2 tightening):**

    Cycle-1's assertion (``_CATALOG_MISS_MARKER in combined_output``) was a
    false-positive RED: Python's ``logging.lastResort`` fallback and
    ``warnings.warn`` machinery BOTH already write the plain marker text to
    stderr without any bootstrap.  The reviewer (review-cycle-1.md) diagnosed
    this as Case C/D and required the assertion to target formatting that ONLY
    RichHandler produces.

    RichHandler writes:  ``WARNING  <message>`` (level + two spaces, no colon)
    lastResort writes:   ``<message>``          (no level prefix)
    warnings writes:     ``path:N: Class: <message>``  (source-location prefix)

    The regex ``r"WARNING\\s{{2,}}Charter catalog miss"`` matches only the
    Rich format.  This assertion is load-bearing: it fails at the
    pre-bootstrap commit and passes only after the bootstrap installs the
    RichHandler (real ATDD red→green per C-011).

    Intentionally subprocess-based per NFR-006: in-process pytest warning
    capture does NOT reflect CLI operator visibility.
    """
    result = _run_cli(
        project_with_typo_charter,
        "charter", "context", "--action", "implement",
    )

    # Combine stdout + stderr: the bootstrap routes warnings to stderr but we
    # also scan stdout in case the handler uses a combined stream.
    combined_output = result.stdout + result.stderr

    # --- Primary assertion: Rich-format level prefix (load-bearing) --------
    # RichHandler emits "WARNING  <message>" (two spaces, no colon after level).
    # Python's raw logging.lastResort emits "<message>" with NO level prefix.
    # warnings.warn emits "path:N: WarningClass: <message>" (source-location).
    # Only the Rich format matches this pattern — making the bootstrap
    # the ONLY change that turns this assertion from FAIL to PASS.
    rich_pattern = re.compile(r"WARNING\s{2,}" + re.escape(_CATALOG_MISS_MARKER))
    assert rich_pattern.search(combined_output), (
        f"Expected Rich-formatted WARNING record matching {rich_pattern.pattern!r} "
        f"in subprocess output but it was not found.\n\n"
        f"This means the CLI is not producing RichHandler-formatted output. "
        f"The bootstrap (FR-130/FR-131) in src/specify_cli/cli/logging_bootstrap.py "
        f"MUST call install_cli_logging_bootstrap() before the Typer app runs so "
        f"that warnings.warn calls route through RichHandler, not lastResort.\n\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
        f"--- returncode ---\n{result.returncode}\n\n"
        f"Cycle-2 note: if you see plain 'Charter catalog miss' without the "
        f"'WARNING  ' prefix, the bootstrap is absent (false-positive RED "
        f"from cycle 1 — see review-cycle-1.md and spec commit 25066955)."
    )

    # --- Secondary assertion: the typo'd ID is attributed correctly ---------
    # Confirms the miss is from our fixture charter, not a spurious built-in
    # catalog miss on an unrelated artifact.
    assert _TYPO_ID in combined_output, (
        f"The typo'd styleguide ID {_TYPO_ID!r} should appear in the warning "
        f"message but was not found in the subprocess output.\n\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
    )
