"""Red-first tests for the model-to-task_type catalog loader (FR-001).

Covers the non-fatal envelope required by the spec:
- valid catalog loads + validates + returns a fresh result
- missing catalog file -> None (non-fatal)
- whole-file-invalid YAML -> None (non-fatal), distinct from a malformed
  *entry* (schema-invalid data), which is allowed to raise
  ``pydantic.ValidationError`` -- that failure mode belongs to normal
  ``ModelToTaskType.model_validate`` behavior, not this loader's
  non-fatal envelope (see spec.md edge cases + WP01 context).
- stale catalog (per ``routing_policy.freshness_policy``) -> flagged,
  not silently dropped.

Also asserts the package-data resolution contract shared with WP05: the
loader's default path resolves to exactly
``src/charter/offering/model_task_routing/catalog/model-to-task_type.yaml`` via
``importlib.resources`` -- no "activation convention", no registry
lookup.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

VALID_MINIMAL_CATALOG = """\
schema_version: "1.0"
generated_at: "2025-06-01T12:00:00Z"
task_types:
  - id: code-generation
    title: Code Generation
models:
  - id: gpt-4o
    provider: openai
    task_fit:
      - task_type: code-generation
        score: 0.9
    cost:
      tier: high
routing_policy:
  objective: balanced
  weights:
    quality: 0.4
    cost: 0.3
    risk: 0.2
    latency: 0.1
  override_policy:
    mode: advisory
    require_reason: false
sources:
  - name: OpenAI pricing page
    url: https://openai.com/pricing
    access_method: manual
    snapshot_at: "2025-06-01T00:00:00Z"
"""

# Same shape as VALID_MINIMAL_CATALOG, plus a freshness_policy that makes a
# catalog "generated_at" a quarter-century ago unambiguously stale.
STALE_CATALOG = """\
schema_version: "1.0"
generated_at: "2000-01-01T00:00:00Z"
task_types:
  - id: code-generation
    title: Code Generation
models:
  - id: gpt-4o
    provider: openai
    task_fit:
      - task_type: code-generation
        score: 0.9
    cost:
      tier: high
routing_policy:
  objective: balanced
  weights:
    quality: 0.4
    cost: 0.3
    risk: 0.2
    latency: 0.1
  override_policy:
    mode: advisory
    require_reason: false
  freshness_policy:
    max_catalog_age_hours: 168
sources:
  - name: OpenAI pricing page
    url: https://openai.com/pricing
    access_method: manual
    snapshot_at: "2025-06-01T00:00:00Z"
"""

# A malformed *entry*: parses fine as YAML but violates the schema
# (score out of [0, 1] range, bad task_type pattern). Distinct from
# whole-file-invalid -- this must raise, not resolve to None.
MALFORMED_ENTRY_CATALOG = """\
schema_version: "1.0"
generated_at: "2025-06-01T12:00:00Z"
task_types:
  - id: Code-Gen
    title: Code Generation
models:
  - id: gpt-4o
    provider: openai
    task_fit:
      - task_type: Code-Gen
        score: 1.5
    cost:
      tier: high
routing_policy:
  objective: balanced
  weights:
    quality: 0.4
    cost: 0.3
    risk: 0.2
    latency: 0.1
  override_policy:
    mode: advisory
    require_reason: false
sources:
  - name: test
    url: https://example.com
    access_method: manual
    snapshot_at: "2025-06-01T00:00:00Z"
"""

WHOLE_FILE_INVALID_YAML = """\
schema_version: "1.0"
generated_at: "2025-06-01T12:00:00Z"
task_types: [this is: not, valid: yaml structure
"""


def _write_catalog(tmp_path: Path, content: str, name: str = "catalog.yaml") -> Path:
    catalog_path = tmp_path / name
    catalog_path.write_text(content, encoding="utf-8")
    return catalog_path


def test_valid_catalog_loads_and_validates(tmp_path: Path) -> None:
    from charter.offering.model_task_routing.loader import load

    catalog_path = _write_catalog(tmp_path, VALID_MINIMAL_CATALOG)

    result = load(catalog_path=catalog_path)

    assert result is not None
    assert result.catalog.schema_version == "1.0"
    assert result.catalog.models[0].id == "gpt-4o"
    assert result.is_stale is False


def test_missing_catalog_returns_none(tmp_path: Path) -> None:
    from charter.offering.model_task_routing.loader import load

    missing_path = tmp_path / "does-not-exist.yaml"

    assert load(catalog_path=missing_path) is None


def test_whole_file_invalid_yaml_returns_none(tmp_path: Path) -> None:
    from charter.offering.model_task_routing.loader import load

    catalog_path = _write_catalog(tmp_path, WHOLE_FILE_INVALID_YAML)

    assert load(catalog_path=catalog_path) is None


def test_empty_file_returns_none(tmp_path: Path) -> None:
    from charter.offering.model_task_routing.loader import load

    catalog_path = _write_catalog(tmp_path, "")

    assert load(catalog_path=catalog_path) is None


def test_malformed_entry_raises_validation_error_not_swallowed(
    tmp_path: Path,
) -> None:
    """A schema-invalid *entry* is a different failure mode than a
    whole-file-invalid document: it must not be silently absorbed into
    the loader's non-fatal envelope."""
    from charter.offering.model_task_routing.loader import load

    catalog_path = _write_catalog(tmp_path, MALFORMED_ENTRY_CATALOG)

    with pytest.raises(ValidationError):
        load(catalog_path=catalog_path)


def test_stale_catalog_is_flagged_not_dropped(tmp_path: Path) -> None:
    from charter.offering.model_task_routing.loader import load

    catalog_path = _write_catalog(tmp_path, STALE_CATALOG)

    result = load(catalog_path=catalog_path)

    assert result is not None
    assert result.is_stale is True


def test_catalog_without_freshness_policy_is_never_stale(tmp_path: Path) -> None:
    from charter.offering.model_task_routing.loader import load

    catalog_path = _write_catalog(tmp_path, VALID_MINIMAL_CATALOG)

    result = load(catalog_path=catalog_path)

    assert result is not None
    assert result.is_stale is False


def test_default_path_resolves_via_package_data_not_activation() -> None:
    """Shared contract with WP05: the default catalog path is exactly
    package data resolved via importlib.resources -- no activation
    registry, no ArtifactKind lookup."""
    from charter.offering.model_task_routing.loader import default_catalog_path

    resolved = default_catalog_path()

    assert resolved.parts[-4:] == (
        "offering",
        "model_task_routing",
        "catalog",
        "model-to-task_type.yaml",
    )


def test_load_with_no_argument_resolves_the_shipped_catalog() -> None:
    """With WP05's populated catalog now shipped as package data, calling
    load() with no override resolves the default package-data path and
    returns the parsed catalog (non-fatal, never raises). Proves WP01's
    default path and WP05's catalog location agree."""
    from charter.offering.model_task_routing.loader import load

    result = load()
    assert result is not None


def test_shipped_catalog_never_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix 4 (mission #2364 aggregate-review remediation): the packaged
    catalog's ``generated_at`` is a fixed value baked in at ship time. If
    ``routing_policy.freshness_policy.max_catalog_age_hours`` were set (as
    it originally was, to 4320h / 180 days), the SHIPPED catalog would
    silently flip ``is_stale`` to ``True`` ~180 days after that date with
    no code change and no test failure -- every dispatch recommendation
    would go inert simultaneously. The packaged default must omit
    ``max_catalog_age_hours`` (schema-legal: it is optional) so
    ``loader._is_stale`` always takes its "no freshness policy configured"
    branch. Freezing the clock far in the future is the actual proof --
    a merely-recent check would not catch a reintroduced finite
    max_catalog_age_hours.

    kernel-clock-single-door (WP05): the loader now reads the current
    instant via the door's ``now_utc()`` producer rather than a raw
    ``datetime.now(UTC)`` call, so the freeze point is ``loader_mod.now_utc``
    itself rather than a subclassed ``datetime.now``.
    """
    from charter.offering.model_task_routing import loader as loader_mod
    from kernel.clock import UTC, datetime

    monkeypatch.setattr(loader_mod, "now_utc", lambda: datetime(2099, 1, 1, tzinfo=UTC))

    result = loader_mod.load()

    assert result is not None
    assert result.is_stale is False
