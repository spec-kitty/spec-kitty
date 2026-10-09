"""Runtime loader for the model-to-task_type routing catalog (FR-001).

The catalog is plain Python **package data** -- it is NOT an activatable
charter offering ``ArtifactKind``, and there is no "activation convention" here.
The ONLY default-resolution mechanism is :func:`importlib.resources.files`
pointed at ``src/charter/offering/model_task_routing/catalog/model-to-task_type.yaml``
(WP05's deliverable); :func:`load` also accepts an injectable
``catalog_path`` override so callers (and this module's own tests) can
point at a fixture catalog instead.

Non-fatal envelope (C-004 / spec.md edge cases):

- A **missing** catalog file resolves to ``None``.
- A **whole-file-invalid** YAML document (parse failure, or a top-level
  document that isn't a mapping) resolves to ``None``.
- A **malformed entry** -- a document that parses as YAML but fails
  ``ModelToTaskType`` schema validation -- is a *different* failure mode
  and is allowed to raise ``pydantic.ValidationError``. That belongs to
  normal ``model_validate`` behavior, not this loader's non-fatal
  envelope, so authoring bugs in the catalog data are not silently
  swallowed.
- A catalog whose ``generated_at`` exceeds
  ``routing_policy.freshness_policy.max_catalog_age_hours`` is still
  returned, flagged via :attr:`CatalogLoadResult.is_stale`. The loader
  does not decide to drop a stale catalog -- that decision belongs to
  the evaluator (a later WP) that consumes this result.

``load()`` is pure/deterministic: no hidden global state, no implicit
caching that could hide staleness from a caller re-checking freshness.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.model_task_routing.models import ModelToTaskType
from kernel.clock import UTC, now_utc, parse_iso

_CATALOG_PACKAGE = "charter.offering.model_task_routing"
_CATALOG_SUBPATH = ("catalog", "model-to-task_type.yaml")


@dataclass(frozen=True)
class CatalogLoadResult:
    """A successfully parsed and schema-validated catalog, plus a freshness flag."""

    catalog: ModelToTaskType
    is_stale: bool


def default_catalog_path() -> Path:
    """Resolve the packaged catalog path via ``importlib.resources``.

    Package data, not an activation-registry lookup -- see module
    docstring. Shared contract with WP05: this MUST resolve to
    ``src/charter/offering/model_task_routing/catalog/model-to-task_type.yaml``.
    """
    resource = files(_CATALOG_PACKAGE)
    for part in _CATALOG_SUBPATH:
        resource = resource.joinpath(part)
    return Path(str(resource))


def _read_yaml_document(catalog_path: Path) -> dict[str, object] | None:
    """Parse ``catalog_path`` as YAML.

    Returns ``None`` when the file is missing, is not parseable YAML, or
    its top-level document is not a mapping -- all "whole-file-invalid"
    per the non-fatal envelope. Does not attempt schema validation.
    """
    if not catalog_path.is_file():
        return None
    yaml_parser = YAML(typ="safe")
    try:
        document = yaml_parser.load(catalog_path.read_text(encoding="utf-8"))
    except (YAMLError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    return document


def _is_stale(catalog: ModelToTaskType) -> bool:
    """Apply ``routing_policy.freshness_policy`` against ``generated_at``.

    Returns ``False`` when no freshness policy is configured, or when
    ``generated_at`` cannot be parsed as an ISO-8601 timestamp -- an
    undeterminable freshness is treated as fresh rather than raising,
    consistent with the loader's non-fatal posture.
    """
    freshness = catalog.routing_policy.freshness_policy
    if freshness is None or freshness.max_catalog_age_hours is None:
        return False
    try:
        generated_at = parse_iso(catalog.generated_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    age_hours = (now_utc() - generated_at).total_seconds() / 3600
    return age_hours > freshness.max_catalog_age_hours


def load(catalog_path: Path | None = None) -> CatalogLoadResult | None:
    """Load and validate the model-to-task_type catalog.

    Args:
        catalog_path: Override path, e.g. a fixture catalog in a test.
            Defaults to :func:`default_catalog_path` (the packaged
            catalog resolved via ``importlib.resources``).

    Returns:
        ``None`` when the catalog is missing or whole-file-invalid
        (non-fatal). Otherwise a :class:`CatalogLoadResult` wrapping the
        validated catalog and its staleness flag.

    Raises:
        pydantic.ValidationError: when the document parses as YAML but a
            malformed entry fails ``ModelToTaskType`` schema validation.
    """
    resolved_path = catalog_path if catalog_path is not None else default_catalog_path()
    document = _read_yaml_document(resolved_path)
    if document is None:
        return None
    catalog = ModelToTaskType.model_validate(document)
    return CatalogLoadResult(catalog=catalog, is_stale=_is_stale(catalog))
