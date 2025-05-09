#!/usr/bin/env python3
"""Push event functionality for detecting changed files."""

import os
import subprocess

from utils import FilesByStatus, filter_files_by_patterns


def get_changed_files_from_git(base_sha: str, head_sha: str, repo_path: str | None = None) -> dict[str, list[str]]:
    """
    Get changed files between two Git commits using git diff.

    Args:
        base_sha: Base commit SHA
        head_sha: Head commit SHA
        repo_path: Path to the Git repository (default: current directory)

    Returns:
        dictionary with files categorized by change type (A: added, M: modified, D: deleted, R: renamed)

    Raises:
        subprocess.CalledProcessError: If the git command fails
    """
    # Default to current directory if no repo path provided
    if not repo_path:
        repo_path = os.getcwd()

    # Execute git command to get name-status diff
    cmd = ["git", "diff", "--name-status", f"{base_sha}...{head_sha}"]

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, check=True)

    # Parse the output and categorize files
    changes: dict[str, list[str]] = {
        "A": [],  # Added
        "M": [],  # Modified
        "D": [],  # Deleted
        "R": [],  # Renamed
    }

    for line in result.stdout.splitlines():
        if not line.strip():
            continue

        parts = line.split("\t")
        status = parts[0]

        # Handle regular changes (added, modified, deleted)
        if status.startswith("A"):
            changes["A"].append(parts[1])
        elif status.startswith("M"):
            changes["M"].append(parts[1])
        elif status.startswith("D"):
            changes["D"].append(parts[1])
        elif status.startswith("R"):
            # For renamed files, the format is R{score}\t{old_path}\t{new_path}
            changes["R"].append(f"{parts[1]}\t{parts[2]}")

    return changes


def parse_git_shas_from_env() -> tuple[str, str]:
    """
    Parse base and head SHAs from GitHub environment variables.

    For push events, GITHUB_BEFORE contains the base SHA and
    GITHUB_AFTER contains the head SHA.

    Returns:
        tuple containing (base_sha, head_sha)

    Raises:
        ValueError: If required environment variables are not found
    """
    base_sha = os.environ.get("GITHUB_BEFORE", "")
    head_sha = os.environ.get("GITHUB_AFTER", "")

    if not base_sha or base_sha == "0000000000000000000000000000000000000000":
        # For the first push to a new branch, GITHUB_BEFORE will be all zeros
        # In this case, we need to find the common ancestor or use HEAD~1
        try:
            result = subprocess.run(["git", "rev-parse", "HEAD~1"], capture_output=True, text=True, check=True)
            base_sha = result.stdout.strip()
        except subprocess.CalledProcessError:
            # If this is the first commit, there is no previous commit
            # We'll use a special Git empty tree object as the base
            base_sha = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # Git empty tree

    if not head_sha:
        # If GITHUB_AFTER is not available, use the current HEAD
        try:
            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
            head_sha = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to determine HEAD SHA: {e}") from e

    return (base_sha, head_sha)


def get_push_changed_files(
    base_sha: str | None = None,
    head_sha: str | None = None,
    repo_path: str | None = None,
    patterns: list[str] | None = None,
) -> FilesByStatus | None:
    """
    Get and categorize changed files from a push event.

    Args:
        base_sha: Optional base SHA override (uses GITHUB_BEFORE if not provided)
        head_sha: Optional head SHA override (uses GITHUB_AFTER if not provided)
        repo_path: Path to the Git repository (default: current directory)
        patterns: list of glob patterns to filter files by

    Returns:
        FilesByStatus dictionary with files categorized by status or None on error

    Raises:
        subprocess.CalledProcessError: If Git commands fail
        ValueError: If required environment variables are missing
    """
    try:
        # If SHAs aren't explicitly provided, get them from environment
        if not base_sha or not head_sha:
            parsed_base_sha, parsed_head_sha = parse_git_shas_from_env()
            base_sha = base_sha or parsed_base_sha
            head_sha = head_sha or parsed_head_sha

        print(f"Comparing changes between {base_sha} and {head_sha}")

        # Get changed files from git
        changes = get_changed_files_from_git(base_sha, head_sha, repo_path)

        # Convert to FilesByStatus format
        file_changes: FilesByStatus = {
            "added": changes["A"],
            "modified": changes["M"],
            "removed": changes["D"],
            "renamed": [],
        }

        # Process renamed files
        for renamed_path in changes["R"]:
            old_path, new_path = renamed_path.split("\t")
            file_changes["renamed"].append({"old": old_path, "new": new_path})

        return filter_files_by_patterns(file_changes, patterns)

    except subprocess.CalledProcessError as e:
        print(f"Error executing Git command: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return None
    except ValueError as e:
        print(f"Error determining commit SHAs: {e}")
        return None
    except Exception as e:
        print(f"Error processing changed files: {str(e)}")
        import traceback

        print(traceback.format_exc())
        return None
