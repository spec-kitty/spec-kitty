"""Explicit fetch scope composes across renderers; argv never interprets prose."""

from dataclasses import replace
from pathlib import Path
import shlex

import pytest

from charter.activation.scope import CharterScope, CharterScopeConflict, OwnedCharterInvocation
from charter.activation.context_renderers.fetch_stanza import fetch_command


def _scope() -> CharterScope:
    root = Path("/owned path ';$(touch PWNED)")
    return replace(CharterScope.default(root), invocation=OwnedCharterInvocation(root, "canonical-mission"))


@pytest.mark.parametrize("selector", ["directive:MANT_003", "directive:space name", "directive:$(touch PWNED);'quoted'"])
def test_fetch_arguments_round_trip_as_single_shell_words(selector: str) -> None:
    scope = _scope()
    assert shlex.split(fetch_command(selector, scope=scope)) == [
        "spec-kitty",
        "charter",
        "context",
        "--include",
        selector,
        "--owned-checkout",
        str(scope.root),
        "--mission",
        "canonical-mission",
    ]


def test_default_fetch_bytes_remain_unchanged() -> None:
    assert fetch_command("directive:MANT_003") == "spec-kitty charter context --include directive:MANT_003"


def test_inconsistent_scope_cannot_emit_a_fetch_claim() -> None:
    with pytest.raises(CharterScopeConflict):
        replace(CharterScope.default(Path("/other")), invocation=_scope().invocation)


def test_composed_profile_renderers_thread_scope() -> None:
    from charter.activation.context_renderers.profile_sections import _render_profile_sections
    from tests.charter.test_emit_delivery_bind import _fixture_profile, _fixture_service

    text = _render_profile_sections(_fixture_profile(), _fixture_service(), scope=_scope())
    commands = [line.strip()[5:] for line in text.splitlines() if line.strip().startswith("Run: ")]
    assert commands
    for command in commands:
        assert shlex.split(command)[-4:] == ["--owned-checkout", str(_scope().root), "--mission", "canonical-mission"]


@pytest.mark.parametrize("handle", ["", "..", "nested/mission"])
def test_fetch_scope_requires_canonical_mission_handle(handle: str) -> None:
    with pytest.raises(CharterScopeConflict):
        replace(CharterScope.default(Path("/owned")), invocation=OwnedCharterInvocation(Path("/owned"), handle))


@pytest.mark.parametrize("mode", ["sections", "selection"])
def test_budget_substitutions_keep_owned_invocation(mode: str) -> None:
    from charter.activation.context_renderers.token_budget import RenderedSection, apply_token_budget, _enforce_token_budget

    scope = _scope()
    if mode == "sections":
        text, _ = apply_token_budget(
            [RenderedSection(section_id="large", header="Large", body="x" * 2000, selector="directive:MANT_003")],
            budget=400,
            scope=scope,
        )
    else:
        from charter.activation.context_renderers.selection_block import _SELECTED_DIRECTIVES_HEADER

        selected = _SELECTED_DIRECTIVES_HEADER + "\n  - MANT_003\n" + "      Intent: " + "x" * 2000
        text = _enforce_token_budget(selected, action="implement", profile_block="", section_block="", selection_block=selected, budget=400, scope=scope)
    commands = [line.strip()[5:] for line in text.splitlines() if line.strip().startswith("Run: ")]
    assert commands
    for command in commands:
        assert shlex.split(command)[-4:] == ["--owned-checkout", str(scope.root), "--mission", "canonical-mission"]


def test_scope_inside_owned_checkout_must_still_contain_the_mission() -> None:
    with pytest.raises(CharterScopeConflict):
        replace(CharterScope.default(_scope().root / "other-package"), invocation=_scope().invocation)
