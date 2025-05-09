#!/usr/bin/env python3
import json
import os
import subprocess
from typing import TypedDict, cast


class FileChange(TypedDict):
    """Type definition for a file change in a PR."""

    filename: str
    status: str
    previous_filename: str | None


class FilesByStatus(TypedDict):
    """Type definition for files organized by status."""

    added: list[str]
    modified: list[str]
    removed: list[str]
    renamed: list[dict[str, str]]
    all: list[str]


def get_pr_number_from_event() -> int | None:
    """
    Get the PR number from the GitHub event context.

    Returns:
        The PR number if available, None otherwise.
    """
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return None

    try:
        with open(event_path, "r", encoding="utf-8") as f:
            event_data = json.load(f)
            pull_request = event_data.get("pull_request", {})
            return pull_request.get("number")
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def get_changed_files(pr_number: int, token: str | None = None) -> list[FileChange]:
    """
    Get changed files from a pull request using GitHub CLI.

    Args:
        pr_number: The pull request number
        token: GitHub token for authentication (optional)

    Returns:
        list of file changes with their status information

    Raises:
        subprocess.CalledProcessError: If the GitHub CLI command fails
    """
    env = os.environ.copy()
    if token:
        env["GH_TOKEN"] = token

    # Use the gh api command to get files from a PR (handles pagination)
    cmd = ["gh", "api", f"repos/{os.environ.get('GITHUB_REPOSITORY', '')}/pulls/{pr_number}/files", "--paginate"]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)

    # Parse the JSON response
    return cast(list[FileChange], json.loads(result.stdout))


def categorize_files(files: list[FileChange]) -> FilesByStatus:
    """
    Categorize files by their status.

    Args:
        files: list of file changes from GitHub API

    Returns:
        Dictionary with files categorized by status
    """
    categories: FilesByStatus = {"added": [], "modified": [], "removed": [], "renamed": [], "all": []}

    for file in files:
        filename = file["filename"]
        status = file["status"]

        # Add to the appropriate category
        if status == "added":
            categories["added"].append(filename)
        elif status == "modified":
            categories["modified"].append(filename)
        elif status == "removed":
            categories["removed"].append(filename)
        elif status == "renamed":
            previous_filename = file.get("previous_filename", "")
            if previous_filename:
                categories["renamed"].append({"old": previous_filename, "new": filename})

        # Add to the "all" category (only the current filename)
        categories["all"].append(filename)

    return categories


def get_pr_changed_files(token: str | None = None, pr_number: int | None = None) -> FilesByStatus | None:
    """
    Get and categorize changed files from the current pull request.

    Args:
        token: GitHub token for authentication (optional)
        pr_number: Optional PR number to override the one from context

    Returns:
        Dictionary with files categorized by status or None on error
    """
    try:
        # Get PR number either from input or environment
        pr_num = pr_number or get_pr_number_from_event()
        if not pr_num:
            print("Error: Unable to determine PR number")
            return None

        # Get changed files using GitHub API
        files = get_changed_files(pr_num, token)
        print(f"Retrieved {len(files)} changed files from PR #{pr_num}")

        # Categorize files by status
        return categorize_files(files)

    except subprocess.CalledProcessError as e:
        print(f"Error executing GitHub CLI: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return None
    except Exception as e:
        print(f"Error processing changed files: {str(e)}")
        import traceback

        print(traceback.format_exc())
        return None
