"""Parsing, validation, and JSON-emit seam for ``agent mission`` (#2056 Seam C).

A one-way leaf module hosting the (mostly pure) tasks.md/spec.md/WP-file parsers,
the owned-files validators, and the JSON-envelope emit shims that ``mission.py``
(and the WP09 shim re-export, plus ``tasks.py``'s
``_parse_requirement_refs_from_tasks_md`` edge) share. Behavior is preserved
byte-for-byte from the pre-decomposition ``mission.py``; the WP01 golden harness
and ``test_json_envelope_strict.py`` pin the envelope keys (INV-2).

INV-8: imports lower layers only (``core``, ``status``, ``requirement_mapping``,
``kernel``) — never back into ``mission`` or another seam.
"""

from __future__ import annotations

import json
from pathlib import Path

from kernel._safe_re import re
from specify_cli.cli.console import console

from specify_cli import __version__ as SPEC_KITTY_VERSION
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.ownership.models import WorkProductKind
from specify_cli.ownership.validation import _PLANNING_PREFIXES
from specify_cli.status import WPMetadata
from kernel.clock import now_utc_stamp
from kernel.paths import to_posix



# ---------------------------------------------------------------------------
# WP-id / parsing helpers
# ---------------------------------------------------------------------------


def _extract_wp_ids_from_task_files(wp_files: list[Path]) -> list[str]:
    """Return canonical WP IDs discovered from task filenames."""
    wp_ids: set[str] = set()
    for wp_file in wp_files:
        wp_id_match = re.match(r"^(WP\d{2})(?:[-_.]|$)", wp_file.name)
        if wp_id_match:
            wp_ids.add(wp_id_match.group(1))
    return sorted(wp_ids)


def _parse_wp_sections_from_tasks_md(tasks_content: str) -> dict[str, str]:
    """Extract WP sections from tasks.md keyed by WP ID."""
    sections: dict[str, str] = {}
    matches = list(
        re.finditer(
            r"(?m)^#{2,4}\s+(?:Work Package\s+)?(WP\d{2})(?:\b|:)",
            tasks_content,
        )
    )

    for idx, match in enumerate(matches):
        wp_id = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(tasks_content)
        sections[wp_id] = tasks_content[start:end]

    return sections


def _parse_dependencies_from_tasks_md(tasks_content: str) -> dict[str, list[str]]:
    """Parse WP dependencies from tasks.md content."""
    dependencies: dict[str, list[str]] = {}

    for wp_id, section_content in _parse_wp_sections_from_tasks_md(tasks_content).items():
        explicit_deps: list[str] = []

        # Pattern: "Depends on WP01" or "Depends on WP01, WP02"
        depends_matches = re.findall(
            r"Depends?\s+on\s+(WP\d{2}(?:\s*,\s*WP\d{2})*)",
            section_content,
            re.IGNORECASE,
        )
        for match in depends_matches:
            explicit_deps.extend(re.findall(r"WP\d{2}", match))

        # Pattern: "**Dependencies**: WP01" or "Dependencies: WP01, WP02"
        deps_line_matches = re.findall(
            r"\*?\*?Dependencies\*?\*?\s*:\s*(.+)",
            section_content,
            re.IGNORECASE,
        )
        for match in deps_line_matches:
            explicit_deps.extend(re.findall(r"WP\d{2}", match))

        dependencies[wp_id] = list(dict.fromkeys(explicit_deps))

    return dependencies


def _parse_requirement_refs_from_tasks_md(tasks_content: str) -> dict[str, list[str]]:
    """Parse requirement references per WP from tasks.md content."""
    requirement_refs: dict[str, list[str]] = {}

    for wp_id, section_content in _parse_wp_sections_from_tasks_md(tasks_content).items():
        refs: list[str] = []
        ref_line_matches = re.findall(
            r"\*?\*?Requirements?\s*(?:Refs)?\*?\*?\s*:\s*(.+)",
            section_content,
            re.IGNORECASE,
        )
        for match in ref_line_matches:
            refs.extend(ref_id.upper() for ref_id in re.findall(r"\b(?:FR|NFR|C)-\d+\b", match, re.IGNORECASE))
        requirement_refs[wp_id] = list(dict.fromkeys(refs))

    return requirement_refs


def _parse_requirement_refs_from_wp_files(wp_files: list[Path]) -> dict[str, list[str]]:
    """Parse requirement refs directly from WP prompt frontmatter."""
    from specify_cli.requirement_mapping import normalize_requirement_refs_value
    from specify_cli.status import read_wp_frontmatter

    parsed: dict[str, list[str]] = {}
    for wp_file in wp_files:
        wp_id_match = re.match(r"^(WP\d{2})(?:[-_.]|$)", wp_file.name)
        if not wp_id_match:
            continue
        wp_id = wp_id_match.group(1)
        try:
            meta, _ = read_wp_frontmatter(wp_file)
        except Exception:
            parsed.setdefault(wp_id, [])
            continue
        refs = normalize_requirement_refs_value(meta.requirement_refs)
        parsed[wp_id] = refs
    return parsed


def _parse_requirement_ids_from_spec_md(spec_content: str) -> dict[str, list[str]]:
    """Parse requirement IDs from spec.md content."""
    from specify_cli.requirement_mapping import parse_requirement_ids_from_spec_md

    return parse_requirement_ids_from_spec_md(spec_content)


def _find_undeclared_requirement_citations(spec_content: str) -> list[str]:
    """#3394 review F1: soft, non-blocking diagnostic for the declared-shape-miss case.

    Returns human-readable warning message(s) when spec.md contains raw
    FR-/NFR-/C-NNN-shaped tokens that matched none of the four recognized
    declared shapes (see ``requirement_mapping._declared_ids``) -- empty when
    there is nothing to warn about. Never raises, never blocks; callers
    surface the result as a console warning + a JSON field, not a gate.
    """
    from specify_cli.requirement_mapping import find_undeclared_requirement_citations

    return find_undeclared_requirement_citations(spec_content)


# ---------------------------------------------------------------------------
# Owned-files validators
# ---------------------------------------------------------------------------


def _normalize_owned_file_path(path: str) -> str:
    """Normalize a WP owned_files entry for repository-relative validation."""
    normalized = to_posix(path.strip())
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_mission_specs_owned_file(path: str) -> bool:
    """Return True when an owned_files entry targets mission planning artifacts."""
    normalized = _normalize_owned_file_path(path)
    return normalized == KITTY_SPECS_DIR or normalized.startswith(f"{KITTY_SPECS_DIR}/")


_EXPLICIT_EMPTY_OWNED_FILES_RE = re.compile(
    r"^owned_files:\s*\[\s*\]\s*$",
    re.MULTILINE,
)


def _owned_files_yaml_is_explicit_empty_list(wp_raw_content: str) -> bool:
    """Return True when WP frontmatter explicitly declares ``owned_files: []``.

    Distinguishes the operator's intent ("this WP owns no files") from the
    "field absent / default to empty" case, where the inference layer should
    populate owned_files from body text. Authored as part of the
    test-stabilization-and-debt-pass mission (Slice Q follow-up): without
    this distinction, planning-artifact WPs that legitimately own nothing
    in ``src/`` or ``tests/`` get their owned_files clobbered by inferred
    paths every time finalize-tasks runs, which then trips the ownership
    overlap validator.

    Only inspects the frontmatter region (between the first two ``---`` lines).
    """
    if not wp_raw_content.startswith("---"):
        return False
    # Frontmatter region is between the first two '---' lines.
    parts = wp_raw_content.split("---", 2)
    if len(parts) < 3:
        return False
    frontmatter = parts[1]
    return bool(_EXPLICIT_EMPTY_OWNED_FILES_RE.search(frontmatter))


def _raw_frontmatter_has_field(wp_raw_content: str, field_name: str) -> bool:
    """Return True when raw WP frontmatter explicitly declares ``field_name``."""
    if not wp_raw_content.startswith("---"):
        return False
    parts = wp_raw_content.split("---", 2)
    if len(parts) < 3:
        return False
    return (
        re.search(
            rf"^\s*{re.escape(field_name)}\s*:",
            parts[1],
            re.MULTILINE,
        )
        is not None
    )


def _raw_frontmatter_dependencies_is_string_form(wp_file: Path) -> bool:
    """Return True when WP frontmatter stores ``dependencies`` as a legacy string.

    The legacy forms (#3941, F-55) are ``dependencies: "[]"``,
    ``dependencies: "WP01, WP02"``, and the bare scalar
    ``dependencies: WP01``. ``WPMetadata`` coerces all of them to the
    canonical list at read time, so the string form is invisible to any
    consumer that only sees the typed model — including finalize-tasks'
    own change detector, which then concludes "nothing to write" and lets
    the string form survive into the tree.

    Detection goes through the canonical
    :class:`~specify_cli.frontmatter.FrontmatterManager` parse — the same
    parser ``WPMetadata`` validates from — so this stays *one* parser for
    the field: no second text-level grammar is introduced. A file that
    cannot be read or parsed is not a string-form declaration (the caller's
    own typed read surfaces that failure separately).
    """
    from specify_cli.frontmatter import FrontmatterManager

    try:
        raw_frontmatter, _ = FrontmatterManager().read(wp_file)
    except Exception:  # noqa: BLE001 — unreadable/invalid YAML is not a legacy declaration
        return False
    return isinstance(raw_frontmatter.get("dependencies"), str)


def _is_confined_planning_wp(metadata: WPMetadata) -> bool:
    """Return True when a WP is a ``planning_artifact`` confined to planning surfaces.

    The kitty-specs owned-files ban is lifted for such a WP (#3222 / #2643): a
    planning checkpoint whose only deliverables live under ``kitty-specs/``/``docs/``
    routes to the repo-root planning lane and may legitimately own its mission-specs
    artifacts. The exemption is granted **iff both**:

    1. ``execution_mode`` equals :data:`WorkProductKind.PLANNING_ARTIFACT` — compared
       against the enum ``.value`` (a normalized string compare) rather than relying
       on incidental ``StrEnum`` equality, so an unset/``None`` mode is never exempt.
    2. **Every** ``owned_files`` entry, normalized via
       :func:`_normalize_owned_file_path`, is under a prefix in
       :data:`_PLANNING_PREFIXES` (imported from ``ownership.validation`` — the single
       authority, not re-derived here).

    Condition 2 is the confinement guard (FR-004): a ``planning_artifact`` WP that
    also owns ``src/``/``tests/`` (or any other non-planning path) is **not** exempted,
    so mislabeling cannot become a backdoor to owning code on the planning lane. The
    check normalizes each entry first so confinement is symmetric with the ban
    predicate ``_is_mission_specs_owned_file``, which also matches on the normalized
    path (a ``./kitty-specs/…`` entry trips the ban yet must still count as confined).
    """
    if str(metadata.execution_mode) != WorkProductKind.PLANNING_ARTIFACT.value:
        return False
    return all(
        _normalize_owned_file_path(owned_file).startswith(_PLANNING_PREFIXES)
        for owned_file in metadata.owned_files
    )


def _invalid_mission_specs_owned_files(
    frontmatter_by_wp: dict[str, WPMetadata],
) -> list[dict[str, str]]:
    """Return structured invalid owned_files entries for finalize-tasks errors.

    A ``planning_artifact`` WP confined to planning surfaces is exempt from the
    kitty-specs ban (see :func:`_is_confined_planning_wp`); every other WP —
    including a ``code_change`` WP and a mislabeled planning WP that also owns a
    non-planning path — stays fail-closed (INV-1).
    """
    invalid: list[dict[str, str]] = []
    for wp_id, metadata in sorted(frontmatter_by_wp.items()):
        if _is_confined_planning_wp(metadata):
            continue
        for owned_file in metadata.owned_files:
            if _is_mission_specs_owned_file(owned_file):
                invalid.append({"wp_id": wp_id, "path": owned_file})
    return invalid


# Dynamic alias preserved from mission.py: the alias name is built from
# ``KITTY_SPECS_DIR`` at runtime (``.replace("-", "_")``) so callers (and patch
# targets) keep resolving the ``_invalid_<dir>_owned_files`` symbol unchanged,
# without hardcoding a raw mission-spec literal in source.
globals()["_invalid_" + KITTY_SPECS_DIR.replace("-", "_") + "_owned_files"] = _invalid_mission_specs_owned_files


# ---------------------------------------------------------------------------
# JSON emit shims + misc
# ---------------------------------------------------------------------------


def _with_cli_version(payload: dict[str, object]) -> dict[str, object]:
    """Attach CLI version metadata to JSON payloads for log observability."""
    if "spec_kitty_version" in payload:
        return payload
    enriched = dict(payload)
    enriched["spec_kitty_version"] = SPEC_KITTY_VERSION
    return enriched


def _with_mission_aliases(payload: dict[str, object]) -> dict[str, object]:
    """Return canonical mission nouns only on live JSON surfaces."""
    return dict(payload)


def _emit_json(payload: dict[str, object]) -> None:
    """Emit a deterministic single JSON object."""
    print(json.dumps(_with_cli_version(_with_mission_aliases(payload))))


def _emit_console_or_json_error(*, json_output: bool, message: str) -> None:
    """Emit a command error consistently across human and JSON modes."""
    if json_output:
        _emit_json({"error": message})
    else:
        console.print(f"[red]Error:[/red] {message}")


def _utc_now_iso() -> str:
    """Return deterministic UTC timestamp string for prompt/runtime variables.

    Delegates to the door's ``now_utc_stamp()`` (kernel-clock-single-door
    WP12, FR-010) rather than reading the wall clock directly. Serialized
    output is byte-identical to before (NFR-004): ``now_utc_stamp()`` is
    defined as exactly ``DEFAULT_CLOCK.now().strftime(
    UTC_SECOND_TIMESTAMP_FORMAT)`` -- the same ``%Y-%m-%dT%H:%M:%SZ`` format
    `task_utils.support.now_utc` also delegates to.
    """
    return now_utc_stamp()
