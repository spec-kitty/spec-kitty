"""Single home of the CLI-wide --feature flag census (#5015).

``tests/specify_cli/cli/test_no_visible_feature_alias.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_cli_no_visible_feature_alias.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Iterator

from typer.main import get_command

from specify_cli import app as _typer_app
from tests import _click_universe as typer_click

# ---------------------------------------------------------------------------
# Resolve the underlying Click command tree.
# ---------------------------------------------------------------------------
# ``specify_cli`` exposes a Typer app. Sibling tests (e.g.
# ``test_decision_command_shape_consistency.py``) import that Typer app directly and let
# Typer's CliRunner handle the conversion. For introspection we want the
# Click command tree, which Typer can give us via ``get_command``.
cli: typer_click.Group = get_command(_typer_app)  # type: ignore[assignment]


def _walk_leaf_commands(group: typer_click.Group, prefix: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], typer_click.Command]]:
    """Yield (path_tuple, command) for every leaf command under ``group``."""
    for name, cmd in group.commands.items():
        path = prefix + (name,)
        if isinstance(cmd, typer_click.Group):
            yield from _walk_leaf_commands(cmd, path)
        else:
            yield path, cmd


def _param_declares_feature_flag(param: typer_click.Parameter) -> bool:
    """Return True iff the param's CLI surface declares ``--feature``.

    We deliberately match on declared option strings (``param.opts`` and
    ``param.secondary_opts``) rather than ``param.name``. The Python-side
    parameter happens to be named ``feature`` on several mission commands
    that bind it exclusively to ``--mission`` — those are not what FR-006
    is policing.
    """
    declared = list(getattr(param, "opts", []) or []) + list(getattr(param, "secondary_opts", []) or [])
    return "--feature" in declared


def test_every_feature_flag_is_hidden() -> None:
    """Every ``--feature`` flag on every leaf command must carry hidden=True.

    Defensively reads ``hidden`` via ``getattr`` so a future Click/Typer
    upgrade that renames or restructures the attribute fails loudly here
    rather than silently letting an alias re-surface.

    NOTE (FR-009 / mission feature-alias-removal-01KW0N87): After WP01–WP03
    all ``--feature`` flags were hard-removed from user-facing commands.  This
    test now passes trivially because there are no ``--feature`` parameters at
    all — see ``test_zero_feature_flags_exist_cli_wide`` for the stronger
    zero-presence assertion.
    """
    offenders: list[str] = []
    for path, cmd in _walk_leaf_commands(cli):
        for param in cmd.params:
            if _param_declares_feature_flag(param) and not getattr(param, "hidden", False):
                offenders.append(" ".join(path))
    assert not offenders, "FR-006 regression: --feature flag is visible on these commands (must be hidden=True):\n  " + "\n  ".join(offenders)


def test_zero_feature_flags_exist_cli_wide() -> None:
    """After alias removal, no ``--feature`` Typer option should exist anywhere in the CLI.

    Stronger companion to ``test_every_feature_flag_is_hidden``: asserts that
    the CLI tree contains ZERO ``--feature`` parameters (hidden or visible),
    not merely that any remaining ones are hidden.

    Authority: spec.md FR-009 / mission feature-alias-removal-01KW0N87 WP04.
    """
    feature_options: list[str] = []
    for path, cmd in _walk_leaf_commands(cli):
        for param in cmd.params:
            if _param_declares_feature_flag(param):
                feature_options.append(" ".join(path))
    assert feature_options == [], (
        f"Found {len(feature_options)} '--feature' option(s) in CLI tree on "
        f"command(s): {feature_options}.  All --feature aliases must be removed "
        "(FR-009 / mission feature-alias-removal-01KW0N87)."
    )
