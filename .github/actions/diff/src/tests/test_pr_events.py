"""Tests for pull request events in the GitHub Action."""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
import json
import os
from pathlib import Path

import pytest

from pr_events import (
    categorize_files,
    get_changed_files,
    get_pr_changed_files,
    get_pr_number_from_event,
)
from utils import FilesByStatus

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


def test_get_pr_number_from_event(pull_request_event: Dict[str, Any]) -> None:
    """
    Test extracting PR number from event context.

    Args:
        pull_request_event: Pull request event fixture
    """
    pr_number = get_pr_number_from_event()

    assert pr_number == 123


def test_get_pr_number_from_event_no_event_path(monkeypatch: "MonkeyPatch") -> None:
    """
    Test getting PR number when GITHUB_EVENT_PATH is not set.

    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    # Remove GITHUB_EVENT_PATH
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    pr_number = get_pr_number_from_event()

    assert pr_number is None


def test_get_pr_number_from_event_no_pr(temp_github_env: Dict[str, str], tmp_path: Path) -> None:
    """
    Test getting PR number from an event that's not a PR.

    Args:
        temp_github_env: GitHub environment variables fixture
        tmp_path: Temporary path fixture
    """
    # Create event file without PR info
    event_path = Path(temp_github_env["GITHUB_EVENT_PATH"])
    with open(event_path, "w", encoding="utf-8") as f:
        json.dump({"push": {"ref": "refs/heads/main"}}, f)

    pr_number = get_pr_number_from_event()

    assert pr_number is None


def test_categorize_files(mock_pr_files: List[Dict[str, Any]]) -> None:
    """
    Test categorizing files by status from PR data.

    Args:
        mock_pr_files: Sample PR files fixture
    """
    categorized = categorize_files(mock_pr_files)

    assert categorized["added"] == ["file1.txt", "file2.py"]
    assert categorized["modified"] == ["file3.md", "file4.yaml"]
    assert categorized["removed"] == ["file5.json"]

    # Check renamed files
    assert len(categorized["renamed"]) == 2
    assert {"old": "old_name.txt", "new": "new_name.txt"} in categorized["renamed"]
    assert {"old": "old_script.py", "new": "new_script.py"} in categorized["renamed"]


def test_get_changed_files(mocker: "MockerFixture", mock_pr_files: List[Dict[str, Any]]) -> None:
    """
    Test fetching changed files from PR using GitHub CLI.

    Args:
        mocker: Pytest mock fixture
        mock_pr_files: Sample PR files data
    """
    # Mock subprocess.run to return PR files data
    mock_subprocess = mocker.patch("subprocess.run")
    mock_subprocess.return_value.stdout = json.dumps(mock_pr_files)
    mock_subprocess.return_value.returncode = 0

    # Mock environment variable
    mocker.patch.dict(os.environ, {"GITHUB_REPOSITORY": "user/repo"})

    result = get_changed_files(pr_number=123, token="fake-token")

    # Verify the subprocess call
    mock_subprocess.assert_called_once()
    assert mock_subprocess.call_args[0][0] == ["gh", "api", "repos/user/repo/pulls/123/files", "--paginate"]
    # Check environment variables passed to subprocess
    assert mock_subprocess.call_args[1]["env"]["GH_TOKEN"] == "fake-token"

    # Verify result
    assert result == mock_pr_files


def test_get_pr_changed_files_success(
    mocker: "MockerFixture",
    mock_pr_files: List[Dict[str, Any]],
    pull_request_event: Dict[str, Any],
    capsys: "CaptureFixture[str]",
) -> None:
    """
    Test getting and categorizing changed files from PR - success case.

    Args:
        mocker: Pytest mock fixture
        mock_pr_files: Sample PR files data
        pull_request_event: Pull request event fixture
        capsys: Pytest capture fixture
    """
    # Mock PR number extraction and file retrieval
    mocker.patch("src.pr_events.get_pr_number_from_event", return_value=123)
    mocker.patch("src.pr_events.get_changed_files", return_value=mock_pr_files)

    result = get_pr_changed_files(token="fake-token", patterns=["**/*.txt", "**/*.py"])

    # Check console output
    captured = capsys.readouterr()
    assert "Retrieved 7 changed files from PR #123" in captured.out

    # Verify result contains only .txt and .py files
    assert result is not None
    assert result["added"] == ["file1.txt", "file2.py"]
    assert result["modified"] == []
    assert result["removed"] == []
    # Verify renamed files with txt and py extensions
    renamed_files = result["renamed"]
    assert any(item["old"] == "old_name.txt" and item["new"] == "new_name.txt" for item in renamed_files)
    assert any(item["old"] == "old_script.py" and item["new"] == "new_script.py" for item in renamed_files)


def test_get_pr_changed_files_no_pr_number(mocker: "MockerFixture", capsys: "CaptureFixture[str]") -> None:
    """
    Test getting changed files when PR number is unavailable.

    Args:
        mocker: Pytest mock fixture
        capsys: Pytest capture fixture
    """
    # Mock PR number extraction to return None
    mocker.patch("src.pr_events.get_pr_number_from_event", return_value=None)

    result = get_pr_changed_files(token="fake-token")

    # Check console output
    captured = capsys.readouterr()
    assert "Error: Unable to determine PR number" in captured.out

    # Verify no result
    assert result is None


def test_get_pr_changed_files_cli_error(mocker: "MockerFixture", capsys: "CaptureFixture[str]") -> None:
    """
    Test handling CLI errors when getting PR files.

    Args:
        mocker: Pytest mock fixture
        capsys: Pytest capture fixture
    """
    import subprocess

    # Mock PR number extraction to succeed
    mocker.patch("src.pr_events.get_pr_number_from_event", return_value=123)

    # Mock get_changed_files to raise subprocess error
    error = subprocess.CalledProcessError(1, "gh api")
    error.stdout = "Error output"
    error.stderr = "Error: authentication failed"
    mocker.patch("src.pr_events.get_changed_files", side_effect=error)

    result = get_pr_changed_files(token="fake-token")

    # Check console output
    captured = capsys.readouterr()
    assert "Error executing GitHub CLI" in captured.out
    assert "Error: authentication failed" in captured.out

    # Verify no result
    assert result is None
