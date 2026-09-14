"""YAML schema validation utilities for styleguides."""

from typing import Any


from charter.offering.shared.errors import reject_inline_refs
from charter.offering.shared.schema_utils import SchemaUtilities


def reject_styleguide_inline_refs(data: dict[str, Any], *, file_path: str) -> None:
    """Raise ``InlineReferenceRejectedError`` if the styleguide YAML carries a
    forbidden inline reference field."""
    reject_inline_refs(data, file_path=file_path, artifact_kind="styleguide")


def validate_styleguide(data: dict[str, Any]) -> list[str]:
    """Validate a dict against the styleguide YAML schema.

    Args:
        data: Dictionary loaded from styleguide YAML file.

    Returns:
        List of validation error messages (empty if valid).
    """
    schema = SchemaUtilities.load_schema("styleguide")
    # #4409: imported here, not at module scope. ``jsonschema`` eagerly
    # loads its format checkers, and one of them
    # (``rfc3987_syntax.syntax_helpers``, reached via ``jsonschema._format``)
    # costs ~1.8s to import — over half of `spec-kitty --help`'s startup,
    # paid by every CLI invocation even though nothing on that path
    # validates a schema. The sibling validation modules defer it the same
    # way; whichever loaded first used to pay for all of them.
    import jsonschema  # noqa: PLC0415 — deferred: see the cost note above

    validator = jsonschema.Draft202012Validator(schema)

    errors: list[str] = []
    for error in validator.iter_errors(data):
        field_path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{field_path}: {error.message}")

    return errors
