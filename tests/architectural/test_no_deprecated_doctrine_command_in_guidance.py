"""No living surface names a removed ``spec-kitty doctrine`` command (#4836, #3732).

The ``spec-kitty doctrine`` group was removed in mission
``charter-pack-cutover-01M491G6`` (#3732, FR-007): every former command has a
``charter`` home (FR-006) and the old spelling exits 2 as an unknown command.
Guidance that still names it sends an operator or an agent to a command that
does not exist, so this gate forbids it everywhere guidance lives:

* ``spec-kitty doctrine`` followed by anything (the retired invocation);
* the bare backticked or RST form of a removed command, e.g.
  ``\\`doctrine asset list\\``` (the closed list ``_REMOVED`` below; the group
  can no longer be introspected).

Scope: the shipped skills and schemas under ``src/charter/offering``, both
packs, the living docs, the CI workflows, ``Makefile``, ``AGENTS.md``,
``CLAUDE.md``, ``README.md`` and the full text of every Python file under
``src/`` and ``scripts/``, docstrings and comments included (the group they
used to describe no longer exists). There is no allowlist; the out-of-scope
roots are listed in ``_EXCLUDED_PREFIXES`` and ``_EXCLUDED_GLOBS`` with a
reason each (see docs/development/reference/terminology-exemptions.md).
"""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app
from tests._support.terminology_scope import FORBIDDEN_SCAN_ROOTS

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: The former commands and sub-groups of the removed ``doctrine`` group (FR-006 table).
_REMOVED = ("fetch", "new", "validate", "org", "pack", "regenerate-graph", "asset", "mission-type")

#: The retired invocation: ``spec-kitty doctrine`` not followed by a word character
#: or a hyphen (so a hyphenated name such as ``doctrine-daphne`` is not an invocation).
_INVOCATION = re.compile(r"spec-kitty doctrine(?![\w-])")
#: The bare backticked (Markdown) or double-backticked (RST) form of a removed command.
_BARE = re.compile(r"`{1,2}doctrine (?:" + "|".join(re.escape(name) for name in _REMOVED) + r")(?![\w-])")

#: Text trees scanned for guidance (text suffixes only).
_TEXT_ROOTS = ("src/charter/offering", "packs", "docs", ".github/workflows")
_TEXT_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".txt", ".toml", ".json"})
#: Single living files outside those trees.
_SINGLE_FILES = ("Makefile", "AGENTS.md", "CLAUDE.md", "README.md")
#: Python trees scanned in full text (string literals, docstrings, comments).
_PYTHON_ROOTS = ("src", "scripts")

#: Out of scope, each for a reason:
#: - FORBIDDEN_SCAN_ROOTS: the shared terminology-exempt roots (historical records,
#:   ADRs, archives, migrations runbooks, missions, tests, .kittify/).
#: - docs/plans/: plans record how past work was planned and delivered.
#: - docs/changelog/: released sections and the FR-017 Before/After quote the old
#:   spelling (the section-aware treatment is FR-018's).
#: - docs/development/docs-retrieval-index.yaml: generated from every docs page,
#:   the historical roots included.
_EXCLUDED_PREFIXES = (
    *FORBIDDEN_SCAN_ROOTS,
    "docs/plans/",
    "docs/changelog/",
    "docs/development/docs-retrieval-index.yaml",
)
#: The cutover migration must spell the legacy literals it rewrites (occurrence-map exception).
_EXCLUDED_GLOBS = ("src/specify_cli/upgrade/migrations/m_*charter_pack_cutover*.py",)

#: Non-vacuity floor: the measured scan count, rounded down to the nearest 100.
_MIN_FILES_SCANNED = 2500


def _offenders(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        found.extend((lineno, match.group(0)) for pattern in (_INVOCATION, _BARE) for match in pattern.finditer(line))
    return found


def _is_excluded(rel: str) -> bool:
    return rel.startswith(_EXCLUDED_PREFIXES) or any(fnmatch(rel, glob) for glob in _EXCLUDED_GLOBS)


def _candidates() -> list[Path]:
    paths = [path for root in _TEXT_ROOTS for path in (_REPO_ROOT / root).rglob("*") if path.suffix in _TEXT_SUFFIXES]
    paths += [path for root in _PYTHON_ROOTS for path in (_REPO_ROOT / root).rglob("*.py")]
    paths += [_REPO_ROOT / name for name in _SINGLE_FILES]
    return paths


def _scanned_files() -> list[Path]:
    return sorted(
        {path for path in _candidates() if path.is_file() and not _is_excluded(path.relative_to(_REPO_ROOT).as_posix())},
    )


def test_no_living_surface_names_a_removed_doctrine_command() -> None:
    violations = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{lineno}  {token}"
        for path in _scanned_files()
        for lineno, token in _offenders(path.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not violations, "`spec-kitty doctrine` was removed (#3732, FR-007); name the `spec-kitty charter` home from the FR-006 table:\n  " + "\n  ".join(
        violations
    )


def test_gate_reaches_a_real_file_count() -> None:
    scanned = {path.relative_to(_REPO_ROOT).as_posix() for path in _scanned_files()}
    assert len(scanned) >= _MIN_FILES_SCANNED
    # Each scope family is reached: a text tree, a Python tree and a single file.
    assert any(rel.startswith("packs/") for rel in scanned)
    assert any(rel.startswith("scripts/") and rel.endswith(".py") for rel in scanned)
    assert "AGENTS.md" in scanned
    assert "docs/api/cli-commands.md" in scanned


def test_gate_flags_a_planted_invocation() -> None:
    assert _offenders("Run `spec-kitty doctrine fetch --pack acme` before committing.")


def test_gate_flags_the_bare_backticked_form() -> None:
    assert _offenders("List them with `doctrine asset list`.")
    assert _offenders("RST spelling: ``doctrine validate``.")


def test_gate_flags_a_formerly_doctrine_only_command() -> None:
    assert _offenders("spec-kitty doctrine regenerate-graph --check")


def test_gate_flags_the_retired_token_in_prose() -> None:
    assert _offenders("Rich agent profile schema for spec-kitty doctrine framework")


def test_gate_flags_a_planted_python_docstring_and_comment() -> None:
    source = 'def hint(path):\n    """Mirrors ``spec-kitty doctrine validate``."""\n    # see `doctrine pack assemble`\n    return path\n'
    assert [lineno for lineno, _ in _offenders(source)] == [2, 3]


@pytest.mark.parametrize(
    "text",
    [
        "Load the doctrine-daphne profile.",
        "agent_profile:doctrine-daphne",
        "Author doctrine artifacts under the project pack.",
        "The doctrine validate step of the old flow",
        "spec-kitty charter pack regenerate-graph --check",
    ],
)
def test_gate_does_not_flag_content_sense_or_c004_names(text: str) -> None:
    assert _offenders(text) == []


#: Container-sense wording the cutover renamed ("doctrine tree" -> charter pack tree). "doctrine
#: artifacts" stays legal: it is the content sense, see the parametrized control above.
_CONTAINER_SENSE = re.compile(r"\bdoctrine (?:assets|tree|missions)\b", re.IGNORECASE)


def test_cli_help_does_not_call_the_pack_container_doctrine() -> None:
    commands = _REPO_ROOT / "src" / "specify_cli" / "cli" / "commands"
    violations = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{lineno}  {match.group(0)}"
        for path in sorted(commands.rglob("*.py"))
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        for match in _CONTAINER_SENSE.finditer(line)
    ]
    assert not violations, "name the charter pack / charter offering, not 'doctrine', in CLI help:\n  " + "\n  ".join(violations)


@pytest.mark.parametrize("name", _REMOVED)
def test_removed_list_matches_the_cli(name: str) -> None:
    """Positive control: every name in the closed list is an unknown command today."""
    result = CliRunner().invoke(app, ["doctrine", name, "--help"])
    assert result.exit_code == 2, result.output


def test_doctrine_group_is_unknown() -> None:
    result = CliRunner().invoke(app, ["doctrine", "--help"])
    assert result.exit_code == 2, result.output
