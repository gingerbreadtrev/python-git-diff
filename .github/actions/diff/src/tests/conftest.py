"""Pytest configuration file for GitHub Action tests."""

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, TypedDict, TYPE_CHECKING

import pytest

from utils import FilesByStatus

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


class GitHubEnv(TypedDict, total=False):
    """TypedDict for GitHub environment variables."""

    GITHUB_EVENT_NAME: str
    GITHUB_EVENT_PATH: str
    GITHUB_TOKEN: str
    GITHUB_REPOSITORY: str
    GITHUB_SHA: str
    GITHUB_REF: str
    GITHUB_BEFORE: str
    GITHUB_AFTER: str
    GITHUB_STEP_SUMMARY: str
    GITHUB_OUTPUT: str
    GITHUB_ENV: str
    RUNNER_DEBUG: str
    INPUT_TOKEN: str
    INPUT_FILTERS: str
    INPUT_BASE_SHA: str
    INPUT_HEAD_SHA: str


@pytest.fixture
def temp_github_env(monkeypatch: "MonkeyPatch", tmp_path: Path) -> Generator[GitHubEnv, None, None]:
    """
    Set up a temporary GitHub Actions environment.

    Args:
        monkeypatch: Pytest fixture for patching environment
        tmp_path: Temporary directory path

    Yields:
        Dictionary with set environment variables
    """
    # Create temporary files that GitHub Actions would normally provide
    github_output = tmp_path / "github_output"
    github_output.touch()

    github_env = tmp_path / "github_env"
    github_env.touch()

    step_summary = tmp_path / "step_summary"
    step_summary.touch()

    event_path = tmp_path / "event.json"

    # Default environment setup
    env_vars: GitHubEnv = {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(event_path),
        "GITHUB_REPOSITORY": "user/repo",
        "GITHUB_OUTPUT": str(github_output),
        "GITHUB_ENV": str(github_env),
        "GITHUB_STEP_SUMMARY": str(step_summary),
    }

    # Apply environment variables
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    yield env_vars


@pytest.fixture
def pull_request_event(temp_github_env: GitHubEnv, tmp_path: Path) -> Dict[str, Any]:
    """
    Create a mock pull request event.

    Args:
        temp_github_env: GitHub environment fixture
        tmp_path: Temporary directory path

    Returns:
        Dictionary representing the pull request event
    """
    event_data = {
        "pull_request": {
            "number": 123,
            "base": {"sha": "base-sha-1234567890", "ref": "main"},
            "head": {"sha": "head-sha-1234567890", "ref": "feature-branch"},
        }
    }

    # Write event data to the event path
    event_path = Path(temp_github_env["GITHUB_EVENT_PATH"])
    with open(event_path, "w", encoding="utf-8") as f:
        json.dump(event_data, f)

    return event_data


@pytest.fixture
def push_event(temp_github_env: GitHubEnv, tmp_path: Path) -> Dict[str, Any]:
    """
    Create a mock push event.

    Args:
        temp_github_env: GitHub environment fixture
        tmp_path: Temporary directory path

    Returns:
        Dictionary representing the push event
    """
    # Update event type
    temp_github_env["GITHUB_EVENT_NAME"] = "push"

    # Set before and after SHAs
    temp_github_env["GITHUB_BEFORE"] = "before-sha-1234567890"
    temp_github_env["GITHUB_AFTER"] = "after-sha-1234567890"

    event_data = {"before": "before-sha-1234567890", "after": "after-sha-1234567890", "ref": "refs/heads/main"}

    # Write event data to the event path
    event_path = Path(temp_github_env["GITHUB_EVENT_PATH"])
    with open(event_path, "w", encoding="utf-8") as f:
        json.dump(event_data, f)

    return event_data


@pytest.fixture
def mock_files_by_status() -> FilesByStatus:
    """
    Create a sample FilesByStatus object for testing.

    Returns:
        FilesByStatus object with sample data
    """
    return {
        "added": ["file1.txt", "file2.py"],
        "modified": ["file3.md", "file4.yaml"],
        "removed": ["file5.json"],
        "renamed": [{"old": "old_name.txt", "new": "new_name.txt"}, {"old": "old_script.py", "new": "new_script.py"}],
    }


@pytest.fixture
def mock_pr_files() -> List[Dict[str, Any]]:
    """
    Create sample PR files data as would be returned by GitHub API.

    Returns:
        List of file changes from a PR
    """
    return [
        {"filename": "file1.txt", "status": "added", "previous_filename": None},
        {"filename": "file2.py", "status": "added", "previous_filename": None},
        {"filename": "file3.md", "status": "modified", "previous_filename": None},
        {"filename": "file4.yaml", "status": "modified", "previous_filename": None},
        {"filename": "file5.json", "status": "removed", "previous_filename": None},
        {"filename": "new_name.txt", "status": "renamed", "previous_filename": "old_name.txt"},
        {"filename": "new_script.py", "status": "renamed", "previous_filename": "old_script.py"},
    ]
