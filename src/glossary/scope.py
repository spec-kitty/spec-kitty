"""GlossaryScope enum and scope resolution utilities."""

from __future__ import annotations

from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, PreservedScalarString

from kernel.clock import now_utc

from .models import Provenance, SenseStatus, TermSense, TermSurface


_SEED_METADATA_FIELDS = ("see_also", "synonyms_to_avoid", "introduced_in_mission")


class GlossaryScope(Enum):
    """Glossary scope levels in the hierarchy."""

    MISSION_LOCAL = "mission_local"
    TEAM_DOMAIN = "team_domain"
    AUDIENCE_DOMAIN = "audience_domain"
    SPEC_KITTY_CORE = "spec_kitty_core"


# Resolution order (highest to lowest precedence)
SCOPE_RESOLUTION_ORDER: list[GlossaryScope] = [
    GlossaryScope.MISSION_LOCAL,
    GlossaryScope.TEAM_DOMAIN,
    GlossaryScope.AUDIENCE_DOMAIN,
    GlossaryScope.SPEC_KITTY_CORE,
]


_STATUS_MAP = {
    "active": SenseStatus.ACTIVE,
    "deprecated": SenseStatus.DEPRECATED,
    "draft": SenseStatus.DRAFT,
}


def _parse_sense_status(raw: str | None) -> SenseStatus:
    """Map a status string to the corresponding SenseStatus enum value.

    Args:
        raw: Status string from seed file or event payload (e.g. "active",
            "deprecated", "draft"). None or unrecognised values default
            to DRAFT.

    Returns:
        Matching SenseStatus enum member.
    """
    if raw is None:
        return SenseStatus.DRAFT
    return _STATUS_MAP.get(raw, SenseStatus.DRAFT)


def load_seed_file(scope: GlossaryScope, repo_root: Path) -> list[TermSense]:
    """
    Load seed file for a scope.

    Args:
        scope: GlossaryScope to load
        repo_root: Repository root path

    Returns:
        List of TermSense objects from seed file
    """
    seed_path = repo_root / ".kittify" / "glossaries" / f"{scope.value}.yaml"

    if not seed_path.exists():
        return []  # Skip cleanly if not configured

    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        data = yaml.load(seed_path)
    except Exception as exc:
        from .exceptions import SeedFileValidationError, SeedValidationError

        raise SeedFileValidationError(
            seed_path,
            [
                SeedValidationError(
                    file_path=seed_path,
                    term_index=None,
                    term_surface=None,
                    field=None,
                    message=f"YAML parse error: {exc}",
                )
            ],
        ) from exc

    # Full Pydantic validation — raises SeedFileValidationError on failure
    from .seed_validation import validate_seed_file_data

    validate_seed_file_data(data, seed_path)

    senses = []
    for term_data in data.get("terms") or []:
        sense = TermSense(
            surface=TermSurface(term_data["surface"]),
            scope=scope.value,
            definition=term_data["definition"],
            provenance=Provenance(
                # kernel-clock-single-door FR-011: was naive `datetime.now()`
                # (local time, mislabeled) -- converted to aware-UTC via the
                # door. Byte-changing: `TermSense.timestamp.isoformat()`
                # (glossary/models.py) now emits a `+00:00` offset for
                # seed-loaded senses where it previously had none. See
                # research/migration-notes.md.
                actor_id="system:seed_file",
                timestamp=now_utc(),
                source="seed_file",
            ),
            confidence=term_data.get("confidence", 1.0),
            status=_parse_sense_status(term_data.get("status")),
        )
        senses.append(sense)

    return senses


def _default_header(scope: GlossaryScope) -> list[str]:
    return [f"# Spec Kitty glossary seed — scope: {scope.value}", ""]


def _needs_quoting(value: str) -> bool:
    return ": " in value or "'" in value


def _seed_scalar_value(value: str) -> str:
    if "\n" in value:
        return PreservedScalarString(value)
    if _needs_quoting(value):
        return DoubleQuotedScalarString(value)
    return value


def _load_existing_seed_metadata(seed_path: Path) -> dict[str, dict[str, Any]]:
    """Return accepted metadata fields keyed by term surface from an existing seed."""
    if not seed_path.exists():
        return {}

    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        data = yaml.load(seed_path)
    except Exception:
        return {}

    metadata: dict[str, dict[str, Any]] = {}
    for term_data in (data or {}).get("terms") or []:
        if not isinstance(term_data, dict):
            continue
        surface = term_data.get("surface")
        if not isinstance(surface, str):
            continue
        preserved = {
            field: term_data[field]
            for field in _SEED_METADATA_FIELDS
            if field in term_data
        }
        if preserved:
            metadata[surface] = preserved
    return metadata


def _dump_seed_body(data: dict[str, Any]) -> str:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    stream = StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()


def save_seed_file(
    scope: GlossaryScope,
    repo_root: Path,
    terms: list[TermSense],
) -> None:
    """Write terms to the seed file for *scope*, sorting alphabetically by surface.

    Creates the file if it does not exist. Preserves the header comment block of
    an existing file so hand-written documentation is not lost on update.
    """
    seed_path = repo_root / ".kittify" / "glossaries" / f"{scope.value}.yaml"
    seed_path.parent.mkdir(parents=True, exist_ok=True)

    from .seed_validation import validate_seed_file_data

    existing_metadata = _load_existing_seed_metadata(seed_path)
    sorted_terms = sorted(terms, key=lambda t: t.surface.surface_text.lower())

    output_data: dict[str, Any] = {"terms": []}
    for t in sorted_terms:
        term_entry: dict[str, Any] = {
            "surface": _seed_scalar_value(t.surface.surface_text),
            "definition": _seed_scalar_value(t.definition),
            "confidence": t.confidence,
            "status": t.status.value,
        }
        term_entry.update(existing_metadata.get(t.surface.surface_text, {}))
        output_data["terms"].append(term_entry)

    validate_seed_file_data(output_data, seed_path)

    # Preserve existing header comment lines; fall back to a generated one.
    if seed_path.exists():
        header: list[str] = []
        for line in seed_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped == "":
                header.append(line)
            else:
                break
    else:
        header = _default_header(scope)

    body = _dump_seed_body(output_data)
    prefix = "\n".join(header)
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"

    seed_path.write_text(prefix + body, encoding="utf-8")


def activate_scope(
    scope: GlossaryScope,
    version_id: str,
    mission_id: str,
    run_id: str,
    repo_root: Path | None = None,
) -> None:
    """
    Activate a glossary scope and emit GlossaryScopeActivated event.

    Args:
        scope: Scope to activate
        version_id: Glossary version ID
        mission_id: Mission ID
        run_id: Run ID
        repo_root: Repository root for event log persistence. If None,
            events are logged but not persisted to disk.
    """
    from .events import emit_scope_activated

    emit_scope_activated(
        scope_id=scope.value,
        glossary_version_id=version_id,
        mission_id=mission_id,
        run_id=run_id,
        repo_root=repo_root,
    )
