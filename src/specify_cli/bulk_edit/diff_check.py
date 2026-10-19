"""Diff-aware review compliance for bulk-edit occurrence maps.

Implements FR-007 and FR-008: when a mission is marked ``change_mode: bulk_edit``
and a work package reaches review, the review gate inspects the WP's diff and
rejects it when

  * any changed file maps (by path heuristic) to a category whose action is
    ``do_not_change``, unless an explicit exception grants a different action
    for that file, **or**

  * any changed file cannot be classified against the occurrence map's
    categories at all (unclassified occurrence surface touched).

Classification is deliberately path-based, not AST-based. Spec constraint
C-001 excludes language-aware occurrence classification. Path heuristics
are imperfect — a ``.py`` file can carry code symbols, import paths, path
literals, and log labels all at once — so we classify each file to a single
primary category based on its filesystem location and file extension. This
is sufficient to catch the most common silent-breakage class: whole-file
modifications inside a surface marked ``do_not_change`` (serialized-key
YAMLs, CLI command modules, test fixtures, user-facing docs, etc.).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from fnmatch import fnmatch
from pathlib import Path

from specify_cli.bulk_edit.occurrence_map import OccurrenceMap, _is_narrow_structural_path
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.coordination.coherence import is_toolchain_generated_churn

# ---------------------------------------------------------------------------
# Path-to-category heuristics
# ---------------------------------------------------------------------------

# Ordered list — first match wins. Patterns are compiled against the POSIX
# path string (forward slashes, relative to the repo root). More specific
# patterns come first so that, e.g., ``tests/cli/commands/foo.py`` classifies
# as ``tests_fixtures`` rather than ``cli_commands``.
_PATH_RULES: list[tuple[str, list[str]]] = [
    (
        "tests_fixtures",
        [
            r"(^|/)tests?/",
            r"(^|/)testing/",
            r"(^|/)fixtures?/",
            r"(^|/)__snapshots__/",
            r"(^|/)__tests__/",
            r"(^|/)conftest\.py$",
            r"_test\.py$",
            r"\.test\.(ts|tsx|js|jsx)$",
            r"(^|/)test_[^/]+\.py$",
        ],
    ),
    (
        "cli_commands",
        [
            r"(^|/)cli/commands/",
            r"(^|/)commands/[^/]+\.py$",
            r"(^|/)bin/[^/]+$",
        ],
    ),
    (
        "user_facing_strings",
        [
            r"\.md$",
            r"(^|/)docs?/",
            r"(^|/)README(\.[^/]+)?$",
            r"(^|/)CHANGELOG(\.[^/]+)?$",
            r"\.rst$",
            r"\.txt$",
            r"(^|/)LICENSE(\.[^/]+)?$",
        ],
    ),
    (
        # Build recipes are dominated by path literals, so they follow the
        # filesystem_paths decision rather than the code one. Listed before
        # ``serialized_keys`` so a compose file is read as a build recipe
        # rather than as an API/config contract.
        "filesystem_paths",
        [
            r"(^|/)Dockerfile$",
            r"(^|/)Dockerfile\.[^/]+$",
            r"(^|/)Containerfile$",
            r"(^|/)docker-compose(\.[^/]+)?\.ya?ml$",
            r"(^|/)compose(\.[^/]+)?\.ya?ml$",
        ],
    ),
    (
        # Server-rendered templates, stylesheets and Ruby build DSLs. These
        # carry identifiers — partial names, CSS classes, helper and gem
        # names — so they belong with the other source.
        #
        # Without these rules a Rails, Phoenix or Laravel application is
        # largely invisible to this classifier: every .erb/.css/.rake file
        # lands as *unclassified* and blocks review under FR-008 even though
        # the occurrence map never made a decision about it. Listed after
        # ``user_facing_strings`` so a template under ``docs/`` still reads
        # as documentation.
        "code_symbols",
        [
            r"\.erb$",
            r"\.haml$",
            r"\.slim$",
            r"\.jbuilder$",
            r"\.heex$",
            r"\.eex$",
            r"\.blade\.php$",
            r"\.vue$",
            r"\.svelte$",
            r"\.astro$",
            r"\.css$",
            r"\.scss$",
            r"\.sass$",
            r"\.less$",
            r"\.rake$",
            r"\.gemspec$",
            r"(^|/)Rakefile$",
            r"(^|/)Gemfile$",
        ],
    ),
    (
        "serialized_keys",
        [
            r"\.ya?ml$",
            r"\.json$",
            r"\.toml$",
            r"\.ini$",
            r"\.cfg$",
        ],
    ),
    (
        "code_symbols",
        [
            r"\.py$",
            r"\.pyi$",
            r"\.ts$",
            r"\.tsx$",
            r"\.js$",
            r"\.jsx$",
            r"\.mjs$",
            r"\.cjs$",
            r"\.go$",
            r"\.rs$",
            r"\.java$",
            r"\.rb$",
            r"\.kt$",
            r"\.swift$",
            r"\.c$",
            r"\.cc$",
            r"\.cpp$",
            r"\.h$",
            r"\.hpp$",
        ],
    ),
]


_COMPILED_RULES: list[tuple[str, list[re.Pattern[str]]]] = [
    (category, [re.compile(p) for p in patterns]) for category, patterns in _PATH_RULES
]


def classify_path(path: str) -> str | None:
    """Return the primary occurrence category for *path*, or ``None``.

    *path* may be absolute or relative; only the normalised POSIX form is
    used for matching. Returns ``None`` when no pattern matches — such files
    are treated as *unclassified* and block review per FR-008.
    """
    posix = Path(path).as_posix()
    for category, patterns in _COMPILED_RULES:
        for pattern in patterns:
            if pattern.search(posix):
                return category
    return None


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------


def _glob_match(posix: str, pattern: str) -> bool:
    """Return ``True`` if *pattern* (``*``/``?``/``**``) matches *posix*.

    Shared by :func:`_path_matches` and :func:`_exception_for`, which both
    need "plain fnmatch, with a ``**`` recursive fallback" glob semantics —
    this is the single place that logic lives so the two call sites cannot
    drift apart.
    """
    if fnmatch(posix, pattern):
        return True
    return "**" in pattern and _fnmatch_recursive(posix, pattern)


def _move_for(path: str, omap: OccurrenceMap) -> tuple[str, str] | None:
    """Return ``(role, reason)`` when *path* participates in a declared move.

    ``role`` is ``"move-source"`` or ``"move-destination"``. A declared
    structural move (IC-10, #1815) is an explicit, reviewer-approved relocation;
    its source and destination paths are expected to change, so they are not
    subject to the ``do_not_change`` path heuristic. Source/destination paths
    are matched as path globs (``*``/``**`` supported) or as a directory
    prefix when the declared path is a directory (no glob, trailing-slash or
    bare directory form), so ``to: src/auth`` covers ``src/auth/login.py``.
    """
    posix = Path(path).as_posix()
    for move in omap.moves:
        for source in move.sources:
            if _path_matches(posix, source):
                return ("move-source", move.reason or "declared move source")
        if _path_matches(posix, move.destination):
            return ("move-destination", move.reason or "declared move destination")
    return None


def _structural_target_for(path: str, omap: OccurrenceMap) -> str | None:
    """Return the declared reason when *path* matches a structural target.

    A structural target (``structural_targets:`` in ``occurrence_map.yaml``)
    is an explicit, reviewer-declared exemption naming ONE file or glob whose
    changes in THIS mission are a genuine structural code edit (new
    function, refactor) rather than a bulk find/replace occurrence. It is
    matched the same way as a declared move — :func:`_path_matches`
    (glob/directory-prefix) — so ``path: src/foo/*.py`` covers every ``.py``
    file directly under ``src/foo/``. Deliberately narrow: only paths named
    here, one at a time, are exempted — never a blanket "ignore all
    src/*.py". Returns ``None`` when no target matches, meaning the ordinary
    classifier (and its ``do_not_change`` enforcement) still applies.

    Defense-in-depth (MINOR, second-opinion squad): narrowness is normally
    enforced at finalize-time by
    :func:`specify_cli.bulk_edit.occurrence_map.validate_occurrence_map`, but
    THIS function is the actual consumption point that grants the exemption
    at review time — and it must not trust that every ``omap`` it is handed
    was validated by the current code (a map finalized by a pre-hardening
    version, or hand-edited after finalize, could still carry a broad entry
    such as ``path: "src/**/*.py"``). Every candidate is re-checked against
    :func:`_is_narrow_structural_path` here, INDEPENDENTLY of validation, so
    a non-narrow entry can never grant an exemption regardless of how it
    entered the map.
    """
    posix = Path(path).as_posix()
    for target in omap.structural_targets:
        if not _is_narrow_structural_path(target.path):
            continue
        if _path_matches(posix, target.path):
            return target.reason or "declared structural target"
    return None


def _path_matches(posix: str, declared: str) -> bool:
    """Match *posix* against a declared move path (glob or directory prefix)."""
    declared = declared.strip()
    if not declared:
        return False
    normalized = Path(declared).as_posix().rstrip("/")
    if "*" in normalized or "?" in normalized:
        return _glob_match(posix, normalized)
    if posix == normalized:
        return True
    # Directory-prefix match: ``src/auth`` covers ``src/auth/login.py``.
    return posix.startswith(f"{normalized}/")


def _exception_for(path: str, omap: OccurrenceMap) -> dict[str, str] | None:
    """Return the first WHOLE-FILE exception whose glob matches *path*, if any.

    Field-scoped exceptions (``field_path`` set, WP02, FR-002) are excluded
    here: they narrow the exemption to one field inside a file that also
    carries entries the category-level action must still classify normally,
    so they must never override the whole file's verdict — see
    :func:`_field_path_pins_for`, which is where they are actually honoured.
    """
    posix = Path(path).as_posix()
    for exception in omap.exceptions:
        if exception.get("field_path"):
            continue
        pattern = exception.get("path", "")
        if not pattern:
            continue
        # Support both plain glob (``CHANGELOG.md``) and directory-style
        # globs (``src/**/*.py``). fnmatch understands ``*`` and ``?`` but
        # not ``**``, so we also try a recursive-glob fallback when the
        # pattern contains ``**``.
        if _glob_match(posix, pattern):
            # `omap.exceptions` is declared `list[dict[str, str]]` on
            # OccurrenceMap, but mypy resolves it as `Any` when this module is
            # type-checked as a standalone narrow-file target (the
            # `specify_cli.*` / `follow_imports = "skip"` override in
            # pyproject.toml treats non-explicitly-listed sibling modules —
            # including occurrence_map.py — as untyped in that mode). An
            # annotated local (not `cast()`, which mypy flags as redundant
            # once whole-package checking resolves the real type) narrows
            # explicitly so the declared return type holds under both
            # invocation shapes.
            matched: dict[str, str] = exception
            return matched
    return None


def _field_path_pins_for(path: str, omap: OccurrenceMap) -> tuple[str, ...]:
    """Return every field name pinned ``do_not_change`` by a field-scoped
    exception matching *path* (WP02, FR-002).

    Unlike :func:`_exception_for`, ALL matches apply, sorted for determinism
    — a single file can carry several distinct protected fields (e.g. an
    agent profile's ``directive-references`` AND ``tactic-references``,
    each declared as its own ``exceptions[]`` entry).
    """
    posix = Path(path).as_posix()
    pins = {
        fpe.field_path
        for fpe in omap.field_path_exceptions
        if _glob_match(posix, fpe.path)
    }
    return tuple(sorted(pins))


def _fnmatch_recursive(path: str, pattern: str) -> bool:
    """fnmatch with ``**`` expanded to match any number of path components."""
    # Turn the pattern into a regex:
    #   ``**`` -> ``.*``
    #   ``*``  -> ``[^/]*``
    #   ``?``  -> ``[^/]``
    placeholder = "\x00DOUBLESTAR\x00"
    regex = (
        pattern.replace("**", placeholder)
        .replace(".", r"\.")
        .replace("*", "[^/]*")
        .replace("?", "[^/]")
        .replace(placeholder, ".*")
    )
    return re.fullmatch(regex, path) is not None


# ---------------------------------------------------------------------------
# Runtime-state gate exemption (FR-007, C-004)
# ---------------------------------------------------------------------------

# IC-07e retirement (WP15, C-010): the former named-tuple runtime-state
# allowlist mechanism is gone. Its basenames split into two genuinely
# different concerns:
#
# * ``status.events.jsonl`` / ``status.json`` / ``issue-matrix.md`` /
#   ``acceptance-matrix.json`` are COORD-partition mission artifacts —
#   toolchain-generated churn a dirty-state gate must ignore. That
#   classification already has ONE canonical owner,
#   :func:`specify_cli.coordination.coherence.is_toolchain_generated_churn`
#   (FR-012); duplicating its basenames here was exactly the "ninth list" the
#   registry (WP10) forbids, so this exemption now delegates to it instead of
#   restating the basenames.
# * ``review-cycle-*.md`` / ``notes.md`` are the running mission's own
#   human-authored review/handoff commentary — NOT toolchain churn (the owner
#   deliberately has no opinion on them: neither has a ``MissionArtifactKind``,
#   and empirically ``is_toolchain_generated_churn`` returns ``False`` for
#   both). Routing them onto the owner would either pollute its boundary with
#   a review-commentary kind it has no business knowing about, or silently
#   drop the exemption and reintroduce a false block (a C-010 regression).
#   This is a genuine, justified must-keep (plan.md L233-235) — NOT a silent
#   survivor: it is registered as an explicit ``justified-survivor`` row,
#   ``tests/architectural/tool_artifact_enrolment/registry/
#   _is_review_lifecycle_basename.md``, so it stays visible to any audit of
#   unowned filename exemptions.


def _is_review_lifecycle_basename(basename: str) -> bool:
    """Return ``True`` for the mission's own review/handoff commentary files.

    A registered survivor mechanism (registry row
    ``_is_review_lifecycle_basename.md``, ``status: justified-survivor``): these
    two patterns are bulk-edit-review-specific domain knowledge that is
    genuinely outside :func:`is_toolchain_generated_churn`'s toolchain-generated-
    write scope, so it is kept here rather than grown onto the owner — see the
    registry row for the full C-010 justification.
    """
    return basename == "notes.md" or _glob_match(basename, "review-cycle-*.md")


# ---------------------------------------------------------------------------
# Files that cannot carry a textual occurrence
# ---------------------------------------------------------------------------

# Opaque binary payloads (fonts, images, archives, compiled objects) and
# generated dependency lockfiles. Neither can carry a *reviewable* textual
# occurrence of a rename target: the first is not text at all, the second is
# resolver output that is regenerated rather than edited.
#
# The occurrence-map schema has no action meaning "contains no occurrences"
# — its four actions are rename / manual_review / do_not_change /
# rename_if_user_visible — so without this class the only way to stop a
# webfont or a lockfile blocking review (FR-008, unclassified) is to label it
# with an action that is simply untrue of it. Recognising the class here
# keeps maps honest, and every match is still surfaced as a warning so the
# exemption is never silent.
# Deliberately limited to media and compiled output. Opaque *data* files
# (``.dat``, ``.bin``, ``.db``, ``.sqlite``, ``.pkl``, and compressed
# archives) are NOT here: they can carry serialized application data, and
# therefore a serialized-key occurrence, so they keep blocking as
# unclassified unless a reviewer names them in the map. Fonts, images, audio,
# video and compiled objects cannot.
_OPAQUE_SUFFIXES: frozenset[str] = frozenset({
    # Webfonts
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # Raster and vector assets
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".avif",
    ".svg", ".pdf",
    # Audio and video
    ".mp3", ".wav", ".ogg", ".flac", ".mp4", ".webm", ".mov",
    # Compiled objects
    ".so", ".dylib", ".dll", ".wasm", ".pyc", ".pyo", ".class", ".jar",
})

# Generated lockfiles, by exact basename. ``.lock`` alone is too broad to
# match on suffix (``*.lock`` is also used for ad-hoc mutex files).
_LOCKFILE_BASENAMES: frozenset[str] = frozenset({
    "Gemfile.lock", "poetry.lock", "uv.lock", "Pipfile.lock",
    "yarn.lock", "pnpm-lock.yaml", "package-lock.json", "bun.lockb",
    "Cargo.lock", "composer.lock", "go.sum", "mix.lock", "flake.lock",
})

# Empty-directory markers. Zero bytes by construction.
_PLACEHOLDER_BASENAMES: frozenset[str] = frozenset({".keep", ".gitkeep"})


def _in_foreign_mission_dir(path: str, feature_dir_rel: str | None) -> bool:
    """Return ``True`` if *path* is inside a mission directory that is not ours.

    ``kitty-specs/<slug>/...`` is the mission-artifact partition. A work
    package may create files under its OWN mission's directory, but creating
    them under another mission's is a cross-mission write (C-004) rather than
    anything an occurrence map has an opinion about — so the creation
    exemption must not cover it.
    """
    parts = Path(Path(path).as_posix()).parts
    if len(parts) < 2 or parts[0] != KITTY_SPECS_DIR:
        return False
    if not feature_dir_rel:
        # No anchor to compare against: treat every mission directory as
        # foreign, which is the fail-closed reading.
        return True
    return parts[1] != Path(feature_dir_rel.strip("/")).name


def _non_occurrence_reason(path: str) -> str | None:
    """Return why *path* cannot carry a textual occurrence, or ``None``.

    ``None`` means "this file is ordinary text"; the caller falls through to
    the path-heuristic classifier.
    """
    p = Path(Path(path).as_posix())
    basename = p.name
    if basename in _PLACEHOLDER_BASENAMES:
        return "empty-directory marker (zero bytes, no occurrences)"
    if basename in _LOCKFILE_BASENAMES:
        return (
            f"'{basename}' is a generated dependency lockfile — resolver "
            "output, regenerated rather than edited"
        )
    # ``.tar.gz`` and friends: any opaque component in the suffix chain is
    # enough, so ``typst-x86_64.tar.xz`` is recognised.
    for suffix in p.suffixes:
        if suffix.lower() in _OPAQUE_SUFFIXES:
            return (
                f"opaque binary payload ('{suffix}') — carries no reviewable "
                "textual occurrence"
            )
    return None


def _under_feature_dir(posix: str, feature_dir_rel: str) -> bool:
    """Return ``True`` if *posix* lives under *feature_dir_rel* (repo-root-relative)."""
    anchor = feature_dir_rel.strip("/")
    if not anchor:
        return False
    return posix == anchor or posix.startswith(f"{anchor}/")


def _own_bookkeeping_exemption(path: str, feature_dir_rel: str | None) -> FileAssessment | None:
    """Return an exemption verdict when *path* is the RUNNING mission's own runtime state.

    Anchored to *feature_dir_rel* — the running mission's OWN feature_dir,
    repo-root-relative — so this can only exempt paths under the mission
    currently being reviewed (C-004). ``None`` (no *feature_dir_rel*, the path
    is outside it, or the path is neither toolchain-generated churn nor a
    review-lifecycle file) means "not exempt here"; the caller falls through
    to the ordinary classifier.
    """
    if not feature_dir_rel:
        return None
    posix = Path(path).as_posix()
    if not _under_feature_dir(posix, feature_dir_rel):
        return None
    basename = Path(posix).name
    mission_slug = Path(feature_dir_rel).name or None
    if not is_toolchain_generated_churn(
        path, mission_slug=mission_slug
    ) and not _is_review_lifecycle_basename(basename):
        return None
    return FileAssessment(
        path=path,
        category=None,
        source="runtime-state",
        action=None,
        violation=False,
        reason=(
            f"'{basename}' is the mission's own runtime-state bookkeeping file "
            "(FR-007 allowlist) — exempt from occurrence classification."
        ),
    )


# ---------------------------------------------------------------------------
# Compliance check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileAssessment:
    """Per-file classification and verdict."""

    path: str
    category: str | None           # None => unclassified
    source: str                    # "path-heuristic" | "exception" | "move" | "structural-target" | "runtime-state"
    action: str | None             # None => no action defined in map
    violation: bool                # True when this file blocks approval
    reason: str                    # Human-readable rationale
    field_path_pins: tuple[str, ...] = ()  # WP02: fields pinned do_not_change


@dataclass(frozen=True)
class DiffCheckResult:
    """Aggregate verdict across all files in a WP diff."""

    passed: bool
    assessments: list[FileAssessment] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def assess_file(
    path: str,
    omap: OccurrenceMap,
    feature_dir_rel: str | None = None,
    status: str | None = None,
) -> FileAssessment:
    """Classify a single file and determine whether it violates the map.

    *feature_dir_rel* is the RUNNING mission's own ``feature_dir``, expressed
    as a repo-root-relative POSIX path. When provided, it anchors the
    runtime-state gate exemption (FR-007, C-004) so only this mission's own
    bookkeeping files are exempted — never another mission's.

    *status* is the file's git change status from ``git diff --name-status``
    (``"A"`` added, ``"M"`` modified, ``"D"`` deleted, ``"R"`` renamed).
    ``None`` means "unknown", which is treated as a modification — the
    conservative reading, and what every caller that passes only path
    strings gets.

    Field-scoped exceptions (WP02, FR-002) never change the base verdict
    computed below — they only ADD a :attr:`FileAssessment.field_path_pins`
    annotation naming the protected field(s), which
    :func:`check_diff_compliance` turns into a targeted warning.
    """
    base = _classify_file(path, omap, feature_dir_rel, status)
    pins = _field_path_pins_for(path, omap)
    if not pins:
        return base
    return replace(base, field_path_pins=pins)


def _classify_file(
    path: str,
    omap: OccurrenceMap,
    feature_dir_rel: str | None,
    status: str | None = None,
) -> FileAssessment:
    """The whole-file classification :func:`assess_file` pins fields onto."""
    # 0a) The running mission's own runtime-state bookkeeping.
    #
    # This MUST be tested before the map's own exceptions. These files are
    # written by spec-kitty itself on every `move-task`, so a mission whose
    # map carries a broad protective exception over its planning directory
    # (e.g. ``kitty-specs/**: do_not_change``, a reasonable thing to write
    # to protect an audit trail) would otherwise have that exception
    # pre-empt this exemption and block review on files the tool had just
    # written on the reviewer's behalf. The mission cannot sensibly protect
    # its artifacts *from the tool that generates them*, and the exemption
    # is already narrowly anchored to this mission's own feature_dir.
    runtime_state = _own_bookkeeping_exemption(path, feature_dir_rel)
    if runtime_state is not None:
        return runtime_state

    # 0b) Newly ADDED files.
    #
    # An occurrence map governs occurrences of the rename target in EXISTING
    # text: every category action is a statement about what may happen to
    # content that is already there ("rename it", "leave it alone", "judge
    # each one"). A file that this diff creates has no prior occurrence to
    # protect, so no category action can be violated by its creation.
    #
    # Without this, the gate reads every added file as though its protected
    # content had been edited, and any work package that brings a tree in —
    # an ingest, a vendored dependency, a generated migration — is blocked
    # wholesale on files it merely created. Deletions and renames are NOT
    # exempted here: removing or relocating a protected file is a genuine
    # change to it, and still classifies normally below.
    #
    # The exemption is reported as a warning by check_diff_compliance, so a
    # reviewer still sees every added path by name.
    #
    # It deliberately does NOT cover another mission's planning directory
    # (C-004): creating a file under `kitty-specs/<other-mission>/` is an
    # ownership violation, not an occurrence question, and the gate is the
    # place that catches it. Only this mission's own artifacts — already
    # handled by 0a above — are exempt there.
    if status == "A" and not _in_foreign_mission_dir(path, feature_dir_rel):
        return FileAssessment(
            path=path,
            category=None,
            source="added",
            action=None,
            violation=False,
            reason=(
                "File is CREATED by this diff — it has no pre-existing "
                "occurrence for the map to protect"
            ),
        )

    # 1) Exceptions take precedence over path heuristics.
    exception = _exception_for(path, omap)
    if exception is not None:
        action = exception.get("action")
        reason = exception.get("reason", "matched exception")
        if action == "do_not_change":
            return FileAssessment(
                path=path,
                category=None,
                source="exception",
                action=action,
                violation=True,
                reason=f"Exception '{exception.get('path', '?')}' marks this file do_not_change: {reason}",
            )
        return FileAssessment(
            path=path,
            category=None,
            source="exception",
            action=action,
            violation=False,
            reason=f"Exception '{exception.get('path', '?')}' allows {action!r}: {reason}",
        )

    # 2) Declared structural moves (IC-10, #1815). A move source/destination is
    #    a reviewer-approved relocation, so it is exempt from the
    #    do_not_change path heuristic.
    move = _move_for(path, omap)
    if move is not None:
        role, move_reason = move
        return FileAssessment(
            path=path,
            category=None,
            source="move",
            action="move",
            violation=False,
            reason=f"Declared structural {role}: {move_reason}",
        )

    # 3) Declared structural target. A reviewer-declared, per-file exemption
    #    (``structural_targets:``) naming a file whose changes in THIS
    #    mission are a genuine structural code edit rather than a bulk
    #    find/replace occurrence — narrow by construction (one path/glob at
    #    a time), never a blanket "ignore all src/*.py".
    structural_reason = _structural_target_for(path, omap)
    if structural_reason is not None:
        return FileAssessment(
            path=path,
            category=None,
            source="structural-target",
            action="structural_edit",
            violation=False,
            reason=f"Declared structural target: {structural_reason}",
        )

    # 4) Files that cannot carry a textual occurrence at all — opaque binary
    #    payloads, generated lockfiles, empty-directory markers. Tested
    #    AFTER the map's exceptions and declarations, so a reviewer who
    #    deliberately named such a path keeps whatever action they chose,
    #    and BEFORE the heuristic, which would otherwise block them as
    #    unclassified.
    non_occurrence = _non_occurrence_reason(path)
    if non_occurrence is not None:
        return FileAssessment(
            path=path,
            category=None,
            source="non-occurrence",
            action=None,
            violation=False,
            reason=non_occurrence,
        )

    # 5) Path heuristic classification.
    category = classify_path(path)
    if category is None:
        return FileAssessment(
            path=path,
            category=None,
            source="path-heuristic",
            action=None,
            violation=True,
            reason=(
                "File path does not match any standard occurrence category "
                "(FR-008: unclassified surface touched). Add an exception "
                "in occurrence_map.yaml if this file is expected."
            ),
        )

    # 6) The classified category must appear in the map.
    category_entry = omap.categories.get(category)
    if category_entry is None:
        return FileAssessment(
            path=path,
            category=category,
            source="path-heuristic",
            action=None,
            violation=True,
            reason=(
                f"File classified as '{category}' but that category is not "
                "present in the occurrence map (FR-008)."
            ),
        )

    action = category_entry.get("action")
    if action == "do_not_change":
        return FileAssessment(
            path=path,
            category=category,
            source="path-heuristic",
            action=action,
            violation=True,
            reason=(
                f"File classified as '{category}' which is marked "
                f"do_not_change (FR-007). Update the occurrence map or add "
                "an exception if this file is legitimately out of scope."
            ),
        )

    return FileAssessment(
        path=path,
        category=category,
        source="path-heuristic",
        action=action,
        violation=False,
        reason=(
            f"Category '{category}' action '{action}' permits modification."
        ),
    )


def check_diff_compliance(
    changed_files: list[str],
    omap: OccurrenceMap,
    feature_dir_rel: str | None = None,
    statuses: Mapping[str, str] | None = None,
) -> DiffCheckResult:
    """Assess every changed file and aggregate the verdict.

    *changed_files* is a list of repo-relative path strings obtained from
    ``git diff --name-status``. *feature_dir_rel* is the running mission's own
    ``feature_dir`` as a repo-root-relative POSIX path — see
    :func:`assess_file` for how it anchors the runtime-state exemption.

    *statuses* maps each path to its git change status (``A``/``M``/``D``/
    ``R``). It is optional: when a path is absent the file is treated as a
    modification, which is both the conservative reading and the behaviour
    every caller had before statuses existed.

    The function is pure — no I/O — so it can be unit-tested directly.
    """
    statuses = statuses or {}
    assessments = [
        assess_file(p, omap, feature_dir_rel, statuses.get(p)) for p in changed_files
    ]
    violations = [a for a in assessments if a.violation]
    errors = [f"{a.path}: {a.reason}" for a in violations]

    manual_review_files = [
        a for a in assessments if a.action == "manual_review"
    ]
    warnings = [
        f"{a.path}: category '{a.category}' requires manual_review — document justification"
        for a in manual_review_files
    ]
    warnings.extend(_field_path_pin_warnings(assessments))
    warnings.extend(_structural_target_warnings(assessments))
    warnings.extend(_created_file_warnings(assessments))
    warnings.extend(_non_occurrence_warnings(assessments))

    return DiffCheckResult(
        passed=len(violations) == 0,
        assessments=assessments,
        errors=errors,
        warnings=warnings,
    )


def _field_path_pin_warnings(assessments: list[FileAssessment]) -> list[str]:
    """Targeted per-field warnings (WP02, FR-002) — the reviewer reviews
    exceptions, not a whole-file sweep.

    Without field-path granularity, a file that carries both migrating AND
    protected content can only be flagged generically (blanket
    ``manual_review``), forcing a reviewer to eyeball every changed line. A
    field-scoped exception names exactly which field(s) must be verified
    unchanged, so the warning names them too.
    """
    return [
        f"{a.path}: field-path exception pins {', '.join(a.field_path_pins)} "
        "as do_not_change — verify only those fields were left untouched"
        for a in assessments
        if a.field_path_pins
    ]


def _created_file_warnings(assessments: list[FileAssessment]) -> list[str]:
    """Name every file exempted because this diff CREATES it.

    The exemption is sound (a new file has no prior occurrence) but it must
    not be silent: a work package that adds a thousand files has still added
    a thousand files a reviewer may want to look at, and the mission's
    occurrence decisions say nothing about any of them.
    """
    return [
        f"{a.path}: created by this diff — exempt from occurrence "
        "classification (no pre-existing occurrence); review the new file "
        "on its merits"
        for a in assessments
        if a.source == "added"
    ]


def _non_occurrence_warnings(assessments: list[FileAssessment]) -> list[str]:
    """Name every file exempted as incapable of carrying an occurrence."""
    return [
        f"{a.path}: {a.reason} — exempt from occurrence classification"
        for a in assessments
        if a.source == "non-occurrence"
    ]


def _structural_target_warnings(assessments: list[FileAssessment]) -> list[str]:
    """Per-file visibility warnings for every structural-target exemption.

    A MAJOR review finding: without this, a ``structural_targets`` exemption
    is invisible in gate output — a WP passes review with no trace that a
    ``do_not_change`` category was bypassed for a specific file. Mirrors
    :func:`_field_path_pin_warnings`'s per-file visibility idiom so every
    exemption that fires is named, with its reviewer-declared reason, in the
    same warnings list a human actually reads.
    """
    return [
        f"{a.path}: structural-target exemption applied ({a.reason}) — "
        "do_not_change bypass; verify this is a genuine structural edit, "
        "not a bulk-occurrence change"
        for a in assessments
        if a.source == "structural-target"
    ]
