# Example Child Server Configurations

This directory contains example configurations for various MCP child servers that can be managed by the Meta MCP Server.

## Available Examples

### 1. File System Server
```yaml
- name: "filesystem-tools"
  command: ["uvx", "mcp-server-filesystem", "/path/to/directory"]
  enabled: true
  description: "File system operations"
```

**Capabilities:**
- Read/write files
- Directory listing
- File search
- File metadata

### 2. Web/HTTP Server
```yaml
- name: "web-tools"
  command: ["uvx", "mcp-server-fetch"]
  enabled: true
  description: "Web scraping and HTTP requests"
```

**Capabilities:**
- HTTP GET/POST requests
- Web page scraping
- API interactions
- Content parsing

### 3. Database Server
```yaml
- name: "database-tools"
  command: ["python", "-m", "mcp_database_server"]
  enabled: true
  description: "Database operations"
  env:
    DB_CONNECTION: "sqlite:///app/data.db"
```

**Capabilities:**
- SQL queries
- Database schema inspection
- Data manipulation
- Transaction management

### 4. Git Server
```yaml
- name: "git-tools"
  command: ["uvx", "mcp-server-git"]
  enabled: true
  description: "Git repository operations"
```

**Capabilities:**
- Repository cloning
- Branch management
- Commit operations
- Diff analysis

### 5. Memory/Notes Server
```yaml
- name: "memory-tools"
  command: ["uvx", "mcp-server-memory"]
  enabled: true
  description: "Persistent memory and notes"
```

**Capabilities:**
- Store/retrieve notes
- Knowledge base management
- Context preservation
- Information retrieval

## Setting Up Child Servers

### Installation
Most MCP servers can be installed using `uvx`:

```bash
# File system server
uvx install mcp-server-filesystem

# Web fetch server
uvx install mcp-server-fetch

# Git server
uvx install mcp-server-git

# Memory server
uvx install mcp-server-memory
```

### Custom Servers
You can also create custom MCP servers:

1. **Python Example:**
```python
# my_custom_server.py
from mcp import Server
import asyncio

server = Server("my-custom-server")

@server.tool("custom_tool")
async def custom_tool(param: str) -> str:
    return f"Processed: {param}"

if __name__ == "__main__":
    asyncio.run(server.run())
```

2. **Configuration:**
```yaml
- name: "custom-server"
  command: ["python", "my_custom_server.py"]
  enabled: true
  description: "My custom MCP server"
```

## Environment Variables

Child servers can use environment variables for configuration:

```yaml
- name: "api-server"
  command: ["uvx", "mcp-server-api"]
  enabled: true
  env:
    API_KEY: "${MY_API_KEY}"
    BASE_URL: "https://api.example.com"
    TIMEOUT: "30"
```

## Documentation Integration

For better RAG-based tool selection, provide documentation for your child servers:

```yaml
- name: "filesystem-tools"
  command: ["uvx", "mcp-server-filesystem", "/workspace"]
  enabled: true
  description: "File system operations"
  documentation: "docs/filesystem-server.md"
```

The documentation should describe:
- Available tools and their purposes
- Parameter requirements
- Usage examples
- Error handling
- Best practices

## Health Checks

Child servers are automatically monitored. The Meta MCP Server will:
- Check server health every 30 seconds
- Restart failed servers automatically
- Track server uptime and performance
- Log server errors and warnings

## Best Practices

1. **Resource Management:**
   - Limit resource usage in child servers
   - Use appropriate timeouts
   - Handle errors gracefully

2. **Security:**
   - Validate all inputs
   - Use least-privilege access
   - Don't expose sensitive information

3. **Performance:**
   - Cache expensive operations
   - Use async/await patterns
   - Optimize tool descriptions for vector search

4. **Monitoring:**
   - Include health check endpoints
   - Log important operations
   - Provide useful error messages

## Troubleshooting

### Server Won't Start
1. Check command path and arguments
2. Verify environment variables
3. Check permissions
4. Review server logs

### Tools Not Found
1. Verify server is running
2. Check tool names and parameters
3. Review server documentation
4. Test server independently

### Performance Issues
1. Monitor resource usage
2. Check network connectivity
3. Optimize tool descriptions
4. Consider caching strategies