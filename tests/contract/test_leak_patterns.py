"""Behaviour of ``contracts/tools/leak_patterns.py``, the single leak-pattern authority (plan D-P11).

Planted values are assembled from string fragments at run time, so this source
holds no literal host path or e-mail address. The two real pass controls of
spec D-14 (a friendly name and a work package title that legitimately carry
``~/`` and ``/tmp``) are the only path-looking literals, and they are the
point of the human-text class.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

MODULE_PATH = Path(__file__).resolve().parents[2] / "contracts" / "tools" / "leak_patterns.py"

SLASH = chr(47)
BACKSLASH = chr(92)
AT = chr(64)


def _home_path(user: str = "someone", tail: str = "project") -> str:
    return SLASH + "home" + SLASH + user + SLASH + tail


def _users_path(user: str = "someone", tail: str = "project") -> str:
    return SLASH + "Users" + SLASH + user + SLASH + tail


def _windows_path() -> str:
    return "C:" + BACKSLASH + "Users" + BACKSLASH + "someone" + BACKSLASH + "project"


def _tmp_path() -> str:
    return SLASH + "tmp" + SLASH + "scratch"


def _email() -> str:
    return "someone" + AT + "example.invalid"


def _github_token(prefix: str = "ghp") -> str:
    return prefix + "_" + "a1B2c3D4e5F6g7H8i9J0" * 2


def _aws_key(prefix: str = "AKIA") -> str:
    return prefix + "ABCDEFGH" + "IJKLMNOP"


def _private_key_header(kind: str = "RSA ") -> str:
    return "-" * 5 + "BEGIN " + kind + "PRIVATE" + " KEY" + "-" * 5


@pytest.fixture(scope="module")
def leaks() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, MODULE_PATH, "leak_patterns_under_test")


# -- strict fields: identifiers, handles and path-like values ----------------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(_home_path(), id="home"),
        pytest.param(_users_path(), id="users"),
        pytest.param(_windows_path(), id="windows"),
        pytest.param(SLASH + "etc" + SLASH + "passwd", id="any-absolute-path"),
        pytest.param("~" + SLASH + "notes", id="tilde-home"),
        pytest.param("C:" + SLASH + "data", id="drive-letter-forward-slash"),
        pytest.param("repo" + SLASH + "home" + SLASH + "someone" + SLASH + "x", id="embedded-home-segment"),
    ],
)
def test_strict_class_flags_host_paths(leaks: ModuleType, value: str) -> None:
    assert "HOST_PATH" in leaks.leak_codes(value, "strict")


@pytest.mark.parametrize("value", ["kitty/mission-x-lane-a", "WP01", "main", "01KDKJTC", "src/specify_cli/status/reducer.py"])
def test_strict_class_passes_ordinary_identifiers(leaks: ModuleType, value: str) -> None:
    assert leaks.leak_codes(value, "strict") == ()


# -- human text fields: real titles legitimately mention ~/ and /tmp ---------


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("see " + _home_path(), id="home-in-sentence"),
        pytest.param("open " + _users_path(), id="users-in-sentence"),
        pytest.param("run " + SLASH + "root" + SLASH + "bin", id="root"),
        pytest.param("write " + _tmp_path(), id="tmp-with-file"),
        pytest.param("a " + SLASH + "var" + SLASH + "tmp" + SLASH + "x", id="var-tmp"),
        pytest.param("a " + SLASH + "var" + SLASH + "folders" + SLASH + "x", id="var-folders"),
        pytest.param("copy " + _windows_path(), id="windows"),
    ],
)
def test_human_class_flags_real_host_paths(leaks: ModuleType, value: str) -> None:
    assert "HOST_PATH" in leaks.leak_codes(value, "human")


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("~/.kittify Runtime Centralization", id="friendly-name-real-control"),
        pytest.param("/tmp burn-down: sync", id="wp-title-real-control"),
        pytest.param("handles the tmp directory", id="bare-word"),
        pytest.param("src/home/page", id="relative-home-segment"),
    ],
)
def test_human_class_passes_the_named_real_controls(leaks: ModuleType, value: str) -> None:
    assert leaks.leak_codes(value, "human") == ()


def test_strict_and_human_classes_disagree_on_the_tilde_control(leaks: ModuleType) -> None:
    """The reason there are two classes: the same real title is a leak as a handle and clean as text."""
    value = "~/.kittify Runtime Centralization"

    assert "HOST_PATH" in leaks.leak_codes(value, "strict")
    assert leaks.leak_codes(value, "human") == ()


# -- e-mail addresses: every string class ------------------------------------


@pytest.mark.parametrize("field_class", ["strict", "human"])
def test_email_is_flagged_in_every_class(leaks: ModuleType, field_class: str) -> None:
    assert "EMAIL" in leaks.leak_codes("contact " + _email(), field_class)


@pytest.mark.parametrize(
    "address",
    [
        pytest.param("dev" + AT + "localhost", id="localhost"),
        pytest.param("root" + AT + "buildhost", id="bare-host"),
        pytest.param("first.last+tag" + AT + "internal", id="dotted-local-part"),
        pytest.param("dev" + AT + "localhost.", id="sentence-final-dot"),
    ],
)
@pytest.mark.parametrize("field_class", ["strict", "human"])
def test_email_without_a_dot_in_the_domain_is_flagged(leaks: ModuleType, address: str, field_class: str) -> None:
    assert "EMAIL" in leaks.leak_codes("mail " + address + " now", field_class)
    assert "EMAIL" in leaks.leak_codes(address, field_class)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("actions" + SLASH + "checkout" + AT + "v4", id="action-ref"),
        pytest.param(AT + "scope" + SLASH + "package", id="npm-scope"),
        pytest.param("uses: owner" + SLASH + "repo" + AT + "a" * 40, id="pinned-action"),
        pytest.param("a mention of " + AT + " alone, or " + AT + "{upstream}", id="bare-at-sign"),
        pytest.param("HEAD" + AT + "{1}", id="reflog"),
        pytest.param("spec-kitty-cli" + AT + "a1b2c3d4e5f6", id="build-id"),
        pytest.param("image" + AT + "sha256:" + "0" * 64, id="digest"),
    ],
)
@pytest.mark.parametrize("field_class", ["strict", "human"])
def test_non_email_at_signs_are_not_flagged(leaks: ModuleType, value: str, field_class: str) -> None:
    assert "EMAIL" not in leaks.leak_codes(value, field_class)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(_github_token("ghp"), id="github-personal"),
        pytest.param(_github_token("gho"), id="github-oauth"),
        pytest.param(_github_token("ghu"), id="github-user-to-server"),
        pytest.param(_github_token("ghs"), id="github-server-to-server"),
        pytest.param(_github_token("ghr"), id="github-refresh"),
        pytest.param("github" + "_pat_" + "A1b2C3d4E5f6G7h8I9j0K1_" + "x" * 40, id="github-fine-grained"),
        pytest.param(_aws_key("AKIA"), id="aws-access-key"),
        pytest.param(_aws_key("ASIA"), id="aws-session-key"),
        pytest.param(_private_key_header("RSA "), id="rsa-private-key"),
        pytest.param(_private_key_header(""), id="plain-private-key"),
        pytest.param(_private_key_header("OPENSSH "), id="openssh-private-key"),
        pytest.param(_private_key_header("EC "), id="ec-private-key"),
    ],
)
@pytest.mark.parametrize("field_class", ["strict", "human"])
def test_secrets_and_tokens_are_flagged_in_every_class(leaks: ModuleType, value: str, field_class: str) -> None:
    assert leaks.leak_codes("token " + value + " end", field_class) == ("SECRET",)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("ghp_short", id="too-short-token"),
        pytest.param("the ghp prefix and gh" + "x_" + "a" * 40, id="unknown-gh-prefix"),
        pytest.param("AKIA" + "SHORT", id="short-aws-key"),
        pytest.param("a note about a private key, BEGIN is not enough", id="prose"),
        pytest.param("-" * 5 + "BEGIN CERTIFICATE" + "-" * 5, id="public-certificate"),
    ],
)
def test_text_that_only_resembles_a_secret_is_not_flagged(leaks: ModuleType, value: str) -> None:
    assert "SECRET" not in leaks.leak_codes(value, "human")


def test_secret_is_reported_after_host_path_and_email(leaks: ModuleType) -> None:
    value = _home_path() + " " + _email() + " " + _aws_key()
    assert leaks.leak_codes(value, "human") == ("HOST_PATH", "EMAIL", "SECRET")


def test_codes_report_each_kind_once(leaks: ModuleType) -> None:
    assert leaks.leak_codes(_home_path() + " " + _email(), "human") == ("HOST_PATH", "EMAIL")


def test_non_string_values_are_not_scanned(leaks: ModuleType) -> None:
    assert leaks.leak_codes(7, "strict") == ()
    assert leaks.leak_codes(None, "human") == ()


def test_unknown_field_class_is_refused(leaks: ModuleType) -> None:
    with pytest.raises(ValueError, match="field class"):
        leaks.leak_codes("x", "free")


# -- forbidden property names ------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "feedback_path",
        "record_path",
        "prompt_path",
        "feature_dir",
        "worktree_path",
        "project_path",
        "worktree",
        "feedbackPath",
        "recordPath",
        "promptPath",
        "featureDir",
        "worktreePath",
        "projectPath",
        "FeedbackPath",
        "feedback-path",
    ],
)
def test_forbidden_property_names_are_detected_in_every_spelling(leaks: ModuleType, name: str) -> None:
    assert leaks.is_forbidden_property_name(name) is True


@pytest.mark.parametrize("name", ["missionId", "slug", "path", "workPackages", "promptMarkdown", "ownedFiles"])
def test_ordinary_property_names_are_allowed(leaks: ModuleType, name: str) -> None:
    assert leaks.is_forbidden_property_name(name) is False


def test_forbidden_names_form_a_non_trivial_set(leaks: ModuleType) -> None:
    assert len(leaks.FORBIDDEN_PROPERTY_NAMES) >= 12


# -- the library does not match its own rules ---------------------------------


def test_the_library_source_is_clean_under_its_own_patterns(leaks: ModuleType) -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert source, "the module source must be readable and non-empty"
    for line in source.splitlines():
        assert leaks.leak_codes(line.strip(), "human") == (), f"scan matched its own source line: {line.strip()!r}"


def test_every_pattern_is_a_compiled_regular_expression(leaks: ModuleType) -> None:
    patterns = [*leaks.STRICT_HOST_PATH_PATTERNS, *leaks.HUMAN_HOST_PATH_PATTERNS, leaks.EMAIL_PATTERN, *leaks.SECRET_PATTERNS]

    assert len(patterns) == 7 + len(leaks.SECRET_PATTERNS)
    assert len(leaks.SECRET_PATTERNS) >= 3
    assert all(isinstance(p, re.Pattern) for p in patterns)
