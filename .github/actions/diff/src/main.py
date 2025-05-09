#!/usr/bin/env python3
"""
Main driver for the changed files GitHub Action.
Detects and reports files changed in either push or pull request events.
"""

import json
import os

from github_actions import GitHubAction, InputOptions
from pr_events import get_pr_changed_files
from push_events import get_push_changed_files
from utils import FilesByStatus, OutputFormat


def get_event_type() -> str:
    """
    Determine if the action is running on a PR or push event.

    Returns:
        String indicating the event type ('pull_request' or 'push')
    """
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    return event_name


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

        # Add the list to the summary
        action.summary.add_list(files)

    # Try to write the summary
    try:
        action.summary.write()
        action.info("Summary created successfully")
    except Exception as e:
        action.info(f"Could not write summary: {e}")
        action.info("This is expected if running locally or in a testing environment")


def set_action_outputs(action: GitHubAction, changed_files: FilesByStatus) -> None:
    """
    Set GitHub Action outputs based on the changed files.

    Args:
        action: The GitHub Action instance
        changed_files: Files categorized by status
    """
    action.info("Setting action outputs...")

    # Create output structure
    output: OutputFormat = {
        "added": changed_files["added"],
        "modified": changed_files["modified"],
        "deleted": changed_files["removed"],
    }

    # Set any-changed boolean output
    has_changes = (
        len(changed_files["added"]) > 0 or len(changed_files["modified"]) > 0 or len(changed_files["removed"]) > 0
    )
    action.set_output("any-changed", str(has_changes).lower())

    # Set the JSON output with all file categories
    action.set_output("changed-files", json.dumps(output))

    action.info("Outputs set successfully")


def main() -> None:
    """
    Main entry point for the GitHub Action.
    Retrieves changed files in a pull request or push event and sets them as outputs.
    """
    action = GitHubAction()

    # Get inputs
    token = action.get_input("token", InputOptions(required=False))
    action.info("GitHub token received")

    # Get filters if provided
    filters = action.get_multiline_input("filters", InputOptions(required=False))
    if not filters:
        filters = ["**/*"]
    action.info(f"Using filters: {filters}")

    # Get optional base and head SHAs
    base_sha = action.get_input("base-sha", InputOptions(required=False))
    head_sha = action.get_input("head-sha", InputOptions(required=False))

    if base_sha:
        action.info(f"Using provided base SHA: {base_sha}")
    if head_sha:
        action.info(f"Using provided head SHA: {head_sha}")

    # Determine event type and get changed files
    event_type = get_event_type()
    action.info(f"Detected event type: {event_type}")

    changed_files: FilesByStatus | None = None

    if event_type == "pull_request" or event_type == "pull_request_target":
        # Get changed files for PR event
        action.info("Retrieving changed files from pull request...")
        changed_files = get_pr_changed_files(token=token, patterns=filters)
    elif event_type == "push":
        # Get changed files for push event
        action.info("Retrieving changed files from push event...")
        changed_files = get_push_changed_files(base_sha=base_sha, head_sha=head_sha, patterns=filters)
    else:
        action.error(f"Unsupported event type: {event_type}")
        return

    if not changed_files:
        action.error("Failed to retrieve changed files")
        return

    # Create summary lists
    create_summary_lists(action, changed_files)

    # Set outputs for GitHub Actions
    set_action_outputs(action, changed_files)


if __name__ == "__main__":
    main()
