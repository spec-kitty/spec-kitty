"""The finalize source helper must cover every module of the family (#5627)."""

from __future__ import annotations

import ast

import pytest

from tests._support.finalize_source import AGENT_DIR, FINALIZE_MODULE_PATHS, finalize_family_source

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_helper_lists_every_finalize_module_on_disk() -> None:
    on_disk = set(AGENT_DIR.glob("mission_finalize*.py"))
    assert set(FINALIZE_MODULE_PATHS) == on_disk


def test_family_source_parses_and_strips_the_routing_qualifier() -> None:
    source = finalize_family_source()
    tree = ast.parse(source)
    names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {"finalize_tasks", "_preserve_or_capture_planning_commit_sha", "_run_commit_pipeline"} <= names
    assert "_mf." not in source
