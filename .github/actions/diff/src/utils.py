#!/usr/bin/env python3
"""Shared utilities for the diff action."""

from pathlib import PurePath
from typing import TypedDict


class FilesByStatus(TypedDict):
    """Type definition for files organized by status."""

    added: list[str]
    modified: list[str]
    removed: list[str]
    renamed: list[dict[str, str]]


class OutputFormat(TypedDict):
    """Output format for GitHub Actions."""

    added: list[str]
    modified: list[str]
    deleted: list[str]


def filter_paths_with_patterns(file_paths: list[str], patterns: list[str]) -> list[str]:
    """
    Filter a list of file paths using glob patterns with pathlib.

    Args:
        file_paths: list of file paths to filter
        patterns: list of glob patterns to match against

    Returns:
        Filtered list of file paths that match at least one pattern
    """
    if not patterns or patterns == ["**/*"]:
        return file_paths

    filtered_paths = []
    for path_str in file_paths:
        path = PurePath(path_str)

        # Check if the path matches any of the patterns
        matched = any(path.full_match(pattern) for pattern in patterns)
        if matched:
            filtered_paths.append(path_str)

    return filtered_paths


def filter_files_by_patterns(files: FilesByStatus, patterns: list[str]) -> FilesByStatus:
    """
    Filter changed files by glob patterns using pathlib.

    Args:
        files: FilesByStatus dictionary with files categorized by status
        patterns: list of glob patterns to filter by

    Returns:
        Filtered FilesByStatus dictionary
    """

    filtered: FilesByStatus = {
        "added": filter_paths_with_patterns(files["added"], patterns),
        "modified": filter_paths_with_patterns(files["modified"], patterns),
        "removed": filter_paths_with_patterns(files["removed"], patterns),
    }

    # Filter renamed files
    for renamed_item in files["renamed"]:
        if renamed_item["old"] not in filtered["removed"]:
            filtered["removed"].extend(filter_paths_with_patterns([renamed_item["old"]], patterns))

        if renamed_item["new"] not in filtered["added"]:
            filtered["added"].extend(filter_paths_with_patterns([renamed_item["new"]], patterns))

    return filtered
