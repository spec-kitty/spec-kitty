"""Subscriber identity consumes issuer refs, with explicit protocol acknowledgment."""

from types import SimpleNamespace
import pytest
from specify_cli.zeitgeist_client import own_filter


def test_both_issuer_sessions_are_forwarded_without_derivation():
    stored = SimpleNamespace(session_ref="issuer-a", focus_session_ref="issuer-focus")
    assert own_filter.identity_header(stored) == "issuer-a,issuer-focus"


@pytest.mark.parametrize("refs", [(None, None), ("bad,ref", None), ("", None)])
def test_unresolvable_identity_fails_loud(refs):
    with pytest.raises(ValueError, match="identity"):
        own_filter.identity_header(SimpleNamespace(session_ref=refs[0], focus_session_ref=refs[1]))


@pytest.mark.parametrize("ack", [None, "false", "TRUE"])
def test_old_or_unconfirmed_relay_fails_before_read(ack):
    with pytest.raises(ValueError, match="confirm"):
        own_filter.require_ack({"X-Zeitgeist-Filter-Own": ack})


def test_true_acknowledgment():
    own_filter.require_ack({"X-Zeitgeist-Filter-Own": "true"})
