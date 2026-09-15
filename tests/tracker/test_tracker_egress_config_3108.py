"""Tests for tracker.egress: Channel-2 key shape and preservation (#3108 WP02).

Covers T009-T014 of the WP02 work-package prompt:

* T009 -- the field shape (raw value + derived fault, ``EGRESS_ABSENT`` sentinel,
  ``isinstance``-guarded decode) over the full 15-value probed set from FR-010.
* T010 -- ``to_dict`` omits ``egress`` when nothing is recorded (FR-009); the
  null-planting red was observed and quoted on the FR-002-only tree before this
  fix landed (see the WP02 PR body for the quoted ``RepresenterError``).
* T011 -- byte-identical round trip over the probed set of exactly 15
  (FR-010), scoped to the ``egress:`` line.
* T012 -- class-A preservation: A2 and A4 asserted at the unit level against
  the constructed object (no red-first pin, no end-to-end pin -- see the WP02
  prompt's rationale for why neither is earnable inside this WP); A3 asserted
  end-to-end on disk, both directions, with the sibling ``sync:`` block as the
  control.
* T013 -- class-B carries: B1 (``apply_binding_upgrade``) and B2
  (``_persist_binding``), the two sites this WP's own field-shape promotion
  breaks. Their reds were observed and quoted on the FR-002-only tree (see the
  WP02 PR body).
* T014 -- sites C (``clear_tracker_config``) and D (``SaaSTrackerService.unbind``):
  a recorded decision outlives its binding, both directions, with the sibling
  ``sync:`` block as the control on every case including "nothing recorded".
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.tracker.config import (
    EGRESS_ABSENT,
    TrackerProjectConfig,
    clear_tracker_config,
    load_tracker_config,
    save_tracker_config,
)
from specify_cli.tracker.local_service import LocalTrackerService
from specify_cli.tracker.saas_service import SaaSTrackerService
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


class TestSiteA3SaaSBindPreservesEgress:
    """FR-011 site A3 (`SaaSTrackerService.bind`, `saas_service.py:266`).

    Erases today -- measured: `TrackerProjectConfig(provider=..., project_slug=...)`
    carries nothing forward. File-level pin, both directions, with the
    sibling `sync:` block asserted present as the control.
    """

    @pytest.mark.parametrize("egress_value", ["refused", "permitted"])
    def test_bind_carries_egress_forward(self, tmp_path: Path, egress_value: str) -> None:
        (tmp_path / ".kittify").mkdir()
        initial = TrackerProjectConfig(provider="linear", project_slug="old-proj", egress=egress_value)
        save_tracker_config(tmp_path, initial)
        config_path = tmp_path / ".kittify" / "config.yaml"
        config_path.write_text(config_path.read_text() + "sync:\n  enabled: true\n")

        loaded = load_tracker_config(tmp_path)
        service = SaaSTrackerService(tmp_path, loaded, client=MagicMock())
        service.bind(provider="linear", project_slug="new-proj")

        after_text = config_path.read_text(encoding="utf-8")
        reloaded = load_tracker_config(tmp_path)
        assert reloaded.egress == egress_value
        assert reloaded.project_slug == "new-proj"  # the rewrite genuinely happened
        assert "sync:\n  enabled: true\n" in after_text  # control: rest of file untouched

    @pytest.mark.parametrize("egress_value", ["refused", "permitted"])
    def test_bind_carries_extra_forward(self, tmp_path: Path, egress_value: str) -> None:
        (tmp_path / ".kittify").mkdir()
        initial = TrackerProjectConfig(provider="linear", project_slug="old-proj", egress=egress_value, _extra={"future_flag": True})
        save_tracker_config(tmp_path, initial)

        loaded = load_tracker_config(tmp_path)
        service = SaaSTrackerService(tmp_path, loaded, client=MagicMock())
        service.bind(provider="linear", project_slug="new-proj")

        reloaded = load_tracker_config(tmp_path)
        assert reloaded._extra == {"future_flag": True}


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


class TestSiteA4SubstitutedBackendUnitLevel:
    """FR-011 site A4 (`TrackerService._resolve_saas_backend_for_provider`,
    `service.py:98`). Defence-in-depth -- NO production write path today
    (`apply_binding_upgrade` has zero callers in `src/`; the three read-only
    call sites at `service.py:210,214,220` persist nothing). NO red-first pin.
    Asserted at the unit level, against the substituted config object, in
    both directions.
    """

    @pytest.mark.parametrize("egress_value", ["refused", "permitted"])
    def test_provider_mismatch_substitution_carries_egress(self, tmp_path: Path, egress_value: str) -> None:
        (tmp_path / ".kittify").mkdir()
        committed = TrackerProjectConfig(provider="beads", workspace="ws", egress=egress_value, _extra={"future_flag": True})
        save_tracker_config(tmp_path, committed)

        captured: dict[str, TrackerProjectConfig] = {}
        original_init = SaaSTrackerService.__init__

        def capturing_init(self: SaaSTrackerService, repo_root: Path, config: TrackerProjectConfig, *a: object, **kw: object) -> None:
            captured["config"] = config
            original_init(self, repo_root, config, *a, **kw)

        with patch.object(SaaSTrackerService, "__init__", capturing_init):
            service = TrackerService(tmp_path)
            service._resolve_saas_backend_for_provider("jira")

        assert captured["config"].provider == "jira"
        assert captured["config"].egress == egress_value
        assert captured["config"]._extra == {"future_flag": True}

    def test_same_provider_does_not_substitute(self, tmp_path: Path) -> None:
        """Negative control: when the on-disk provider already matches, no
        substitution happens at all -- the loaded config (with its already
        correct egress) is used directly."""
        (tmp_path / ".kittify").mkdir()
        committed = TrackerProjectConfig(provider="jira", project_slug="p", egress="refused")
        save_tracker_config(tmp_path, committed)

        service = TrackerService(tmp_path)
        backend = service._resolve_saas_backend_for_provider("jira")
        assert backend._config.egress == "refused"


# ---------------------------------------------------------------------------
# T013 -- class B carries: the two sites this WP's own promotion breaks.
#
# Both were observed red on the FR-002-only tree (T009 applied, before these
# carries were added) and quoted in the WP02 PR body:
#
#   B1: AssertionError: B1 RED: expected 'refused', got EGRESS_ABSENT (is EGRESS_ABSENT: True)
#   B2: AssertionError: B2 RED: expected 'permitted', got EGRESS_ABSENT (is EGRESS_ABSENT: True)
#
# Detection signal: tests/specify_cli/tracker/test_binding_report_only.py's
# test_apply_binding_upgrade_preserves_extra_fields must stay green -- it
# would red if the fix here replaced the `_extra` carry instead of adding an
# `egress` carry beside it (not owned or touched by this WP; run as part of
# the wider regression suite, not duplicated in this file).
# ---------------------------------------------------------------------------


class TestSiteB1ApplyBindingUpgradeCarriesEgress:
    @pytest.mark.parametrize("egress_value", ["refused", "permitted"])
    def test_apply_binding_upgrade_carries_egress(self, tmp_path: Path, egress_value: str) -> None:
        (tmp_path / ".kittify").mkdir()
        committed = TrackerProjectConfig(provider="linear", project_slug="p", egress=egress_value)
        save_tracker_config(tmp_path, committed)

        loaded = load_tracker_config(tmp_path)
        service = SaaSTrackerService(tmp_path, loaded, client=MagicMock())
        service.apply_binding_upgrade("new-binding-ref-123")

        reloaded = load_tracker_config(tmp_path)
        assert reloaded.egress == egress_value


class TestSiteB2PersistBindingCarriesEgress:
    @pytest.mark.parametrize("egress_value", ["refused", "permitted"])
    def test_validate_and_bind_carries_egress(self, tmp_path: Path, egress_value: str) -> None:
        (tmp_path / ".kittify").mkdir()
        committed = TrackerProjectConfig(provider="linear", project_slug="p", egress=egress_value)
        save_tracker_config(tmp_path, committed)

        loaded = load_tracker_config(tmp_path)
        mock_client = MagicMock()
        mock_client.bind_validate.return_value = {
            "valid": True,
            "binding_ref": "lin-abc",
            "reason": None,
            "guidance": None,
            "display_label": "My Board",
            "provider": "linear",
            "provider_context": {},
        }
        service = SaaSTrackerService(tmp_path, loaded, client=mock_client)
        service.validate_and_bind(provider="linear", bind_ref="lin-abc")

        reloaded = load_tracker_config(tmp_path)
        assert reloaded.egress == egress_value


# ---------------------------------------------------------------------------
# T014 -- sites C and D: unbind keeps the decision (SC-009).
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


class TestSiteDUnbindResetsToLoadedConfig:
    """FR-011 site D (`SaaSTrackerService.unbind`, `saas_service.py:281`).
    Library-caller reachable only. Unit-level: after `unbind`, `self._config`
    matches what site C just left on disk, in both directions."""

    @pytest.mark.parametrize("egress_value", ["refused", "permitted"])
    def test_unbind_resets_in_memory_config_from_disk(self, tmp_path: Path, egress_value: str) -> None:
        (tmp_path / ".kittify").mkdir()
        committed = TrackerProjectConfig(provider="linear", project_slug="p", egress=egress_value)
        save_tracker_config(tmp_path, committed)

        loaded = load_tracker_config(tmp_path)
        service = SaaSTrackerService(tmp_path, loaded, client=MagicMock())
        service.unbind()

        assert service._config.egress == egress_value

    def test_unbind_resets_in_memory_config_to_absent_when_nothing_recorded(self, tmp_path: Path) -> None:
        (tmp_path / ".kittify").mkdir()
        committed = TrackerProjectConfig(provider="linear", project_slug="p")
        save_tracker_config(tmp_path, committed)

        loaded = load_tracker_config(tmp_path)
        service = SaaSTrackerService(tmp_path, loaded, client=MagicMock())
        service.unbind()

        assert service._config.egress is EGRESS_ABSENT
