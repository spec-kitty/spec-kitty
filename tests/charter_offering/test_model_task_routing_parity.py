"""Schema/model parity coverage for model-task-routing."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from charter.offering.model_task_routing.models import ModelToTaskType

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "charter"
    / "offering"
    / "schemas"
    / "model-to-task_type.schema.yaml"
)


def _valid_catalog() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at": "2025-06-01T12:00:00Z",
        "task_types": [
            {
                "id": "code-generation",
                "title": "Code Generation",
            }
        ],
        "models": [
            {
                "id": "gpt-4o",
                "provider": "openai",
                "task_fit": [
                    {
                        "task_type": "code-generation",
                        "score": 0.9,
                    }
                ],
                "cost": {
                    "tier": "high",
                },
            }
        ],
        "routing_policy": {
            "objective": "balanced",
            "weights": {
                "quality": 0.4,
                "cost": 0.3,
                "risk": 0.2,
                "latency": 0.1,
            },
            "override_policy": {
                "mode": "advisory",
                "require_reason": False,
            },
        },
        "sources": [
            {
                "name": "OpenAI pricing page",
                "url": "https://openai.com/pricing",
                "access_method": "manual",
                "snapshot_at": "2025-06-01T00:00:00Z",
            }
        ],
    }


def _schema_validator() -> Draft202012Validator:
    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(schema, dict)
    return Draft202012Validator(schema)


def _with_path_value(
    catalog: dict[str, Any],
    path: tuple[str | int, ...],
    value: Any,
) -> dict[str, Any]:
    updated = deepcopy(catalog)
    cursor: Any = updated
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value
    return updated


def _generated_property(path: tuple[str, ...]) -> dict[str, Any]:
    schema = ModelToTaskType.model_json_schema(ref_template="#/definitions/{model}")
    cursor: dict[str, Any] = schema
    for part in path[:-1]:
        cursor = cursor["$defs"] if part == "definitions" else cursor[part]
    value = cursor[path[-1]]
    assert isinstance(value, dict)
    return value


def test_valid_catalog_is_accepted_by_model_and_schema() -> None:
    catalog = _valid_catalog()

    model = ModelToTaskType.model_validate(catalog)
    schema_errors = list(_schema_validator().iter_errors(catalog))

    assert model.generated_at == "2025-06-01T12:00:00Z"
    assert not schema_errors, [error.message for error in schema_errors]


@pytest.mark.parametrize(
    "path",
    [
        ("generated_at",),
        ("task_types", 0, "title"),
        ("models", 0, "id"),
        ("models", 0, "provider"),
        ("sources", 0, "name"),
        ("sources", 0, "url"),
        ("sources", 0, "snapshot_at"),
    ],
)
def test_required_string_emptiness_is_rejected_by_model_and_schema(
    path: tuple[str | int, ...],
) -> None:
    catalog = _with_path_value(_valid_catalog(), path, "")

    with pytest.raises(ValidationError) as exc_info:
        ModelToTaskType.model_validate(catalog)
    assert "string_too_short" in {
        str(error["type"]) for error in exc_info.value.errors()
    }

    schema_errors = list(_schema_validator().iter_errors(catalog))
    assert "minLength" in {error.validator for error in schema_errors}


@pytest.mark.parametrize(
    "path",
    [
        ("properties", "generated_at"),
        ("definitions", "TaskType", "properties", "title"),
        ("definitions", "ModelEntry", "properties", "id"),
        ("definitions", "ModelEntry", "properties", "provider"),
        ("definitions", "DataSource", "properties", "name"),
        ("definitions", "DataSource", "properties", "url"),
        ("definitions", "DataSource", "properties", "snapshot_at"),
    ],
)
def test_pydantic_schema_declares_required_strings_non_empty(
    path: tuple[str, ...],
) -> None:
    assert _generated_property(path)["minLength"] == 1
