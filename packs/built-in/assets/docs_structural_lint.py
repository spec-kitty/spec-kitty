"""Structural docs lint (FR-007/008/011) — successor to the retired ratchet.

The retired anti-sprawl ratchet (removed by PR #2855) mechanically checked
index *existence* and an absolute basename-uniqueness count. Both proved too
blunt: every section index is not curated (most are landing pages), and a
single global "no duplicate basename" count cannot express "these two
sections legitimately both have a ``README.md``". This module is the durable
mechanical successor — four independently-testable checks, each **scoped so
the current clean tree passes** (NFR-003):

1. ``index_completeness`` — a non-index page in a **curated-complete**
   section (config-declared; initially ``architecture/`` only) is absent from
   that section's ``index.md``. Every other section index is a landing page
   and is exempt.
2. ``point_in_time_placement`` — a file that is dated (basename pattern) or
   self-declares point-in-time/closeout (frontmatter marker) lives outside
   ``plans/**`` and is not allowlisted (``adr/**``, ``plans/research/**``,
   ``plans/investigations/**``).
3. ``shadow_tree_basename`` — the same non-nav content basename exists under
   two distinct section subtrees (nav basenames, sanctioned era files, and
   config-declared redirect stubs are exempt). A content-duplicate check, not
   an absolute-uniqueness count.
4. ``frontmatter_contract`` — an in-scope page (section ``README.md`` landing
   pages excluded) lacks a required frontmatter field.

**Config SSOT (FR-011, C-005)**: every section list, pattern, allowlist,
required-field list, and exemption list is LOADED from a data file carrying
the ``structural_lint_config:`` block — the built-in default lives at
``assets/docs_structural_lint.config.yaml``, and a project may override it
with its own file carrying the same wrapper key — nothing here hard-codes
policy that could diverge from that data. A missing or malformed block is a
hard, loud error (:class:`ConfigError`); there is no silent fallback to an
inline default.

This module is shipped as the ``common-docs-structural-lint`` doctrine asset:
it imports only the stdlib and ``ruamel.yaml`` (nothing from the Spec Kitty
source tree), so it runs unchanged in a consumer repo. The file it loads its
policy from is supplied explicitly — the ``--styleguide PATH`` CLI argument,
else the ``SPEC_KITTY_STYLEGUIDE`` environment variable — with no hard-coded
``src/charter/offering/...`` fallback. Despite its flag/env-var name (kept for CLI
backward compatibility), the path may point at any file carrying the
``structural_lint_config:`` block, not specifically a styleguide.

Invocation::

    python docs_structural_lint.py --styleguide PATH [--json] [DOCS_ROOT=docs]

Exit ``0`` when no violations; exit ``1`` when any violation exists; exit
``2`` when the config file cannot be loaded. ``--json`` emits::

    {"violations": [{"rule_id": str, "path": str, "message": str}, ...],
     "checked": int}

where ``checked`` is the total number of ``.md`` pages walked under
``DOCS_ROOT`` (so a "0 violations" result can never silently mean "0
checked"). Completes in under 5 seconds on the current tree (NFR-003).

This module never mutates ``docs/`` — it only inspects, classifies, and
reports (mirrors the report-only rulers in this package).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

__all__ = [
    "ConfigError",
    "LintConfig",
    "LintReport",
    "PointInTimeMarker",
    "Violation",
    "build_parser",
    "check_frontmatter_contract",
    "check_index_completeness",
    "check_one_index_per_dir",
    "check_point_in_time_placement",
    "check_sanctioned_section_membership",
    "check_shadow_tree_basename",
    "load_config",
    "main",
    "parse_frontmatter",
    "run",
]

DEFAULT_DOCS_ROOT: Final[str] = "docs"

#: The pinned interface contract with the data file carrying this asset's
#: default policy (built-in default: ``assets/docs_structural_lint.config.yaml``,
#: overridable by a project's own file carrying the same key). Renaming this
#: wrapper key requires updating both that file and here.
_CONFIG_KEY: Final[str] = "structural_lint_config"

#: Environment variable naming the config file the lint LOADS its policy from,
#: consulted when ``--styleguide`` is not passed. Keeps this asset consumable
#: from any repo without a hard-coded ``src/charter/offering/...`` path.
_STYLEGUIDE_ENV_VAR: Final[str] = "SPEC_KITTY_STYLEGUIDE"

_MD_LINK_RE: Final[re.Pattern[str]] = re.compile(r"\]\(([^)]+)\)")

_FRONTMATTER_FENCE: Final[str] = "---"


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse a markdown page's leading ``---`` YAML frontmatter block.

    Self-contained, ``ruamel``-based frontmatter extractor (inlined so this
    lint — shipped as a doctrine asset — depends on nothing but the stdlib and
    ``ruamel.yaml``, and resolves in a consumer repo with no access to the
    Spec Kitty source tree).

    Returns an empty mapping when the page has no frontmatter or the block is
    malformed (the lint is report-only and must not crash on a single bad
    page).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return {}

    closing_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_FENCE:
            closing_index = index
            break
    if closing_index is None:
        return {}

    block = "\n".join(lines[1:closing_index])
    yaml = YAML(typ="safe")
    try:
        loaded = yaml.load(block)
    except YAMLError:
        return {}
    if not isinstance(loaded, Mapping):
        return {}
    return {str(key): value for key, value in loaded.items()}


# --- Result shapes -----------------------------------------------------------


@dataclass(slots=True, frozen=True)
class Violation:
    """One structural-lint finding: ``{rule_id, path, message}`` (data-model.md)."""

    rule_id: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        """Serialize to the contract's ``{rule_id, path, message}`` shape."""
        return {"rule_id": self.rule_id, "path": self.path, "message": self.message}


@dataclass(slots=True, frozen=True)
class LintReport:
    """Result of a full structural-lint run."""

    checked: int = 0
    violations: list[Violation] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serialize to the contract's JSON shape."""
        return {
            "violations": [v.as_dict() for v in self.violations],
            "checked": self.checked,
        }


# --- Config (FR-011 SSOT) ----------------------------------------------------


@dataclass(slots=True, frozen=True)
class PointInTimeMarker:
    """A frontmatter ``field: value`` signal a page self-declares point-in-time."""

    frontmatter_field: str
    frontmatter_value: str


@dataclass(slots=True, frozen=True)
class LintConfig:
    """Typed view of the data file's ``structural_lint_config:`` block."""

    curated_complete_sections: tuple[str, ...]
    concern_bucket_to_section: dict[str, str]
    point_in_time_patterns: tuple[str, ...]
    point_in_time_markers: tuple[PointInTimeMarker, ...]
    point_in_time_allowlist: tuple[str, ...]
    frontmatter_required_fields: tuple[str, ...]
    frontmatter_in_scope_exclusions: tuple[str, ...]
    shadow_tree_nav_exemptions: tuple[str, ...]
    redirect_stub_description_prefix: str
    guides_boundary: str
    # T004 invariant fields (common-docs-convergence WP04). Defaulted so a
    # direct-construction test fixture that predates them still builds; the real
    # config always populates them via ``_build_config`` (loud on absence).
    sanctioned_content_sections: tuple[str, ...] = ()
    non_content_dirs: tuple[str, ...] = ()
    root_allowlist: tuple[str, ...] = ()
    one_index_per_dir: bool = False


class ConfigError(Exception):
    """Raised when ``structural_lint_config:`` is missing or malformed.

    Fail LOUD (C-005): this is never converted to an inline default — a
    missing/malformed block is a hard error naming exactly what is wrong.
    """


_REQUIRED_STR_LIST_KEYS: Final[tuple[str, ...]] = (
    "curated_complete_sections",
    "point_in_time_patterns",
    "point_in_time_allowlist",
    "frontmatter_required_fields",
    "frontmatter_in_scope_exclusions",
    "shadow_tree_nav_exemptions",
    # T004 invariant list fields (common-docs-convergence WP04).
    "sanctioned_content_sections",
    "non_content_dirs",
    "root_allowlist",
)


def _resolve_styleguide(arg: str | None) -> Path:
    """Resolve the config-file path from the CLI arg, then the environment.

    Resolution order (there is deliberately NO hard-coded ``src/charter/offering/...``
    default — this asset ships to consumer repos that do not have the Spec
    Kitty source tree, so the path must be supplied explicitly):

    1. the ``--styleguide PATH`` CLI argument, when given;
    2. else the ``SPEC_KITTY_STYLEGUIDE`` environment variable, when set;
    3. else a hard, loud :class:`ConfigError` naming both knobs.
    """
    if arg:
        return Path(arg)
    env_value = os.environ.get(_STYLEGUIDE_ENV_VAR)
    if env_value:
        return Path(env_value)
    raise ConfigError(
        "no config file configured — pass --styleguide <path> or set "
        f"{_STYLEGUIDE_ENV_VAR} to a file carrying the '{_CONFIG_KEY}:' "
        f"block (built-in default: assets/docs_structural_lint.config.yaml)."
    )


def load_config(styleguide_path: Path) -> LintConfig:
    """Load the lint's policy from its data file (FR-011).

    Parameters
    ----------
    styleguide_path:
        Path to a file carrying the ``structural_lint_config:`` block — the
        built-in default is ``assets/docs_structural_lint.config.yaml``, and
        a project may override it with its own file carrying the same key.
        Required — the lint no longer hard-codes a ``src/charter/offering/...``
        default so it stays consumable from a repo with no access to the
        Spec Kitty source tree. Callers resolve it via
        :func:`_resolve_styleguide` (``--styleguide`` /
        ``SPEC_KITTY_STYLEGUIDE``).

    Raises
    ------
    ConfigError
        If the file is missing, malformed YAML, or lacks a well-formed
        ``structural_lint_config:`` block. Never falls back to a hard-coded
        default (C-005).
    """
    path = styleguide_path
    if not path.is_file():
        raise ConfigError(f"Config file not found at {path} — cannot load '{_CONFIG_KEY}:'.")

    yaml = YAML(typ="safe")
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw: Any = yaml.load(handle)
    except YAMLError as exc:
        raise ConfigError(f"Malformed YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict) or _CONFIG_KEY not in raw:
        raise ConfigError(
            f"{path} has no '{_CONFIG_KEY}:' block. The lint refuses to fall "
            "back to a hard-coded default policy (C-005) — add the block to "
            "a file carrying the 'structural_lint_config:' key (built-in "
            "default: assets/docs_structural_lint.config.yaml), or point "
            "--styleguide / SPEC_KITTY_STYLEGUIDE at one that does."
        )
    block = raw[_CONFIG_KEY]
    if not isinstance(block, dict):
        raise ConfigError(f"{path}: '{_CONFIG_KEY}:' must be a mapping")
    return _build_config(block, path)


def _build_config(block: Mapping[str, Any], source: Path) -> LintConfig:
    """Validate + assemble :class:`LintConfig` from the raw config mapping."""
    values = {key: _require_str_list(block, key, source) for key in _REQUIRED_STR_LIST_KEYS}
    return LintConfig(
        curated_complete_sections=values["curated_complete_sections"],
        point_in_time_patterns=values["point_in_time_patterns"],
        point_in_time_markers=_require_markers(block, source),
        point_in_time_allowlist=values["point_in_time_allowlist"],
        frontmatter_required_fields=values["frontmatter_required_fields"],
        frontmatter_in_scope_exclusions=values["frontmatter_in_scope_exclusions"],
        shadow_tree_nav_exemptions=values["shadow_tree_nav_exemptions"],
        concern_bucket_to_section=_require_str_dict(
            block, "concern_bucket_to_section", source
        ),
        redirect_stub_description_prefix=_require_str(
            block, "redirect_stub_description_prefix", source
        ),
        guides_boundary=_require_str(block, "guides_boundary", source),
        sanctioned_content_sections=values["sanctioned_content_sections"],
        non_content_dirs=values["non_content_dirs"],
        root_allowlist=values["root_allowlist"],
        one_index_per_dir=_require_bool(block, "one_index_per_dir", source),
    )


def _require_str_list(block: Mapping[str, Any], key: str, source: Path) -> tuple[str, ...]:
    raw = block.get(key)
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ConfigError(f"{source}: '{_CONFIG_KEY}.{key}' must be a list of strings")
    return tuple(raw)


def _require_str(block: Mapping[str, Any], key: str, source: Path) -> str:
    raw = block.get(key)
    if not isinstance(raw, str) or not raw:
        raise ConfigError(f"{source}: '{_CONFIG_KEY}.{key}' must be a non-empty string")
    return raw


def _require_bool(block: Mapping[str, Any], key: str, source: Path) -> bool:
    raw = block.get(key)
    if not isinstance(raw, bool):
        raise ConfigError(f"{source}: '{_CONFIG_KEY}.{key}' must be a boolean")
    return raw


def _require_str_dict(block: Mapping[str, Any], key: str, source: Path) -> dict[str, str]:
    raw = block.get(key)
    if not isinstance(raw, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in raw.items()
    ):
        raise ConfigError(f"{source}: '{_CONFIG_KEY}.{key}' must be a mapping of str to str")
    return dict(raw)


def _require_markers(block: Mapping[str, Any], source: Path) -> tuple[PointInTimeMarker, ...]:
    raw = block.get("point_in_time_markers")
    if not isinstance(raw, list):
        raise ConfigError(f"{source}: '{_CONFIG_KEY}.point_in_time_markers' must be a list")
    markers: list[PointInTimeMarker] = []
    for index, entry in enumerate(raw):
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("frontmatter_field"), str)
            or not isinstance(entry.get("frontmatter_value"), str)
        ):
            raise ConfigError(
                f"{source}: '{_CONFIG_KEY}.point_in_time_markers[{index}]' must "
                "have string 'frontmatter_field' and 'frontmatter_value' keys"
            )
        markers.append(
            PointInTimeMarker(
                frontmatter_field=entry["frontmatter_field"],
                frontmatter_value=entry["frontmatter_value"],
            )
        )
    return tuple(markers)


# --- Glob matching (supports leading/trailing ``**`` segments) --------------


def _match_segments(pattern_segments: list[str], path_segments: list[str]) -> bool:
    """Match path segments against glob segments, with ``**`` = "0+ segments"."""
    if not pattern_segments:
        return not path_segments
    head, *rest_pattern = pattern_segments
    if head == "**":
        if not rest_pattern:
            return True
        return any(
            _match_segments(rest_pattern, path_segments[i:])
            for i in range(len(path_segments) + 1)
        )
    if not path_segments:
        return False
    if not _fnmatch_segment(path_segments[0], head):
        return False
    return _match_segments(rest_pattern, path_segments[1:])


def _fnmatch_segment(name: str, pattern: str) -> bool:
    """Single-segment ``fnmatch``-style match (``*``/``?`` wildcards)."""
    return fnmatch.fnmatchcase(name, pattern)


def _glob_match(candidate: str, pattern: str) -> bool:
    """Match a ``/``-joined ``candidate`` against a limited glob ``pattern``."""
    return _match_segments(pattern.split("/"), candidate.split("/"))


def _glob_match_any(candidate: str, patterns: tuple[str, ...]) -> bool:
    return any(_glob_match(candidate, pattern) for pattern in patterns)


# --- Shared helpers -----------------------------------------------------------


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _repo_relative(path: Path, base: Path) -> str:
    """Render ``path`` as a POSIX path relative to ``base`` (best-effort)."""
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# --- Check 1: index_completeness --------------------------------------------


def _linked_targets(index_path: Path) -> set[Path]:
    """Resolved absolute targets of every relative markdown link in ``index_path``."""
    text = _read_text(index_path)
    if text is None:
        return set()
    targets: set[Path] = set()
    for match in _MD_LINK_RE.finditer(text):
        raw = match.group(1).strip().split("#", 1)[0].strip()
        if not raw or "://" in raw or raw.startswith("mailto:"):
            continue
        targets.add((index_path.parent / raw).resolve())
    return targets


def check_index_completeness(
    docs_root: Path, repo_root: Path, config: LintConfig
) -> list[Violation]:
    """Flag pages in a curated-complete section absent from its ``index.md``.

    Recurses into the section's subdirectories (a page under
    ``architecture/assessments/...`` must be enumerated in
    ``architecture/index.md`` too). Sections not in
    ``config.curated_complete_sections`` are never walked — their indexes are
    landing pages, exempt by design.
    """
    violations: list[Violation] = []
    for section in config.curated_complete_sections:
        section_dir = docs_root / section
        index_path = section_dir / "index.md"
        if not section_dir.is_dir() or not index_path.is_file():
            continue
        linked = _linked_targets(index_path)
        for page in sorted(section_dir.rglob("*.md")):
            if page.name == "index.md" or page.resolve() in linked:
                continue
            page_rel = _repo_relative(page, repo_root)
            violations.append(
                Violation(
                    rule_id="index_completeness",
                    path=page_rel,
                    message=(
                        f"{page_rel} is missing from "
                        f"{_repo_relative(index_path, repo_root)}"
                    ),
                )
            )
    return violations


# --- Check 2: point_in_time_placement ---------------------------------------


def _is_point_in_time(md_path: Path, config: LintConfig) -> bool:
    """A file is point-in-time if its basename is dated or self-declares it."""
    basename = md_path.name
    if any(re.match(pattern, basename) for pattern in config.point_in_time_patterns):
        return True
    frontmatter = parse_frontmatter(_read_text(md_path) or "")
    return any(
        frontmatter.get(marker.frontmatter_field) == marker.frontmatter_value
        for marker in config.point_in_time_markers
    )


def check_point_in_time_placement(
    md_files: list[Path], docs_root: Path, repo_root: Path, config: LintConfig
) -> list[Violation]:
    """Flag point-in-time files living outside their canonical ``plans/**`` home."""
    violations: list[Violation] = []
    for md_path in md_files:
        rel_to_docs = _repo_relative(md_path, docs_root)
        if _glob_match_any(rel_to_docs, config.point_in_time_allowlist):
            continue
        if not _is_point_in_time(md_path, config):
            continue
        page_rel = _repo_relative(md_path, repo_root)
        violations.append(
            Violation(
                rule_id="point_in_time_placement",
                path=page_rel,
                message=(
                    f"{page_rel} is a point-in-time document; its canonical "
                    "home is plans/** (e.g. plans/engineering-notes/)."
                ),
            )
        )
    return violations


# --- Check 3: shadow_tree_basename -------------------------------------------


def _is_redirect_stub(md_path: Path, config: LintConfig) -> bool:
    """True when a page self-declares as a redirect stub via its description.

    A redirect stub is a legitimate old-path placeholder retained so existing
    links/URLs keep resolving; it deliberately shares the moved file's basename
    with its canonical relocated twin, so it must NOT be flagged as duplicated
    content. The signal is config-declared (``redirect_stub_description_prefix``)
    — the lint hard-codes no marker (FR-011/C-005).
    """
    prefix = config.redirect_stub_description_prefix
    if not prefix:
        return False
    frontmatter = parse_frontmatter(_read_text(md_path) or "")
    description = frontmatter.get("description")
    return isinstance(description, str) and description.startswith(prefix)


def check_shadow_tree_basename(
    md_files: list[Path], docs_root: Path, repo_root: Path, config: LintConfig
) -> list[Violation]:
    """Flag a non-nav content basename duplicated across section subtrees.

    A content-duplicate check, not an absolute basename-uniqueness count
    (NFR-005): two files sharing a basename within the SAME section subtree
    are not flagged, only across DISTINCT top-level section subtrees.
    """
    groups: dict[str, list[tuple[str, str]]] = {}
    for md_path in md_files:
        basename = md_path.name
        if _glob_match_any(basename, config.shadow_tree_nav_exemptions):
            continue
        if _is_redirect_stub(md_path, config):
            continue
        rel_to_docs = _repo_relative(md_path, docs_root)
        section = rel_to_docs.split("/", 1)[0]
        groups.setdefault(basename, []).append(
            (section, _repo_relative(md_path, repo_root))
        )

    violations: list[Violation] = []
    for basename, entries in sorted(groups.items()):
        sections = {section for section, _ in entries}
        if len(sections) < 2:
            continue
        paths = sorted(path for _, path in entries)
        violations.append(
            Violation(
                rule_id="shadow_tree_basename",
                path=paths[0],
                message=(
                    f"basename '{basename}' is duplicated non-nav content "
                    f"across section subtrees: {', '.join(paths)}"
                ),
            )
        )
    return violations


# --- Check 4: frontmatter_contract -------------------------------------------


def check_frontmatter_contract(
    md_files: list[Path], docs_root: Path, repo_root: Path, config: LintConfig
) -> list[Violation]:
    """Flag in-scope pages missing a required frontmatter field.

    "In-scope" excludes section ``README.md`` landing pages (config
    ``frontmatter_in_scope_exclusions``) — a page with no frontmatter block
    at all is treated as missing every required field, unless excluded.
    """
    violations: list[Violation] = []
    for md_path in md_files:
        rel_to_docs = _repo_relative(md_path, docs_root)
        if _glob_match_any(rel_to_docs, config.frontmatter_in_scope_exclusions):
            continue
        frontmatter = parse_frontmatter(_read_text(md_path) or "")
        missing = [
            required_field
            for required_field in config.frontmatter_required_fields
            if not frontmatter.get(required_field)
        ]
        if not missing:
            continue
        page_rel = _repo_relative(md_path, repo_root)
        violations.append(
            Violation(
                rule_id="frontmatter_contract",
                path=page_rel,
                message=(
                    f"{page_rel} is missing required frontmatter field(s): "
                    f"{', '.join(missing)}"
                ),
            )
        )
    return violations


# --- Check 5 (T011): one_index_per_dir (advisory; not wired into run()) ------


#: Basenames that count as a directory "index / landing" page for the
#: ``one_index_per_dir`` check. A directory carrying more than one of these is
#: flagged when ``config.one_index_per_dir`` is enabled.
_INDEX_LANDING_BASENAMES: Final[tuple[str, ...]] = ("index.md", "README.md")


def _is_exempt_landing(
    md_path: Path, docs_root: Path, curated: set[str], config: LintConfig
) -> bool:
    """True when a landing page does not COMPETE with a dir's canonical index.md.

    ``index.md`` is always the canonical keeper (never exempted away). A
    ``README.md`` is exempt when it is a redirect stub (old-path placeholder) or
    it sits in a curated-complete section (prose intro alongside the enumerating
    index). See :func:`check_one_index_per_dir` for the rationale.
    """
    if md_path.name == "index.md":
        return False
    if _is_redirect_stub(md_path, config):
        return True
    return _top_level_section(md_path, docs_root) in curated


def check_one_index_per_dir(
    md_files: list[Path],
    docs_root: Path,
    repo_root: Path,
    config: LintConfig,
) -> list[Violation]:
    """Flag directories carrying more than one *competing* landing page (T011).

    Config-gated: a no-op unless ``config.one_index_per_dir`` is true. When a
    directory holds both an ``index.md`` and a ``README.md`` the directory has
    two landing pages; the surviving landing is ``index.md`` and the rest are
    reported — with two principled exemptions so the terminal-verification flip
    (OB-2) is green without deleting intentional pages:

    * A **redirect-stub** landing (``description: "Redirect stub: …"``) is not a
      competing page — it is an old-path placeholder that redirects to the
      canonical ``index.md`` (mirrors the ``shadow_tree_basename`` exemption).
      This covers the ``adr/<era>/README.md`` era stubs (#2227).
    * A ``README.md`` inside a **curated-complete** section (config
      ``curated_complete_sections``) is the section's prose intro that
      legitimately coexists with the enumerating ``index.md`` (e.g.
      ``architecture/README.md``, which the architecture-consistency contract
      requires alongside the curated ``index.md``).
    """
    if not config.one_index_per_dir:
        return []
    curated = set(config.curated_complete_sections)
    by_dir: dict[Path, list[Path]] = {}
    for md_path in md_files:
        if md_path.name in _INDEX_LANDING_BASENAMES:
            by_dir.setdefault(md_path.parent, []).append(md_path)
    violations: list[Violation] = []
    for directory, all_landings in sorted(by_dir.items()):
        landings = [
            p
            for p in all_landings
            if not _is_exempt_landing(p, docs_root, curated, config)
        ]
        if len(landings) < 2:
            continue
        # Prefer index.md as the surviving landing; flag the rest.
        ordered = sorted(landings, key=lambda p: (p.name != "index.md", p.name))
        for extra in ordered[1:]:
            extra_rel = _repo_relative(extra, repo_root)
            keeper_rel = _repo_relative(ordered[0], repo_root)
            violations.append(
                Violation(
                    rule_id="one_index_per_dir",
                    path=extra_rel,
                    message=(
                        f"{_repo_relative(directory, repo_root)} carries more than "
                        f"one index/landing page; {extra_rel} competes with "
                        f"{keeper_rel}"
                    ),
                )
            )
    return violations


# --- Check 6 (T011): sanctioned_section_membership (advisory) -----------------


def _top_level_section(md_path: Path, docs_root: Path) -> str:
    """The first path segment of ``md_path`` relative to ``docs_root``.

    Files that live directly under ``docs_root`` (no subdirectory) return the
    empty string, treated as the implicit ``index`` section by callers.
    """
    rel = _repo_relative(md_path, docs_root)
    head, _, tail = rel.partition("/")
    return head if tail else ""


def _under_non_content_dir(rel_to_docs: str, non_content: tuple[str, ...]) -> bool:
    """True when a ``docs_root``-relative path lives under a non-content dir.

    Matches the FULL ``non_content_dirs`` entry as a path PREFIX, not just the
    top-level segment — so a **nested** entry such as ``templates/spec-kitty/``
    is honoured. The prior top-level-only comparison silently never matched a
    multi-segment entry (a page under ``templates/spec-kitty/`` mapped to the
    top segment ``templates``, which is not in the list), so the whole nested
    scaffolding zone was wrongly flagged as off-structure (WP04 reviewer bug).
    """
    return any(
        rel_to_docs == prefix or rel_to_docs.startswith(f"{prefix}/")
        for prefix in non_content
    )


def check_sanctioned_section_membership(
    md_files: list[Path], docs_root: Path, repo_root: Path, config: LintConfig
) -> list[Violation]:
    """Flag pages whose top-level section is not sanctioned (T011).

    A page is off-structure when its top-level section under ``docs_root`` is
    neither in ``config.sanctioned_content_sections`` nor covered by
    ``config.non_content_dirs`` (nav/scaffolding zones). ``non_content_dirs``
    entries are matched as full path PREFIXES via
    :func:`_under_non_content_dir`, so **nested** scaffolding zones (e.g.
    ``templates/spec-kitty/``) are honoured — not only single-segment ones.
    Pages that sit directly at ``docs_root`` map to the implicit ``index``
    section. Reads the config lists (no inlined literals).
    """
    sanctioned = set(config.sanctioned_content_sections)
    non_content = tuple(entry.rstrip("/") for entry in config.non_content_dirs)
    violations: list[Violation] = []
    for md_path in md_files:
        section = _top_level_section(md_path, docs_root) or "index"
        if section in sanctioned:
            continue
        if _under_non_content_dir(_repo_relative(md_path, docs_root), non_content):
            continue
        page_rel = _repo_relative(md_path, repo_root)
        violations.append(
            Violation(
                rule_id="sanctioned_section_membership",
                path=page_rel,
                message=(
                    f"{page_rel} lives in non-sanctioned section '{section}/' "
                    "(not in sanctioned_content_sections / non_content_dirs)"
                ),
            )
        )
    return violations


# --- Aggregation + CLI --------------------------------------------------------


def run(*, docs_root: Path, repo_root: Path, config: LintConfig) -> LintReport:
    """Run the four standing checks over ``docs_root`` and return the aggregate.

    This is the default per-PR aggregate. The two T004 structural invariants
    (``sanctioned_section_membership`` and ``one_index_per_dir``) are NOT wired
    in here: a standing single-root/sanctioned-section blocking lint reverses
    #2851 (the anti-sprawl ratchet was deliberately retired). They are enforced
    as **terminal verification** via :func:`run_extended` instead (OB-2).
    """
    if not docs_root.exists() or not docs_root.is_dir():
        return LintReport(checked=0, violations=[])

    md_files = sorted(docs_root.rglob("*.md"))
    violations: list[Violation] = []
    violations.extend(check_index_completeness(docs_root, repo_root, config))
    violations.extend(check_point_in_time_placement(md_files, docs_root, repo_root, config))
    violations.extend(check_shadow_tree_basename(md_files, docs_root, repo_root, config))
    violations.extend(check_frontmatter_contract(md_files, docs_root, repo_root, config))
    violations.sort(key=lambda v: (v.rule_id, v.path))
    return LintReport(checked=len(md_files), violations=violations)


def run_extended(*, docs_root: Path, repo_root: Path, config: LintConfig) -> LintReport:
    """Terminal-verification aggregate: the standing checks PLUS the T004 invariants.

    Adds ``sanctioned_section_membership`` (single-root / sanctioned-section) and
    ``one_index_per_dir`` to :func:`run`. This is the OB-2 terminal-blocking stance
    the convergence mission's pre-merge build enforces (``--extended``), kept
    OFF the standing per-PR aggregate so it does not re-impose the retired #2851
    ratchet on unrelated changes. Green on the reconciled tree = the invariants hold.
    """
    if not docs_root.exists() or not docs_root.is_dir():
        return LintReport(checked=0, violations=[])

    base = run(docs_root=docs_root, repo_root=repo_root, config=config)
    md_files = sorted(docs_root.rglob("*.md"))
    extra: list[Violation] = []
    extra.extend(check_sanctioned_section_membership(md_files, docs_root, repo_root, config))
    extra.extend(check_one_index_per_dir(md_files, docs_root, repo_root, config))
    violations = sorted(base.violations + extra, key=lambda v: (v.rule_id, v.path))
    return LintReport(checked=base.checked, violations=violations)


def build_parser() -> argparse.ArgumentParser:
    """Build the structural-lint CLI parser."""
    parser = argparse.ArgumentParser(
        prog="docs_structural_lint",
        description=(
            "Structural docs lint (FR-007/008/011) — the durable successor to "
            "the retired anti-sprawl ratchet. Exits non-zero on any violation."
        ),
    )
    parser.add_argument(
        "docs_root",
        nargs="?",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Docs tree to scan (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Base for rendering repo-relative paths (default: cwd).",
    )
    parser.add_argument(
        "--styleguide",
        default=None,
        help=(
            "Path to a file carrying the 'structural_lint_config:' block "
            "(built-in default: assets/docs_structural_lint.config.yaml; a "
            "project may override with its own file carrying the same "
            f"key). Falls back to the {_STYLEGUIDE_ENV_VAR} environment "
            "variable when omitted."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of a human summary.",
    )
    parser.add_argument(
        "--extended",
        action="store_true",
        help=(
            "Terminal-verification mode (OB-2): also enforce the T004 structural "
            "invariants (sanctioned_section_membership + one_index_per_dir). Used "
            "by the pre-merge build gate; OFF by default to avoid re-imposing the "
            "retired #2851 ratchet on unrelated per-PR changes."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code (0/1/2)."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(_resolve_styleguide(args.styleguide))
    except ConfigError as exc:
        sys.stderr.write(f"docs_structural_lint: {exc}\n")
        return 2
    runner = run_extended if args.extended else run
    report = runner(docs_root=args.docs_root, repo_root=args.repo_root, config=config)
    _emit(report, as_json=args.json)
    return 1 if report.violations else 0


def _emit(report: LintReport, *, as_json: bool) -> None:
    """Print the report — JSON payload or a human-readable summary."""
    if as_json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
        return

    sys.stdout.write(
        f"docs_structural_lint: checked {report.checked} page(s); "
        f"{len(report.violations)} violation(s).\n"
    )
    for violation in report.violations:
        sys.stdout.write(f"  [{violation.rule_id}] {violation.path}: {violation.message}\n")


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
