"""Tests for push events in the GitHub Action."""

from typing import Dict, List, Any, Tuple, TYPE_CHECKING
import os
import subprocess
from unittest.mock import call

import pytest

from push_events import (
    get_changed_files_from_git,
    get_push_changed_files,
    parse_git_shas_from_env,
)
from utils import FilesByStatus

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


class TestGetChangedFilesFromGit:
    """Tests for get_changed_files_from_git function."""

    def test_normal_output(self, mocker: "MockerFixture") -> None:
        """
        Test parsing normal git diff output.

        Args:
            mocker: Pytest mocker fixture
        """
        # Sample git diff output
        git_diff_output = """A\tfile1.txt
M\tfile2.py
M\tpath/to/file3.md
D\tfile4.json
R100\told_name.txt\tnew_name.txt
R095\told_script.py\tnew_script.py
A\t.github/workflow.yml
"""
        # Mock subprocess.run to return the sample output
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = git_diff_output
        mock_run.return_value.returncode = 0

        # Call the function under test
        result = get_changed_files_from_git("base-sha", "head-sha")

        # Verify correct git command was called
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "diff", "--name-status", "base-sha...head-sha"]

        # Verify the result contains correctly categorized files
        assert result["A"] == ["file1.txt", ".github/workflow.yml"]
        assert result["M"] == ["file2.py", "path/to/file3.md"]
        assert result["D"] == ["file4.json"]
        assert result["R"] == ["old_name.txt\tnew_name.txt", "old_script.py\tnew_script.py"]

    def test_empty_output(self, mocker: "MockerFixture") -> None:
        """
        Test handling empty git diff output (no changes).

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock subprocess to return empty output
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0

        # Call the function under test
        result = get_changed_files_from_git("base-sha", "head-sha")

        # Verify all categories exist but are empty
        assert result["A"] == []
        assert result["M"] == []
        assert result["D"] == []
        assert result["R"] == []

    def test_custom_repo_path(self, mocker: "MockerFixture") -> None:
        """
        Test specifying a custom repository path.

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock subprocess
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = "A\tfile.txt"
        mock_run.return_value.returncode = 0

        # Call with custom repo path
        custom_path = "/path/to/repo"
        get_changed_files_from_git("base-sha", "head-sha", repo_path=custom_path)

        # Verify the custom path was used
        assert mock_run.call_args[1]["cwd"] == custom_path

    def test_subprocess_error(self, mocker: "MockerFixture") -> None:
        """
        Test handling subprocess errors.

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock subprocess to raise an error
        error = subprocess.CalledProcessError(128, "git diff")
        error.stdout = ""
        error.stderr = "fatal: Not a git repository"
        mock_run = mocker.patch("subprocess.run", side_effect=error)

        # The function should propagate the exception
        with pytest.raises(subprocess.CalledProcessError):
            get_changed_files_from_git("base-sha", "head-sha")


class TestParseGitShasFromEnv:
    """Tests for parse_git_shas_from_env function."""

    def test_normal_environment(self, mocker: "MockerFixture") -> None:
        """
        Test parsing SHAs from normal environment variables.

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock environment variables
        mocker.patch.dict(os.environ, {"GITHUB_BEFORE": "base-sha-12345", "GITHUB_AFTER": "head-sha-67890"})

        # Call the function under test
        base_sha, head_sha = parse_git_shas_from_env()

        # Verify correct SHAs were parsed
        assert base_sha == "base-sha-12345"
        assert head_sha == "head-sha-67890"

    def test_new_branch(self, mocker: "MockerFixture") -> None:
        """
        Test parsing SHAs for a new branch (GITHUB_BEFORE is all zeros).

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock environment variables for new branch scenario
        mocker.patch.dict(
            os.environ, {"GITHUB_BEFORE": "0000000000000000000000000000000000000000", "GITHUB_AFTER": "head-sha-67890"}
        )

        # Mock git rev-parse command for HEAD~1
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = "previous-sha-12345\n"
        mock_run.return_value.returncode = 0

        # Call the function under test
        base_sha, head_sha = parse_git_shas_from_env()

        # Verify the correct commands were run and SHAs returned
        mock_run.assert_called_once_with(["git", "rev-parse", "HEAD~1"], capture_output=True, text=True, check=True)

        assert base_sha == "previous-sha-12345"
        assert head_sha == "head-sha-67890"

    def test_first_commit(self, mocker: "MockerFixture") -> None:
        """
        Test parsing SHAs for the first commit in a repository.

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock environment variables with zeros for GITHUB_BEFORE
        mocker.patch.dict(
            os.environ, {"GITHUB_BEFORE": "0000000000000000000000000000000000000000", "GITHUB_AFTER": "head-sha-67890"}
        )

        # Mock git rev-parse to fail (simulating first commit)
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(
            128, "git rev-parse HEAD~1", stderr="fatal: ambiguous argument 'HEAD~1': unknown revision"
        )

        # Call the function under test
        base_sha, head_sha = parse_git_shas_from_env()

        # For first commit, the function should use the Git empty tree object
        assert base_sha == "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # Git empty tree
        assert head_sha == "head-sha-67890"

    def test_missing_after_sha(self, mocker: "MockerFixture") -> None:
        """
        Test parsing SHAs when GITHUB_AFTER is missing.

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock environment with only GITHUB_BEFORE
        mocker.patch.dict(os.environ, {"GITHUB_BEFORE": "base-sha-12345"}, clear=True)

        # Mock git rev-parse for HEAD
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = "current-head-sha\n"
        mock_run.return_value.returncode = 0

        # Call the function under test
        base_sha, head_sha = parse_git_shas_from_env()

        # Verify correct command was run to get current HEAD
        mock_run.assert_called_once_with(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)

        assert base_sha == "base-sha-12345"
        assert head_sha == "current-head-sha"

    def test_missing_both_shas(self, mocker: "MockerFixture") -> None:
        """
        Test parsing SHAs when both environment variables are missing.

        Args:
            mocker: Pytest mocker fixture
        """
        # Clear environment variables
        mocker.patch.dict(os.environ, {}, clear=True)

        # Mock git rev-parse calls for both SHAs
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = [
            # First call for HEAD~1
            subprocess.CompletedProcess(
                args=["git", "rev-parse", "HEAD~1"], returncode=0, stdout="previous-head-sha\n", stderr=""
            ),
            # Second call for HEAD
            subprocess.CompletedProcess(
                args=["git", "rev-parse", "HEAD"], returncode=0, stdout="current-head-sha\n", stderr=""
            ),
        ]

        # Call the function under test
        with pytest.raises(ValueError, match="Failed to determine"):
            # This should fail since we're missing GITHUB_BEFORE
            parse_git_shas_from_env()

    def test_rev_parse_failure(self, mocker: "MockerFixture") -> None:
        """
        Test handling git command failures when determining HEAD.

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock environment with only GITHUB_BEFORE
        mocker.patch.dict(os.environ, {"GITHUB_BEFORE": "base-sha-12345"}, clear=True)

        # Mock git rev-parse to fail for HEAD
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(
            128, "git rev-parse HEAD", stderr="fatal: not a git repository"
        )

        # Call the function under test - should raise ValueError
        with pytest.raises(ValueError, match="Failed to determine HEAD SHA"):
            parse_git_shas_from_env()


class TestGetPushChangedFiles:
    """Tests for get_push_changed_files function."""

    def test_successful_retrieval(self, mocker: "MockerFixture", capsys: "CaptureFixture[str]") -> None:
        """
        Test successful retrieval of changed files from push event.

        Args:
            mocker: Pytest mocker fixture
            capsys: Pytest capture fixture
        """
        # Mock SHA parsing and git diff
        mocker.patch("src.push_events.parse_git_shas_from_env", return_value=("base-sha", "head-sha"))

        # Sample git diff output with various file types
        git_diff_output = """A\tfile1.txt
A\tfile2.py
M\tfile3.yaml
M\tfile4.md
D\tfile5.json
R100\told_file.txt\tnew_file.txt
"""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = git_diff_output
        mock_run.return_value.returncode = 0

        # Call with filter patterns for .txt and .py files
        result = get_push_changed_files(patterns=["**/*.txt", "**/*.py"])

        # Check console output
        captured = capsys.readouterr()
        assert "Comparing changes between base-sha and head-sha" in captured.out

        # Verify result contains only filtered files
        assert result is not None
        assert result["added"] == ["file1.txt", "file2.py"]  # Both match patterns
        assert result["modified"] == []  # No .txt or .py files in modified
        assert result["removed"] == []  # No .txt or .py files in removed

        # Check renamed .txt files (should match pattern)
        renamed = result["renamed"]
        assert len(renamed) == 1
        assert renamed[0]["old"] == "old_file.txt"
        assert renamed[0]["new"] == "new_file.txt"

    def test_explicit_shas(self, mocker: "MockerFixture") -> None:
        """
        Test using explicitly provided SHAs instead of environment variables.

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock git diff
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = "A\tfile.txt"
        mock_run.return_value.returncode = 0

        # Call with explicit SHAs
        get_push_changed_files(base_sha="explicit-base", head_sha="explicit-head")

        # Verify git command used explicit SHAs
        assert mock_run.call_args[0][0] == ["git", "diff", "--name-status", "explicit-base...explicit-head"]

        # Verify parse_git_shas_from_env wasn't called
        assert not mocker.patch.object("src.push_events", "parse_git_shas_from_env", return_value=None).called

    def test_git_command_error(self, mocker: "MockerFixture", capsys: "CaptureFixture[str]") -> None:
        """
        Test handling git command errors.

        Args:
            mocker: Pytest mocker fixture
            capsys: Pytest capture fixture
        """
        # Mock SHA parsing
        mocker.patch("src.push_events.parse_git_shas_from_env", return_value=("base-sha", "head-sha"))

        # Mock git diff to fail
        error = subprocess.CalledProcessError(128, "git diff")
        error.stdout = ""
        error.stderr = "fatal: Not a git repository"

        mock_run = mocker.patch("subprocess.run", side_effect=error)

        # Call function - should handle the error
        result = get_push_changed_files()

        # Verify error was logged
        captured = capsys.readouterr()
        assert "Error executing Git command" in captured.out
        assert "fatal: Not a git repository" in captured.out

        # Verify function returned None
        assert result is None

    def test_parsing_error(self, mocker: "MockerFixture", capsys: "CaptureFixture[str]") -> None:
        """
        Test handling SHA parsing errors.

        Args:
            mocker: Pytest mocker fixture
            capsys: Pytest capture fixture
        """
        # Mock SHA parsing to fail
        error_msg = "Missing environment variables"
        mocker.patch("src.push_events.parse_git_shas_from_env", side_effect=ValueError(error_msg))

        # Call function - should handle the error
        result = get_push_changed_files()

        # Verify error was logged
        captured = capsys.readouterr()
        assert "Error determining commit SHAs" in captured.out
        assert error_msg in captured.out

        # Verify function returned None
        assert result is None

    def test_general_exception(self, mocker: "MockerFixture", capsys: "CaptureFixture[str]") -> None:
        """
        Test handling unexpected exceptions.

        Args:
            mocker: Pytest mocker fixture
            capsys: Pytest capture fixture
        """
        # Mock an unexpected exception during processing
        unexpected_error = RuntimeError("Unexpected failure")
        mocker.patch("src.push_events.parse_git_shas_from_env", side_effect=unexpected_error)

        # Call function - should handle the error
        result = get_push_changed_files()

        # Verify error was logged
        captured = capsys.readouterr()
        assert "Error processing changed files" in captured.out
        assert "Unexpected failure" in captured.out

        # Verify function returned None
        assert result is None

    def test_custom_repo_path(self, mocker: "MockerFixture") -> None:
        """
        Test using a custom repository path.

        Args:
            mocker: Pytest mocker fixture
        """
        # Mock SHA parsing and git diff
        mocker.patch("src.push_events.parse_git_shas_from_env", return_value=("base-sha", "head-sha"))

        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.stdout = "A\tfile.txt"
        mock_run.return_value.returncode = 0

        # Call with custom repo path
        custom_path = "/custom/repo/path"
        get_push_changed_files(repo_path=custom_path)

        # Verify custom path was passed to git command
        assert mock_run.call_args[1]["cwd"] == custom_path
