"""Kernel runtime-shape reader (fail-closed) and WP-iteration rule."""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.mission_runtime_shape import (
    read_runtime_shape_step_ids,
    step_ids_declare_wp_iteration,
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mission-runtime.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_steps_return_ordered_ids(tmp_path: Path) -> None:
    path = _write(tmp_path, "steps:\n  - {id: b, title: B}\n  - {id: a, title: A}\n")
    assert read_runtime_shape_step_ids(path) == ["b", "a"]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "steps: [unclosed",
        "- not-a-mapping\n",
        "steps: nope\n",
        "steps:\n  - {id: a, title: A}\n  - {title: B}\n",
        "steps:\n  - {id: a, title: A}\n  - {id: b}\n",
        "steps:\n  - {id: a, title: A}\n  - just-a-string\n",
    ],
)
def test_malformed_shapes_fail_closed(tmp_path: Path, text: str) -> None:
    assert read_runtime_shape_step_ids(_write(tmp_path, text)) == []


def test_missing_file_fails_closed(tmp_path: Path) -> None:
    assert read_runtime_shape_step_ids(tmp_path / "absent.yaml") == []


def test_wp_iteration_rule() -> None:
    assert step_ids_declare_wp_iteration(["specify", "plan", "implement", "review"]) is True
    assert step_ids_declare_wp_iteration(["specify", "research", "plan", "review"]) is False
    assert step_ids_declare_wp_iteration([]) is False
