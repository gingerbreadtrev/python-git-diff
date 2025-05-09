"""Tests for the main module of the GitHub Action."""

from typing import Dict, List, Any, Optional, TYPE_CHECKING
import json
import os

import pytest

from main import create_summary_lists, get_event_type, main, set_action_outputs
from utils import FilesByStatus

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


def test_get_event_type_pull_request(temp_github_env: Dict[str, str]) -> None:
    """
    Test detecting pull request event type.

    Args:
        temp_github_env: GitHub environment variables fixture
    """
    # Environment is already set up as pull_request in the fixture
    event_type = get_event_type()

    assert event_type == "pull_request"


def test_get_event_type_push(temp_github_env: Dict[str, str], monkeypatch: "MonkeyPatch") -> None:
    """
    Test detecting push event type.

    Args:
        temp_github_env: GitHub environment variables fixture
        monkeypatch: Pytest monkeypatch fixture
    """
    # Change event type to push
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")

    event_type = get_event_type()

    assert event_type == "push"


def test_set_action_outputs(mocker: "MockerFixture", mock_files_by_status: FilesByStatus) -> None:
    """
    Test setting action outputs based on changed files.

    Args:
        mocker: Pytest mocker fixture
        mock_files_by_status: Mock FilesByStatus fixture
    """
    # Mock GitHub Action instance
    mock_action = mocker.Mock()

    # Call the function
    set_action_outputs(mock_action, mock_files_by_status)

    # Verify outputs were set
    expected_output = {
        "added": ["file1.txt", "file2.py"],
        "modified": ["file3.md", "file4.yaml"],
        "deleted": ["file5.json"],
    }

    # Verify the any-changed output is set to "true"
    mock_action.set_output.assert_any_call("any-changed", "true")

    # Verify the changed-files output is set with the expected JSON
    mock_action.set_output.assert_any_call("changed-files", json.dumps(expected_output))


def test_set_action_outputs_no_changes(mocker: "MockerFixture") -> None:
    """
    Test setting action outputs when there are no changes.

    Args:
        mocker: Pytest mocker fixture
    """
    # Mock GitHub Action instance
    mock_action = mocker.Mock()

    # Empty FilesByStatus
    empty_files: FilesByStatus = {"added": [], "modified": [], "removed": [], "renamed": []}

    # Call the function
    set_action_outputs(mock_action, empty_files)

    # Verify the any-changed output is set to "false"
    mock_action.set_output.assert_any_call("any-changed", "false")


def test_create_summary_lists(mocker: "MockerFixture", mock_files_by_status: FilesByStatus) -> None:
    """
    Test creating summary lists for GitHub Actions UI.

    Args:
        mocker: Pytest mocker fixture
        mock_files_by_status: Mock FilesByStatus fixture
    """
    # Mock GitHub Action and summary instance
    mock_action = mocker.Mock()
    mock_summary = mocker.Mock()
    mock_action.summary = mock_summary

    # Call the function
    create_summary_lists(mock_action, mock_files_by_status)

    # Verify summary methods were called
    mock_summary.add_heading.assert_any_call("Changed Files Summary", 2)
    mock_summary.add_heading.assert_any_call("Added Files", 3)
    mock_summary.add_heading.assert_any_call("Modified Files", 3)
    mock_summary.add_heading.assert_any_call("Deleted Files", 3)

    # Verify lists were added
    mock_summary.add_list.assert_any_call(["file1.txt", "file2.py"])
    mock_summary.add_list.assert_any_call(["file3.md", "file4.yaml"])
    mock_summary.add_list.assert_any_call(["file5.json"])

    # Verify write was called
    mock_summary.write.assert_called_once()


def test_create_summary_lists_exception(
    mocker: "MockerFixture", mock_files_by_status: FilesByStatus, capsys: "CaptureFixture[str]"
) -> None:
    """
    Test handling exceptions when writing summary.

    Args:
        mocker: Pytest mocker fixture
        mock_files_by_status: Mock FilesByStatus fixture
        capsys: Pytest capture fixture
    """
    # Mock GitHub Action and summary instance
    mock_action = mocker.Mock()
    mock_summary = mocker.Mock()
    mock_action.summary = mock_summary

    # Make summary.write throw an exception
    mock_summary.write.side_effect = Exception("Failed to write summary")

    # Call the function
    create_summary_lists(mock_action, mock_files_by_status)

    # Verify info methods were called with appropriate messages
    mock_action.info.assert_any_call("Could not write summary: Failed to write summary")
    mock_action.info.assert_any_call("This is expected if running locally or in a testing environment")


def test_main_pr_event(mocker: "MockerFixture", pull_request_event: Dict[str, Any]) -> None:
    """
    Test main function with pull request event.

    Args:
        mocker: Pytest mocker fixture
        pull_request_event: Pull request event fixture
    """
    # Mock GitHubAction class and instance
    mock_action_class = mocker.patch("src.main.GitHubAction")
    mock_action = mock_action_class.return_value

    # Mock inputs
    mock_action.get_input.return_value = "fake-token"
    mock_action.get_multiline_input.return_value = ["**/*.txt", "**/*.py"]

    # Mock PR event detection
    mocker.patch("src.main.get_event_type", return_value="pull_request")

    # Mock PR file retrieval
    mock_files: FilesByStatus = {
        "added": ["file1.txt", "file2.py"],
        "modified": [],
        "removed": ["file3.txt"],
        "renamed": [],
    }
    mocker.patch("src.main.get_pr_changed_files", return_value=mock_files)

    # Mock summary and outputs functions
    mock_create_summary = mocker.patch("src.main.create_summary_lists")
    mock_set_outputs = mocker.patch("src.main.set_action_outputs")

    # Run main function
    main()

    # Verify function calls
    mock_action.get_multiline_input.assert_called_with("filters", mocker.ANY)
    mock_action.get_input.assert_any_call("token", mocker.ANY)

    # Verify PR event handling
    mocker.patch("src.main.get_pr_changed_files").assert_called_once()

    # Verify summary and outputs were set
    mock_create_summary.assert_called_once_with(mock_action, mock_files)
    mock_set_outputs.assert_called_once_with(mock_action, mock_files)


def test_main_push_event(mocker: "MockerFixture", push_event: Dict[str, Any]) -> None:
    """
    Test main function with push event.

    Args:
        mocker: Pytest mocker fixture
        push_event: Push event fixture
    """
    # Mock GitHubAction class and instance
    mock_action_class = mocker.patch("src.main.GitHubAction")
    mock_action = mock_action_class.return_value

    # Mock inputs
    mock_action.get_input.side_effect = lambda name, options: {
        "token": "fake-token",
        "base-sha": "base-sha-123",
        "head-sha": "head-sha-456",
    }.get(name, "")
    mock_action.get_multiline_input.return_value = ["**/*.yaml"]

    # Mock push event detection
    mocker.patch("src.main.get_event_type", return_value="push")

    # Mock push file retrieval
    mock_files: FilesByStatus = {"added": ["file1.yaml"], "modified": ["file2.yaml"], "removed": [], "renamed": []}
    mocker.patch("src.main.get_push_changed_files", return_value=mock_files)

    # Mock summary and outputs functions
    mock_create_summary = mocker.patch("src.main.create_summary_lists")
    mock_set_outputs = mocker.patch("src.main.set_action_outputs")

    # Run main function
    main()

    # Verify push event handling
    mocker.patch("src.main.get_push_changed_files").assert_called_once()

    # Verify summary and outputs were set
    mock_create_summary.assert_called_once_with(mock_action, mock_files)
    mock_set_outputs.assert_called_once_with(mock_action, mock_files)


def test_main_unsupported_event(mocker: "MockerFixture") -> None:
    """
    Test main function with unsupported event type.

    Args:
        mocker: Pytest mocker fixture
    """
    # Mock GitHubAction class and instance
    mock_action_class = mocker.patch("src.main.GitHubAction")
    mock_action = mock_action_class.return_value

    # Mock event type detection
    mocker.patch("src.main.get_event_type", return_value="workflow_dispatch")

    # Run main function
    main()

    # Verify error was reported
    mock_action.error.assert_called_once_with("Unsupported event type: workflow_dispatch")


def test_main_file_retrieval_failure(mocker: "MockerFixture") -> None:
    """
    Test main function when file retrieval fails.

    Args:
        mocker: Pytest mocker fixture
    """
    # Mock GitHubAction class and instance
    mock_action_class = mocker.patch("src.main.GitHubAction")
    mock_action = mock_action_class.return_value

    # Mock pull request event
    mocker.patch("src.main.get_event_type", return_value="pull_request")

    # Mock file retrieval to fail
    mocker.patch("src.main.get_pr_changed_files", return_value=None)

    # Run main function
    main()

    # Verify error was reported
    mock_action.error.assert_called_once_with("Failed to retrieve changed files")
