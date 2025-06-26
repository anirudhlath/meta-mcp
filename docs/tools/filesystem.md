# Filesystem MCP Server Tools

This document describes the tools available from the Filesystem MCP server for file and directory operations.

## Available Tools

### read_file
Read the contents of a file.

**Description**: Reads and returns the complete contents of a specified file.

**Parameters**:
- `path` (string, required): Absolute or relative path to the file

**Example Usage**:
```
Read the contents of config.json
Show me the README.md file
Open and read the Python script main.py
```

**Use Cases**:
- Viewing configuration files
- Reading documentation
- Examining source code
- Checking log files

**Supported File Types**:
- Text files (.txt, .md, .py, .js, .html, etc.)
- Configuration files (.json, .yaml, .xml, .ini)
- Code files (any programming language)
- Log files

### write_file
Write content to a file.

**Description**: Creates a new file or overwrites an existing file with the provided content.

**Parameters**:
- `path` (string, required): Path where the file should be written
- `content` (string, required): Content to write to the file

**Example Usage**:
```
Create a new Python script with hello world code
Write configuration data to settings.json
Save the output to a text file
```

**Use Cases**:
- Creating new files
- Updating configuration files
- Saving generated content
- Creating documentation

### list_directory
List contents of a directory.

**Description**: Returns a list of files and subdirectories in the specified directory.

**Parameters**:
- `path` (string, required): Path to the directory to list

**Example Usage**:
```
List all files in the current directory
Show contents of the src folder
What files are in /home/user/documents?
```

**Use Cases**:
- Exploring project structure
- Finding specific files
- Understanding directory organization
- Checking for file existence

### create_directory
Create a new directory.

**Description**: Creates a new directory at the specified path, including any necessary parent directories.

**Parameters**:
- `path` (string, required): Path of the directory to create

**Example Usage**:
```
Create a new folder called "projects"
Make a directory structure src/components/ui
Create a backup folder
```

**Use Cases**:
- Organizing project structure
- Creating backup directories
- Setting up new project folders
- Preparing deployment directories

### delete_file
Delete a file.

**Description**: Permanently removes a file from the filesystem.

**Parameters**:
- `path` (string, required): Path to the file to delete

**Example Usage**:
```
Delete the temporary file temp.txt
Remove the old configuration config.old
Clean up the log file debug.log
```

**Use Cases**:
- Cleaning up temporary files
- Removing outdated files
- Managing disk space
- File maintenance

### move_file
Move or rename a file.

**Description**: Moves a file from one location to another, or renames a file in the same directory.

**Parameters**:
- `source` (string, required): Current path of the file
- `destination` (string, required): New path for the file

**Example Usage**:
```
Rename script.py to main.py
Move the file to the backup folder
Reorganize files into subdirectories
```

**Use Cases**:
- Renaming files
- Reorganizing project structure
- Moving files to different directories
- File maintenance

### copy_file
Copy a file to a new location.

**Description**: Creates a copy of a file at a new location while preserving the original.

**Parameters**:
- `source` (string, required): Path of the file to copy
- `destination` (string, required): Path where the copy should be created

**Example Usage**:
```
Create a backup copy of important.txt
Copy the template to start a new file
Duplicate the configuration for testing
```

**Use Cases**:
- Creating backups
- Duplicating templates
- Copying files for modification
- Creating multiple versions

### get_file_info
Get information about a file or directory.

**Description**: Returns metadata about a file or directory including size, modification time, and permissions.

**Parameters**:
- `path` (string, required): Path to the file or directory

**Example Usage**:
```
Check when the file was last modified
Get the size of the database file
See the permissions on the config directory
```

**Use Cases**:
- File system analysis
- Checking file properties
- Monitoring file changes
- Debugging permission issues

### search_files
Search for files by name or pattern.

**Description**: Recursively searches for files matching a specified pattern within a directory.

**Parameters**:
- `directory` (string, required): Directory to search in
- `pattern` (string, required): Filename pattern or glob to match
- `recursive` (boolean, optional): Whether to search subdirectories (default: true)

**Example Usage**:
```
Find all Python files in the project
Search for configuration files (*.conf, *.cfg)
Locate all README files
```

**Use Cases**:
- Finding specific file types
- Locating configuration files
- Project file discovery
- Cleanup operations

## Common Patterns

### Project Setup Workflow
1. Create main project directory
2. Create subdirectories (src, docs, tests)
3. Copy template files
4. Initialize configuration files

### File Management Workflow
1. List directory contents to understand structure
2. Read existing files to understand current state
3. Create or modify files as needed
4. Move or organize files for better structure

### Backup and Maintenance Workflow
1. Get file info to check sizes and dates
2. Copy important files to backup location
3. Delete temporary or outdated files
4. Reorganize files into appropriate directories

## Security Considerations

**Path Restrictions**: The filesystem server operates within configured boundaries:
- Cannot access files outside the specified root directory
- Prevents path traversal attacks (../ sequences)
- Restricts access to system files and directories

**File Permissions**: 
- Respects operating system file permissions
- Cannot modify read-only files
- Cannot access files without appropriate permissions

**Safe Operations**:
- All operations are logged for audit purposes
- File operations can be restricted by configuration
- Dangerous operations may require confirmation

## Error Handling

Common error scenarios:

- **File Not Found**: Verify the path is correct and file exists
- **Permission Denied**: Check file/directory permissions
- **Disk Full**: Ensure sufficient disk space for write operations
- **Path Too Long**: File paths may have system-imposed length limits
- **Invalid Characters**: Some characters may not be allowed in filenames

## Best Practices

1. **Use absolute paths**: When possible, use full paths to avoid ambiguity
2. **Check before overwriting**: Use get_file_info to check if files exist
3. **Create backups**: Copy important files before modifying them
4. **Organize logically**: Use meaningful directory structures
5. **Clean up regularly**: Remove temporary and outdated files
6. **Validate input**: Ensure file paths and content are appropriate

## File Type Handling

### Text Files
- Automatically detects text encoding
- Preserves line endings
- Supports Unicode content

### Binary Files
- Limited support for reading binary files
- Use appropriate tools for binary file manipulation
- Consider file size limitations

### Special Files
- Handles symbolic links appropriately
- Respects file system permissions
- Manages file locking when necessary