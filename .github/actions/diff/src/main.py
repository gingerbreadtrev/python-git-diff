#!/usr/bin/env python3

from github_actions import GitHubAction, InputOptions


def main() -> None:
    action = GitHubAction()

    token = action.get_input("token", InputOptions(required=True))
    action.info(f"got token: {token}")

    filters = action.get_multiline_input("filters", InputOptions(required=False))
    if not filters:
        filters = ["**/*"]
    action.info(f"filters: {filters}")

    base_sha = action.get_input("base-sha", InputOptions(required=False))
    if base_sha:
        action.info(f"Base SHA: {base_sha}")
    else:
        action.info("No base SHA provided, will use default comparison")

    head_sha = action.get_input("head-sha", InputOptions(required=False))
    if head_sha:
        action.info(f"Head SHA: {head_sha}")
    else:
        action.info("No head SHA provided, will use default comparison")

    changed_files = {
        "added": ["file1.yml", "file2.py"],
        "modified": ["README.md", "src/main.py"],
        "deleted": ["old_file.txt"],
        "renamed": ["old_name.js → new_name.js"],
        "all": ["file1.yml", "file2.py", "README.md", "src/main.py", "old_file.txt", "new_name.js"],
    }

    # Create tables for each category
    categories = ["added", "modified", "deleted", "renamed"]
    for category in categories:
        if not changed_files[category]:
            continue

        action.summary.add_heading(f"{category.capitalize()} Files", 3)

        # Create table with one column for files
        category_table = [[{"data": "File Path", "header": True}]]

        # Add each file to the table
        for file in changed_files[category]:
            category_table.append([file])

        action.summary.add_table(category_table)

    # Try to write the summary
    try:
        action.summary.write()
        action.info("Summary table written successfully")
    except Exception as e:
        action.info(f"Could not write summary table: {e}")
        action.info("This is expected if running locally or in a testing environment")

    action.set_output("changed_files", "heloooooo")
    action.set_output("any_changed", "True")


if __name__ == "__main__":
    main()
