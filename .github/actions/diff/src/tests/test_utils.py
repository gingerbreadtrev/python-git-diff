"""Tests for utility functions in the GitHub Action."""

from typing import List, TYPE_CHECKING

import pytest

from utils import FilesByStatus, filter_files_by_patterns, filter_paths_with_patterns

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


def test_filter_paths_with_patterns_no_patterns() -> None:
    """
    Test filtering paths with no patterns returns all paths.
    """
    file_paths = ["file1.txt", "file2.py", "dir/file3.md"]
    patterns: List[str] = []

    result = filter_paths_with_patterns(file_paths, patterns)

    assert result == file_paths


def test_filter_paths_with_patterns_all_match() -> None:
    """
    Test filtering paths with wildcard pattern matches everything.
    """
    file_paths = ["file1.txt", "file2.py", "dir/file3.md"]
    patterns = ["**/*"]

    result = filter_paths_with_patterns(file_paths, patterns)

    assert result == file_paths


def test_filter_paths_with_patterns_extension_filter() -> None:
    """
    Test filtering paths by file extension.
    """
    file_paths = ["file1.txt", "file2.py", "dir/file3.md", "dir/file4.txt"]
    patterns = ["**/*.txt"]

    result = filter_paths_with_patterns(file_paths, patterns)

    assert result == ["file1.txt", "dir/file4.txt"]


def test_filter_paths_with_patterns_directory_filter() -> None:
    """
    Test filtering paths by directory.
    """
    file_paths = ["file1.txt", "file2.py", "dir/file3.md", "dir/file4.txt"]
    patterns = ["dir/**"]

    result = filter_paths_with_patterns(file_paths, patterns)

    assert result == ["dir/file3.md", "dir/file4.txt"]


def test_filter_paths_with_patterns_multiple_patterns() -> None:
    """
    Test filtering paths with multiple patterns.
    """
    file_paths = ["file1.txt", "file2.py", "dir/file3.md", "dir/file4.txt"]
    patterns = ["**/*.py", "**/*.md"]

    result = filter_paths_with_patterns(file_paths, patterns)

    assert result == ["file2.py", "dir/file3.md"]


def test_filter_files_by_patterns(mock_files_by_status: FilesByStatus) -> None:
    """
    Test filtering FilesByStatus object by patterns.

    Args:
        mock_files_by_status: Mock FilesByStatus fixture
    """
    patterns = ["**/*.txt", "**/*.py"]

    result = filter_files_by_patterns(mock_files_by_status, patterns)

    # Check that only .txt and .py files were retained
    assert result["added"] == ["file1.txt", "file2.py"]
    assert result["modified"] == []  # No .txt or .py files in modified
    assert result["removed"] == []  # No .txt or .py files in removed

    # Check renamed files - both old and new filenames should be filtered
    assert any(
        item["old"] == "old_name.txt" and item["new"] == "new_name.txt" for item in mock_files_by_status["renamed"]
    )
    assert any(
        item["old"] == "old_script.py" and item["new"] == "new_script.py" for item in mock_files_by_status["renamed"]
    )


def test_filter_files_by_patterns_no_patterns(mock_files_by_status: FilesByStatus) -> None:
    """
    Test filtering FilesByStatus with no patterns returns all files.

    Args:
        mock_files_by_status: Mock FilesByStatus fixture
    """
    patterns: List[str] = []

    result = filter_files_by_patterns(mock_files_by_status, patterns)

    # All files should be included when no patterns are provided
    assert result == mock_files_by_status
