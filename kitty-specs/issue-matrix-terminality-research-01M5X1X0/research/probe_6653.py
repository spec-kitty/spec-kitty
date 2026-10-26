from pathlib import Path

import pytest

import tests.policy.test_merge_gates_issue_matrix as m


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    m._init_git_repo(r)
    return r


def test_uncited_in_mission_row(repo, monkeypatch):
    slug = m._build_lanes_mission(repo, mid8="01PROBE1", primary_matrix={"#1234": "fixed", "#5678": "in-mission"})
    ok, gates = m._run_gates(repo, slug, mode="block")
    g = m._gate(gates, m._TERMINALITY_GATE)
    print("UNCITED:", g.verdict, g.details)


def test_zero_refs_in_mission_row(repo, monkeypatch):
    monkeypatch.setattr(m, "_GATING_SPEC_TEXT", "# Spec\n\nNo refs.\n")
    slug = m._build_lanes_mission(repo, mid8="01PROBE2", primary_matrix={"#5678": "in-mission"})
    ok, gates = m._run_gates(repo, slug, mode="block")
    g = m._gate(gates, m._TERMINALITY_GATE)
    print("ZERO:", g.verdict, g.details)


def test_one_digit_ref(repo, monkeypatch):
    monkeypatch.setattr(m, "_GATING_SPEC_TEXT", "This mission fixes the crash reported in #8.\n")
    slug = m._build_lanes_mission(repo, mid8="01PROBE3", primary_matrix={"#8": "in-mission"})
    ok, gates = m._run_gates(repo, slug, mode="block")
    g = m._gate(gates, m._TERMINALITY_GATE)
    print("ONEDIGIT:", g.verdict, g.details)
