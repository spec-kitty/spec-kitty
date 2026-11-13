"""The docs staleness inventory: one record per published living page (#7520, epic #3891).

The section passes (#7522-#7528) start from this inventory. A *published living page* is
a page the doc-kitty site publishes (``_dockitty_contract.published_pages``) outside the
immutable history folders ``adr/``, ``plans/``, ``reports/``, ``changelog/`` and
``archive/``. For each one the inventory records:

* ``last_content_change``: the newest commit that changed the page's text. Frontmatter,
  whitespace and link targets are ignored, so the frontmatter migration (#6929) and
  mechanical link rewrites (#6939) do not count. Renames are followed.
* ``paths_checked`` / ``paths_missing``: how many repository paths the page names (``src/...``,
  ``scripts/...``, ``tests/...``, ``.github/...``, ``packs/...``), checked against the tree.
  ``packs/`` paths resolve once ``make sync-packs`` has run.
* ``commands_checked`` / ``commands_missing``: how many ``spec-kitty`` commands the page names in
  code (fenced blocks and inline code spans), checked against the committed CLI command tree ``src/specify_cli/_completion_manifest.json``.
  A hidden or deprecated command counts as missing. A heuristic: arguments that look like
  command words can be read as a missing subcommand.
* ``readers``: the audience profiles the frontmatter names (``docs/context/audience/``).
* ``retired_surfaces``: the retired surfaces the page names in its body, ``title`` or
  ``description`` (:func:`scripts.docs._living_pages.published_text`, the same text the retired-surface gate scans).
* ``text_diagrams``: code fences drawn as text (box-drawing characters or arrow art in an
  untyped or ``text`` fence) that could move to build-time Mermaid or PlantUML. A heuristic.
* ``kind``, ``divio_signals``, ``mixed_types``: the declared kind and the Divio types its
  headings signal (``divio-type-discipline``). A heuristic, reported as a hint.

The inventory is generated on demand, never committed under ``docs/`` (its main field
changes with every docs commit; see the Mission plan, D-6)::

    python -m scripts.docs.staleness_audit --out <dir>

It writes ``<dir>/inventory.json`` and ``<dir>/page-lists.md`` (one list per section
sub-issue). Two runs on one commit write identical bytes. It needs the full history: on a
shallow clone it exits 2 and asks for ``git fetch --unshallow``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

# Runnable bare (`python3 scripts/docs/staleness_audit.py`): resolve `scripts.*` from the script, not the cwd.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs._dockitty_contract import body_of  # noqa: E402  (sys.path bootstrap above)
from scripts.docs._inventory import parse_frontmatter  # noqa: E402  (sys.path bootstrap above)
from scripts.docs._living_pages import living_pages, published_text  # noqa: E402  (sys.path bootstrap above)
from scripts.retired_surfaces import surfaces_named  # noqa: E402  (sys.path bootstrap above)

__all__ = [
    "DEFAULT_SECTION_ISSUE",
    "SECTION_ISSUES",
    "ContentChange",
    "ShallowHistoryError",
    "DivioReading",
    "GitHistory",
    "PageRecord",
    "build_inventory",
    "divio",
    "main",
    "named_commands",
    "named_paths",
    "readers",
    "render_json",
    "render_page_lists",
    "section_issue",
    "text_diagrams",
]

#: The section sub-issue of epic #3891 that owns each top-level section.
SECTION_ISSUES: Final[Mapping[str, str]] = {
    "context": "#7522",
    "guides": "#7523",
    "architecture": "#7524",
    "development": "#7525",
    "api": "#7526",
    "migrations": "#7527",
}
#: Every other section and the root pages (#7528: operations, configuration and the small sections).
DEFAULT_SECTION_ISSUE: Final[str] = "#7528"

_SMALL_SECTIONS: Final[str] = "operations/, configuration/ and the small sections"
#: The section title the page lists print for each sub-issue, derived from :data:`SECTION_ISSUES`.
_SECTION_TITLES: Final[Mapping[str, str]] = {**{issue: f"{head}/" for head, issue in SECTION_ISSUES.items()}, DEFAULT_SECTION_ISSUE: _SMALL_SECTIONS}

_DOCS: Final[str] = "docs"
_MANIFEST: Final[str] = "src/specify_cli/_completion_manifest.json"
_LINK_TARGET: Final[re.Pattern[str]] = re.compile(r"(\]\()[^)]*(\))")
_PATH: Final[re.Pattern[str]] = re.compile(r"(?<![\w./-])((?:src|scripts|tests|\.github|packs)/[\w./*-]+)")
_COMMAND: Final[re.Pattern[str]] = re.compile(r"(?<![\w./-])spec-kitty((?: [a-z][a-z0-9-]*)+)")
_FENCE: Final[re.Pattern[str]] = re.compile(r"^(`{3,}|~{3,})[ \t]*([\w+-]*)[^\n]*\n(.*?)^\1[ \t]*$", re.MULTILINE | re.DOTALL)
_INLINE_CODE: Final[re.Pattern[str]] = re.compile(r"`([^`\n]+)`")
_TEXT_FENCES: Final[frozenset[str]] = frozenset({"", "text", "txt", "ascii", "plain", "plaintext"})
_BOX_CHARS: Final[re.Pattern[str]] = re.compile(r"[┌┐└┘├┤┬┴┼─│═║╔╗╚╝╠╣╦╩╬►▶▼▲◄◀]")
_ARROW_ART: Final[re.Pattern[str]] = re.compile(r"-{2,}>|<-{2,}|={2,}>|\+-{3,}\+|\|\s*v\s*$")
_HEADING: Final[re.Pattern[str]] = re.compile(r"^#{2,6}\s+(.+?)\s*$", re.MULTILINE)
_QUADRANTS: Final[frozenset[str]] = frozenset({"Tutorial", "How-To", "Reference", "Explanation"})
#: Heading words that signal a Divio type (``divio-type-discipline``).
_SIGNALS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("Tutorial", re.compile(r"\b(tutorial|what you will (build|learn)|your first)\b", re.IGNORECASE)),
    ("How-To", re.compile(r"\b(prerequisites|steps?|how to|procedure|troubleshoot\w*)\b", re.IGNORECASE)),
    ("Reference", re.compile(r"\b(options|flags|fields|parameters|arguments|exit codes|schema|syntax)\b", re.IGNORECASE)),
    ("Explanation", re.compile(r"\b(why|rationale|background|trade-?offs?|design|history|concepts?)\b", re.IGNORECASE)),
)


def section_issue(page: str) -> str:
    """The section sub-issue (#7522-#7528) a page under ``docs/`` belongs to."""
    head, _, rest = page.partition("/")
    return SECTION_ISSUES.get(head, DEFAULT_SECTION_ISSUE) if rest else DEFAULT_SECTION_ISSUE


# --- Last real content change ---------------------------------------------------------


@dataclass(frozen=True)
class ContentChange:
    """The commit that last changed a page's text, with its author date (``YYYY-MM-DD``)."""

    sha: str
    date: str


def content_signature(text: str) -> str:
    """The page text that counts as content: body only, link targets dropped, whitespace collapsed."""
    return " ".join(_LINK_TARGET.sub(r"\1\2", body_of(text)).split())


class ShallowHistoryError(RuntimeError):
    """The repository is a shallow clone, so a page's oldest content change cannot be told apart from the graft."""


class GitHistory:
    """Reads page history from git: one ``git log --follow`` per page, blobs through one ``cat-file --batch``.

    A shallow clone is refused (:class:`ShallowHistoryError`): its boundary commit has no
    parent, so every page older than the graft would be dated at the graft.
    """

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root
        self._batch: subprocess.Popen[bytes] | None = None
        if self._git("rev-parse", "--is-shallow-repository").strip() == "true":
            raise ShallowHistoryError(
                f"{repo_root} is a shallow clone, so the last content change of older pages would read as the "
                "graft commit; run `git fetch --unshallow` (read-only) and generate the inventory again"
            )

    def _git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self._root, capture_output=True, text=True, check=True).stdout

    def _blob(self, revision: str) -> str | None:
        if self._batch is None:
            self._batch = subprocess.Popen(["git", "cat-file", "--batch"], cwd=self._root, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        stdin, stdout = self._batch.stdin, self._batch.stdout
        assert stdin is not None and stdout is not None  # both are pipes (Popen above)
        stdin.write(revision.encode("utf-8") + b"\n")
        stdin.flush()
        header = stdout.readline().split()
        if len(header) != 3:  # "<rev> missing"
            return None
        data = stdout.read(int(header[2]))
        stdout.read(1)  # the newline after each object
        return data.decode("utf-8", errors="replace")

    def close(self) -> None:
        """Stop the ``cat-file`` process."""
        if self._batch is not None:
            self._batch.communicate()
            self._batch = None

    def last_content_change(self, repo_path: str) -> ContentChange | None:
        """The newest commit whose change to *repo_path* (renames followed) altered its content signature."""
        log = self._git("log", "--follow", "--format=@%H %as", "--name-only", "--", repo_path)
        entries: list[tuple[str, str, str]] = []
        for chunk in log.split("@")[1:]:
            lines = [line for line in chunk.splitlines() if line.strip()]
            sha, date = lines[0].split()
            entries.append((sha, date, lines[-1] if len(lines) > 1 else repo_path))
        for index, (sha, date, path) in enumerate(entries):
            after = self._blob(f"{sha}:{path}")
            before_path = entries[index + 1][2] if index + 1 < len(entries) else path
            before = self._blob(f"{sha}^:{before_path}")
            if after is None or before is None or content_signature(after) != content_signature(before):
                return ContentChange(sha=sha, date=date)
        return None


# --- What a page names ------------------------------------------------------------------


def named_paths(body: str, repo_root: Path) -> tuple[list[str], list[str]]:
    """Repository paths *body* names, and those missing from the tree (globs are never judged missing)."""
    named = sorted({match.rstrip(".,:;)`'\"/") for match in _PATH.findall(body)})
    missing = [path for path in named if "*" not in path and not (repo_root / path).exists()]
    return named, missing


def _resolve_command(manifest: Mapping[str, Any], words: list[str]) -> tuple[list[str], bool]:
    """The command words name, and whether the CLI has it live (not hidden, not deprecated).

    A group with subcommands consumes the next word, which must be one of them; a leaf
    command stops the walk, and the words after it are its arguments.
    """
    node: Mapping[str, Any] = manifest
    walked: list[str] = []
    for word in words:
        children = node.get("commands") or {}
        if not children and walked:
            return walked, True
        if word not in children:
            return [*walked, word], False
        node = children[word]
        walked.append(word)
        if node.get("hidden") or node.get("deprecated"):
            return walked, False
    return walked, True


def _code_text(body: str) -> str:
    """The code in *body*: fenced blocks and inline code spans, where a page names a command."""
    fenced = [match.group(3) for match in _FENCE.finditer(body)]
    inline = _INLINE_CODE.findall(_FENCE.sub("", body))
    return "\n".join([*fenced, *inline])


def named_commands(body: str, manifest: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """``spec-kitty`` commands *body* names in code, and those the CLI does not have (or hides).

    Only code is read (fenced blocks and inline code spans): prose such as "the spec-kitty
    project" names no command.
    """
    named: set[str] = set()
    missing: set[str] = set()
    for match in _COMMAND.finditer(_code_text(body)):
        walked, live = _resolve_command(manifest, match.group(1).split())
        command = " ".join(("spec-kitty", *walked))
        named.add(command)
        if not live:
            missing.add(command)
    return sorted(named), sorted(missing)


def readers(frontmatter: Mapping[str, Any]) -> list[str]:
    """The audience profiles the frontmatter names, sorted."""
    audience = frontmatter.get("audience")
    if not isinstance(audience, list):
        return []
    return sorted(str(entry["profile"]) for entry in audience if isinstance(entry, Mapping) and entry.get("profile"))


def text_diagrams(body: str) -> int:
    """How many untyped or ``text`` fences draw a diagram with box characters or arrow art."""
    count = 0
    for match in _FENCE.finditer(body):
        if match.group(2).lower() not in _TEXT_FENCES:
            continue
        content = match.group(3)
        if _BOX_CHARS.search(content) or sum(1 for line in content.splitlines() if _ARROW_ART.search(line)) >= 2:
            count += 1
    return count


@dataclass(frozen=True)
class DivioReading:
    """The declared kind, the Divio types the headings signal, and whether the page mixes types."""

    kind: str
    signals: tuple[str, ...]
    mixed: bool


def divio(kind: str, body: str) -> DivioReading:
    """Read a page's Divio type from its declared kind and its headings (a hint, not a verdict)."""
    headings = _HEADING.findall(body)
    signals = tuple(name for name, pattern in _SIGNALS if any(pattern.search(heading) for heading in headings))
    # A quadrant page mixes when its headings signal another quadrant; a hub or other kind when they signal two.
    mixed = any(signal != kind for signal in signals) if kind in _QUADRANTS else len(signals) > 1
    return DivioReading(kind=kind, signals=signals, mixed=mixed)


# --- The inventory ------------------------------------------------------------------------


@dataclass(frozen=True)
class PageRecord:
    """One published living page and what the audit found on it."""

    page: str
    section_issue: str
    updated: str
    last_content_change: str | None
    last_content_commit: str | None
    readers: list[str]
    kind: str
    divio_signals: list[str]
    mixed_types: bool
    paths_checked: int
    paths_missing: list[str]
    commands_checked: int
    commands_missing: list[str]
    retired_surfaces: list[str]
    text_diagrams: int


def _record(repo_root: Path, page: str, history: GitHistory, manifest: Mapping[str, Any]) -> PageRecord:
    text = (repo_root / _DOCS / page).read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    body = body_of(text)
    change = history.last_content_change(f"{_DOCS}/{page}")
    paths, missing_paths = named_paths(body, repo_root)
    commands, missing_commands = named_commands(body, manifest)
    reading = divio(str(frontmatter.get("kind") or ""), body)
    return PageRecord(
        page=page,
        section_issue=section_issue(page),
        updated=str(frontmatter.get("updated") or "")[:10],
        last_content_change=change.date if change else None,
        last_content_commit=change.sha if change else None,
        readers=readers(frontmatter),
        kind=reading.kind,
        divio_signals=list(reading.signals),
        mixed_types=reading.mixed,
        paths_checked=len(paths),
        paths_missing=missing_paths,
        commands_checked=len(commands),
        commands_missing=missing_commands,
        retired_surfaces=sorted(surfaces_named(published_text(text))),
        text_diagrams=text_diagrams(body),
    )


def build_inventory(repo_root: Path) -> list[PageRecord]:
    """One record per published living page, in page order."""
    manifest = json.loads((repo_root / _MANIFEST).read_text(encoding="utf-8"))
    history = GitHistory(repo_root)
    try:
        return [_record(repo_root, page, history, manifest) for page in living_pages(repo_root / _DOCS)]
    finally:
        history.close()


def render_json(records: Iterable[PageRecord], head: str) -> str:
    """``inventory.json``: the commit it was built from and one compact record per line, sorted keys."""
    lines = ",\n".join(json.dumps(asdict(record), sort_keys=True, ensure_ascii=False, separators=(",", ":")) for record in records)
    header = json.dumps({"commit": head, "kind": "docs-staleness-inventory", "version": 1}, sort_keys=True)[:-1]
    return f'{header}, "pages": [\n{lines}\n]}}\n'


def _row(record: PageRecord) -> str:
    cells = (
        f"`{record.page}`",
        record.last_content_change or "-",
        record.updated or "-",
        ", ".join(record.readers) or "**none**",
        record.kind + (" (mixed)" if record.mixed_types else ""),
        ", ".join(f"`{surface}`" for surface in record.retired_surfaces) or "-",
        str(len(record.paths_missing) + len(record.commands_missing)) if record.paths_missing or record.commands_missing else "-",
        str(record.text_diagrams) if record.text_diagrams else "-",
    )
    return "| " + " | ".join(cells) + " |"


def render_page_lists(records: Iterable[PageRecord], head: str) -> str:
    """``page-lists.md``: one table per section sub-issue, oldest content first."""
    by_issue: dict[str, list[PageRecord]] = {}
    for record in records:
        by_issue.setdefault(record.section_issue, []).append(record)
    lines = [
        "# Docs refresh page lists (#7520)",
        "",
        f"Generated by `python -m scripts.docs.staleness_audit` at commit `{head[:12]}`. One list per",
        "section sub-issue of #3891. Columns: last content change (frontmatter, whitespace and",
        "link-target edits ignored), the `updated` frontmatter date, the named reader, the declared",
        "kind (mixed: the headings signal another Divio type), retired surfaces named, missing paths",
        "and commands, and text-drawn diagrams. Pages are listed oldest content first.",
    ]
    header = "| Page | Content changed | `updated` | Reader | Kind | Retired surfaces | Missing refs | Text diagrams |"
    for issue in sorted(_SECTION_TITLES):
        pages = sorted(by_issue.get(issue, []), key=lambda record: (record.last_content_change or "", record.page))
        lines += ["", f"## {_SECTION_TITLES[issue]} ({issue}): {len(pages)} pages", "", header, "|---|---|---|---|---|---|---|---|"]
        lines += [_row(record) for record in pages]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Write ``inventory.json`` and ``page-lists.md`` to ``--out``."""
    parser = argparse.ArgumentParser(prog="staleness_audit", description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--out", type=Path, required=True, help="Directory to write inventory.json and page-lists.md to.")
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
    try:
        records = build_inventory(repo_root)
    except ShallowHistoryError as error:
        print(f"staleness_audit: {error}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "inventory.json").write_text(render_json(records, head), encoding="utf-8")
    (args.out / "page-lists.md").write_text(render_page_lists(records, head), encoding="utf-8")
    print(f"staleness_audit: {len(records)} published living pages -> {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
