"""Common Docs retrieval CLI commands.

Provides ``spec-kitty docs query``, a first-class query surface over the
generated Common Docs retrieval index
(``docs/development/docs-retrieval-index.yaml``, produced by
``scripts/docs/docs_index.py``). The index is
loaded once per invocation and filtered entirely in memory (NFR-002) -- there
is no per-query filesystem walk.

Commands:
    docs query  -- Search page title / heading anchors / abstract for a term,
                   optionally narrowed by ``--divio-type`` or ``--section``.

Module layering (see ``data-model.md`` "Module layering (packaging-critical)"
and ``src/specify_cli/docs/index_model.py``'s own docstring): ``scripts/`` is
not shipped in the wheel, so this module imports the schema and query store
from the **packaged** ``specify_cli.docs.index_model`` -- never
``scripts.*``. There is no local mirror of ``DocsQueryEntry``/``Anchor``.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table
from ruamel.yaml.error import YAMLError

from specify_cli.cli.console import CliConsole, err_console
from specify_cli.docs.index_model import (
    DEFAULT_INDEX_PATH,
    Anchor,
    DivioType,
    DocsIndexStore,
    DocsQueryEntry,
)

app = typer.Typer(help="Common Docs retrieval commands")
# A deliberately wide, fixed-width console for the human table (mirrors
# glossary.py's `CliConsole(width=120)`) -- the shared, unwidened singleton
# would truncate repo-relative doc paths under the CliRunner's default
# non-tty width. Errors still route through the shared `err_console`.
console = CliConsole(width=120)

# `--divio-type` validates against the canonical, packaged
# `specify_cli.docs.index_model.DivioType` -- the single source the generator
# also coerces against, so the CLI and the emitted index cannot drift.
_VALID_DIVIO_TYPES: tuple[str, ...] = tuple(t.value for t in DivioType)

# `docs query` reads a pre-generated index. That index is an opt-in artifact of
# a project's own Common Docs tooling -- it is NOT deployed into consumer repos
# (the generator lives in the unshipped `scripts/` tree). So the hint is
# consumer-neutral: it explains the feature is opt-in and names the Spec Kitty
# self-host command only as a parenthetical, not as something every consumer can
# run.
_GENERATOR_HINT = (
    "`docs query` requires a committed Common Docs retrieval index, which this "
    "project does not have (it is an opt-in artifact; in the Spec Kitty "
    "repository itself, `python scripts/docs/docs_index.py --write` generates it)"
)


def _load_store() -> DocsIndexStore:
    """Load the generated docs retrieval index once for this invocation.

    Distinguishes a missing ``docs/`` tree from a missing (but expected)
    index file so the two get distinct, actionable messages -- neither case
    is a Python traceback, and neither is conflated with "no match" (which
    is a valid, successful query result, not an error).
    """
    # Paths resolve against the current working directory (matching the
    # glossary/inventory convention -- these commands are run from a project
    # root). The messages below say "current directory", not "this repository",
    # so an invocation from a subdirectory is not misreported as docs-less.
    # (A project-root walk-up is a possible future enhancement, deliberately
    # out of scope here to stay consistent with the sibling commands.)
    index_path = Path(DEFAULT_INDEX_PATH)
    if not index_path.exists():
        docs_root = Path("docs")
        if not docs_root.exists():
            err_console.print(
                "[red]Error: no docs/ tree found in the current directory.[/red]"
            )
        else:
            err_console.print(
                f"[red]Error: no Common Docs retrieval index at "
                f"{index_path}.[/red] {_GENERATOR_HINT}."
            )
        raise typer.Exit(1)
    try:
        return DocsIndexStore.load(index_path)
    except (OSError, YAMLError) as exc:
        # A syntactically malformed index (hand-edit, truncated write, leftover
        # merge markers) makes ruamel raise a YAMLError; an unreadable file
        # raises OSError. Either way, surface a clean, actionable one-line error
        # rather than a multi-frame traceback.
        err_console.print(
            f"[red]Error: could not read or parse the docs retrieval index at "
            f"{index_path}: {exc}[/red]"
        )
        raise typer.Exit(1) from exc


def _matching_anchors(
    entry: DocsQueryEntry, normalized_term: str, section: str | None
) -> list[Anchor]:
    """Return only the anchors of ``entry`` that matched the query (FR-003).

    An anchor is "matching" if the term substring hits its ``text`` or
    ``slug``, or if it is the anchor that satisfied an explicit ``--section``
    filter. Anchors that merely co-exist on a page matched via title/abstract
    are excluded -- the caller should be able to tell *which* heading hit.
    """
    matched: list[Anchor] = []
    for anchor in entry.anchors:
        term_hit = normalized_term in anchor.text.lower() or normalized_term in anchor.slug.lower()
        section_hit = section is not None and anchor.slug == section
        if term_hit or section_hit:
            matched.append(anchor)
    return matched


def _entry_to_dict(
    entry: DocsQueryEntry, normalized_term: str, section: str | None
) -> dict[str, object]:
    """Serialize one matched entry to the JSON element shape (cli-contract.md)."""
    anchors = _matching_anchors(entry, normalized_term, section)
    return {
        "path": entry.path,
        "title": entry.title,
        "divio_type": entry.divio_type,
        "abstract": entry.abstract,
        "anchors": [{"slug": a.slug, "text": a.text, "level": a.level} for a in anchors],
    }


def _validate_term(term: str) -> str:
    """Reject an empty/whitespace-only TERM with a usage error (exit 2)."""
    normalized = term.strip()
    if not normalized:
        raise typer.BadParameter("TERM must not be empty.")
    return normalized


def _validate_divio_type(divio_type: str | None) -> None:
    """Reject a ``--divio-type`` value outside the known set (exit 2)."""
    if divio_type is not None and divio_type not in _VALID_DIVIO_TYPES:
        raise typer.BadParameter(
            f"Invalid --divio-type '{divio_type}'. "
            f"Valid values: {', '.join(_VALID_DIVIO_TYPES)}."
        )


def _render_table(term: str, matches: list[DocsQueryEntry], section: str | None) -> None:
    """Render the human-readable result table for ``matches``."""
    if not matches:
        console.print(f"[dim]No docs pages match '{term}'.[/dim]")
        return

    normalized_term = term.strip().lower()
    table = Table(title=f"Docs matching '{term}'")
    table.add_column("Path", style="cyan")
    table.add_column("Title", style="bold")
    table.add_column("Type", style="yellow")
    table.add_column("Matching anchors")

    for entry in matches:
        anchors = _matching_anchors(entry, normalized_term, section)
        anchor_text = ", ".join(anchor.slug for anchor in anchors) if anchors else "-"
        table.add_row(entry.path, entry.title, entry.divio_type, anchor_text)

    console.print(table)


@app.command("query")
def query_command(
    term: str = typer.Argument(
        ...,
        help="Case-insensitive substring matched against title, anchor text/slug, and abstract.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON via plain print (no Rich markup).",
    ),
    divio_type: str | None = typer.Option(
        None,
        "--divio-type",
        help="Restrict to pages of this Divio type (tutorial|how-to|reference|explanation|none).",
    ),
    section: str | None = typer.Option(
        None,
        "--section",
        help="Restrict to pages containing an anchor with this slug.",
    ),
) -> None:
    """Query the Common Docs retrieval index for pages matching TERM."""
    normalized_term = _validate_term(term)
    _validate_divio_type(divio_type)

    store = _load_store()
    matches = store.query(normalized_term, divio_type=divio_type, section=section)

    if json_output:
        normalized_lower = normalized_term.lower()
        output = [_entry_to_dict(entry, normalized_lower, section) for entry in matches]
        # Plain `print`, NOT Rich `console.print`/`print_json` -- guarantees no
        # markup/ANSI leaks into piped `--json` output (contract risk #1).
        print(json.dumps(output, indent=2))
        return

    _render_table(term, matches, section)
