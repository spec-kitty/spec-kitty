"""Tests for the WP01/#3104 bundle-presence + org-pack-safe ``is_charter_empty`` predicate.

Behaviour matrix under test (``research.md`` "The dispatch predicate (#3104) --
corrected, org-pack-safe"; ``kitty-specs/charter-pack-usage-journey-01KYWWTF/
tasks/WP01-dispatch-net-predicate.md``):

- empty project -> net fires (generic-agent).
- ``charter activate --preset minimal --no-compile`` -> net still fires -- the
  **#3104 fix**. Before this WP, applying a preset made the composite predicate
  flip to "configured" with no bundle and no routable profile, so an
  unmatched request hard-failed with a bare ``ROUTER_NO_MATCH`` -- worse than
  the fully empty project it was meant to guard.
- a compiled bundle present -> net disengages; the router runs and an
  unmatched request surfaces the honest ``ROUTER_NO_MATCH``.
- an org pack registered (no compiled bundle) -> net stays off (regression
  guard: an org-pack project already has routable profiles).
- a bootstrapped-empty compiled bundle (SC-005) -> net stays off (presence
  only -- bundle *contents* are never inspected).
- an explicit ``activated_agent_profiles: []`` (frozenset() opt-out, no
  bundle) -> net stays off, matching the ``is not None`` three-state
  semantics ``PackContext`` already carries.

Cases 1-3 drive the REAL dispatch seam end-to-end (`spec-kitty dispatch` CLI
-> ``ProfileInvocationExecutor.invoke`` -> ``resolve_generic_fallback`` /
``ActionRouter.route``) against the real built-in agent-profile catalog, not
``is_charter_empty`` in isolation. Case 2 in particular is built via the REAL
`spec-kitty charter activate --preset minimal --no-compile` command (the fixture-realism guard --
a hand-crafted ``activated_agent_profiles: []`` would make the predicate
return ``False`` and silently defeat the #3104 proof).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import Result
from ruamel.yaml import YAML
from typer import Typer
from typer.testing import CliRunner

from charter.activation.pack_context import PackContext
from specify_cli import app as cli_app
from specify_cli.cli.commands.charter import charter_app
from specify_cli.invocation.empty_charter import (
    GENERIC_AGENT_ID,
    is_charter_empty,
    resolve_generic_fallback,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _ArgvCliRunner(CliRunner):
    """CliRunner that also patches ``sys.argv`` (mirrors ``test_dispatch.py``).

    The readiness/auth precheck (``specify_cli.readiness.coordinator
    ._derive_output_policy``) classifies interactive vs. machine-output mode
    by inspecting ``sys.argv`` directly (looking for ``--json``/``--quiet``),
    not the parsed Click args -- plain ``CliRunner.invoke`` never touches
    ``sys.argv``, so that check would otherwise misclassify every invocation
    here as interactive and print an unrelated stderr auth banner that
    corrupts the ``--json`` stdout payload this file parses.
    """

    def invoke(  # type: ignore[override]
        self,
        app: Typer,
        args: str | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> Result:
        argv = ["spec-kitty", *(list(args) if args is not None and not isinstance(args, str) else [])]
        with patch.object(sys, "argv", argv):
            return super().invoke(app, args, **kwargs)


runner = _ArgvCliRunner()

#: The request the router genuinely cannot match: no canonical verb (ADR-3
#: ``CANONICAL_VERB_MAP``), no built-in profile domain keyword or
#: collaboration canonical-verb. Shared across cases 2/3 so the ONLY variable
#: between "the net saves it" and "the router honestly fails" is the charter
#: state, not the request text.
_UNROUTABLE_REQUEST = "help me"

_MATCHABLE_REQUEST = "implement the payment module"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _write_config(repo_root: Path, data: dict[str, object]) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(data, fh)


def _write_compiled_bundle(repo_root: Path, content: str = "{}\n") -> Path:
    """Materialize a compiled-bundle presence fixture at the read authority.

    Presence-only per the predicate contract: the content is deliberately a
    near-empty placeholder (never a full ``compile_charter`` product) because
    :func:`is_charter_empty` must never inspect bundle contents -- only
    whether the file exists.
    """
    bundle_dir = repo_root / ".kittify" / "charter"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / "charter.yaml"
    bundle_path.write_text(content, encoding="utf-8")
    return bundle_path


def _dispatch(project: Path, args: list[str]) -> Result:
    with (
        patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project),
        patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX),
    ):
        return runner.invoke(cli_app, ["dispatch", *args])


def _dispatch_json(project: Path, args: list[str]) -> dict[str, object]:
    result = _dispatch(project, [*args, "--json"])
    assert result.exit_code == 0, result.output
    payload: dict[str, object] = json.loads(result.output)
    return payload


def _apply_minimal_via_real_cli(project: Path) -> Result:
    """Apply the built-in ``minimal`` preset via the REAL `charter activate --preset` command.

    Fixture-realism guard (WP01 T003): this is the actual
    ``spec-kitty charter activate --preset minimal --no-compile`` command (it
    replaced ``charter pack apply minimal``, #3732), not a hand-authored
    config.yaml -- a hand-crafted ``activated_agent_profiles: []`` would
    become ``frozenset()`` (not ``None``) and make the #3104 proof a false
    green (the predicate would already return ``False`` on that dimension
    alone, independent of the bundle-presence fix under test).
    """
    return runner.invoke(
        charter_app,
        ["activate", "--preset", "minimal", "--no-compile", "--repo-root", str(project)],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Journey 1 -- wholly empty project: unmatched dispatch falls back
# ---------------------------------------------------------------------------


def test_journey1_empty_project_falls_back_to_generic_agent(tmp_path: Path) -> None:
    """No `.kittify` at all -> the net fires; dispatch never reaches the router."""
    envelope = _dispatch_json(tmp_path, [_MATCHABLE_REQUEST])

    assert envelope["profile_id"] == GENERIC_AGENT_ID
    assert envelope["router_confidence"] == "generic_fallback"
    assert envelope["empty_charter_fallback"] is True


# ---------------------------------------------------------------------------
# Journey 2 -- #3104 RED-FIRST: apply minimal WITHOUT compiling still falls back
# ---------------------------------------------------------------------------


def test_journey2_apply_minimal_without_compile_still_falls_back_not_router_no_match(
    tmp_path: Path,
) -> None:
    """THE #3104 REGRESSION TEST.

    Before this WP: applying the `minimal` preset wrote ``activated_directives``/
    ``activated_tactics`` into config.yaml with no compiled bundle and no
    agent-profile activation. The pre-#3104-fix composite predicate treated
    that as "configured" (a non-empty URN set), so the generic-agent net
    disengaged and an unmatched request like ``_UNROUTABLE_REQUEST`` hit the
    router directly and raised ``RouterAmbiguityError("ROUTER_NO_MATCH")`` --
    dispatch exited 1, strictly worse than the empty-project case (journey 1).

    This test is RED against the pre-WP01 predicate (dispatch would exit 1
    with error_code ROUTER_NO_MATCH) and GREEN after the bundle-presence
    rewrite (the net fires purely because no compiled bundle exists yet).
    """
    apply_result = _apply_minimal_via_real_cli(tmp_path)
    assert apply_result.exit_code == 0, apply_result.output

    config_path = tmp_path / ".kittify" / "config.yaml"
    written = YAML(typ="safe").load(config_path.read_text(encoding="utf-8"))
    # Fixture-realism guard: the real `minimal` preset declares no
    # `activated_agent_profiles` key at all (packs/built-in/presets/minimal.yaml) --
    # confirm the produced config carries no such key, so this scenario truly
    # exercises the three-state `None` (not a stand-in `frozenset()`).
    assert "activated_agent_profiles" not in written
    assert not (tmp_path / ".kittify" / "charter" / "charter.yaml").exists()

    envelope = _dispatch_json(tmp_path, [_UNROUTABLE_REQUEST])

    assert envelope["profile_id"] == GENERIC_AGENT_ID
    assert envelope["router_confidence"] == "generic_fallback"
    assert envelope["empty_charter_fallback"] is True


# ---------------------------------------------------------------------------
# Journey 3 -- compiled bundle present: net disengages, router runs honestly
# ---------------------------------------------------------------------------


def test_journey3_compiled_bundle_present_disengages_net_router_no_match_is_honest(
    tmp_path: Path,
) -> None:
    """A compiled bundle answers "configured" on its own -- the net turns off and
    the router is allowed to fail honestly on a genuinely unmatched request.
    """
    _write_compiled_bundle(tmp_path)

    result = _dispatch(tmp_path, [_UNROUTABLE_REQUEST, "--json"])

    assert result.exit_code == 1
    error_obj = json.loads(result.output)
    assert error_obj["error_code"] == "ROUTER_NO_MATCH"


def test_journey3_compiled_bundle_present_matched_request_still_routes(tmp_path: Path) -> None:
    """Sanity companion: with the net off, a MATCHABLE request reaches the real
    router (not generic-agent, not the fallback) -- the bundle presence alone
    doesn't suppress the router for requests it actually can resolve.

    The full built-in catalog has several IMPLEMENTER-role specialists, so
    ``_MATCHABLE_REQUEST`` may resolve unambiguously OR tie between them
    (``ROUTER_AMBIGUOUS``) -- either is real router engagement. Only the
    empty-charter fallback (never raised by the router itself) would be a
    #3104-predicate regression here.
    """
    _write_compiled_bundle(tmp_path)

    result = _dispatch(tmp_path, [_MATCHABLE_REQUEST, "--json"])
    payload = json.loads(result.output)

    if result.exit_code == 0:
        assert payload["empty_charter_fallback"] is False
        assert payload["profile_id"] != GENERIC_AGENT_ID
        assert payload["router_confidence"] != "generic_fallback"
    else:
        # RouterDecision.confidence never includes "generic_fallback" for a
        # router-raised ambiguity -- ROUTER_AMBIGUOUS/ROUTER_NO_MATCH are the
        # only two error codes route() ever raises, both proof the net is off.
        assert payload["error_code"] in {"ROUTER_AMBIGUOUS", "ROUTER_NO_MATCH"}


# ---------------------------------------------------------------------------
# Org-pack composite-safety regression guard (research.md Journey #3)
# ---------------------------------------------------------------------------


def test_org_pack_present_no_bundle_keeps_net_off(tmp_path: Path) -> None:
    """An org/project pack registered in config.yaml already makes the router
    routable, even with no compiled bundle -- the net must stay off (no
    regression vs. the pre-#3104 predicate's org-pack handling).
    """
    pack_root = tmp_path / "org-packs" / "orgzilla-governance-pack"
    pack_root.mkdir(parents=True)
    _write_config(
        tmp_path,
        {"doctrine": {"org": {"packs": [{"name": "orgzilla-governance-pack", "local_path": str(pack_root)}]}}},
    )
    assert not (tmp_path / ".kittify" / "charter" / "charter.yaml").exists()

    pack_context = PackContext.from_config(tmp_path)
    assert pack_context.org_roots != ()

    assert is_charter_empty(tmp_path) is False
    assert resolve_generic_fallback(tmp_path, _MATCHABLE_REQUEST) is None


# ---------------------------------------------------------------------------
# SC-005 -- bootstrapped-empty compiled bundle keeps the net OFF
# ---------------------------------------------------------------------------


def test_bootstrapped_empty_bundle_keeps_net_off(tmp_path: Path) -> None:
    """A compiled ``charter.yaml`` with NO activations still counts as
    "configured" (presence, never contents) -- pinned so a future
    contents-inspecting change to the predicate can't regress this.
    """
    _write_compiled_bundle(tmp_path, content="{}\n")
    # No config.yaml activation keys at all -- if the predicate ever started
    # inspecting bundle *contents*, this repo would look wholly empty and
    # wrongly re-engage the net.
    assert not (tmp_path / ".kittify" / "config.yaml").exists()

    assert is_charter_empty(tmp_path) is False
    assert resolve_generic_fallback(tmp_path, _MATCHABLE_REQUEST) is None


# ---------------------------------------------------------------------------
# frozenset() opt-out pin -- explicit zero-profile activation stays routable
# ---------------------------------------------------------------------------


def test_explicit_empty_agent_profile_list_keeps_net_off(tmp_path: Path) -> None:
    """An explicit ``activated_agent_profiles: []`` is `frozenset()`, NOT
    `None` -- three-state semantics say "key present" is still "configured".
    Pinned so a later reader can't "tidy" `is not None` into a truthiness
    check (`if pack_context.activated_agent_profiles:`), which would silently
    treat this case as unconfigured again.
    """
    _write_config(tmp_path, {"activated_agent_profiles": []})
    assert not (tmp_path / ".kittify" / "charter" / "charter.yaml").exists()

    pack_context = PackContext.from_config(tmp_path)
    assert pack_context.activated_agent_profiles == frozenset()
    assert pack_context.activated_agent_profiles is not None

    assert is_charter_empty(tmp_path) is False
    assert resolve_generic_fallback(tmp_path, _MATCHABLE_REQUEST) is None


# ---------------------------------------------------------------------------
# NFR-001 perf spy (advisory, folds #3118)
# ---------------------------------------------------------------------------


def test_perf_spy_bounds_from_config_and_bundle_stat_calls(tmp_path: Path) -> None:
    """Advisory NFR-001 bound: on an unconfigured repo, `is_charter_empty`
    performs <= 1 `PackContext.from_config` call and <= 1 `.exists()` check on
    the bundle path, with NO `charter_activated_urns` URN load at all (folding
    #3118's double config-load -- the pre-WP01 predicate loaded config once
    for `charter_activated_urns` and again for `PackContext.from_config`).
    """
    from specify_cli.invocation import empty_charter as empty_charter_module

    bundle_exists_calls: list[Path] = []
    original_exists = Path.exists

    def _spying_exists(self: Path) -> bool:
        if self.name == "charter.yaml" and self.parent.name == "charter":
            bundle_exists_calls.append(self)
        return original_exists(self)

    from_config_call_count = 0
    original_from_config = empty_charter_module.PackContext.from_config

    def _spying_from_config(repo_root: Path) -> PackContext:
        nonlocal from_config_call_count
        from_config_call_count += 1
        return original_from_config(repo_root)

    with (
        patch.object(Path, "exists", _spying_exists),
        patch.object(empty_charter_module.PackContext, "from_config", _spying_from_config),
        patch(
            "charter.activation.pack_context.charter_activated_urns",
            side_effect=AssertionError("is_charter_empty must not load charter_activated_urns (#3118 fold)"),
        ) as urn_load_spy,
    ):
        result = empty_charter_module.is_charter_empty(tmp_path)

    assert result is True
    assert len(bundle_exists_calls) <= 1
    assert from_config_call_count <= 1
    urn_load_spy.assert_not_called()


def test_charter_bundle_path_matches_canonical_bundle_constant() -> None:
    """Drift guard (second-opinion NOTE): ``empty_charter``'s local bundle-path
    literal must equal the canonical ``charter.bundle.CHARTER_YAML``. The copy is a
    deliberate fast-path literal (avoids importing ``charter.bundle``'s pydantic
    machinery on the hot dispatch net), so this pins the two in sync — a future
    relocation of ``CHARTER_YAML`` would otherwise silently misfire the
    generic-fallback net while ``is_charter_empty`` still read the stale path.
    """
    from charter.bundle import CHARTER_YAML

    from specify_cli.invocation import empty_charter

    assert empty_charter._CHARTER_BUNDLE_PATH == CHARTER_YAML
