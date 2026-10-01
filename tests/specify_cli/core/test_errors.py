"""Tests for the shared :class:`StructuredError` base (#1893, NFR-007)."""

from __future__ import annotations

import pytest

from specify_cli.core.errors import StructuredError

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestStructuredErrorBase:
    """Base defaults and the default ``to_dict`` envelope."""

    def test_is_runtime_error_subclass(self) -> None:
        assert issubclass(StructuredError, RuntimeError)

    def test_default_error_code_is_empty(self) -> None:
        assert StructuredError.error_code == ""
        assert StructuredError("boom").error_code == ""

    def test_to_dict_shape(self) -> None:
        err = StructuredError("boom")
        assert err.to_dict() == {"error_code": "", "message": "boom"}

    def test_to_dict_reflects_message(self) -> None:
        err = StructuredError("specific failure")
        payload = err.to_dict()
        assert set(payload) == {"error_code", "message"}
        assert payload["message"] == "specific failure"


class TestStructuredErrorSubclass:
    """Subclasses override ``error_code`` and inherit the default envelope."""

    def test_class_attr_override(self) -> None:
        class MyError(StructuredError):
            error_code = "MY_CODE"

        err = MyError("nope")
        assert err.error_code == "MY_CODE"
        assert err.to_dict() == {"error_code": "MY_CODE", "message": "nope"}

    def test_subclass_is_catchable_as_base_and_runtime_error(self) -> None:
        class MyError(StructuredError):
            error_code = "MY_CODE"

        err = MyError("nope")
        assert isinstance(err, StructuredError)
        assert isinstance(err, RuntimeError)


class TestAdoptedFamiliesInheritBase:
    """The three families adopted in #1893 reparent onto StructuredError."""

    def test_git_preflight_error_adopts_base(self) -> None:
        from specify_cli.core.git_preflight import GitPreflightError

        assert issubclass(GitPreflightError, StructuredError)
        err = GitPreflightError("bad repo", error_code="NOT_A_GIT_REPOSITORY")
        assert err.error_code == "NOT_A_GIT_REPOSITORY"
        # Inherited default ``to_dict`` now available for free.
        assert err.to_dict() == {
            "error_code": "NOT_A_GIT_REPOSITORY",
            "message": "bad repo",
        }
        # Family-specific behaviour preserved.
        assert err.is_deterministic is True

    def test_mission_runtime_error_adopts_base(self) -> None:
        from runtime.next._internal_runtime.schema import (
            MissionRuntimeError,
            MissionTemplateHasNoStepsError,
        )

        assert issubclass(MissionRuntimeError, StructuredError)
        assert issubclass(MissionTemplateHasNoStepsError, MissionRuntimeError)
        err = MissionTemplateHasNoStepsError("no steps")
        assert err.error_code == "MISSION_TEMPLATE_HAS_NO_STEPS"
        assert err.to_dict() == {
            "error_code": "MISSION_TEMPLATE_HAS_NO_STEPS",
            "message": "no steps",
        }
