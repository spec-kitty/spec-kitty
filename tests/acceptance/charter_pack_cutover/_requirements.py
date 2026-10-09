"""Closed requirement data for the charter-pack cutover acceptance suite (#3732).

Everything here is hard-coded from ``kitty-specs/charter-pack-cutover-01M491G6/spec.md``
on purpose: the suite must not derive its expectations from the code it judges.

* :data:`REQUIRED_IDS` is the closed list of ids every test file's ``covers(...)``
  decorators must span (``test_traceability.py`` checks it against the spec text).
* :data:`FR018_FORBIDDEN_TOKENS`, :data:`FR018_LIVING_ROOTS` and
  :data:`FR018_HISTORICAL_PREFIXES` restate spec FR-018's closed lists. The FR-018
  gate (WP25) is never imported to obtain them.
* :data:`FR018_FLOOR` is the scanned-file floor, a literal recorded at the mission
  base (:data:`FR018_FLOOR_BASE_SHA`) with :func:`count_living_text_files`.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

MISSION_SLUG = "charter-pack-cutover-01M491G6"

#: Repository root (``tests/acceptance/charter_pack_cutover/_requirements.py`` -> repo).
REPO_ROOT = Path(__file__).resolve().parents[3]
MISSION_DIR = REPO_ROOT / "kitty-specs" / MISSION_SLUG
SPEC_PATH = MISSION_DIR / "spec.md"

# --------------------------------------------------------------------------------------
# Id grammar (``covers(...)`` validates every id against it)
# --------------------------------------------------------------------------------------

DM_IDS: tuple[str, ...] = (
    "DM-01M497EW60HNWWJQCXDFA99R0H",
    "DM-01M497F0NAQARAK3JZFVWF1SD0",
)

ID_GRAMMAR = re.compile(r"^(?:FR-\d{3}|NFR-\d{3}|SC-\d{3}|US\d-\d|C-\d{3}|OD-\d+|" + "|".join(re.escape(dm) for dm in DM_IDS) + r"|INV:.+|EC:.+)$")

# --------------------------------------------------------------------------------------
# Closed list of required ids (spec.md)
# --------------------------------------------------------------------------------------

FR_IDS = tuple(f"FR-{n:03d}" for n in range(1, 20))
NFR_IDS = tuple(f"NFR-{n:03d}" for n in range(1, 5))
SC_IDS = tuple(f"SC-{n:03d}" for n in range(1, 6))
US_IDS = (
    *(f"US1-{n}" for n in range(1, 6)),
    *(f"US2-{n}" for n in range(1, 8)),
    *(f"US3-{n}" for n in range(1, 5)),
    *(f"US4-{n}" for n in range(1, 3)),
    *(f"US5-{n}" for n in range(1, 3)),
)

#: First cell of every row of the spec's "FR-012 migration inventory" table.
INVENTORY_ITEMS: tuple[str, ...] = (
    "Org packs list",
    "Single-pack legacy form",
    "Flat org list",
    "Governance selection",
    "Tracker ownership",
    "Interview answers",
    "Activation entry key",
    "Project layer",
    "Synthesis manifest",
    "Provenance sidecars",
    "Pack-skill manifest",
    "Ignore rules",
    "Stale activation lists",
    "Stale kind gate",
    "Released `minimal` kind gate",
    "Normalizer empty lists",
    "Installed skills",
    "Customised lists, `minimal`-equal lists",
)

#: Bold lead of every bullet under the spec's "### Edge Cases".
EDGE_CASES: tuple[str, ...] = (
    "Both project roots present",
    "Canonical and legacy config keys both present",
    "Preset id resolution",
    "Pack without presets",
    "Stale list plus one customisation",
    "List equal to the `minimal` preset",
    "Deliberate `[]` for a kind",
    "Lists mixing default ids with other ids",
    "Saved script calling `spec-kitty doctrine fetch`",
    "Uncommitted edits in moved or rewritten files",
    "Windows",
    'User-chosen path values containing "doctrine"',
    "Lane worktrees created before the upgrade",
)

OD_IDS = tuple(f"OD-{n}" for n in range(1, 11))

REQUIRED_IDS: tuple[str, ...] = (
    *FR_IDS,
    *NFR_IDS,
    *SC_IDS,
    *US_IDS,
    *(f"INV:{item}" for item in INVENTORY_ITEMS),
    *(f"EC:{title}" for title in EDGE_CASES),
    *OD_IDS,
    *DM_IDS,
)

# --------------------------------------------------------------------------------------
# FR-018 closed lists (restated from the spec, never imported from the gate)
# --------------------------------------------------------------------------------------

#: The twelve skill ids FR-008 removes (seven ``spk-doctrine-*`` plus the five folded skills),
#: plus ``spec-kitty-constitution-doctrine`` whose historical rename migration is neutralised.
REMOVED_SKILL_IDS: tuple[str, ...] = (
    "spk-doctrine-bulk-edit",
    "spk-doctrine-charter",
    "spk-doctrine-glossary",
    "spk-doctrine-profile-load",
    "spk-doctrine-semantic-compression",
    "spk-doctrine-show-me",
    "spk-doctrine-spdd-reasons",
    "spec-kitty-charter-doctrine",
    "spec-kitty-glossary-context",
    "spec-kitty-bulk-edit-classification",
    "spec-kitty-spdd-reasons",
    "ad-hoc-profile-load",
)
RETIRED_EXTRA_SKILL_IDS: tuple[str, ...] = ("spec-kitty-constitution-doctrine",)

FR018_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "doctrine pack",
    "spk-doctrine-",
    "spec-kitty doctrine",
    "doctrine.org.packs",
    "organisation_packs",
    ".kittify/doctrine",
    "accompanies_doctrine_pack",
    "CharterPackManager",
    "CharterPackConfigError",
    "CHARTER_PACK_CONFIG_INVALID",
    "charter pack apply",
    "Pack Default Charter",
    "default charter pack",
    "BUILTIN_PACKS",
    "specify_cli.doctrine",
    "doctor doctrine",
    "--doctrine-mode",
    "doctrine_mode",
    "doctrine_skill",
    "doctrine_pack_id",  # OD-1 renames it to charter_pack_id
    *REMOVED_SKILL_IDS,
)

#: Living surfaces in scope (spec FR-018), as repository-relative path prefixes / files.
FR018_LIVING_ROOTS: tuple[str, ...] = (
    "src/",
    "packs/",
    "docs/",
    ".github/workflows/",
    "Makefile",
    "CLAUDE.md",
    # generated agent copies tracked in this repository (CLAUDE.md agent table)
    ".claude/commands/",
    ".github/prompts/",
    ".gemini/commands/",
    ".cursor/commands/",
    ".qwen/commands/",
    ".opencode/command/",
    ".windsurf/workflows/",
    ".kilocode/workflows/",
    ".augment/commands/",
    ".amazonq/prompts/",
    ".kiro/prompts/",
    ".agent/workflows/",
    ".llxprt/commands/",
    ".agents/skills/",
)

#: Historical roots (spec FR-018) plus the shared ``FORBIDDEN_SCAN_ROOTS``
#: (``tests/_support/terminology_scope.py`` at base), as path prefixes.
FR018_HISTORICAL_PREFIXES: tuple[str, ...] = (
    "kitty-specs/",
    "docs/adr/",
    "docs/reports/",
    "docs/plans/",
    "docs/archive/",
    ".kittify/evidence/",
    ".kittify/migrations/",
    # FORBIDDEN_SCAN_ROOTS at base
    "architecture/",
    ".kittify/",
    "tests/",
    "docs/migrations/",
)

#: Tombstone files (spec FR-018), exempt by file. ``m_*.py`` migrations are matched by pattern.
FR018_TOMBSTONE_FILES: tuple[str, ...] = (
    "src/specify_cli/skills/retired.py",
    "src/charter/offering/packs/retired_fields.py",
    "src/specify_cli/upgrade/metadata.py",
)
FR018_TOMBSTONE_PATTERN = re.compile(r"^src/specify_cli/upgrade/migrations/m_[^/]*\.py$")

#: Scanned-file floor (SC-003): tracked text files under the living roots minus the
#: historical roots and tombstone files, counted with :func:`count_living_text_files`
#: at :data:`FR018_FLOOR_BASE_SHA`. Literal on purpose: never derive it from the gate.
FR018_FLOOR = 2459
FR018_FLOOR_BASE_SHA = "fcf7a82710d2424a231c2f7b23f490ffde8bd9ab"


def is_living_path(path: str) -> bool:
    """Whether repository-relative *path* is on an FR-018 living surface and not historical."""
    if not any(path == root or path.startswith(root) for root in FR018_LIVING_ROOTS):
        return False
    if any(path.startswith(prefix) for prefix in FR018_HISTORICAL_PREFIXES):
        return False
    if "/archive/" in f"/{path}":
        return False
    if path in FR018_TOMBSTONE_FILES:
        return False
    return not FR018_TOMBSTONE_PATTERN.match(path)


def _is_text(blob: bytes) -> bool:
    if b"\x00" in blob:
        return False
    try:
        blob.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _tree_entries(repo: Path, sha: str) -> list[tuple[str, str, str]]:
    """``(mode, object, path)`` for every blob in *sha*'s tree."""
    raw = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "-z", "--full-tree", sha],
        check=True,
        capture_output=True,
    ).stdout
    entries: list[tuple[str, str, str]] = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, kind, obj = meta.decode().split()
        if kind == "blob":
            entries.append((mode, obj, path.decode("utf-8", "surrogateescape")))
    return entries


def _read_blobs(repo: Path, objects: Iterable[str]) -> dict[str, bytes]:
    wanted = list(dict.fromkeys(objects))
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=("\n".join(wanted) + "\n").encode(),
        check=True,
        capture_output=True,
    )
    out = proc.stdout
    blobs: dict[str, bytes] = {}
    pos = 0
    for obj in wanted:
        header_end = out.index(b"\n", pos)
        size = int(out[pos:header_end].split()[2])
        start = header_end + 1
        blobs[obj] = out[start : start + size]
        pos = start + size + 1
    return blobs


def living_text_files(repo: Path, sha: str) -> list[str]:
    """Tracked regular text files of *sha* on FR-018 living surfaces (symlinks excluded)."""
    candidates = [(obj, path) for mode, obj, path in _tree_entries(repo, sha) if mode in {"100644", "100755"} and is_living_path(path)]
    blobs = _read_blobs(repo, (obj for obj, _ in candidates))
    return sorted(path for obj, path in candidates if _is_text(blobs[obj]))


def count_living_text_files(repo: Path, sha: str) -> int:
    """The FR-018 scanned-file floor measure at *sha*."""
    return len(living_text_files(repo, sha))
