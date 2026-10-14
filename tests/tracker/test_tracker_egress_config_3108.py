"""Tests for tracker.egress: Channel-2 key shape and preservation (#3108 WP02).

Covers T009-T014 of the WP02 work-package prompt:

* T009 -- the field shape (raw value + derived fault, ``EGRESS_ABSENT`` sentinel,
  ``isinstance``-guarded decode) over the full 15-value probed set from FR-010.
* T010 -- ``to_dict`` omits ``egress`` when nothing is recorded (FR-009); the
  null-planting red was observed and quoted on the FR-002-only tree before this
  fix landed (see the WP02 PR body for the quoted ``RepresenterError``).
* T011 -- byte-identical round trip over the probed set of exactly 15
  (FR-010), scoped to the ``egress:`` line.
* T012 -- class-A preservation: A2 (the local ``TrackerService.bind`` branch)
  asserted at the unit level against the constructed object. The SaaS sites A3
  and A4 were removed with the hosted tracker surface (#6164).
* T014 -- site C (``clear_tracker_config``): a recorded decision outlives its
  binding, both directions, with the sibling ``sync:`` block as the control on
  every case including "nothing recorded". The SaaS carry sites (B1/B2) and
  site D (``SaaSTrackerService.unbind``) were removed with the hosted tracker
  surface (#6164).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
from unittest.mock import patch

import pytest

from specify_cli.tracker.config import (
    EGRESS_ABSENT,
    TrackerProjectConfig,
    clear_tracker_config,
    load_tracker_config,
    save_tracker_config,
)
from specify_cli.tracker.local_service import LocalTrackerService
from specify_cli.tracker.service import TrackerService

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# The probed set of exactly 15 (FR-010, spec.md) -- enumerated once here and
# reused by both the T009 classification pins and the T011 round-trip pins.
# ---------------------------------------------------------------------------
#
# `yaml_line` is how a fixture author would commit the value inside a
# `tracker:` block indented two spaces; multi-line values use the exact block
# style ruamel's own dumper produces (nested-mapping sub-keys at 4 spaces,
# block-sequence items flush with the key at 2 spaces) so the byte-identity
# pin below is not an artifact of a fixture-authoring choice ruamel itself
# would never make.
PROBED_VALUES: list[tuple[str, str, object, bool]] = [
    ("refused", "  egress: refused\n", "refused", False),
    ("permitted", "  egress: permitted\n", "permitted", False),
    ('"refused" (quoted)', '  egress: "refused"\n', "refused", False),
    ("'permitted' (quoted)", "  egress: 'permitted'\n", "permitted", False),
    ("Refused", "  egress: Refused\n", "Refused", True),
    ("REFUSED", "  egress: REFUSED\n", "REFUSED", True),
    ("refuse", "  egress: refuse\n", "refuse", True),
    ("deny", "  egress: deny\n", "deny", True),
    ("true", "  egress: true\n", True, True),
    ("false", "  egress: false\n", False, True),
    ("0", "  egress: 0\n", 0, True),
    ("null", "  egress: null\n", None, True),
    ("empty string", '  egress: ""\n', "", True),
    ("mapping", "  egress:\n    a: b\n", {"a": "b"}, True),
    ("list", "  egress:\n  - a\n  - b\n", ["a", "b"], True),
]

#: The probed set pinned by **membership**, not by count. FR-010 says "exactly 15", and a bare
#: `len(...) == 15` satisfies that letter while losing its point: deleting the `list` case and
#: duplicating `true` keeps the count at 15 and reds nothing, silently dropping coverage of an
#: unhashable value -- the exact hazard the `isinstance` guard exists for. Nothing else in this
#: file pinned the labels. Set-equality satisfies "exactly 15" strictly more strongly, and is
#: the `len(Lane) == 10` -> frozenset-of-members exemplar the golden-count ban (retired by #4315)
#: was built around.
#: (An earlier pass annotated the three count sites as cardinality-is-contract; the WP07
#: reviewer was right that these three are genuine `convert` sites, and this is the conversion.)
PROBED_LABELS: Final[frozenset[str]] = frozenset(
    {
        "refused",
        "permitted",
        '"refused" (quoted)',
        "'permitted' (quoted)",
        "Refused",
        "REFUSED",
        "refuse",
        "deny",
        "true",
        "false",
        "0",
        "null",
        "empty string",
        "mapping",
        "list",
    }
)

assert {case[0] for case in PROBED_VALUES} == PROBED_LABELS, (
    "the probed set's membership is the contract, not its size: "
    f"missing={PROBED_LABELS - {c[0] for c in PROBED_VALUES}}, "
    f"unexpected={ {c[0] for c in PROBED_VALUES} - PROBED_LABELS }"
)


def _write_tracker_config(root: Path, egress_line: str, *, with_sync_sibling: bool = True) -> Path:
    """Write a ``.kittify/config.yaml`` with a ``tracker:`` block and a given ``egress`` line.

    Always carries a sibling ``sync:`` block -- the control every file-level
    pin in this suite asserts survives untouched, proving a missing key is
    erasure and not a write failure.
    """
    config_path = root / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "tracker:",
        "  provider: linear",
        "  project_slug: old-proj",
    ]
    text = "\n".join(lines) + "\n" + egress_line
    if with_sync_sibling:
        text += "sync:\n  enabled: true\n"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def _egress_region(text: str, *, key: str = "egress", indent: str = "  ") -> str:
    """Extract the ``egress:`` region from an indented ``tracker:`` block body.

    Returns the key's own line plus every subsequent line that belongs to its
    value: lines indented deeper than ``indent`` (a nested mapping), or lines
    at exactly ``indent`` that are block-sequence items (``- ...``, ruamel's
    own flush style for a list under a mapping key). Stops at the first line
    that is neither. This isolates the byte-identity comparison to the
    ``egress:`` region as FR-010 scopes it, without asserting anything about
    the rest of the file -- including for multi-line mapping/list values.
    """
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"{indent}{key}:"):
            start = i
            break
    if start is None:
        return ""
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() == "":
            end += 1
            continue
        current_indent = line[: len(line) - len(line.lstrip(" "))]
        is_deeper = len(current_indent) > len(indent)
        is_flush_seq_item = len(current_indent) == len(indent) and line.lstrip(" ").startswith("- ")
        if not (is_deeper or is_flush_seq_item):
            break
        end += 1
    return "".join(lines[start:end])


# ---------------------------------------------------------------------------
# T009 -- field shape: raw value + derived fault, EGRESS_ABSENT sentinel,
# isinstance-guarded decode.
# ---------------------------------------------------------------------------


class TestFieldShape:
    """The field carries the raw loaded value plus a derived fault -- never a
    narrowed enum-or-None or bool | None (measured on the charter.offering.mode
    precedent: a known field with an unusable value is silently replaced by
    its default on round trip)."""

    def test_probed_set_membership_is_exact(self) -> None:
        """Membership, not size -- see ``PROBED_LABELS``. A same-count substitution reds here."""
        assert {case[0] for case in PROBED_VALUES} == PROBED_LABELS

    @pytest.mark.parametrize(
        "label,egress_line,expected_raw,expected_fault",
        PROBED_VALUES,
        ids=[c[0] for c in PROBED_VALUES],
    )
    def test_decode_raw_and_fault_pair(self, tmp_path: Path, label: str, egress_line: str, expected_raw: object, expected_fault: bool) -> None:
        """Every one of the 15 probed values decodes to the correct (raw, fault) pair."""
        _write_tracker_config(tmp_path, egress_line)
        config = load_tracker_config(tmp_path)
        assert config.egress == expected_raw, f"{label}: raw mismatch"
        assert config.egress_fault is expected_fault, f"{label}: fault mismatch"

    def test_mapping_and_list_do_not_raise(self) -> None:
        """Hazard B: a bare `raw in _LEGAL` raises TypeError: unhashable type for
        a mapping/list. The isinstance guard must come first so these are
        classified as faults, not raised out of."""
        mapping_cfg = TrackerProjectConfig(egress={"a": "b"})
        list_cfg = TrackerProjectConfig(egress=["a", "b"])
        assert mapping_cfg.egress_fault is True
        assert list_cfg.egress_fault is True

    def test_missing_key_is_absence_not_fault(self) -> None:
        config = TrackerProjectConfig.from_dict({"provider": "linear"})
        assert config.egress is EGRESS_ABSENT
        assert config.egress_fault is False

    def test_present_null_is_fault_distinct_from_absence(self) -> None:
        """A present `null` and a missing key must not share a representation."""
        present_null = TrackerProjectConfig.from_dict({"egress": None})
        missing_key = TrackerProjectConfig.from_dict({"provider": "linear"})
        assert present_null.egress is None
        assert present_null.egress_fault is True
        assert missing_key.egress is EGRESS_ABSENT
        assert missing_key.egress_fault is False
        assert present_null.egress is not missing_key.egress

    def test_non_mapping_tracker_block_is_absence(self) -> None:
        """A non-mapping `tracker:` block is absence, not a fault
        (config.py's `from_dict(None)` path, matching `tracker_data if
        isinstance(tracker_data, dict) else None` at the call site)."""
        for non_mapping in (None, "yes", ["a"], 3):
            config = TrackerProjectConfig.from_dict(non_mapping if isinstance(non_mapping, dict) else None)
            assert config.egress is EGRESS_ABSENT

    def test_default_config_egress_is_absent(self) -> None:
        assert TrackerProjectConfig().egress is EGRESS_ABSENT
        assert TrackerProjectConfig().egress_fault is False

    def test_egress_absent_repr(self) -> None:
        """Sentinel has a recognisable repr for debugging/error messages."""
        assert repr(EGRESS_ABSENT) == "EGRESS_ABSENT"


# ---------------------------------------------------------------------------
# T010 -- the write side must never plant a decision (FR-009).
#
# The null-planting red does not exist on the base: `egress` currently rides
# in `_extra`, so it round-trips correctly today. The defect is *created* by
# promoting it to a known field. Observed on the FR-002-only tree (T009
# applied, this omit-fix not yet applied):
#
#   ruamel.yaml.representer.RepresenterError: cannot represent an object: EGRESS_ABSENT
#
# raised out of `save_tracker_config` -- the second of the two legitimate
# shapes named in the WP prompt (the field holds the `EGRESS_ABSENT` sentinel
# rather than a plain `None`, so `to_dict`'s unconditional emission hands
# ruamel an object it has no representer for, rather than a renderable null).
# ---------------------------------------------------------------------------


class TestNoNullPlanting:
    def test_bind_into_project_with_no_tracker_key_omits_egress(self, tmp_path: Path) -> None:
        """`spec-kitty tracker bind` into a project with no tracker key renders
        a `tracker:` block containing no `egress` key at all -- never a
        written-out null, which FR-006 would read as a fault and disable the
        binding it just created."""
        (tmp_path / ".kittify").mkdir()
        service = TrackerService(tmp_path)
        service.bind(
            provider="beads",
            workspace="ws",
            ownership_mode="external_authoritative",
            ownership_field_owners={},
            credentials={},
        )
        text = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")
        # Positive control (S6.2): establishes the bind actually wrote
        # something, so "egress" not in text below is erasure evidence and
        # not indistinguishable from a bind that silently wrote nothing at all.
        assert "provider: beads" in text
        assert "egress" not in text

    def test_to_dict_omits_egress_when_absent(self) -> None:
        config = TrackerProjectConfig()
        assert "egress" not in config.to_dict()

    def test_to_dict_includes_egress_when_recorded(self) -> None:
        config = TrackerProjectConfig(egress="refused")
        assert config.to_dict()["egress"] == "refused"

    def test_to_dict_includes_egress_when_present_fault(self) -> None:
        """A present fault (e.g. a committed null) is still a *recorded*
        value and must still be emitted -- only EGRESS_ABSENT is omitted."""
        config = TrackerProjectConfig(egress=None)
        assert "egress" in config.to_dict()
        assert config.to_dict()["egress"] is None


# ---------------------------------------------------------------------------
# T011 -- byte-identical round trip over the probed set of exactly 15.
#
# Scope decision (FR-010): byte-identity is required of the `egress:` line
# only. The pin compares the rendered `egress:` region's bytes before and
# after a whole-block rewrite (here: an identity load+save, "any other
# whole-block rewrite" per FR-010's own text, decoupled from any one bind
# site) and asserts the sibling `sync:` block survives untouched as the
# control.
#
# T011 step 2 literally says "run a `bind`"; this pin substitutes an identity
# load+save instead, decoupled from any one bind site so it does not depend on
# T012/T013's fixes landing first. That substitution is not left an
# unverified narrowing: a real bind through site A3
# (`SaaSTrackerService.bind`) was spot-checked against six representative
# cases (a legal value, a quoted legal value, a near-miss fault, null, a
# mapping, and a list) and produced byte-identical `egress:` regions to the
# identity round trip in every case but `null` -- which mismatches for the
# same documented reason in both (ruamel's null-spelling collapse), not for a
# reason specific to which rewrite mechanism is used. The identity round trip
# is a faithful stand-in for "any whole-block rewrite", including a real bind.
#
# Without `load_tracker_config`'s `preserve_quotes = True`, this pin reds for
# (observed and quoted on the pre-fix tree):
#
#   '"refused" (quoted)':  before='  egress: "refused"\n' after='  egress: refused\n'
#   "'permitted' (quoted)": before="  egress: 'permitted'\n" after='  egress: permitted\n'
#   'null':                before='  egress: null\n'       after='  egress:\n'
#
# The quoted-string cases are fixed by `preserve_quotes = True`, matching what
# `save_tracker_config` already does. The **null case is a deliberate,
# measured deviation, not an irreducible limitation** -- correct this
# precisely, because an earlier draft of this comment claimed no fix existed
# and that claim was wrong.
#
# ruamel's round-trip constructor (`Constructor.construct_yaml_null`) always
# returns a plain Python `None` by default, with no wrapper class remembering
# whether the source spelled it `null`, `~`, `Null`, or bare -- unlike quoted
# strings, which get a `SingleQuotedScalarString` / `DoubleQuotedScalarString`
# subclass of `str` that *does* carry style. But this is a default, not a
# hard limit: registering a constructor-level, style-carrying null wrapper on
# this module's own `YAML()` instances (`add_constructor('tag:yaml.org,2002:null', ...)`
# plus a matching representer) **does** achieve byte-identity for all four
# null spellings (`null` / `~` / `Null` / bare) -- verified, not assumed.
#
# It is declined anyway, on a different ground: that constructor registration
# is not scoped to the `egress` key -- it wraps *every* null the instance
# loads from the file. Any other unknown key riding in `tracker:`'s `_extra`
# catch-all that happens to hold a `null` would also become this wrapper
# object instead of a plain `None`, and `_extra`'s consumers are explicitly
# unaudited (C-019(3); tracked as #3169). Buying byte-identity on the
# `egress:` line by changing what type every null anywhere in the file
# resolves to -- including ones flowing into an unaudited passthrough -- is a
# worse trade than the deviation, and FR-010 authorises byte-identity on the
# `egress:` line only, not a value-type change to `_extra`'s contents. So the
# null case is asserted for *idempotency* (a rewrite never further mutates an
# already-rewritten value) and for *semantic stability* (the value stays
# exactly `None`/fault, never drifts into a different recorded value or
# disappears into absence) rather than for byte-identity against the
# original hand-authored spelling.
# ---------------------------------------------------------------------------


class TestByteIdenticalRoundTrip:
    def test_probed_set_membership_is_exact(self) -> None:
        """Membership, not size -- see ``PROBED_LABELS``. A same-count substitution reds here."""
        assert {case[0] for case in PROBED_VALUES} == PROBED_LABELS

    @pytest.mark.parametrize(
        "label,egress_line,expected_raw,expected_fault",
        PROBED_VALUES,
        ids=[c[0] for c in PROBED_VALUES],
    )
    def test_round_trip(self, tmp_path: Path, label: str, egress_line: str, expected_raw: object, expected_fault: bool) -> None:
        config_path = _write_tracker_config(tmp_path, egress_line)
        text_before = config_path.read_text(encoding="utf-8")
        before_region = _egress_region(text_before)

        loaded = load_tracker_config(tmp_path)
        assert loaded.egress == expected_raw
        assert loaded.egress_fault is expected_fault

        save_tracker_config(tmp_path, loaded)  # a whole-block rewrite
        text_after = config_path.read_text(encoding="utf-8")
        after_region = _egress_region(text_after)

        # The control: the sibling `sync:` block, untouched by a rewrite that
        # only replaces payload["tracker"].
        assert "sync:\n  enabled: true\n" in text_after

        if label == "null":
            # Declined deviation (see module comment above): the literal
            # spelling is not preserved, but this pins what stands in for it --
            # the key must still be present (never silently dropped, which
            # would be indistinguishable from absence), stable under a second
            # rewrite, and -- the semantic contract a byte-identity check
            # would otherwise leave unpinned -- still decode to exactly the
            # same (raw, fault) pair. Without this, a regression that rewrote
            # `egress: null` as `egress: refused` would produce a non-empty,
            # idempotent region and pass.
            assert after_region != "", "egress key must not disappear for a present null"
            reloaded = load_tracker_config(tmp_path)
            assert reloaded.egress is None
            assert reloaded.egress_fault is True
            save_tracker_config(tmp_path, reloaded)
            text_after2 = config_path.read_text(encoding="utf-8")
            assert _egress_region(text_after2) == after_region, "must be idempotent after the first rewrite"
        else:
            assert before_region == after_region, f"{label}: egress: region changed byte-for-byte"


class TestClearTrackerConfigPreservesQuotes:
    def test_clear_tracker_config_preserves_quotes_in_sibling_block(self, tmp_path: Path) -> None:
        """FR-010: `clear_tracker_config`'s third `YAML()` gains `preserve_quotes`
        too, so `unbind` stops destroying quoting in sibling blocks it has no
        business touching."""
        config_path = tmp_path / ".kittify" / "config.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            'tracker:\n  provider: linear\n  project_slug: "quoted-proj"\nsync:\n  team_slug: "quoted-team"\n',
            encoding="utf-8",
        )
        clear_tracker_config(tmp_path)
        text = config_path.read_text(encoding="utf-8")
        assert '"quoted-team"' in text, "sibling block quoting must survive an unbind with no recorded egress"


# ---------------------------------------------------------------------------
# T012 -- class A preservation: A2, A3, and the pin-less A4.
# ---------------------------------------------------------------------------


class TestSiteA2LocalBranchUnitLevel:
    """FR-011 site A2 (`TrackerService.bind`'s local branch, `service.py:163`).

    Class A' -- defence-in-depth. `LocalTrackerService.bind`
    (`local_service.py:47-63`) never reads `self._config`: it builds a fresh
    `TrackerProjectConfig` from its own keyword arguments and saves that, so
    handing it the loaded config here changes **nothing on disk** until site
    A1 (`local_service.py:57`) lands -- and A1 is WP04's, in T024. An
    end-to-end pin here would be red before this fix and red after it. So this
    is asserted at the unit level, against the object handed to the
    `LocalTrackerService` constructor, in both directions. NO red-first pin,
    NO end-to-end pin, and NO exit criterion for this site inside this WP.
    """

    @pytest.mark.parametrize("egress_value", ["refused", "permitted"])
    def test_local_branch_hands_constructor_the_loaded_egress(self, tmp_path: Path, egress_value: str) -> None:
        (tmp_path / ".kittify").mkdir()
        committed = TrackerProjectConfig(provider="beads", workspace="ws", egress=egress_value, _extra={"future_flag": True})
        save_tracker_config(tmp_path, committed)

        captured: dict[str, TrackerProjectConfig] = {}
        original_init = LocalTrackerService.__init__

        def capturing_init(self: LocalTrackerService, repo_root: Path, config: TrackerProjectConfig, *a: object, **kw: object) -> None:
            captured["config"] = config
            original_init(self, repo_root, config, *a, **kw)

        with patch.object(LocalTrackerService, "__init__", capturing_init):
            service = TrackerService(tmp_path)
            service.bind(
                provider="beads",
                workspace="ws2",
                ownership_mode="external_authoritative",
                ownership_field_owners={},
                credentials={},
            )

        assert captured["config"].egress == egress_value
        assert captured["config"]._extra == {"future_flag": True}


# ---------------------------------------------------------------------------
# T014 -- site C: unbind keeps the decision (SC-009).
# ---------------------------------------------------------------------------


class TestSiteCClearTrackerConfigPreservesEgress:
    """FR-011 site C (`clear_tracker_config`, `config.py:178-194`). Erases
    today -- unconditional `del payload["tracker"]`. File-level pin, both
    directions plus the no-key case, with the sibling `sync:` block asserted
    present as the control on every case."""

    @pytest.mark.parametrize("egress_value", ["refused", "permitted"])
    def test_unbind_leaves_only_egress_when_recorded(self, tmp_path: Path, egress_value: str) -> None:
        _write_tracker_config(tmp_path, f"  egress: {egress_value}\n")
        clear_tracker_config(tmp_path)

        text = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")
        assert f"egress: {egress_value}" in text
        assert "provider" not in text.split("sync:")[0]  # every other tracker key gone
        assert "sync:\n  enabled: true\n" in text  # control

        reloaded = load_tracker_config(tmp_path)
        assert reloaded.egress == egress_value

    def test_unbind_removes_tracker_block_when_no_egress_recorded(self, tmp_path: Path) -> None:
        config_path = tmp_path / ".kittify" / "config.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            "tracker:\n  provider: linear\n  project_slug: p\nsync:\n  enabled: true\n",
            encoding="utf-8",
        )
        clear_tracker_config(tmp_path)

        text = config_path.read_text(encoding="utf-8")
        assert "tracker:" not in text
        assert "sync:\n  enabled: true\n" in text  # control

    def test_unbind_removes_non_mapping_tracker_block(self, tmp_path: Path) -> None:
        """A non-mapping `tracker:` block is absence, not a fault (FR-006),
        so `clear_tracker_config` takes the same `from_dict(None)` ->
        `EGRESS_ABSENT` -> delete path as the no-key case above."""
        config_path = tmp_path / ".kittify" / "config.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text('tracker: "foo"\nsync:\n  enabled: true\n', encoding="utf-8")
        clear_tracker_config(tmp_path)

        text = config_path.read_text(encoding="utf-8")
        assert "tracker:" not in text
        assert "sync:\n  enabled: true\n" in text  # control
