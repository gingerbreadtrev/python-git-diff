#!/usr/bin/env python3

import json
import os
import subprocess
from typing import Dict, List, Optional, TypedDict, Any, Set
from pathlib import PurePath

from github_actions import GitHubAction, InputOptions
from pr_events import get_pr_changed_files, ChangedFilesByStatus


class PullRequestOutput(TypedDict):
    """Pull Request output structure for the GitHub Action."""

    added: List[str]
    modified: List[str]
    deleted: List[str]


def get_event_type() -> str:
    """
    Determine if the action is running on a PR or push event.

    Returns:
        String indicating the event type ('pull_request' or 'push')
    """
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    return event_name


def get_push_changed_files(token: str) -> Optional[ChangedFilesByStatus]:
    """
    Get changed files for a push event.

    Args:
        token: GitHub token for authentication

    Returns:
        ChangedFilesByStatus object or None if an error occurred
    """
    # Placeholder for push implementation
    # In a real implementation, you would use git commands to get the diff
    # between GITHUB_BEFORE and GITHUB_AFTER

    # Example implementation placeholder:
    try:
        # For now, just log that we detected a push event
        print("Push event detected - implementation placeholder")
        print(f"GITHUB_BEFORE: {os.environ.get('GITHUB_BEFORE', 'N/A')}")
        print(f"GITHUB_AFTER: {os.environ.get('GITHUB_AFTER', 'N/A')}")

        # Return empty file categories
        # When implementing for real, use git diff to populate these categories
        return {"added": [], "modified": [], "removed": [], "renamed": [], "all": []}
    except Exception as e:
        print(f"Error getting changed files for push event: {str(e)}")
        return None


def filter_changed_files(changed_files: ChangedFilesByStatus, filters: List[str]) -> ChangedFilesByStatus:
    """
    Filter changed files based on glob patterns using PurePath.match_full from Python 3.13+.

    Args:
        changed_files: Files categorized by status
        filters: List of glob patterns to filter files

    Returns:
        ChangedFilesByStatus with only files matching the filters
    """
    if not filters or filters == ["**/*"]:
        # No filtering needed, return original files
        return changed_files

    filtered_files: ChangedFilesByStatus = {"added": [], "modified": [], "removed": [], "renamed": [], "all": []}

    # Filter each category
    for category in ["added", "modified", "removed", "all"]:
        for file_path in changed_files[category]:
            path = PurePath(file_path)
            if any(path.full_match(pattern) for pattern in filters):
                filtered_files[category].append(file_path)

    # Filter renamed files
    for renamed_file in changed_files["renamed"]:
        # Check if either old or new path matches filters
        old_path = PurePath(renamed_file["old"])
        new_path = PurePath(renamed_file["new"])

        if any(old_path.full_match(pattern) for pattern in filters):
            filtered_files[category].append(old_path)

        if any(new_path.full_match(pattern) for pattern in filters):
            filtered_files[category].append(new_path)

    return filtered_files


def main() -> None:
    """
    Main entry point for the GitHub Action.
    Retrieves changed files in a pull request or push event and sets them as outputs.
    """
    action = GitHubAction()

    # Get inputs
    token = action.get_input("token", InputOptions(required=True))
    action.info("GitHub token received")

    # Get filters if provided
    filters = action.get_multiline_input("filters", InputOptions(required=False))
    if not filters:
        filters = ["**/*"]
    action.info(f"Using filters: {filters}")

    # Determine event type and get changed files
    event_type = get_event_type()
    action.info(f"Detected event type: {event_type}")

    # Get all changed files (unfiltered)
    if event_type == "pull_request":
        # Get changed files for PR event
        action.info("Retrieving changed files from pull request...")
        all_changed_files = get_pr_changed_files(token=token)
    elif event_type == "push":
        # Get changed files for push event
        action.info("Retrieving changed files from push event...")
        all_changed_files = get_push_changed_files(token=token)
    else:
        action.error(f"Unsupported event type: {event_type}")
        return

    if not all_changed_files:
        action.error("Failed to retrieve changed files")
        return

    # Process renamed files in all changed files (add to added and deleted categories)
    process_renamed_files(all_changed_files)

    # Filter changed files based on provided filters
    filtered_changed_files = filter_changed_files(all_changed_files, filters)

    # Create summary lists using all changed files (for visibility)
    create_summary_lists(action, all_changed_files, filtered_changed_files)

    # Set outputs using only the filtered files
    set_outputs(action, filtered_changed_files)


def process_renamed_files(changed_files: ChangedFilesByStatus) -> None:
    """
    Process renamed files by adding their new paths to 'added' and old paths to 'deleted'.

    Args:
        changed_files: Files categorized by status
    """
    # Add renamed files to the added and deleted categories
    for renamed_file in changed_files["renamed"]:
        # Add the new path to added files
        changed_files["added"].append(renamed_file["new"])
        # Add the old path to deleted files
        changed_files["removed"].append(renamed_file["old"])


def create_summary_lists(
    action: GitHubAction, all_files: ChangedFilesByStatus, filtered_files: ChangedFilesByStatus
) -> None:
    """
    Create summary lists for the GitHub Action UI.

    Args:
        action: The GitHub Action instance
        all_files: All files that changed (unfiltered)
        filtered_files: Files that match the filter criteria
    """
    # Add title to the summary
    action.summary.add_heading("Changed Files Summary", 2)

    # First, summarize filter results
    total_changed = len(filtered_files["added"]) + len(filtered_files["modified"]) + len(filtered_files["removed"])

    action.summary.add_raw(f"Total files changed: {total_changed}")
    action.summary.add_eol().add_eol()

    # Categories to display in the summary
    categories = [("Added Files", "added"), ("Modified Files", "modified"), ("Deleted Files", "removed")]

    # Create lists for each category
    for title, category in categories:
        files = filtered_files[category]
        if not files:
            continue

        # Add section heading
        action.summary.add_heading(title, 3)

        # Create a list with all files in this category
        file_list = []
        for file in files:
            file_list.append(file)

        # Add the list to the summary
        action.summary.add_list(file_list)

    # Try to write the summary
    try:
        action.summary.write()
        action.info("Summary created successfully")
    except Exception as e:
        action.info(f"Could not write summary: {e}")
        action.info("This is expected if running locally or in a testing environment")


def set_outputs(action: GitHubAction, filtered_files: ChangedFilesByStatus) -> None:
    """
    Set GitHub Action outputs based on the filtered changed files.

    Args:
        action: The GitHub Action instance
        filtered_files: Files that match the filter criteria
    """
    action.info("Setting action outputs...")

    # Create simplified output structure - even if there are no changes, include empty arrays
    output: PullRequestOutput = {
        "added": filtered_files["added"],
        "modified": filtered_files["modified"],
        "deleted": filtered_files["removed"],
    }

    # Set any-changed boolean output - only true if filtered files have changes
    has_changes = (
        len(filtered_files["added"]) > 0 or len(filtered_files["modified"]) > 0 or len(filtered_files["removed"]) > 0
    )
    action.set_output("any-changed", str(has_changes).lower())
    action.info(f"Output 'any-changed' set to: {has_changes}")

    # Set the single JSON output with all file categories
    action.set_output("changed-files", json.dumps(output))
    action.info("Files output set successfully")


if __name__ == "__main__":
    main()
