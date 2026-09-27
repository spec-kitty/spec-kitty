#!/usr/bin/env python3
"""
Performance tests for GitignoreManager.

Tests that operations complete within the <1 second requirement.

#4015: the wall-clock budget assertions below were split out of the
original mixed timing+functional tests into dedicated
``@pytest.mark.performance`` tests (nightly-only); the functional
assertions (``result.success``) stay unmarked on the per-PR path. Budgets
are preserved via ``tests/_perf_helpers.py::assert_timing_budget``.
"""

import sys
import tempfile
import time
from pathlib import Path

import pytest
from specify_cli import gitignore_manager

from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.integration]

GitignoreManager = gitignore_manager.GitignoreManager


def test_performance_protect_all_agents():
    """Verify protect_all_agents succeeds (functional half of #4015 split)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        manager = GitignoreManager(project_path)

        result = manager.protect_all_agents()

        assert result.success, "Operation should succeed"


@pytest.mark.performance
def test_protect_all_agents_stays_under_one_second():
    """Verify protect_all_agents completes in under 1 second (nightly).

    Split from ``test_performance_protect_all_agents`` (#4015); budget preserved.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        manager = GitignoreManager(project_path)

        start_time = time.perf_counter()
        manager.protect_all_agents()
        elapsed = time.perf_counter() - start_time

        assert_timing_budget(elapsed, 1.0, name="protect_all_agents")

        print(f"✓ protect_all_agents completed in {elapsed:.3f}s")


def test_performance_with_large_gitignore():
    """Verify protect_all_agents succeeds against a large existing .gitignore.

    Functional half of the #4015 split.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        gitignore_path = project_path / ".gitignore"

        # Create large .gitignore (10,000 lines)
        large_content = "\n".join([f"pattern{i}/" for i in range(10000)])
        gitignore_path.write_text(large_content)

        manager = GitignoreManager(project_path)

        result = manager.protect_all_agents()

        assert result.success, "Operation should succeed"


@pytest.mark.performance
def test_large_gitignore_stays_under_one_second():
    """Verify a large existing .gitignore doesn't push protect_all_agents past 1s (nightly).

    Split from ``test_performance_with_large_gitignore`` (#4015); budget preserved.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        gitignore_path = project_path / ".gitignore"

        large_content = "\n".join([f"pattern{i}/" for i in range(10000)])
        gitignore_path.write_text(large_content)

        manager = GitignoreManager(project_path)

        start_time = time.perf_counter()
        manager.protect_all_agents()
        elapsed = time.perf_counter() - start_time

        assert_timing_budget(elapsed, 1.0, name="large_gitignore_protect_all_agents")

        print(f"✓ Large file (10K lines) completed in {elapsed:.3f}s")


@pytest.mark.performance
def test_performance_multiple_runs():
    """Test performance of multiple consecutive runs (idempotency)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        manager = GitignoreManager(project_path)

        # First run
        start1 = time.perf_counter()
        manager.protect_all_agents()
        elapsed1 = time.perf_counter() - start1

        # Second run (should be faster - just checking)
        start2 = time.perf_counter()
        manager.protect_all_agents()
        elapsed2 = time.perf_counter() - start2

        # Third run
        start3 = time.perf_counter()
        manager.protect_all_agents()
        elapsed3 = time.perf_counter() - start3

        assert_timing_budget(elapsed1, 1.0, name="multiple_runs_first")
        assert_timing_budget(elapsed2, 1.0, name="multiple_runs_second")
        assert_timing_budget(elapsed3, 1.0, name="multiple_runs_third")

        print(f"✓ Multiple runs: {elapsed1:.3f}s, {elapsed2:.3f}s, {elapsed3:.3f}s")


def test_performance_selected_agents():
    """Verify protect_selected_agents succeeds across several selections.

    Functional half of the #4015 split.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        manager = GitignoreManager(project_path)

        # Test with various selections
        test_cases = [
            (["claude"], "single"),
            (["claude", "codex", "gemini"], "three"),
            (["claude", "codex", "gemini", "cursor", "qwen", "kiro"], "six"),
        ]

        for agents, desc in test_cases:
            result = manager.protect_selected_agents(agents)

            assert result.success, f"Operation should succeed for {desc}"


@pytest.mark.performance
def test_selected_agents_stay_under_one_second():
    """Verify protect_selected_agents completes in under 1 second per selection (nightly).

    Split from ``test_performance_selected_agents`` (#4015); budget preserved.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        manager = GitignoreManager(project_path)

        test_cases = [
            (["claude"], "single"),
            (["claude", "codex", "gemini"], "three"),
            (["claude", "codex", "gemini", "cursor", "qwen", "kiro"], "six"),
        ]

        for agents, desc in test_cases:
            start_time = time.perf_counter()
            manager.protect_selected_agents(agents)
            elapsed = time.perf_counter() - start_time

            assert_timing_budget(elapsed, 1.0, name=f"protect_selected_agents[{desc}]")

            print(f"✓ protect_selected_agents ({desc}) completed in {elapsed:.3f}s")


def run_performance_tests():
    """Run all performance tests."""
    tests = [
        test_performance_protect_all_agents,
        test_protect_all_agents_stays_under_one_second,
        test_performance_with_large_gitignore,
        test_large_gitignore_stays_under_one_second,
        test_performance_multiple_runs,
        test_performance_selected_agents,
        test_selected_agents_stay_under_one_second,
    ]

    print("Running Performance Tests")
    print("=" * 40)
    print("Requirement: All operations must complete in <1 second")
    print()

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: Unexpected error: {e}")
            failed += 1

    print()
    print("=" * 40)
    print(f"Results: {passed} passed, {failed} failed")

    if passed == len(tests):
        print("✅ Performance requirement met: All operations <1 second")
    else:
        print("❌ Performance requirement NOT met")

    return failed == 0


if __name__ == "__main__":
    success = run_performance_tests()
    sys.exit(0 if success else 1)
