"""Cross-cutting parity checks over ALL FOUR `expected-artifacts.yaml` manifests
at once (WP05 / IC-05, T020).

These checks genuinely require every manifest's **final**, post-reconciliation
content to exist first -- they read across `research`/`documentation`/
`software-dev` (AS7) or all four manifests including the new `plan` one
(SC-006, FR-013) simultaneously, rather than asserting on one manifest's
content in isolation the way `tests/dossier/test_manifest.py`'s per-IC
classes (`TestManifestReconciliation`, `TestPlanManifest`) do. Kept in this SEPARATE file specifically
so WP05 never needs to touch `test_manifest.py`'s per-IC-owned sections --
see `plan.md`'s Implementation Concern Map, "Test file ownership" note, and
`tracer-approach.md`'s "Chokepoint note" for the full rationale.

Covers:
- AS7/SC-001: every `required_by_step` key in the three CLI-guarded manifests
  either corresponds to a real branch in `runtime_bridge_cores.py`'s guard
  tables, or carries an inline YAML comment documenting the non-filesystem-
  expressible check it stands in for.
- SC-006: `manifest_version == "1"` on all four manifests (Decision 2 --
  `manifest_version` is a sync-namespace identity key, not a content-freshness
  counter, so this mission's content edits must not bump it).
- FR-013: the Decision-2 rationale comment is actually present, as a comment
  (not merely the unchanged version value SC-006 already checks), on all four
  manifests.

See kitty-specs/expected-artifacts-manifest-repair-01KZY498/tracer-design-decisions.md
for Decisions 1-2 (the `plan` manifest's honest-scaffolding framing and the
`manifest_version` stability rationale this file's checks encode as regression
guards) and tracer-approach.md for the "reconcile-to-guard, never the reverse"
principle AS7's allow-list below is built from.
"""

from pathlib import Path

import pytest
import ruamel.yaml

from specify_cli.dossier.manifest import ArtifactClassEnum, ManifestRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MANIFEST_ROOT = Path(__file__).parent.parent.parent / "packs" / "built-in" / "missions"

_FOUR_MANIFEST_TYPES = ("research", "documentation", "software-dev", "plan")

# ---------------------------------------------------------------------------
# AS7 guard-branch allow-list -- hand-verified against
# src/runtime/next/runtime_bridge_cores.py at WP05 authoring time (per
# plan.md's Test Strategy table + this WP's own re-verification, not merely
# copied from the plan). A step id maps to a real branch when
# `evaluate_guards()`'s dispatch chain reaches dedicated logic for it; a step
# id NOT listed here falls through to that family's generic default (research/
# software-dev: a bare/fail-closed fallback with no per-step logic; both such
# fallbacks are legitimate outcomes, not bugs -- see the per-family notes
# below), so it must instead carry an explanatory comment (condition (b)).
#
# Known maintenance limitation (spec.md "Edge Cases", named there as a future
# follow-up, not required by this mission's acceptance bar): if
# runtime_bridge_cores.py's guard tables change in a later, unrelated mission,
# this allow-list can drift stale. A structural (source-introspecting) parity
# gate is out of scope here.
# ---------------------------------------------------------------------------

_GUARD_BRANCH_STEP_IDS: dict[str, frozenset[str]] = {
    # mission_family == "research" -> _evaluate_research_guards. Steps not
    # listed here fall through to that function's final
    # `return [f"No guard registered for research action: {action}"]` line --
    # not a per-step branch, so "done" relies on condition (b) below.
    "research": frozenset({"scoping", "methodology", "gathering", "synthesis", "output"}),
    # mission_family == "documentation" -> _evaluate_documentation_guards.
    # Every step documentation's mission.yaml defines has an explicit branch,
    # including the "accept" terminal branch (`if action == "accept": return
    # []`) -- a real, if trivial, dedicated branch, not a fallback.
    "documentation": frozenset(
        {"discover", "audit", "design", "generate", "validate", "publish", "accept"}
    ),
    # Anything else (including the literal "software-dev" family) ->
    # _evaluate_software_dev_guards. "discovery" and "done" are NOT dispatched
    # to a per-step branch -- they fall through to the function's final bare
    # `return []` -- so those two rely on condition (b) below.
    #
    # "implement" is listed here deliberately: this is the historical
    # divergence #8 from the issue's own investigation (spec.md FR-008/AS6).
    # The manifest USED to require `analysis-report.md` at this step, but
    # `_evaluate_wp_iteration_guard` only ever checks WP-lane status
    # (`wp_advance_ready`), never any filesystem artifact, for "implement".
    # WP02 reconciled the MANIFEST side (removed the requirement, per
    # "reconcile-to-guard, never the reverse" -- tracer-approach.md), so
    # "implement" now correctly maps to condition (a): a real branch
    # (`step_id in ("implement", "review") -> _evaluate_wp_iteration_guard`)
    # that happens to enforce nothing filesystem-shaped. The GUARD side is
    # deliberately left unchanged (C-001) and is NOT re-litigated by this
    # parity check -- this allow-list entry documents that explicitly rather
    # than silently omitting divergence #8's history.
    "software-dev": frozenset(
        {
            "specify",
            "plan",
            "tasks_outline",
            "tasks_packages",
            "tasks_finalize",
            "implement",
            "review",
        }
    ),
}

_ROUND_TRIP_YAML = ruamel.yaml.YAML()


def _load_raw_manifest(mission_type: str):
    """Load a manifest with ruamel's round-trip loader (preserves comments)."""
    path = _MANIFEST_ROOT / mission_type / "expected-artifacts.yaml"
    with path.open(encoding="utf-8") as f:
        return _ROUND_TRIP_YAML.load(f)


def _has_trailing_comment(commented_map, key: str) -> bool:
    """True if `key` in a ruamel CommentedMap carries a real, substantive
    comment attached after it (index 3 of its `ca.items` entry) -- the slot
    ruamel populates for a block comment written between `key:` and its
    value/next key, which is exactly where this repo's manifests put their
    per-step guard-parity rationale (see e.g. the `gathering:` step in
    `research/expected-artifacts.yaml`). Index 1 is deliberately NOT
    consulted here: it is populated even for a bare blank-line separator
    with no documenting text (verified empirically against every shipped
    manifest at authoring time), so using it would make this check
    vacuously pass for undocumented keys.
    """
    entry = commented_map.ca.items.get(key)
    if not entry:
        return False
    trailing = entry[3]
    return bool(trailing)


def _comments_near_key(commented_map, key: str) -> str:
    """Collect comment text ruamel attaches at-or-near `key` in a top-level
    CommentedMap. A comment block written on the line(s) immediately BEFORE
    `key:` is commonly attached by ruamel to the PRECEDING sibling key's
    entry (empirically confirmed for this repo's four manifests: the
    Decision-2 rationale comment above `manifest_version:` attaches to
    `mission_type`'s `ca.items` entry, not `manifest_version`'s own), so this
    helper checks both `key` itself and its immediate predecessor, matching
    the WP prompt's "attached at/near" phrasing.
    """
    keys = list(commented_map.keys())
    idx = keys.index(key)
    candidates = [key]
    if idx > 0:
        candidates.append(keys[idx - 1])
    texts: list[str] = []
    for candidate in candidates:
        entry = commented_map.ca.items.get(candidate)
        if not entry:
            continue
        for slot in entry:
            if slot is None:
                continue
            tokens = slot if isinstance(slot, list) else [slot]
            texts.extend(tok.value for tok in tokens if tok is not None)
    return "\n".join(texts)


class TestGuardCommentParity:
    """AS7/SC-001: every `required_by_step` key across the three CLI-guarded
    manifests either corresponds to a real `runtime_bridge_cores.py` guard
    branch, or is documented with an inline comment explaining the
    non-filesystem-expressible (or intentionally-empty) check it stands in
    for. Zero unexplained divergences is the pass condition.
    """

    def test_all_required_by_step_keys_match_guard_or_carry_comment(self):
        unexplained: list[str] = []
        for mission_type in ("research", "documentation", "software-dev"):
            data = _load_raw_manifest(mission_type)
            required_by_step = data["required_by_step"]
            allow_list = _GUARD_BRANCH_STEP_IDS[mission_type]
            for step_id in required_by_step:
                has_real_branch = step_id in allow_list
                has_comment = _has_trailing_comment(required_by_step, step_id)
                if not has_real_branch and not has_comment:
                    unexplained.append(f"{mission_type}/{step_id}")
        assert not unexplained, (
            "required_by_step keys with neither a real guard branch nor an "
            f"explanatory comment: {unexplained}"
        )

    def test_software_dev_tasks_packages_and_finalize_path_pattern_is_wp_glob(self):
        """Dedicated, narrower check on top of the step-key-presence check
        above (per T020 step 2): the literal `path_pattern` string for
        `tasks_packages`/`tasks_finalize` must be exactly `"tasks/WP*.md"`,
        not merely "some pattern present" -- a future regression to the
        broader `tasks/*.md` pattern (which the guard's
        `tasks_dir.glob("WP*.md")` call does not actually match, per
        FR-007/AS5) is caught structurally here, not only by manual review.
        """
        manifest = ManifestRegistry.load_manifest("software-dev")
        assert manifest is not None
        for step_id in ("tasks_packages", "tasks_finalize"):
            specs = manifest.required_by_step[step_id]
            # Pins the whole collection -- exactly one spec, with the exact
            # WP-glob path_pattern -- so both a stray extra/removed spec and
            # a regression to the broader `tasks/*.md` pattern fail here.
            assert [
                (s.artifact_key, s.artifact_class, s.path_pattern, s.blocking) for s in specs
            ] == [
                ("output.tasks.per_wp", ArtifactClassEnum.OUTPUT, "tasks/WP*.md", True),
            ], f"{step_id}'s required spec must be exactly the WP-glob output.tasks.per_wp entry"


class TestManifestVersionStability:
    """SC-006: `manifest_version` stays `"1"` on all four manifests -- the
    concrete regression guard for Decision 2/C-002 (do not bump the
    sync-namespace identity key on a content-only reconciliation).
    """

    def setup_method(self):
        ManifestRegistry.clear_cache()

    def teardown_method(self):
        ManifestRegistry.clear_cache()

    def test_manifest_version_unchanged_on_all_four_files(self):
        for mission_type in _FOUR_MANIFEST_TYPES:
            manifest = ManifestRegistry.load_manifest(mission_type)
            assert manifest is not None, f"{mission_type} manifest failed to load"
            assert manifest.manifest_version == "1", (
                f"{mission_type} manifest_version must stay '1' (Decision 2); "
                f"got {manifest.manifest_version!r}"
            )


class TestManifestVersionRationaleComment:
    """FR-013: the Decision-2 rationale is present as an inline YAML comment
    on all four manifests -- a content check on the comment ITSELF, distinct
    from `TestManifestVersionStability`'s value-only check above (reverting
    just the comment, while leaving `manifest_version: "1"` unchanged, must
    fail THIS test but not that one).
    """

    _RATIONALE_MARKERS = ("sync-namespace identity key", "content-freshness counter")

    def test_manifest_version_rationale_comment_present(self):
        for mission_type in _FOUR_MANIFEST_TYPES:
            data = _load_raw_manifest(mission_type)
            comment_text = _comments_near_key(data, "manifest_version")
            missing_markers = [m for m in self._RATIONALE_MARKERS if m not in comment_text]
            assert not missing_markers, (
                f"{mission_type}/expected-artifacts.yaml: manifest_version comment "
                f"missing Decision-2 rationale marker(s) {missing_markers}; "
                f"found comment text: {comment_text!r}"
            )
