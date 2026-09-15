"""YAML schema validation utilities for agent profiles."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from importlib.resources import files
from ruamel.yaml import YAML

from charter.offering.shared.errors import reject_inline_refs

AGENT_PROFILE_SCHEMA_FILENAME = "agent-profile.schema.yaml"


def reject_agent_profile_inline_refs(
    data: dict[str, Any], *, file_path: str
) -> None:
    """Raise ``InlineReferenceRejectedError`` if the agent-profile YAML
    carries a forbidden inline reference field."""
    reject_inline_refs(data, file_path=file_path, artifact_kind="agent_profile")


@lru_cache(maxsize=1)
def _load_agent_profile_schema() -> dict[str, Any]:
    """Load the agent-profile JSON schema (cached).

    Returns:
        Schema dict loaded from YAML file
    """
    try:
        # Try package resources first
        resource = files("charter.offering.schemas")
        if hasattr(resource, "joinpath"):
            schema_path = Path(str(resource.joinpath(AGENT_PROFILE_SCHEMA_FILENAME)))
        else:
            schema_path = Path(str(resource)) / AGENT_PROFILE_SCHEMA_FILENAME
    except (ModuleNotFoundError, TypeError):
        # Fallback to relative path
        schema_path = Path(__file__).parent.parent / "schemas" / AGENT_PROFILE_SCHEMA_FILENAME

    yaml = YAML(typ="safe")
    with schema_path.open() as f:
        schema_data: dict[str, Any] = yaml.load(f)

    return schema_data


def validate_agent_profile_yaml(data: dict[str, Any]) -> list[str]:
    """Validate a dict against the agent-profile YAML schema.

    Args:
        data: Dictionary loaded from agent profile YAML file

    Returns:
        List of validation error messages (empty if valid)
    """
    # #4409: imported here, not at module scope. ``jsonschema`` eagerly loads
    # its format checkers, and one of them (``rfc3987_syntax.syntax_helpers``,
    # reached via ``jsonschema._format``) costs ~1.75s to import — over half of
    # `spec-kitty --help`'s total startup, paid by every CLI invocation even
    # though nothing on that path validates a schema.
    import jsonschema  # noqa: PLC0415 — deferred: see the cost note above

    schema = _load_agent_profile_schema()
    validator = jsonschema.Draft7Validator(schema)

    errors = []
    for error in validator.iter_errors(data):
        # Build a human-readable error message
        field_path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{field_path}: {error.message}")

    return errors


def is_agent_profile_file(file_path: Path) -> bool:
    """Check if a file is an agent profile YAML file.

    Args:
        file_path: Path to check

    Returns:
        True if file has .agent.yaml extension
    """
    return file_path.suffix == ".yaml" and file_path.stem.endswith(".agent")
