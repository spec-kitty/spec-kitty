"""Frontmatter migration that lets doc-kitty build ``docs/`` (#6929, ADR 2026-10-31-1 D-7/D-8).

Three rewrites, each frontmatter-only, each idempotent:

* **audience** — a persona path (``docs/context/audience/internal/maintainer.md``,
  scalar or list) becomes doc-kitty's profile list
  ``[{profile: internal/maintainer, guidance_text: …}]``. A free-text value keeps its
  text as the profile.
* **ADRs** — every dated ADR gains ``doc_status`` (``Accepted``/``Proposed`` ->
  ``active``, ``Superseded`` -> ``superseded``) and ``kind: ADR``; ``status``,
  ``date`` and ``superseded_by`` are untouched.
* **related** — an entry naming a published page becomes that page's slug. Anything
  else (a path outside ``docs/``, a non-Markdown file, a draft or excluded page) moves
  to ``external_references`` as a repository URL; an entry whose target no longer
  exists is dropped and reported.

How it edits: only the ``audience``/``related`` blocks are replaced and the
``doc_status``/``kind``/``external_references`` lines inserted; every other line, and
every character after the closing fence, is kept as it is. Each rewrite is re-parsed
and compared key by key, and any difference outside the intended keys aborts.

Usage::

    python -m scripts.docs.dockitty_frontmatter_migration --check
    python -m scripts.docs.dockitty_frontmatter_migration --apply
    python -m scripts.docs.dockitty_frontmatter_migration --verify-against origin/main

Kept for the migration and its re-runs (a later conflict with another docs PR is
resolved by re-running ``--apply``); dropped with the other migration-era tools at
DocFX retirement (ADR D-6).
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from ruamel.yaml import YAML

from scripts.ci.generated_docs_surfaces import is_generated_surface
from scripts.docs._dockitty_contract import (
    body_of,
    is_dated_adr,
    is_excluded,
    is_published,
    page_for_slug,
    persona_page,
    profile_of_persona_path,
    slug_of,
    split_frontmatter,
)
from scripts.docs._inventory import parse_frontmatter

__all__ = [
    "ADR_DOC_STATUS",
    "ADR_KIND",
    "Corpus",
    "MigrationError",
    "MigrationIntegrityError",
    "MigrationReport",
    "build_parser",
    "main",
    "migrate_text",
    "migrate_tree",
    "verify_against",
]

#: MADR ``status`` -> doc-kitty ``doc_status`` (ADR D-7; ruling 5: Proposed stays published).
ADR_DOC_STATUS: Final[Mapping[str, str]] = {"Accepted": "active", "Proposed": "active", "Superseded": "superseded"}
ADR_KIND: Final[str] = "ADR"

_AUDIENCE: Final[str] = "audience"
_RELATED: Final[str] = "related"
_EXTERNAL: Final[str] = "external_references"
_DOC_STATUS: Final[str] = "doc_status"
_KIND: Final[str] = "kind"
_STATUS: Final[str] = "status"
_TITLE: Final[str] = "title"
_DOCS_PREFIX: Final[str] = "docs/"
_REPO_URL: Final[str] = "https://github.com/spec-kitty/spec-kitty"
_PERSONA_TITLE_PREFIXES: Final[tuple[str, ...]] = ("Stakeholder Persona: ",)
_INTENDED_KEYS: Final[frozenset[str]] = frozenset({_AUDIENCE, _RELATED, _EXTERNAL, _DOC_STATUS, _KIND})

#: Files the migration never edits: #6928 owns the dual-index README stubs and the
#: architecture landing page; the era index tables are generated surfaces.
_SKIPPED_FILES: Final[frozenset[str]] = frozenset({"adr/1.x/README.md", "adr/2.x/README.md", "adr/3.x/README.md", "architecture/README.md"})
_SKIPPED_FOLDERS: Final[tuple[str, ...]] = ("changelog/unreleased/",)


class MigrationError(RuntimeError):
    """A page cannot be migrated mechanically (fail closed)."""


class MigrationIntegrityError(MigrationError):
    """A rewrite changed something other than the intended frontmatter keys."""


@dataclass(slots=True)
class MigrationReport:
    """What a run changed (or would change)."""

    changed_files: list[str] = field(default_factory=list)
    audience_files: int = 0
    adr_files: int = 0
    related_files: int = 0
    external_references: int = 0
    dropped_references: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """JSON shape of the report."""
        return {
            "changed_files": len(self.changed_files),
            "audience_files": self.audience_files,
            "adr_files": self.adr_files,
            "related_files": self.related_files,
            "external_references": self.external_references,
            "dropped_references": self.dropped_references,
        }


def _published_after_migration(rel: str, data: Mapping[str, Any]) -> bool:
    """Whether a page is published once the ADR rule has given an ADR its ``doc_status``."""
    if is_dated_adr(rel) and _DOC_STATUS not in data and isinstance(data.get(_STATUS), str):
        mapped = ADR_DOC_STATUS.get(data[_STATUS])
        if mapped is not None:
            return is_published(rel, {**data, _DOC_STATUS: mapped})
    return is_published(rel, data)


@dataclass(frozen=True, slots=True)
class _Source:
    """The page whose ``related`` list is being migrated, read from its own frontmatter."""

    rel: str
    excluded: bool
    published: bool

    @classmethod
    def of(cls, rel: str, data: Mapping[str, Any]) -> _Source:
        return cls(rel=rel, excluded=is_excluded(rel), published=_published_after_migration(rel, data))


@dataclass(frozen=True, slots=True)
class Corpus:
    """The docs tree as the rules need it: every page's frontmatter, keyed by path under ``docs/``."""

    docs_root: Path
    repo_root: Path
    frontmatter: Mapping[str, Mapping[str, Any]]

    @classmethod
    def load(cls, *, docs_root: Path, repo_root: Path) -> Corpus:
        """Read every ``docs/**/*.md`` page's frontmatter."""
        pages: dict[str, Mapping[str, Any]] = {}
        for path in sorted(docs_root.rglob("*.md")):
            rel = path.relative_to(docs_root).as_posix()
            pages[rel] = parse_frontmatter(path.read_text(encoding="utf-8"))
        return cls(docs_root=docs_root, repo_root=repo_root, frontmatter=pages)

    def published(self, rel: str) -> bool:
        """Whether the page at *rel* is published once the migration has run."""
        return _published_after_migration(rel, self.frontmatter.get(rel, {}))

    def related_target_allowed(self, source: _Source, target: str) -> bool:
        """Whether *source* may name *target* in ``related`` (doc-kitty resolves it in every build that builds *source*).

        An excluded source is never built, so any page will do. A draft source is built
        in a drafts-on preview, where draft targets exist but excluded ones never do. A
        published source is built with drafts off, so its target must be published.
        """
        if source.excluded:
            return True
        if not source.published:
            return not is_excluded(target)
        return self.published(target)

    def title(self, rel: str) -> str:
        """The page's title, or its path when it has none."""
        value = self.frontmatter.get(rel, {}).get(_TITLE)
        return value.strip() if isinstance(value, str) and value.strip() else f"docs/{rel}"

    def persona_name(self, profile: str) -> str | None:
        """The reader-facing persona name for *profile*, or ``None`` when no persona page exists."""
        page = persona_page(self.docs_root, profile)
        if page is None:
            return None
        title = self.title(page.relative_to(self.docs_root).as_posix())
        for prefix in _PERSONA_TITLE_PREFIXES:
            title = title.removeprefix(prefix)
        return title


# ---------------------------------------------------------------------------
# Rules: old value -> new value (pure, idempotent)
# ---------------------------------------------------------------------------


def _audience_entry(value: str, corpus: Corpus) -> dict[str, str]:
    text = value.strip()
    profile = profile_of_persona_path(text) or text
    name = corpus.persona_name(profile)
    guidance = f"Written for the {name} reader." if name else f"Written for {profile}."
    return {"profile": profile, "guidance_text": guidance}


def migrate_audience(value: object, corpus: Corpus) -> object:
    """Rule for ``audience``: path strings become ``{profile, guidance_text}`` entries."""
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list):
        raise MigrationError(f"audience is neither a string nor a list: {value!r}")
    entries: list[object] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            entries.append(_audience_entry(item, corpus))
        elif isinstance(item, Mapping):
            entries.append(dict(item))
        else:
            raise MigrationError(f"audience entry is not a persona path or profile: {item!r}")
    return entries


def adr_fields(rel: str, frontmatter: Mapping[str, Any]) -> dict[str, str]:
    """Rule for ADRs: the ``doc_status`` and ``kind`` a dated ADR must carry (empty for other pages)."""
    if not is_dated_adr(rel):
        return {}
    status = frontmatter.get(_STATUS)
    mapped = ADR_DOC_STATUS.get(status) if isinstance(status, str) else None
    if mapped is None:
        raise MigrationError(f"{rel}: ADR status {status!r} has no doc_status mapping")
    for key, wanted in ((_DOC_STATUS, mapped), (_KIND, ADR_KIND)):
        present = frontmatter.get(key)
        if present is not None and present != wanted:
            raise MigrationError(f"{rel}: {key} is {present!r}, expected {wanted!r} for status {status!r}")
    return {_DOC_STATUS: mapped, _KIND: ADR_KIND}


def _repo_url(repo_root: Path, repo_path: str) -> str:
    kind = "tree" if (repo_root / repo_path).is_dir() else "blob"
    return f"{_REPO_URL}/{kind}/main/{repo_path}"


def _external(corpus: Corpus, repo_path: str, title: str) -> dict[str, str]:
    return {"url": _repo_url(corpus.repo_root, repo_path), "title": title}


@dataclass(slots=True)
class _RelatedOutcome:
    related: list[object] = field(default_factory=list)
    external: list[dict[str, str]] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def _classify_docs_page(source: _Source, target: str, slug: str, corpus: Corpus, out: _RelatedOutcome) -> None:
    if corpus.related_target_allowed(source, target):
        out.related.append(slug)
    else:
        out.external.append(_external(corpus, f"{_DOCS_PREFIX}{target}", corpus.title(target)))


def _classify_entry(source: _Source, entry: str, corpus: Corpus, out: _RelatedOutcome) -> None:
    if entry.startswith(_DOCS_PREFIX):
        target = entry[len(_DOCS_PREFIX) :]
        if target.endswith(".md") and (corpus.docs_root / target).is_file():
            _classify_docs_page(source, target, slug_of(target), corpus, out)
            return
    else:
        page = page_for_slug(corpus.docs_root, entry)
        if page is not None:
            _classify_docs_page(source, page.relative_to(corpus.docs_root).as_posix(), entry, corpus, out)
            return
    if (corpus.repo_root / entry).exists():
        out.external.append(_external(corpus, entry.rstrip("/"), entry.rstrip("/")))
    else:
        out.dropped.append(entry)


def migrate_related(source: _Source, value: object, existing_external: object, corpus: Corpus) -> _RelatedOutcome:
    """Rule for ``related``: published pages by slug; everything else external or dropped."""
    if not isinstance(value, list):
        raise MigrationError(f"related is not a list: {value!r}")
    out = _RelatedOutcome()
    if isinstance(existing_external, list):
        out.external.extend(dict(item) for item in existing_external if isinstance(item, Mapping))
    for entry in value:
        if isinstance(entry, Mapping):
            out.related.append(dict(entry))
        elif isinstance(entry, str) and entry.strip():
            _classify_entry(source, entry.strip(), corpus, out)
        else:
            raise MigrationError(f"related entry is not a string or {{ref, note}}: {entry!r}")
    out.related = _dedupe(out.related)
    out.external = [ref for ref in _dedupe(out.external) if isinstance(ref, dict)]
    return out


def _dedupe(items: Sequence[object]) -> list[Any]:
    seen: list[object] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


# ---------------------------------------------------------------------------
# Line-level frontmatter editing
# ---------------------------------------------------------------------------


def _emit(key: str, value: object) -> list[str]:
    yaml = YAML(typ="safe", pure=True)
    yaml.default_flow_style = False
    yaml.width = 4096
    yaml.allow_unicode = True
    yaml.sort_base_mapping_type_on_output = False  # type: ignore[assignment]  # ruamel attribute missing from its stubs
    stream = io.StringIO()
    yaml.dump({key: value}, stream)
    return stream.getvalue().splitlines(keepends=True)


def _block_span(lines: Sequence[str], key: str) -> tuple[int, int] | None:
    """``(start, end)`` of the top-level block for *key* in frontmatter *lines* (fences excluded)."""
    for start, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            end = start + 1
            while end < len(lines) and lines[end][:1] in (" ", "\t", "-"):
                end += 1
            return start, end
    return None


@dataclass(slots=True)
class _Editor:
    lines: list[str]

    def replace(self, key: str, value: object | None) -> None:
        span = _block_span(self.lines, key)
        new = [] if value is None else _emit(key, value)
        if span is None:
            self.lines.extend(new)
        else:
            self.lines[span[0] : span[1]] = new

    def insert_after(self, anchor: str, key: str, value: object) -> None:
        span = _block_span(self.lines, anchor)
        at = len(self.lines) if span is None else span[1]
        self.lines[at:at] = _emit(key, value)


def _check_integrity(rel: str, old: Mapping[str, Any], new: Mapping[str, Any], intended: Mapping[str, Any]) -> None:
    for key in set(old) | set(new):
        if key in _INTENDED_KEYS:
            expected = intended[key] if key in intended else old.get(key)
            if new.get(key) != expected:
                raise MigrationIntegrityError(f"{rel}: {key} is {new.get(key)!r}, intended {expected!r}")
        elif old.get(key) != new.get(key):
            raise MigrationIntegrityError(f"{rel}: frontmatter key {key!r} changed")


def _is_skipped(rel: str) -> bool:
    return rel in _SKIPPED_FILES or rel.startswith(_SKIPPED_FOLDERS) or is_generated_surface(f"{_DOCS_PREFIX}{rel}")


def _intended_changes(rel: str, data: Mapping[str, Any], corpus: Corpus, report: MigrationReport) -> dict[str, Any]:
    """The new value of every key this page needs changed (``None`` deletes the key)."""
    intended: dict[str, Any] = {}
    if _AUDIENCE in data:
        audience = migrate_audience(data[_AUDIENCE], corpus)
        if audience != data[_AUDIENCE]:
            intended[_AUDIENCE] = audience
            report.audience_files += 1
    adr = {k: v for k, v in adr_fields(rel, data).items() if data.get(k) != v}
    if adr:
        intended.update(adr)
        report.adr_files += 1
    if _RELATED in data:
        outcome = migrate_related(_Source.of(rel, data), data[_RELATED], data.get(_EXTERNAL), corpus)
        report.dropped_references.extend({"from": f"{_DOCS_PREFIX}{rel}", "to": d} for d in outcome.dropped)
        new_related = outcome.related or None
        new_external = outcome.external or None
        if new_related != data[_RELATED] or new_external != data.get(_EXTERNAL):
            intended[_RELATED] = new_related
            intended[_EXTERNAL] = new_external
            report.related_files += 1
            report.external_references += len(outcome.external) - len(data.get(_EXTERNAL) or [])
    return intended


def _apply_edits(editor: _Editor, intended: Mapping[str, Any]) -> None:
    if _AUDIENCE in intended:
        editor.replace(_AUDIENCE, intended[_AUDIENCE])
    if _DOC_STATUS in intended:
        editor.insert_after(_STATUS, _DOC_STATUS, intended[_DOC_STATUS])
    if _KIND in intended:
        editor.insert_after(_DOC_STATUS, _KIND, intended[_KIND])
    if _RELATED in intended:
        external = intended.get(_EXTERNAL)
        if external is not None:
            editor.replace(_EXTERNAL, None)
            anchor = _RELATED if intended[_RELATED] is not None else None
            editor.replace(_RELATED, intended[_RELATED])
            if anchor is None:
                editor.lines.extend(_emit(_EXTERNAL, external))
            else:
                editor.insert_after(_RELATED, _EXTERNAL, external)
        else:
            editor.replace(_EXTERNAL, None)
            editor.replace(_RELATED, intended[_RELATED])


def migrate_text(rel: str, text: str, corpus: Corpus, report: MigrationReport | None = None) -> str:
    """Return *text* with its frontmatter migrated; the body is never touched.

    *rel* is the page's path under ``docs/``. Files the migration skips, and files
    without frontmatter, come back unchanged.
    """
    report = report if report is not None else MigrationReport()
    parts = split_frontmatter(text)
    if parts is None or _is_skipped(rel):
        return text
    block, body = parts
    data = parse_frontmatter(text)
    intended = _intended_changes(rel, data, corpus, report)
    if not intended:
        return text
    lines = block.splitlines(keepends=True)
    newline = "\r\n" if lines[0].endswith("\r\n") else "\n"
    editor = _Editor(lines=[line.replace("\r\n", "\n") for line in lines[1:-1]])
    _apply_edits(editor, intended)
    fence_close = lines[-1]
    new_block = lines[0] + "".join(line.replace("\n", newline) for line in editor.lines) + fence_close
    migrated = new_block + body
    _check_integrity(rel, data, parse_frontmatter(migrated), intended)
    if body_of(migrated) != body:
        raise MigrationIntegrityError(f"{rel}: body changed")
    return migrated


def migrate_tree(*, docs_root: Path, repo_root: Path, write: bool) -> MigrationReport:
    """Migrate every page under *docs_root*; write only when *write* is true."""
    corpus = Corpus.load(docs_root=docs_root, repo_root=repo_root)
    report = MigrationReport()
    for path in sorted(docs_root.rglob("*.md")):
        rel = path.relative_to(docs_root).as_posix()
        before = path.read_text(encoding="utf-8")
        after = migrate_text(rel, before, corpus, report)
        if after != before:
            report.changed_files.append(f"{_DOCS_PREFIX}{rel}")
            if write:
                path.write_bytes(after.encode("utf-8"))
    return report


# ---------------------------------------------------------------------------
# Verify a diff is frontmatter-only
# ---------------------------------------------------------------------------

_GitRunner = Callable[[Sequence[str]], str]


def _git(repo_root: Path) -> _GitRunner:
    def run(args: Sequence[str]) -> str:
        result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, check=True)
        return result.stdout

    return run


def verify_against(*, repo_root: Path, ref: str, docs_dir: str = "docs", git: _GitRunner | None = None) -> list[str]:
    """Every ``docs/**/*.md`` file changed since *ref* whose body differs from *ref* (added files skipped)."""
    run = git or _git(repo_root)
    changed = run(["diff", "--name-only", "--diff-filter=M", ref, "--", docs_dir]).splitlines()
    offenders: list[str] = []
    for rel in sorted(path for path in changed if path.endswith(".md")):
        before = run(["show", f"{ref}:{rel}"])
        after = (repo_root / rel).read_text(encoding="utf-8")
        if body_of(before) != body_of(after):
            offenders.append(rel)
    return offenders


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """The migration's command-line parser."""
    parser = argparse.ArgumentParser(prog="dockitty_frontmatter_migration", description=__doc__.splitlines()[0])
    parser.add_argument("--docs-root", type=Path, default=Path("docs"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report what would change; exit 1 when anything would.")
    mode.add_argument("--apply", action="store_true", help="Rewrite the frontmatter in place.")
    mode.add_argument("--verify-against", metavar="REF", help="Fail when a changed docs file's body differs from REF.")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    return parser


def _emit_report(report: MigrationReport, *, as_json: bool, mode: str) -> None:
    if as_json:
        sys.stdout.write(json.dumps({"mode": mode, **report.as_dict()}, indent=2, sort_keys=True) + "\n")
        return
    sys.stdout.write(
        f"{mode}: {len(report.changed_files)} file(s); audience {report.audience_files}, "
        f"ADR {report.adr_files}, related {report.related_files} "
        f"({report.external_references} external reference(s), {len(report.dropped_references)} dropped).\n"
    )
    for dropped in report.dropped_references:
        sys.stdout.write(f"  DROPPED {dropped['from']} -> {dropped['to']}\n")


def _print_lines(lines: Iterable[str]) -> None:
    for line in lines:
        sys.stdout.write(f"  {line}\n")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    args = build_parser().parse_args(argv)
    if args.verify_against:
        offenders = verify_against(repo_root=args.repo_root, ref=args.verify_against)
        sys.stdout.write(f"verify-against {args.verify_against}: {len(offenders)} body change(s).\n")
        _print_lines(offenders)
        return 1 if offenders else 0
    try:
        report = migrate_tree(docs_root=args.docs_root, repo_root=args.repo_root, write=args.apply)
    except MigrationError as exc:
        sys.stderr.write(f"dockitty_frontmatter_migration: ERROR: {exc}\n")
        return 2
    _emit_report(report, as_json=args.json, mode="apply" if args.apply else "check")
    return 1 if args.check and report.changed_files else 0


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
