#!/usr/bin/env python3

import json
import os

# import subprocess
from typing import List, Optional, TypedDict

from github_actions import GitHubAction, InputOptions
from pr_events import get_pr_changed_files, FilesByStatus


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


def get_push_changed_files(token: str) -> Optional[FilesByStatus]:
    """
    Get changed files for a push event.

    Args:
        token: GitHub token for authentication

    Returns:
        FilesByStatus object or None if an error occurred
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

    if event_type == "pull_request":
        # Get changed files for PR event
        action.info("Retrieving changed files from pull request...")
        changed_files = get_pr_changed_files(token=token)
    elif event_type == "push":
        # Get changed files for push event
        action.info("Retrieving changed files from push event...")
        changed_files = get_push_changed_files(token=token)
    else:
        action.error(f"Unsupported event type: {event_type}")
        return

    if not changed_files:
        action.error("Failed to retrieve changed files")
        return

    # Process renamed files (add to added and deleted categories)
    process_renamed_files(changed_files)

    # Create summary lists
    create_summary_lists(action, changed_files)

    # Set simplified outputs for GitHub Actions
    set_simplified_outputs(action, changed_files)


def process_renamed_files(changed_files: FilesByStatus) -> None:
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


def create_summary_lists(action: GitHubAction, changed_files: FilesByStatus) -> None:
    """
    Create summary lists for the GitHub Action UI.

    Args:
        action: The GitHub Action instance
        changed_files: Files categorized by status
    """
    # Add title to the summary
    action.summary.add_heading("Changed Files Summary", 2)

    # Categories to display in the summary
    categories = [("Added Files", "added"), ("Modified Files", "modified"), ("Deleted Files", "removed")]

    # Create lists for each category
    for title, category in categories:
        files = changed_files[category]
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


def set_simplified_outputs(action: GitHubAction, changed_files: FilesByStatus) -> None:
    """
    Set simplified GitHub Action outputs based on the changed files.

    Args:
        action: The GitHub Action instance
        changed_files: Files categorized by status
    """
    action.info("Setting action outputs...")

    # Create simplified output structure
    output: PullRequestOutput = {
        "added": changed_files["added"],
        "modified": changed_files["modified"],
        "deleted": changed_files["removed"],
    }

    # Set any-changed boolean output
    has_changes = (
        len(changed_files["added"]) > 0 or len(changed_files["modified"]) > 0 or len(changed_files["removed"]) > 0
    )
    action.set_output("any-changed", str(has_changes).lower())

    # Set the single JSON output with all file categories
    action.set_output("files", json.dumps(output))

    action.info("Outputs set successfully")


if __name__ == "__main__":
    main()
