"""The immutable corpus did not move while its frontmatter was migrated (#6931).

ADR 2026-10-31-1 D-7 allows one kind of change to ADRs, plans, reports and changelog
entries — "a frontmatter-only change made by a recorded, mechanical migration" — and
requires the migration step to carry a test that hashes every immutable file's body
before and after. This is that test, in two independent halves:

1. **The recorded baseline** (``docs/_meta/immutable-body-hashes.json``) is compared
   with the tree. It catches the thing a property test cannot: a body rewritten by a
   human, by another tool, or by a later PR that thought it was being helpful.
2. **The transformation property** is asserted directly on the migration for every
   published page and for adversarial synthetic inputs. It catches the thing a
   baseline cannot: a migration that would move a body on the *next* run, or on a
   page shape the corpus does not happen to contain today.

Both halves are needed. Either one alone is a green light that can be wrong.

The baseline was recorded on this branch after the migration ran, and the migration's
own diff was verified line-by-line: every changed line is a frontmatter line
(``git diff -U0`` reports no body line), so the recorded hashes are the pre-migration
bodies by construction. ``test_the_migration_changed_no_body_against_the_base_commit``
re-proves that against ``origin/main`` for as long as the branch is unmerged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.docs.frontmatter_contract import (
    apply_edit,
    body_of,
    plan_page,
    validate_tree,
)
from scripts.docs.immutable_bodies import (
    BASELINE_PATH,
    IMMUTABLE_PREFIXES,
    MUTABLE_PREFIXES,
    collect,
    diff_baseline,
    load_baseline,
)

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_ROOT = _REPO_ROOT / "docs"


def test_every_immutable_body_matches_the_recorded_baseline() -> None:
    """The baseline is a real gate: a changed body is drift, named by path."""
    baseline = load_baseline(_REPO_ROOT / BASELINE_PATH)
    drift = diff_baseline(baseline, collect(_REPO_ROOT))
    assert drift == [], [
        f"{entry.kind} {entry.path}" for entry in drift
    ]


def test_the_baseline_covers_every_immutable_page() -> None:
    """A body cannot escape the rule by being added after the baseline was written."""
    baseline = set(load_baseline(_REPO_ROOT / BASELINE_PATH))
    observed = set(collect(_REPO_ROOT))
    assert observed - baseline == set(), "immutable pages missing from the baseline"
    assert baseline - observed == set(), "baseline names pages that no longer exist"


def test_open_changelog_fragments_are_not_pinned() -> None:
    """A fragment is authored while its PR is open; freezing it would be churn.

    The rule starts at the released entries (``docs/changelog/*.md`` and the era
    pages). Without this, every PR that adds a fragment would red the baseline.
    """
    baseline = load_baseline(_REPO_ROOT / BASELINE_PATH)
    for mut in MUTABLE_PREFIXES:
        assert not any(path.startswith(mut) for path in baseline), mut
    # The released changelog pages are pinned, so the exclusion is not a loophole.
    assert any(path.startswith("docs/changelog/") for path in baseline)


def test_the_baseline_covers_all_four_immutable_trees() -> None:
    """All four D-7 classes are represented, not just the ADR tree."""
    baseline = load_baseline(_REPO_ROOT / BASELINE_PATH)
    for prefix in IMMUTABLE_PREFIXES:
        assert any(path.startswith(prefix) for path in baseline), f"{prefix} has no hashed bodies"
    assert len(baseline) > 300, f"only {len(baseline)} immutable pages hashed"


def test_the_migration_cannot_move_a_body_on_any_immutable_page() -> None:
    """The transformation property, over every immutable page in the tree.

    ``plan_page`` may legitimately fail on a page it cannot classify (it must, per
    D-7), but for every page where it *does* produce an edit, applying that edit must
    leave the body byte-identical.
    """
    checked = 0
    for path, _digest in collect(_REPO_ROOT).items():
        absolute = _REPO_ROOT / path
        text = absolute.read_text(encoding="utf-8")
        try:
            edit = plan_page(path, text)
        except ValueError:
            continue
        assert body_of(apply_edit(text, edit)) == body_of(text), path
        checked += 1
    assert checked > 300, f"only {checked} immutable pages exercised the migration"


def test_the_migration_cannot_move_a_body_on_any_published_page() -> None:
    """The same property over the whole published corpus, not only the ADR classes."""
    checked = 0
    for path in sorted(_published_paths()):
        text = (_REPO_ROOT / path).read_text(encoding="utf-8")
        try:
            edit = plan_page(path, text)
        except ValueError:
            continue
        assert body_of(apply_edit(text, edit)) == body_of(text), path
        checked += 1
    assert checked >= 650, f"only {checked} published pages exercised the migration"


def _published_paths() -> list[str]:
    """The published page set, as repo-relative strings."""
    from scripts.docs._published_pages import resolve_published_pages

    return [page.as_posix() for page in resolve_published_pages(docs_root=_DOCS_ROOT).pages]


@pytest.mark.parametrize(
    ("path", "text"),
    [
        # No frontmatter at all: nothing for the migration to rewrite, body intact.
        ("docs/adr/x.md", "just prose\nwith no fence\n"),
        # CRLF frontmatter and body.
        ("docs/adr/x.md", "---\r\ntitle: t\r\nkind: ADR\r\nupdated: '2026-01-01'\r\n---\r\nbody\r\n"),
        # Empty body.
        ("docs/adr/x.md", "---\ntitle: t\nkind: ADR\nupdated: '2026-01-01'\n---\n"),
        # A body that itself contains `---` lines (horizontal rules must survive).
        ("docs/adr/x.md", "---\ntitle: t\nkind: ADR\nupdated: '2026-01-01'\n---\nbefore\n\n---\n\nafter\n"),
        # Trailing whitespace in the body.
        ("docs/plans/x.md", "---\ntitle: t\nkind: Planning\nupdated: '2026-01-01'\n---\nline   \n"),
    ],
)
def test_adversarial_page_shapes_keep_their_body(path: str, text: str) -> None:
    """Inputs the corpus does not contain today, so a future one cannot ambush the rule."""
    try:
        edit = plan_page(path, text)
    except ValueError:
        assert body_of(text) == text or "---" in text
        return
    assert body_of(apply_edit(text, edit)) == body_of(text)


def test_the_migration_changed_no_body_against_the_base_commit() -> None:
    """Re-proves the branch's own migration against ``origin/main``.

    Only meaningful while the branch is unmerged (afterwards the base commit *is* the
    migration); the test therefore skips when the base already contains it.
    """
    base = subprocess.run(
        ["git", "merge-base", "origin/main", "HEAD"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if base.returncode != 0:
        pytest.skip("origin/main is not available in this checkout")

    changed = subprocess.run(
        ["git", "diff", "--name-only", base.stdout.strip(), "--", "docs"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    if not changed:
        pytest.skip("the branch does not differ from origin/main for docs/")

    # Only the D-7 immutable classes: this PR also *edits prose* in a reference page
    # on purpose, which is not a body that moved.
    immutable = set(collect(_REPO_ROOT))
    mismatches: list[str] = []
    for path in changed:
        if not path.endswith(".md") or path not in immutable:
            continue
        old = subprocess.run(
            ["git", "show", f"{base.stdout.strip()}:{path}"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if old.returncode != 0:
            continue  # a new page: nothing to have moved
        new_text = (_REPO_ROOT / path).read_text(encoding="utf-8")
        if body_of(old.stdout) != body_of(new_text):
            mismatches.append(path)
    assert mismatches == [], f"bodies moved against the base commit: {mismatches[:10]}"


def test_the_whole_tree_still_satisfies_the_contract_after_the_migration() -> None:
    """The migration is only acceptable if the gate it serves is green."""
    report = validate_tree(docs_root=_DOCS_ROOT, repo_root=_REPO_ROOT)
    assert report.errors == ()
    assert report.warnings == ()
