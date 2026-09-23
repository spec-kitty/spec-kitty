"""Lightweight shell-completion fast path for the Spec Kitty CLI.

Shell completion is latency-critical: every TAB press spawns ``spec-kitty`` with
a ``_SPEC_KITTY_COMPLETE`` instruction in the environment.  Building the full
Typer application imports the entire command tree (status, events, upgrade,
migration, tool-surface, ...), which costs ~0.8-2.2 s on a warm venv — far over
the mission's 500 ms responsiveness budget (NFR-001 / SC-003).

This module avoids that by completing command/subcommand *names* from a small,
pre-generated manifest (``_completion_manifest.MANIFEST``).  The manifest is
turned into a throwaway ``TyperGroup``/``TyperCommand`` tree carrying only names,
help text, hidden, and deprecated flags — no callbacks, no implementation
imports — and handed to Typer's own completion machinery so the emitted output
is byte-for-byte identical to the full application across bash/zsh/fish/pwsh.

Only pure command-name navigation is served here.  As soon as an option token
(anything starting with ``-``) appears on the completion line we return ``None``
so the caller falls back to the full application, which knows every command's
options and value completers.  This keeps the fast path correct: it can only
ever emit the same command names the real app would, never wrong suggestions.

Drift between the manifest and the real command tree is caught in CI by
``tests/specify_cli/cli/commands/test_completion_fast_path.py`` (it rebuilds the
real app, regenerates the manifest, and compares completion output byte-wise).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping
    from pathlib import Path

PROG_NAME = "spec-kitty"
COMPLETE_VAR = "_SPEC_KITTY_COMPLETE"

# Environment variables the Typer completion classes read to learn the current
# command line.  We only consult them to decide whether an option token is
# present (the fast-path fallback gate); Typer itself re-reads them when it
# generates candidates.
_COMPLETION_LINE_ENV_VARS = (
    "COMP_WORDS",
    "_TYPER_COMPLETE_ARGS",
    "_TYPER_COMPLETE_WORD_TO_COMPLETE",
)


def _completion_line_has_option(env: Mapping[str, str]) -> bool:
    """Return True if any token on the completion line looks like an option.

    Options and option values are out of scope for the manifest, so their
    presence forces a fallback to the full application.
    """
    for var in _COMPLETION_LINE_ENV_VARS:
        value = env.get(var)
        if not value:
            continue
        for token in value.split():
            if token.startswith("-"):
                return True
    return False


def _build_command_tree(manifest: dict[str, Any]) -> Any:
    """Build a throwaway Typer command tree from the manifest.

    The tree carries only the attributes shell completion reads (name, help,
    hidden, deprecated, child order). It performs no implementation imports.
    """
    from typer.core import TyperCommand, TyperGroup

    def build(node: dict[str, Any], name: str | None) -> Any:
        children = node.get("commands")
        if children is not None:
            group = TyperGroup(name=name)
            group.help = node.get("help") or None
            group.hidden = bool(node.get("hidden", False))
            group.deprecated = bool(node.get("deprecated", False))
            for child_name, child in children.items():
                group.add_command(build(child, child_name), name=child_name)
            return group
        command = TyperCommand(name=name)
        command.help = node.get("help") or None
        command.hidden = bool(node.get("hidden", False))
        command.deprecated = bool(node.get("deprecated", False))
        return command

    root_children = dict(manifest.get("commands", {}))
    root = {**manifest, "commands": root_children}
    return build(root, PROG_NAME)


_MANIFEST_FILENAME = "_completion_manifest.json"
_MANIFEST_CACHE: dict[str, Any] | None = None


def _manifest_path() -> Path:
    from pathlib import Path

    return Path(__file__).with_name(_MANIFEST_FILENAME)


def _load_manifest() -> dict[str, Any]:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        import json

        _MANIFEST_CACHE = json.loads(_manifest_path().read_text(encoding="utf-8"))
    return _MANIFEST_CACHE


def run_completion(env: Mapping[str, str] | None = None) -> int:
    """Emit completions from the manifest and return the process exit code."""
    active_env = os.environ if env is None else env
    instruction = active_env.get(COMPLETE_VAR, "")

    from typer._completion_classes import completion_init
    from typer.completion import shell_complete

    completion_init()
    command = _build_command_tree(_load_manifest())
    return shell_complete(command, {}, PROG_NAME, COMPLETE_VAR, instruction)


def maybe_run_completion(
    argv: list[str],  # noqa: ARG001 - kept for a uniform fast-path signature
    env: Mapping[str, str] | None = None,
) -> int | None:
    """Run the completion fast path when it applies; otherwise return ``None``.

    Returns an exit code when the fast path handled the request. Returns
    ``None`` (so the caller proceeds to the full application) when completion is
    not requested, an option token is present, or any error occurs while
    generating candidates — the full app then produces correct output.
    """
    active_env = os.environ if env is None else env
    if not active_env.get(COMPLETE_VAR):
        return None
    if _completion_line_has_option(active_env):
        return None
    try:
        return run_completion(active_env)
    except Exception:  # noqa: BLE001 - completion must never break; fall back to full app
        return None


def build_manifest_from_command(command: Any) -> dict[str, Any]:
    """Walk a resolved Click/Typer command into a serializable manifest node.

    Used by the manifest generator and the drift-guard test, not at runtime.
    """
    import click

    def walk(cmd: Any) -> dict[str, Any]:
        node: dict[str, Any] = {
            "help": cmd.help or "",
            "hidden": bool(getattr(cmd, "hidden", False)),
            "deprecated": bool(getattr(cmd, "deprecated", False)),
        }
        if hasattr(cmd, "list_commands"):
            # Use Click's public API. Typer 0.26 removed the private
            # ``typer._click`` compatibility module.
            ctx = click.Context(cmd, info_name=cmd.name)
            names = cmd.list_commands(ctx)
            if names:
                commands: dict[str, Any] = {}
                for name in names:
                    sub = cmd.get_command(ctx, name)
                    if sub is not None:
                        commands[name] = walk(sub)
                node["commands"] = commands
        return node

    return walk(command)


def generate_manifest() -> dict[str, Any]:
    """Build the real CLI application and capture its completion manifest.

    This imports the full command tree and is intentionally slow; it is only
    invoked by the regeneration helper and the drift-guard test, never on the
    completion hot path.

    ``SPEC_KITTY_ENABLE_SAAS_SYNC`` gates runtime behaviour inside a handful of
    commands (e.g. ``tracker``, ``mission create --from-ticket``), never their
    Typer registration, so the command tree captured here is identical
    regardless of that flag's value (the ``saas_gated`` manifest field this
    function used to compute died with the sync transport, issue #5, once its
    last consumer -- the ``tracker`` command -- started registering
    unconditionally).

    Landing fold (PR #4992): ``register_commands()`` reads the global
    ``sys.argv`` to decide lazy (single-leaf) vs full registration, so
    ``_build_app()`` returns an argv-dependent tree. Whatever ``sys.argv``
    happens to be live when this function runs (e.g. a real ``spec-kitty
    doctor ...`` process regenerating the manifest, or a test harness with
    its own argv) would otherwise silently narrow the captured tree. ``argv``
    is pinned to the bare program name -- which resolves to no single leaf --
    for the duration of the ``_build_app()`` call and restored in a
    ``finally``, so the manifest always reflects the FULL command set
    regardless of ambient argv.
    """
    import sys

    import specify_cli
    from typer.main import get_command

    saved_argv = sys.argv[:]
    sys.argv = [PROG_NAME]
    try:
        app = specify_cli._build_app()
    finally:
        sys.argv = saved_argv

    return build_manifest_from_command(get_command(app))


def render_manifest_json(manifest: dict[str, Any]) -> str:
    """Render the manifest as deterministic JSON text for the data file."""
    import json

    return json.dumps(manifest, indent=1, ensure_ascii=False) + "\n"


def regenerate_manifest_file() -> str:
    """Regenerate ``_completion_manifest.json`` from the live CLI; return its path."""
    manifest = generate_manifest()
    target = _manifest_path()
    target.write_text(render_manifest_json(manifest), encoding="utf-8")
    return str(target)


def _main(argv: list[str]) -> int:
    if "--regenerate" in argv:
        path = regenerate_manifest_file()
        print(f"Regenerated {path}")
        return 0
    print("usage: python -m specify_cli.completion --regenerate", flush=True)
    return 1


__all__ = [
    "maybe_run_completion",
]


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))
