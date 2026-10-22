"""The machine-global scope warning must stay in the env-var reference.

Regression cover for spec-kitty#3030. In the 2026-07-27 breach the operator
exported ``SPEC_KITTY_ENABLE_SAAS_SYNC`` into a shell — on our own advice — and
nothing in the documentation said that arming it there arms every project the
shell subsequently touches. The absent warning is why the shell was armed.

This test asserts on the *substance* (the variable name plus the phrase that
carries the meaning), not on a heading, because a heading anchor passes happily
against an emptied section.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_DOC = Path(__file__).resolve().parents[2] / "docs" / "api" / "environment-variables.md"


def test_env_var_reference_states_machine_global_scope() -> None:
    text = _DOC.read_text(encoding="utf-8")

    assert "SPEC_KITTY_ENABLE_SAAS_SYNC" in text
    assert "machine-global" in text, (
        "the env-var reference must state that the hosted-sync variable is "
        "machine-global; see spec-kitty#3030"
    )
    assert "no project-scoped form" in text, (
        "the reference must say the variable has no project-scoped form"
    )
    assert "every project that shell subsequently touches" in text, (
        "the reference must spell out the consequence of exporting in a shell"
    )
