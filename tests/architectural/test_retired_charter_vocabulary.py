"""FR-018 / SC-003 gate: the retired charter vocabulary stays off the living surfaces (#3732).

Mission ``charter-pack-cutover-01M491G6`` retired the "doctrine pack" vocabulary
for the three names of ADR ``2026-10-06-1`` (charter pack, active charter, charter
offering). This gate keeps the retired spellings from coming back on a living
surface. Every list below is closed and restates spec FR-018 ("FR-018 closed
lists"): no token, root or file may be added without a spec change.

Matching rules
--------------
* **Prose tokens**: case-insensitive substring (``doctrine pack`` also matches
  ``Doctrine Packs``).
* **Skill tokens**: case-sensitive, not preceded by ``[A-Za-z0-9-]``. A full skill
  id must also not be followed by ``[A-Za-z0-9-]``; the ``spk-doctrine-`` prefix
  covers the seven ``spk-doctrine-*`` ids, so it has no trailing boundary.
* **Identifier tokens**: case-sensitive, on identifier boundaries
  (``(?<![A-Za-z0-9_])token(?![A-Za-z0-9_])``), so a recorded migration id such as
  ``2.1.2_fix_charter_doctrine_skill`` does not match ``doctrine_skill``.

Every token is built from fragments, so this file does not flag itself.

Scope
-----
Living surfaces (spec FR-018): tracked regular text files (symlinks and binary
files are skipped) under ``src/`` (shipped skills live in
``src/charter/offering/skills/``), ``packs/``, ``docs/``, ``.github/workflows/``,
``Makefile``, ``CLAUDE.md`` (and ``AGENTS.md``, the same file) and the generated
agent copies tracked in this repository.

Exemptions are path-based only, never content-based:

* the historical roots of spec FR-018 (``docs/adr/``, ``docs/reports/``,
  ``docs/plans/``, archive roots, ``.kittify/evidence/``, ``.kittify/migrations/``)
  and the shared ``FORBIDDEN_SCAN_ROOTS`` (``tests/_support/terminology_scope.py``);
* released changelog content, section-aware: in ``docs/changelog/CHANGELOG.md``
  only the ``## [Unreleased]`` section is scanned, and inside it the entries whose
  bold headline starts ``Charter pack cutover:`` are exempt (the FR-017 Before/After
  must spell the old names). The other files under ``docs/changelog/`` that hold
  released notes are listed by name in :data:`_RELEASED_CHANGELOG_FILES`;
* by file, the cutover migration module and its ``_charter_pack_cutover_*``
  helpers and the legacy-state predicate module;
* the tombstone files, each with its reason in :data:`_TOMBSTONE_FILES`, and every
  ``src/specify_cli/upgrade/migrations/m_*.py`` module (historical migrations whose
  ``migration_id`` values are recorded in consumer projects).

Two exemptions are orchestrator rulings beyond the spec's closed list (escalated to
the owner, mission ``charter-pack-cutover-01M491G6``, WP22/WP24/WP25):

* the built-in glossary pack, by file (:data:`_GLOSSARY_PACK`): FR-013 requires its
  deprecated-term redirect entries to spell the retired terms;
* the generated docs retrieval index (:data:`_RETRIEVAL_INDEX`), section-aware: a
  page block is scanned only when the page it indexes is itself a living surface,
  so the index's copies of historical pages are not, and its living pages are.

Allowlist
---------
:data:`_ALLOWLIST` holds ``(path, token)`` pairs and may only name the C-004
identifiers (``doctrine-daphne``, ``DIRECTIVE_039``). Neither contains a token, so
it is empty.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

from scripts.docs.check_changelog_style import parse_section
from scripts.release.validate_release import unreleased_section
from tests._support.terminology_scope import FORBIDDEN_SCAN_ROOTS

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo, pytest.mark.docs_scoped]

_REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------------------
# Closed token list (spec FR-018 "Forbidden tokens"), built from fragments
# --------------------------------------------------------------------------------------

_D = "doc" + "trine"

#: Case-insensitive substrings.
_PROSE_TOKENS: tuple[str, ...] = (
    f"{_D} pack",
    f"spec-kitty {_D}",
    f"{_D}.org.packs",
    f".kittify/{_D}",
    "charter pack " + "apply",
    "Pack Default " + "Charter",
    "default charter " + "pack",
    f"specify_cli.{_D}",
    f"doctor {_D}",
    f"--{_D}-mode",
)

#: The ``spk-doctrine-*`` prefix (seven skill ids) and the five folded skill ids (FR-008).
_SKILL_PREFIX = f"spk-{_D}-"
_SKILL_IDS: tuple[str, ...] = (
    f"spec-kitty-charter-{_D}",
    "spec-kitty-glossary-" + "context",
    "spec-kitty-bulk-edit-" + "classification",
    "spec-kitty-spdd-" + "reasons",
    "ad-hoc-profile-" + "load",
)

#: Case-sensitive identifiers on identifier boundaries.
_IDENTIFIER_TOKENS: tuple[str, ...] = (
    "organisation" + "_packs",
    f"accompanies_{_D}_pack",
    "CharterPack" + "Manager",
    "CharterPack" + "ConfigError",
    "CHARTER_PACK_" + "CONFIG_INVALID",
    "BUILTIN" + "_PACKS",
    f"{_D}_mode",
    f"{_D}_skill",
    f"{_D}_pack_id",  # OD-1 renamed it to charter_pack_id
)

_TOKENS: tuple[str, ...] = (*_PROSE_TOKENS, _SKILL_PREFIX, *_SKILL_IDS, *_IDENTIFIER_TOKENS)


def _compile(token: str) -> re.Pattern[str]:
    escaped = re.escape(token)
    if token in _PROSE_TOKENS:
        return re.compile(escaped, re.IGNORECASE)
    if token == _SKILL_PREFIX:
        return re.compile(rf"(?<![A-Za-z0-9-]){escaped}")
    if token in _SKILL_IDS:
        return re.compile(rf"(?<![A-Za-z0-9-]){escaped}(?![A-Za-z0-9-])")
    return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])")


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple((token, _compile(token)) for token in _TOKENS)

# --------------------------------------------------------------------------------------
# Closed scope lists (spec FR-018 "Living surfaces" and "Historical roots")
# --------------------------------------------------------------------------------------

#: Living roots: directory prefixes (ending in ``/``) or single files.
_LIVING_ROOTS: tuple[str, ...] = (
    "src/",
    "packs/",
    "docs/",
    ".github/workflows/",
    "Makefile",
    "CLAUDE.md",
    "AGENTS.md",
    # generated agent copies tracked in this repository (CLAUDE.md agent table)
    ".claude/",
    ".github/prompts/",
    ".gemini/",
    ".cursor/",
    ".qwen/",
    ".opencode/",
    ".windsurf/",
    ".kilocode/",
    ".augment/",
    ".amazonq/",
    ".kiro/",
    ".agent/",
    ".llxprt/",
    ".agents/",
    ".codex/",
)

#: Living roots that must each contribute at least one scanned file (non-vacuity).
_REQUIRED_ROOTS: tuple[str, ...] = ("src/", "packs/", "docs/", ".github/workflows/", "Makefile", "CLAUDE.md")

#: Historical roots of spec FR-018 plus the shared ``FORBIDDEN_SCAN_ROOTS``.
_HISTORICAL_PREFIXES: tuple[str, ...] = (
    "kitty-specs/",
    "docs/adr/",
    "docs/reports/",
    "docs/archive/",
    "docs/plans/",
    ".kittify/evidence/",
    ".kittify/migrations/",
    *FORBIDDEN_SCAN_ROOTS,
)

_CHANGELOG = "docs/changelog/CHANGELOG.md"
_CUTOVER_HEADLINE = "Charter pack cutover:"

#: Released notes under ``docs/changelog/`` (historical; every other file there is scanned).
_RELEASED_CHANGELOG_FILES: tuple[str, ...] = (
    "docs/changelog/1x/artifacts-and-commands.md",
    "docs/changelog/1x/branches-and-workspaces.md",
    "docs/changelog/1x/index.md",
    "docs/changelog/1x/orchestration-and-api.md",
    "docs/changelog/1x/toc.yml",
    "docs/changelog/1x/workflow.md",
    "docs/changelog/2x/adr-coverage.md",
    "docs/changelog/3.2.x.md",
    "docs/changelog/3.3.x.md",
    "docs/changelog/release-notes-3.2.6.md",
    "docs/changelog/release-notes-3.2.6rc1.md",
)

_MIGRATIONS = "src/specify_cli/upgrade/migrations/"

#: The cutover migration and its helpers, and the legacy-state predicate module (by file).
_CUTOVER_FILES: tuple[str, ...] = (
    f"{_MIGRATIONS}_charter_pack_cutover_report.py",
    f"{_MIGRATIONS}_charter_pack_cutover_snapshots.py",
    f"{_MIGRATIONS}_charter_pack_cutover_resets.py",
    f"{_MIGRATIONS}_charter_pack_cutover_skills.py",
    "src/specify_cli/migration/legacy_charter_layout.py",
)
_CUTOVER_MODULE = re.compile(r"^src/specify_cli/upgrade/migrations/m_[^/]*charter_pack_cutover[^/]*\.py$")

#: Tombstone files: their job is to name retired things.
_TOMBSTONE_FILES: dict[str, str] = {
    "src/specify_cli/skills/retired.py": "RETIRED_CANONICAL_SKILL_NAMES lists the removed skill ids",
    "src/charter/offering/packs/retired_fields.py": "names the retired pack fields to refuse them (RETIRED_PACK_FIELD)",
    "src/specify_cli/upgrade/metadata.py": "recorded migration ids of consumer projects",
}
#: Historical migrations: their ``migration_id`` values are recorded in consumer projects.
_HISTORICAL_MIGRATION = re.compile(r"^src/specify_cli/upgrade/migrations/m_[^/]*\.py$")

#: Orchestrator ruling (WP24, escalated): FR-013's deprecated-term redirects spell the old terms.
_GLOSSARY_PACK = "packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml"

#: Orchestrator ruling (WP22, escalated): generated from every docs page; only the
#: blocks of living pages are scanned (``scripts/docs/docs_index.py``).
_RETRIEVAL_INDEX = "docs/development/docs-retrieval-index.yaml"
_INDEX_PAGE = re.compile(r'^  - path: "([^"]+)"$')

#: ``(path, token)`` exemptions: only the C-004 identifiers may appear here.
_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()
_C004_NAMES: tuple[str, ...] = ("doctrine-daphne", "DIRECTIVE_039")

#: Scanned-file floor (SC-003). ``FR018_FLOOR`` = 2459 is the literal WP01 recorded at the
#: mission base ``fcf7a82710d2424a231c2f7b23f490ffde8bd9ab``
#: (``tests/acceptance/charter_pack_cutover/_requirements.py``); never derived from
#: :func:`living_paths`. The mission deleted 67 of those files, measured at WP25 with
#: ``git diff --name-only --no-renames --diff-filter=D fcf7a827..HEAD`` filtered to the
#: living surfaces (renames count as deletions; their new paths are scanned).
#: 2459 - 67 = 2392.
_FILE_FLOOR = 2392


@dataclass(frozen=True)
class Finding:
    """One retired token on a living surface."""

    path: str
    line: int
    token: str
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.token!r}: {self.text.strip()[:160]}"


# --------------------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------------------


def _under(path: str, roots: Iterable[str]) -> bool:
    return any(path.startswith(root) if root.endswith("/") else path == root for root in roots)


def _is_archive(path: str) -> bool:
    return "archive" in PurePosixPath(path).parts[:-1]


def _exempt_file(path: str) -> bool:
    if path in _CUTOVER_FILES or path in _TOMBSTONE_FILES or path in _RELEASED_CHANGELOG_FILES or path == _GLOSSARY_PACK:
        return True
    return bool(_CUTOVER_MODULE.match(path) or _HISTORICAL_MIGRATION.match(path))


def in_scope(path: str) -> bool:
    """Whether repository-relative *path* is a living surface (FR-018)."""
    if not _under(path, _LIVING_ROOTS):
        return False
    if _under(path, _HISTORICAL_PREFIXES) or _is_archive(path):
        return False
    return not _exempt_file(path)


def _tracked_regular_files(repo: Path) -> list[str]:
    raw = subprocess.run(["git", "-C", str(repo), "ls-files", "-s", "-z"], check=True, capture_output=True).stdout
    paths: list[str] = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        if meta.split()[0] in {b"100644", b"100755"}:
            paths.append(path.decode("utf-8", "surrogateescape"))
    return paths


def _read_text(path: Path) -> str | None:
    try:
        blob = path.read_bytes()
    except FileNotFoundError:
        return None
    if b"\x00" in blob:
        return None
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return None


def living_paths(repo: Path) -> Iterator[str]:
    """Tracked regular text files on the living surfaces, in ``git ls-files`` order."""
    for rel in _tracked_regular_files(repo):
        if in_scope(rel) and _read_text(repo / rel) is not None:
            yield rel


# --------------------------------------------------------------------------------------
# Scan
# --------------------------------------------------------------------------------------


def _entry_lines(start: int, count: int) -> range:
    return range(start, start + count)


def _changelog_lines(text: str) -> set[int]:
    """1-based lines of the changelog that are scanned: Unreleased minus cutover entries."""
    section = unreleased_section(text)
    if section is None:
        return set()
    scanned = set(_entry_lines(section.start_line + 1, len(section.lines)))
    for entry in parse_section(section).entries:
        if not (entry.headline or "").startswith(_CUTOVER_HEADLINE):
            continue
        scanned -= set(_entry_lines(entry.line, len(entry.lines)))
        for start, block in zip(entry.nested_lines, entry.nested, strict=True):
            scanned -= set(_entry_lines(start, len(block)))
    return scanned


def _index_lines(text: str) -> list[int]:
    """1-based lines of the retrieval index that are scanned: the header and living pages' blocks."""
    scanned: list[int] = []
    living = True
    for number, line in enumerate(text.splitlines(), start=1):
        page = _INDEX_PAGE.match(line)
        if page:
            living = in_scope(page.group(1))
        if living:
            scanned.append(number)
    return scanned


def _scanned_lines(path: str, text: str) -> Iterable[int]:
    if path == _CHANGELOG:
        return sorted(_changelog_lines(text))
    if path == _RETRIEVAL_INDEX:
        return _index_lines(text)
    return range(1, len(text.splitlines()) + 1)


def _scan_text(path: str, text: str) -> Iterator[Finding]:
    lines = text.splitlines()
    numbers = _scanned_lines(path, text)
    for number in numbers:
        line = lines[number - 1]
        for token, pattern in _PATTERNS:
            if pattern.search(line) and (path, token) not in _ALLOWLIST:
                yield Finding(path, number, token, line)


def scan(repo: Path, paths: Sequence[str] | Iterable[str]) -> Iterator[Finding]:
    """Findings for every in-scope *path* under *repo* (out-of-scope paths are skipped)."""
    for rel in paths:
        if not in_scope(rel):
            continue
        text = _read_text(repo / rel)
        if text is not None:
            yield from _scan_text(rel, text)


# --------------------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------------------


def test_living_surfaces_carry_no_retired_charter_vocabulary() -> None:
    paths = list(living_paths(_REPO_ROOT))
    assert len(paths) >= _FILE_FLOOR, f"scanned {len(paths)} files < floor {_FILE_FLOOR}: the scope shrank"
    empty_roots = [root for root in _REQUIRED_ROOTS if not any(_under(p, (root,)) for p in paths)]
    assert empty_roots == [], f"living roots that contributed no file: {empty_roots}"
    findings = [str(f) for f in scan(_REPO_ROOT, paths)]
    assert findings == [], "retired charter vocabulary on a living surface (FR-018):\n" + "\n".join(findings[:80])


def test_allowlist_is_empty_except_c004() -> None:
    assert all(any(name in f"{path} {token}" for name in _C004_NAMES) for path, token in _ALLOWLIST), _ALLOWLIST
    assert frozenset() == _ALLOWLIST


def test_every_listed_exempt_file_exists() -> None:
    listed = (*_RELEASED_CHANGELOG_FILES, *_CUTOVER_FILES, *_TOMBSTONE_FILES, _CHANGELOG, _GLOSSARY_PACK, _RETRIEVAL_INDEX)
    missing = [path for path in listed if not (_REPO_ROOT / path).is_file()]
    assert missing == [], missing
    assert any(_CUTOVER_MODULE.match(p) for p in _tracked_regular_files(_REPO_ROOT)), "the cutover module is gone"


def test_token_list_is_closed() -> None:
    assert len(_TOKENS) == len(set(_TOKENS)) == 25
    assert all(token in "\n".join(_TOKENS) for token in _SKILL_IDS)


# --------------------------------------------------------------------------------------
# Self-tests: planted tokens and negative controls (no git needed)
# --------------------------------------------------------------------------------------


def _plant(root: Path, rel: str, body: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def _found(root: Path, rel: str) -> list[str]:
    return [finding.token for finding in scan(root, [rel])]


@pytest.mark.parametrize("token", _TOKENS)
@pytest.mark.parametrize("rel", ["src/x.py", "docs/guide.md"])
def test_planted_token_is_reported(token: str, rel: str, tmp_path: Path) -> None:
    _plant(tmp_path, rel, f"before\nuse {token} here\n")
    assert _found(tmp_path, rel) == [token]


@pytest.mark.parametrize("rel", ["docs/adr/0001-old.md", "docs/plans/p.md", "docs/migrations/m.md", "tests/x.py", "pkg/archive/x.md", f"{_MIGRATIONS}m_9_9_9_x.py"])
def test_planted_token_on_historical_root_is_not_reported(rel: str, tmp_path: Path) -> None:
    _plant(tmp_path, rel, f"{_PROSE_TOKENS[0]} and {_IDENTIFIER_TOKENS[0]}\n")
    assert _found(tmp_path, rel) == []


def test_boundaries_do_not_over_match(tmp_path: Path) -> None:
    body = f"2.1.2_fix_charter_{_D}_skill\nmy_{_D}_mode_x\nnot-ad-hoc-profile-loader\nspk-{_D}x\n"
    _plant(tmp_path, "src/x.py", body)
    assert _found(tmp_path, "src/x.py") == []


def test_changelog_is_section_aware(tmp_path: Path) -> None:
    token = _PROSE_TOKENS[0]
    body = (
        "# Changelog\n\n## [Unreleased]\n\n### Changed\n\n"
        f"- **{_CUTOVER_HEADLINE} the {token} is renamed.** Before: `{token}`.\n"
        f"  - Before: {token}; After: charter pack.\n"
        f"- **Something else.** It says {token}.\n\n"
        f"## [1.0.0] - 2020-01-01\n\n- **Old.** The {token} shipped.\n"
    )
    _plant(tmp_path, _CHANGELOG, body)
    findings = list(scan(tmp_path, [_CHANGELOG]))
    assert [(f.line, f.token) for f in findings] == [(9, token)], [str(f) for f in findings]


def test_retrieval_index_scans_only_living_page_blocks(tmp_path: Path) -> None:
    token = _PROSE_TOKENS[0]
    body = f'# GENERATED\npages:\n  - path: "docs/adr/0001.md"\n    abstract: "the {token}"\n  - path: "docs/guide.md"\n    abstract: "the {token}"\n'
    _plant(tmp_path, _RETRIEVAL_INDEX, body)
    assert [(f.line, f.token) for f in scan(tmp_path, [_RETRIEVAL_INDEX])] == [(6, token)]
