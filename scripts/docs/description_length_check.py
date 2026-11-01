"""``description`` metadata gate for the published documentation tree.

Every published page must carry a ``description`` that is **unique**, **not
boilerplate**, and **50-180 characters** long (the SEO band the DocFX build
publishes into ``<meta name=...>`` and the social cards).

This module is the *source-level* gate: it runs at PR time, needs no .NET, and
therefore blocks before merge — which the built-output verifier structurally
cannot do.

Which pages are in scope is **not** this module's decision. It asks
:func:`scripts.docs._published_pages.resolve_published_pages`, which reads
``docs/docfx.json`` — the same declaration the build follows. The gate used to
walk ``docs_root.rglob("*.md")`` itself, and its sibling in
``tests/docs/test_docs_seo.py`` used a hardcoded glob list; the two answers
diverged and the SEO gate spent months guarding 16 of 674 pages while reporting
green. There is now exactly one authority.

``--changed-from BASE_REF`` limits reported violations to changed, published
Markdown pages on PRs while retaining the complete published corpus as the
comparison context for uniqueness. A changed page that duplicates an unchanged
page therefore still fails, but a violation confined to an unchanged page does
not. Without the flag, the whole-tree behavior is unchanged.

A violation is one of:

* ``missing``     — no ``description`` key, or it is blank;
* ``boilerplate`` — the description is a known render-side fallback, i.e. the
  author wrote nothing and inherited the default (distinct from ``missing``
  because the two call for different author actions);
* ``too_short``   — ``len(description) < 50``;
* ``too_long``    — ``len(description) > 180``;
* ``duplicate``   — another published page carries the byte-identical
  description; every such violation names its colliding peers, because a
  one-sided uniqueness report is not actionable.

Output shape::

    { "checked_count": int,
      "violations": [ {"path": str, "reason": str,
                       "length": int | null, "peers": [str]} ] }

Exit codes:

===  =========================================================================
0    No violations, or violations under the default report-only mode.
1    ``--strict`` and at least one violation.
2    The gate could not establish a trustworthy page set (:class:`CoverageError`),
     or ``--changed-from`` could not resolve its Git base. Both are gate
     malfunctions and fail regardless of ``--strict``.
===  =========================================================================

Retirement (#6931, ADR 2026-10-31-1 D-6). D-6 marks this gate "port" to
``dockitty-validate-frontmatter`` and deletes it "in the step that ports it". That
binary is not on ``main`` yet (it arrives with the ``site/`` scaffold, #6930/#6937),
so deleting this module today would remove description enforcement with no
replacement. The retirement is therefore deferred, deliberately and in writing:
when the ``docs-site`` job runs ``dockitty-validate-frontmatter`` over the published
sections, delete this module and its tests, and move the 50-character lower bound
(an SEO rule of this repository, not of doc-kitty, which only bounds the upper end)
into whatever replaces it.

Depends only on the standard library plus ``ruamel.yaml`` (via
:func:`scripts.docs._inventory.parse_frontmatter`). No new dependency.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from scripts.docs import seo_postprocess
from scripts.docs._guards import GitDiffError, resolve_changed_files
from scripts.docs._inventory import parse_frontmatter
from scripts.docs._published_pages import (
    MINIMUM_EXPECTED_PAGES,
    PublishedPageSet,
    resolve_published_pages,
)
from scripts.docs.frontmatter_contract import (
    MAX_DESCRIPTION_LENGTH as MAX_DESCRIPTION_LENGTH_CONTRACT,
    MIN_DESCRIPTION_LENGTH as MIN_DESCRIPTION_LENGTH_CONTRACT,
)

__all__ = [
    "BOILERPLATE_DESCRIPTIONS",
    "DEFAULT_DOCS_ROOT",
    "EXIT_COVERAGE_FAILURE",
    "MAX_DESCRIPTION_LENGTH",
    "MIN_DESCRIPTION_LENGTH",
    "CoverageError",
    "LengthReport",
    "LengthViolation",
    "build_parser",
    "check_description_length",
    "main",
    "validate_descriptions",
    "validate_descriptions_diff_scoped",
]

DEFAULT_DOCS_ROOT: Final[str] = "docs"

# Historical note — the retired ``docs/adr/`` exclusion.
#
# This module used to hold every ADR body out of the gate:
#
#     #: Content-invariant doc subtree excluded from the description gate.
#     _EXCLUDE_PREFIXES: Final[tuple[str, ...]] = ("docs/adr/",)
#
# The stated justification was that ADR bodies are byte-identical to their
# pre-move originals (C-002, "enforced by ``test_adr_content_invariance``") and
# carry only bare ``status`` frontmatter, so by design they have no
# ``description``.
#
# That justification expired. The byte-identity content-invariance proof was a
# transitional gate for the move itself and was retired upstream on 2026-06-29
# (``ccd278061``); ``tests/docs/test_adr_content_invariance.py`` records this in
# its own docstring. The census gate that survived it asserts only a canonical
# ``status`` value and explicitly permits additional frontmatter keys, so
# nothing forbids an ADR from carrying a ``description`` — and the
# ``docs-seo-metadata-enforcement`` mission backfilled one onto all 151 of them.
# The exclusion is therefore gone: ADRs are in scope like every other published
# page, and the exclusions that remain are the enumerated, reasoned ones the
# resolver owns (``_published_pages.DEFAULT_EXCLUSIONS``).
#
# Scope note (DIRECTIVE_024): only the *description* exemption was retired. The
# structural-lint frontmatter contract still exempts ADR bodies through its own
# styleguide config; that exemption is deliberately untouched, because widening
# it would pull 151 files into a different contract's full field requirements.

#: Inclusive description length band (NFR-003). 50 and 180 are both **valid**;
#: 49 and 181 are violations. The band itself lives in the frontmatter-contract
#: module (#6931), which is the one place a docs frontmatter rule is stated: this
#: gate keeps its own *SEO* lower bound in the contract's constant table so the two
#: gates cannot disagree about the upper bound doc-kitty also enforces.
MIN_DESCRIPTION_LENGTH: Final[int] = MIN_DESCRIPTION_LENGTH_CONTRACT
MAX_DESCRIPTION_LENGTH: Final[int] = MAX_DESCRIPTION_LENGTH_CONTRACT

#: Exit code for a coverage failure — the gate could not trust its page set.
EXIT_COVERAGE_FAILURE: Final[int] = 2

_REASON_MISSING: Final[str] = "missing"
_REASON_BOILERPLATE: Final[str] = "boilerplate"
_REASON_TOO_SHORT: Final[str] = "too_short"
_REASON_TOO_LONG: Final[str] = "too_long"
_REASON_DUPLICATE: Final[str] = "duplicate"


def _render_side_fallback() -> str:
    """Return the description ``seo_postprocess`` substitutes for a page with none.

    Probed from the render side rather than retyped here. A retyped copy would
    silently disarm the boilerplate check the moment the fallback changed —
    which is the same drift-between-two-copies failure this gate exists to fix.
    """
    return seo_postprocess.extract_description("<html><head></head></html>")


#: Descriptions that mean "nobody wrote one". Derived from the render side (see
#: :func:`_render_side_fallback`), never typed out in this module.
BOILERPLATE_DESCRIPTIONS: Final[frozenset[str]] = frozenset({_render_side_fallback()})


class CoverageError(RuntimeError):
    """The gate could not establish a trustworthy set of pages to check.

    Raised when the published page set is empty or has collapsed below
    :data:`scripts.docs._published_pages.MINIMUM_EXPECTED_PAGES`. Distinct from
    a content violation: nothing is wrong with any page, the *gate* is not in a
    position to make an assertion — and silently reporting "0 violations" from
    that position is precisely the defect under repair.
    """


@dataclass(slots=True, frozen=True)
class LengthViolation:
    """A page whose ``description`` fails the metadata contract."""

    path: str
    reason: str
    length: int | None
    peers: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Serialize to the contract's ``{path, reason, length, peers}`` shape."""
        return {
            "path": self.path,
            "reason": self.reason,
            "length": self.length,
            "peers": list(self.peers),
        }


@dataclass(slots=True, frozen=True)
class LengthReport:
    """Result of a ``description`` validation pass over the published set."""

    checked_count: int = 0
    violations: list[LengthViolation] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        """Serialize to the contract's JSON shape."""
        return {
            "checked_count": self.checked_count,
            "violations": [v.as_dict() for v in self.violations],
        }


def check_description_length(description: str | None) -> str | None:
    """Return a per-page violation reason for ``description``, or ``None``.

    A length of exactly 50 or 180 is **valid** (inclusive band). ``None`` and
    blank-after-strip descriptions are ``missing``. A known render-side fallback
    is ``boilerplate`` — checked before the band, since the fallback happens to
    sit inside it and would otherwise pass unnoticed.

    Uniqueness is deliberately **not** decided here: it is a property of the set,
    not of a single string. See :func:`validate_descriptions`.
    """
    if description is None or not description.strip():
        return _REASON_MISSING
    if description in BOILERPLATE_DESCRIPTIONS:
        return _REASON_BOILERPLATE
    length = len(description)
    if length < MIN_DESCRIPTION_LENGTH:
        return _REASON_TOO_SHORT
    if length > MAX_DESCRIPTION_LENGTH:
        return _REASON_TOO_LONG
    return None


def validate_descriptions(
    *,
    docs_root: Path,
    repo_root: Path,
    docfx_config: Path | None = None,
) -> LengthReport:
    """Validate every published page's ``description``.

    Parameters
    ----------
    docs_root:
        Documentation tree. The published subset of it is resolved from
        ``docfx.json``; this function never decides publication for itself.
    repo_root:
        Base against which page paths are rendered repo-relative in the report.
    docfx_config:
        Optional explicit ``docfx.json`` path, forwarded to the resolver.

    Raises
    ------
    CoverageError
        The resolved page set is empty or below the non-vacuity floor.
    """
    page_set = _resolve_page_set(docs_root=docs_root, docfx_config=docfx_config)
    _assert_coverage(page_set, docs_root=docs_root)

    descriptions = _collect_descriptions(sorted(page_set.pages), docs_root=docs_root, repo_root=repo_root)
    violations = _per_page_violations(descriptions)
    violations.extend(_duplicate_violations(descriptions, flagged={v.path for v in violations}))
    violations.sort(key=lambda v: (v.path, v.reason))
    return LengthReport(checked_count=len(descriptions), violations=violations)


def validate_descriptions_diff_scoped(
    *,
    docs_root: Path,
    repo_root: Path,
    changed_files: list[str],
    docfx_config: Path | None = None,
) -> LengthReport:
    """Validate only changed, published Markdown pages.

    Per-page violations are reported only for changed files under ``docs_root``.
    Uniqueness still compares those pages with the complete published corpus,
    so a changed description cannot duplicate an unchanged peer unnoticed.
    Deleted paths and resolved diffs with no changed docs produce an empty
    report. Changed but unpublished pages are excluded by the shared page-set
    authority. The corpus-level non-vacuity floor (:func:`_assert_coverage`)
    is still asserted once the corpus is resolved; no floor is applied to the
    changed *subset* itself, because zero changed published pages is a valid
    scoped result.

    Raises
    ------
    CoverageError
        The resolved published corpus is empty or below the non-vacuity floor.
    """
    docs_root_rel = _repo_relative(docs_root, repo_root)
    changed_docs = {rel for rel in changed_files if rel.startswith(f"{docs_root_rel}/") and rel.endswith(".md") and (repo_root / rel).is_file()}
    effective_docfx_config = docfx_config or docs_root / "docfx.json"
    docfx_config_rel = _repo_relative(effective_docfx_config, repo_root)
    if not changed_docs and docfx_config_rel not in changed_files:
        return LengthReport()

    # The shared resolver remains the publication authority, and the corpus
    # floor is re-asserted here exactly as on the whole-tree path: diff scoping
    # filters only the *violation report* down to changed pages, never the
    # corpus the gate trusts. A collapsed corpus is a gate malfunction on a PR
    # too. Zero published pages in the changed subset is still a valid scoped
    # result — that check is on the corpus, not on the subset.
    page_set = _resolve_page_set(docs_root=docs_root, docfx_config=docfx_config)
    _assert_coverage(page_set, docs_root=docs_root)
    if not changed_docs:
        return LengthReport()
    descriptions = _collect_descriptions(sorted(page_set.pages), docs_root=docs_root, repo_root=repo_root)
    scoped_paths = changed_docs.intersection(descriptions)
    if not scoped_paths:
        return LengthReport()

    all_per_page = _per_page_violations(descriptions)
    all_flagged = {violation.path for violation in all_per_page}
    violations = [violation for violation in all_per_page if violation.path in scoped_paths]
    violations.extend(violation for violation in _duplicate_violations(descriptions, flagged=all_flagged) if violation.path in scoped_paths)
    violations.sort(key=lambda violation: (violation.path, violation.reason))
    return LengthReport(checked_count=len(scoped_paths), violations=violations)


def _resolve_page_set(*, docs_root: Path, docfx_config: Path | None) -> PublishedPageSet:
    """Ask the resolver for the published set, translating its refusals.

    The resolver fails closed — a missing, unparseable, empty, or collapsed
    declaration raises rather than yielding a partial set. Those refusals are
    re-raised as :class:`CoverageError` so the CLI can report them as a gate
    malfunction instead of crashing with a traceback.
    """
    try:
        return resolve_published_pages(docs_root=docs_root, docfx_config=docfx_config)
    except (FileNotFoundError, ValueError) as exc:
        raise CoverageError(f"description gate could not resolve its published page set: {exc}") from exc


def _assert_coverage(page_set: PublishedPageSet, *, docs_root: Path) -> None:
    """Refuse to validate a vacuous or collapsed page set (FR-003, I-01/I-02).

    The resolver already enforces this floor; asserting it again here is
    deliberate. This gate's promise is "every published page was checked", and
    that promise must not become unenforced if the resolver's own floor is ever
    relaxed. A gate that validates zero pages must fail, not pass — reporting
    green over an empty set is exactly how the defect under repair stayed
    invisible.
    """
    globs = list(page_set.source_globs)
    observed = len(page_set.pages)
    if observed == 0:
        raise CoverageError(
            f"description gate resolved no published pages under {docs_root}; source globs were {globs}. A gate that validates zero pages must fail, not pass."
        )
    if observed < MINIMUM_EXPECTED_PAGES:
        raise CoverageError(
            f"description gate resolved {observed} published page(s) under "
            f"{docs_root}, below the required floor of {MINIMUM_EXPECTED_PAGES}; "
            f"source globs were {globs}. Either the globs under-collect or the "
            "tree has collapsed; both must fail loud."
        )


def _collect_descriptions(pages: list[Path], *, docs_root: Path, repo_root: Path) -> dict[str, str | None]:
    """Read every page's ``description``, keyed by repo-relative path.

    Resolver pages are rendered relative to ``docs_root.parent`` (i.e.
    ``docs/api/slash-commands.md``), so that directory is what turns them back
    into readable absolute paths.
    """
    tree_root = docs_root.parent
    collected: dict[str, str | None] = {}
    for page in pages:
        absolute = tree_root / page
        collected[_repo_relative(absolute, repo_root)] = _read_description(absolute)
    return collected


def _per_page_violations(descriptions: dict[str, str | None]) -> list[LengthViolation]:
    """Apply :func:`check_description_length` to every collected page."""
    violations: list[LengthViolation] = []
    for path, description in sorted(descriptions.items()):
        reason = check_description_length(description)
        if reason is None:
            continue
        violations.append(
            LengthViolation(
                path=path,
                reason=reason,
                length=None if description is None else len(description),
            )
        )
    return violations


def _duplicate_violations(descriptions: dict[str, str | None], *, flagged: set[str]) -> list[LengthViolation]:
    """Flag every page sharing a byte-identical description with another (FR-007).

    Comparison is exact-match on the raw string: normalising case or whitespace
    is deliberately **not** applied, because two descriptions differing only in
    case are still duplicates for search purposes and exact matching keeps the
    rule explainable.

    Pages already carrying a per-page violation are skipped — a page reported as
    ``missing`` or ``boilerplate`` has a more specific and more actionable
    reason, and 151 identical ``boilerplate`` reports would bury it.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for path, description in descriptions.items():
        if path in flagged or description is None:
            continue
        groups[description].append(path)

    violations: list[LengthViolation] = []
    for description, members in groups.items():
        if len(members) < 2:
            continue
        ordered = sorted(members)
        violations.extend(
            LengthViolation(
                path=path,
                reason=_REASON_DUPLICATE,
                length=len(description),
                peers=tuple(peer for peer in ordered if peer != path),
            )
            for path in ordered
        )
    return violations


def _read_description(md_path: Path) -> str | None:
    """Return the ``description`` frontmatter value (``None`` if absent)."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return None
    raw = parse_frontmatter(text).get("description")
    return raw if isinstance(raw, str) else None


def _repo_relative(path: Path, repo_root: Path) -> str:
    """Render ``path`` as a POSIX repo-relative string (best-effort)."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    """Build the description-gate CLI parser."""
    parser = argparse.ArgumentParser(
        prog="description_length_check",
        description=("Validate that every published page carries a unique, non-boilerplate 'description' of 50-180 chars. Report-only (exit 0) unless --strict."),
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(DEFAULT_DOCS_ROOT),
        help=f"Docs tree whose published subset is checked (default: {DEFAULT_DOCS_ROOT}).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Base for rendering repo-relative page paths (default: cwd).",
    )
    parser.add_argument(
        "--docfx-config",
        type=Path,
        default=None,
        help="Explicit docfx.json declaring the published set (default: <docs-root>/docfx.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report as JSON instead of a human summary.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any description is missing, boilerplate, out-of-band, or duplicated.",
    )
    parser.add_argument(
        "--changed-from",
        metavar="BASE_REF",
        default=None,
        help=(
            "Diff-scope violations to published docs-root *.md files changed "
            "since BASE_REF. Fails closed only when BASE_REF cannot be "
            "resolved; a resolved diff with zero in-scope docs files is a "
            "clean pass."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    changed: list[str] | None = None
    if args.changed_from is not None:
        try:
            changed = resolve_changed_files(args.repo_root, args.changed_from)
        except GitDiffError as exc:
            sys.stderr.write(f"description_length_check: ERROR: {exc}\n")
            return EXIT_COVERAGE_FAILURE

    try:
        if changed is None:
            report = validate_descriptions(
                docs_root=args.docs_root,
                repo_root=args.repo_root,
                docfx_config=args.docfx_config,
            )
        else:
            report = validate_descriptions_diff_scoped(
                docs_root=args.docs_root,
                repo_root=args.repo_root,
                changed_files=changed,
                docfx_config=args.docfx_config,
            )
    except CoverageError as exc:
        sys.stderr.write(f"description_length_check: COVERAGE FAILURE: {exc}\n")
        return EXIT_COVERAGE_FAILURE
    _emit(report, as_json=args.json)
    if args.strict and report.violations:
        return 1
    return 0


def _emit(report: LengthReport, *, as_json: bool) -> None:
    """Print the report — JSON payload or a human-readable summary."""
    if as_json:
        sys.stdout.write(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n")
        return

    sys.stdout.write(f"description_length_check: checked {report.checked_count} page(s); {len(report.violations)} violation(s).\n")
    for violation in report.violations:
        peers = f" also on: {', '.join(violation.peers)}" if violation.peers else ""
        sys.stdout.write(f"  {violation.reason.upper()} {violation.path} (length={violation.length}){peers}\n")


if __name__ == "__main__":  # pragma: no cover - module-level CLI guard
    raise SystemExit(main())
