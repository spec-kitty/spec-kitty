"""PR-CONTRACT-001: ``_resolve_single_leaf_command`` must not misroute when a
root option precedes the command token.

Before this fix, ``_resolve_single_leaf_command`` treated every ``-``-prefixed
argv token as value-less and skipped straight to the first non-dash token as
the resolved command. That is safe today only because the real root app's
sole option (``--version``/``-v``) is boolean/eager and consumes no value --
nothing enforced that invariant. A future value-taking root option (e.g.
``--config PATH``) would have its VALUE token misread as the command name,
silently registering the wrong module (or none at all).

The fix derives the set of value-less ("boolean flag") root-option spellings
from the actual registered root callback (``app.registered_callback``) and
falls back to full registration (``None``) whenever it meets an option token
it cannot prove is value-less -- never guessing.
"""

from __future__ import annotations

import typer

from specify_cli.cli.commands import (
    _COMMAND_REGISTRARS,
    _resolve_single_leaf_command,
    _root_boolean_flag_tokens,
)


def _real_app() -> typer.Typer:
    """Build a Typer app with the real ``main_callback`` attached, mirroring
    ``specify_cli._build_app()``'s registration order (callback before
    ``register_commands``) without pulling in that function's heavier
    side effects (init-command registration, live-work fast-path checks)."""
    from specify_cli import main_callback

    app = typer.Typer()
    app.callback()(main_callback)
    return app


def _app_with_value_taking_root_option() -> typer.Typer:
    """A synthetic root app whose one option TAKES a value -- the shape the
    real CLI does not have today but that this function must stay safe
    against (the finding's own named risk)."""

    def synthetic_callback(
        ctx: typer.Context,  # noqa: ARG001
        config: str = typer.Option(None, "--config"),  # noqa: ARG001
    ) -> None:
        pass

    app = typer.Typer()
    app.callback()(synthetic_callback)
    return app


def _app_with_no_callback() -> typer.Typer:
    return typer.Typer()


def test_root_boolean_flag_tokens_recognizes_the_real_version_flag() -> None:
    app = _real_app()
    assert _root_boolean_flag_tokens(app) == frozenset({"--version", "-v"})


def test_root_boolean_flag_tokens_excludes_a_value_taking_option() -> None:
    app = _app_with_value_taking_root_option()
    assert "--config" not in _root_boolean_flag_tokens(app)
    assert _root_boolean_flag_tokens(app) == frozenset()


def test_root_boolean_flag_tokens_empty_without_a_registered_callback() -> None:
    assert _root_boolean_flag_tokens(_app_with_no_callback()) == frozenset()


def test_real_version_flag_still_resolves_the_command_that_follows_it() -> None:
    """Regression control: today's only root option (boolean/eager) must
    keep being skipped over so a command after it still resolves."""
    app = _real_app()
    assert _resolve_single_leaf_command(["spec-kitty", "-v", "merge"], app) == "merge"
    assert _resolve_single_leaf_command(["spec-kitty", "--version", "merge"], app) == "merge"


def test_command_with_no_leading_option_still_resolves() -> None:
    app = _real_app()
    assert _resolve_single_leaf_command(["spec-kitty", "merge"], app) == "merge"


def test_synthetic_value_taking_option_falls_back_to_full_registration() -> None:
    """The core regression this finding names: a value-taking root option's
    VALUE token must never be misread as the command name -- the resolver
    must instead fall back to ``None`` (full registration) as soon as it
    meets an option it cannot prove is value-less.

    The synthetic option value is a REAL ``_COMMAND_REGISTRARS`` key
    (``"merge"``) so this test is non-vacuous: the naive pre-fix
    skip-every-dash-token shape would misread "merge" (the --config value)
    as the resolved command and return it, not ``None``, and "charter" (a
    second real command name) sits right after it so a naive implementation
    that kept scanning would still land on a wrong-but-real command rather
    than coincidentally falling through to ``None``.
    """
    app = _app_with_value_taking_root_option()
    assert _resolve_single_leaf_command(["spec-kitty", "--config", "merge", "charter"], app) is None


def test_synthetic_value_taking_option_alone_also_falls_back() -> None:
    """Same collision as above, without a trailing command token: the naive
    shape would still misread "merge" (the --config value) as the resolved
    command and return it, not ``None``."""
    app = _app_with_value_taking_root_option()
    assert _resolve_single_leaf_command(["spec-kitty", "--config", "merge"], app) is None


def test_unrecognized_option_token_falls_back_even_on_the_real_app() -> None:
    """An option the resolver has never seen on the root callback (not even
    the version flag's own spelling) is never guessed at -- fall back."""
    app = _real_app()
    assert _resolve_single_leaf_command(["spec-kitty", "--totally-unknown-option", "merge"], app) is None


def test_help_before_command_still_returns_none() -> None:
    app = _real_app()
    assert _resolve_single_leaf_command(["spec-kitty", "--help"], app) is None
    assert _resolve_single_leaf_command(["spec-kitty", "-h", "merge"], app) is None


def test_unresolvable_command_name_still_returns_none() -> None:
    app = _real_app()
    assert _resolve_single_leaf_command(["spec-kitty", "not-a-real-command"], app) is None


def test_every_registrar_key_resolves_to_itself_on_the_real_app() -> None:
    """Sanity: the fix must not have narrowed which legitimate single-leaf
    commands resolve on the unmodified real callback."""
    app = _real_app()
    for name in _COMMAND_REGISTRARS:
        assert _resolve_single_leaf_command(["spec-kitty", name], app) == name
