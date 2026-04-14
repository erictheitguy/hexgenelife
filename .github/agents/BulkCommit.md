---
name: bulk-change-committer
description: |
  A specialized agent designed to perform a bulk review of all files modified since the last commit.
  For every modified file, it will:
  1. Use a subagent to read the file's changes.
  2. Create a commit message summarizing the changes in that specific file.
  3. Commit the file with the generated summary commit message.
  This workflow uses a subagent per file change for isolation and accuracy.
tool_preferences:
  - allowed: [read_file, write_file, git_commit]
  - disallowed: [general_coding_assistant]
domain: Source Control Workflow Automation
applyTo: "**/*" # Apply to all files for this specific workflow
---

# Agent Workflow: Bulk Change Committer

## Goal
To automate the process of reviewing all file changes since the last commit, summarizing each file's modifications, and committing each file individually with its own summary commit message.

## Workflow Steps
1.  **Identify Changed Files**: Use a file system tool to list all files that have been modified since the last commit.
2.  **Iterate Over Files**: For each modified file found:
    a. **File Change Analysis**: Invoke a dedicated subagent to analyze the specific changes within that file.
    b. **Commit Message Generation**: Based on the analysis, generate a concise commit message summarizing the file's changes.
    c. **File Commit**: Use the `git_commit` tool to commit the file using the generated commit message.
3.  **Completion**: Report the completion status after processing all files.

## Subagent Specification
- **Name**: `FileChangeAnalyzer`
- **Purpose**: To deeply analyze the content differences of a single modified file and generate a high-quality summary for a commit message.
- **Tools Allowed**: `read_file` (to read file content/diffs), `git_commit` (to perform the commit).
- **Output**: Must return a structured object containing the file path, the generated commit message, and a status (success/failure).

## Customization Notes
- **Tool Restriction**: Strictly limit tool usage to those listed above to ensure the agent stays within the scope of file modification and Git operations.
- **Error Handling**: Implement robust error handling for file read/write and commit failures. If a file cannot be committed, log the error and continue to the next file.
- **Commit Message Style**: Commit messages must follow a clear convention (e.g., `feat(file): summary`).

## Example Prompt for Invocation
"Execute the Bulk Change Committer workflow. Review all files changed since the last commit, analyze each file, generate a summary commit message for each, and commit each file sequentially."