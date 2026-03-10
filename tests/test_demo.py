"""Tests that the example demos run without error."""

import pytest
import subprocess
import sys


@pytest.mark.parametrize("script", [
    "examples/two_agent_demo.py",
    "examples/three_agent_split.py",
    "examples/unknown_outcome.py",
])
def test_demo_runs(script):
    """Each demo script should exit 0."""
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        timeout=30,
        cwd="/Users/omoshola/Documents/agentra/xap-sdk",
    )
    assert result.returncode == 0, f"{script} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
