# GitHub MCP Server Tools

This document describes the tools available from the GitHub MCP server for repository management and interaction.

## Available Tools

### create_repository
Create a new GitHub repository.

**Description**: Creates a new repository in your GitHub account with the specified configuration.

**Parameters**:
- `name` (string, required): Repository name
- `description` (string, optional): Repository description
- `private` (boolean, optional): Whether the repository should be private (default: false)
- `auto_init` (boolean, optional): Initialize with README (default: true)

**Example Usage**:
```
Create a new repository called "my-project" with description "A sample project"
```

**Use Cases**:
- Starting new projects
- Creating repositories for experiments
- Setting up documentation repositories

### get_repository
Get information about a repository.

**Description**: Retrieves detailed information about a specified GitHub repository.

**Parameters**:
- `owner` (string, required): Repository owner username
- `repo` (string, required): Repository name

**Example Usage**:
```
Get information about the repository "microsoft/vscode"
```

**Use Cases**:
- Checking repository details
- Validating repository existence
- Getting repository metadata

### list_issues
List issues in a repository.

**Description**: Retrieves a list of issues from a specified repository with optional filtering.

**Parameters**:
- `owner` (string, required): Repository owner username
- `repo` (string, required): Repository name
- `state` (string, optional): Issue state (open, closed, all) (default: open)
- `labels` (string, optional): Comma-separated list of labels to filter by
- `limit` (integer, optional): Maximum number of issues to return (default: 30)

**Example Usage**:
```
List all open issues in the repository "facebook/react"
Show only bugs: List issues with label "bug" in "microsoft/typescript"
```

**Use Cases**:
- Project management
- Bug tracking
- Issue triaging

### create_issue
Create a new issue.

**Description**: Creates a new issue in the specified repository.

**Parameters**:
- `owner` (string, required): Repository owner username
- `repo` (string, required): Repository name
- `title` (string, required): Issue title
- `body` (string, optional): Issue description
- `labels` (array, optional): Array of label names
- `assignees` (array, optional): Array of usernames to assign

**Example Usage**:
```
Create an issue titled "Fix login bug" with description "Users cannot log in with special characters in password"
```

**Use Cases**:
- Bug reporting
- Feature requests
- Task tracking

### search_repositories
Search for repositories.

**Description**: Searches GitHub repositories using the GitHub search API.

**Parameters**:
- `query` (string, required): Search query
- `sort` (string, optional): Sort criteria (stars, forks, updated) (default: stars)
- `order` (string, optional): Sort order (asc, desc) (default: desc)
- `limit` (integer, optional): Maximum number of results (default: 30)

**Example Usage**:
```
Search for Python machine learning repositories
Find repositories with "docker" in the name
```

**Use Cases**:
- Finding similar projects
- Discovering libraries
- Research and exploration

### get_file_contents
Get file contents from a repository.

**Description**: Retrieves the contents of a specific file from a repository.

**Parameters**:
- `owner` (string, required): Repository owner username
- `repo` (string, required): Repository name
- `path` (string, required): File path within the repository
- `ref` (string, optional): Branch, tag, or commit SHA (default: default branch)

**Example Usage**:
```
Get the contents of README.md from the main branch
Read the package.json file from a JavaScript project
```

**Use Cases**:
- Code review
- Documentation reading
- Configuration inspection

### create_pull_request
Create a pull request.

**Description**: Creates a new pull request in the specified repository.

**Parameters**:
- `owner` (string, required): Repository owner username
- `repo` (string, required): Repository name
- `title` (string, required): Pull request title
- `head` (string, required): Branch containing changes
- `base` (string, required): Branch to merge into
- `body` (string, optional): Pull request description

**Example Usage**:
```
Create a pull request to merge feature branch into main
Submit code changes for review
```

**Use Cases**:
- Code collaboration
- Feature submissions
- Bug fixes

## Common Patterns

### Repository Management Workflow
1. Search for similar repositories
2. Create a new repository
3. Add initial issues for planning
4. Create pull requests for features

### Issue Tracking Workflow
1. List existing issues to avoid duplicates
2. Create new issue with detailed description
3. Monitor issue status and updates

### Code Review Workflow
1. Get repository information
2. Read relevant file contents
3. Create pull request with changes
4. Review and discuss changes

## Error Handling

Common error scenarios and solutions:

- **Authentication Error**: Ensure GITHUB_TOKEN environment variable is set
- **Repository Not Found**: Verify owner and repository name are correct
- **Rate Limiting**: GitHub API has rate limits; consider implementing delays
- **Permission Denied**: Check if token has sufficient permissions for the operation

## Best Practices

1. **Use descriptive titles**: For issues and pull requests, use clear, descriptive titles
2. **Include context**: Provide sufficient detail in descriptions and commit messages
3. **Label appropriately**: Use relevant labels to categorize issues and PRs
4. **Check existing work**: Search for existing issues/PRs before creating new ones
5. **Follow repository guidelines**: Respect each repository's contributing guidelines
