# MCP Router

An intelligent MCP (Model Context Protocol) router that routes requests to child MCP servers using advanced tool selection strategies. This server acts as a smart proxy, optimizing context length and reducing LLM confusion by selectively exposing only the most relevant tools based on the current context.

## Quick Start

The simplest way to use mcp-router is with `uvx`:

```bash
# Run with automatic setup (recommended)
uvx mcp-router

# Or with custom configuration
uvx mcp-router --config my-config.yaml --mcp-servers-json my-servers.json

# Or with web UI enabled
uvx mcp-router --web-ui
```

That's it! `uvx mcp-router` will automatically:
- Install all dependencies
- Detect and setup container runtime (Docker or Apple Container Framework)
- Start Qdrant vector database
- Auto-detect existing Claude Desktop configurations
- Start the meta-mcp server with web UI at http://localhost:8080

## Features

### Intelligent Tool Selection
- **Vector Search**: Fast semantic similarity using embeddings
- **LLM Selection**: AI-powered tool selection using local LLMs
- **RAG-Based Selection**: Context-augmented selection using retrieved documentation

### Automatic Setup
- **Container Runtime Detection**: Automatically uses Apple Container Framework on macOS or Docker
- **Dependency Management**: Handles all Python dependencies and model downloads
- **Configuration Discovery**: Auto-detects existing MCP server configurations
- **Infrastructure Setup**: Starts Qdrant and other required services automatically

### Web Management Interface
- Real-time server monitoring and logs
- Interactive configuration editor
- Tool usage analytics and metrics
- Child server status monitoring

### Production Ready
- Comprehensive logging and error handling
- Performance monitoring and caching
- Hot-reload configuration support
- Docker deployment ready

## Configuration

### Auto-Detection
MCP Router automatically looks for configuration files in these locations:

**Main Config (meta-server.yaml):**
- `./config/meta-server.yaml`
- `./meta-server.yaml`
- `~/.meta-mcp/config.yaml`
- `/etc/meta-mcp/config.yaml`

**MCP Servers Config (JSON):**
- `./mcp-servers.json`
- `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
- `~/.config/claude/claude_desktop_config.json` (Linux/Windows)

### Manual Configuration

If you want to customize the setup, you can provide specific paths:

```bash
uvx mcp-router --config path/to/config.yaml --mcp-servers-json path/to/servers.json
```

### Creating Custom Config

Create a `mcp-servers.json` file with your child servers:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "uvx",
      "args": ["@modelcontextprotocol/server-filesystem", "/path/to/files"]
    },
    "github": {
      "command": "uvx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

For advanced configuration, create a `meta-server.yaml`:

```yaml
strategy:
  primary: "vector"      # vector, llm, or rag
  fallback: "vector"     # fallback strategy
  vector_threshold: 0.75 # similarity threshold
  max_tools: 10         # max tools to return

server:
  host: "localhost"
  port: 3456

web_ui:
  enabled: true
  port: 8080

embeddings:
  # Primary: LM Studio (optional)
  lm_studio_endpoint: "http://localhost:1234/v1/embeddings"
  lm_studio_model: "nomic-embed-text-v1.5"

  # Fallback: Local model (automatic)
  fallback_model: "all-MiniLM-L6-v2"
```

## Command Options

```bash
uvx mcp-router [OPTIONS]

Options:
  --config PATH              Path to configuration file (auto-detected)
  --mcp-servers-json PATH    Path to MCP servers JSON (auto-detected)
  --web-ui / --no-web-ui     Enable web UI (default: enabled)
  --host TEXT                Server host
  --port INTEGER             Server port
  --log-level TEXT           Log level (DEBUG, INFO, WARNING, ERROR)
  --setup / --no-setup       Auto-setup infrastructure (default: enabled)
  --help                     Show this message and exit
```

## Advanced Usage

### Development Mode

For development with the project locally:

```bash
# Clone and use development version
git clone <repository-url>
cd mcp-router

# Install dependencies
uv sync --extra web --extra dev

# Run with development tools
uv run mcp-router start --log-level DEBUG --web-ui
```

### Legacy Commands

The following commands are still available for advanced users:

```bash
uvx mcp-router run [OPTIONS]           # Original run command
uvx mcp-router validate-config FILE    # Validate configuration
uvx mcp-router health [OPTIONS]        # System health check
uvx mcp-router init-config [OPTIONS]   # Create example config
```

## Tool Selection Strategies

### 1. Vector Search Strategy (Default)
- Fast semantic similarity using embeddings
- Suitable for most use cases
- ~50ms response time

### 2. LLM Selection Strategy
- AI-powered context-aware selection
- Best for complex queries
- Requires LM Studio (optional)
- ~200-500ms response time

### 3. RAG-Based Strategy
- Documentation-enhanced selection
- Highest accuracy with good docs
- ~100-200ms response time

## Integration with Claude Code

MCP Router can automatically configure itself for Claude Code:

1. Run `uvx mcp-router` once to start the server
2. The server will create the necessary Claude Code configuration
3. Restart Claude Code
4. MCP Router will be available as an MCP server

The configuration is automatically added to:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux/Windows: `~/.config/claude/claude_desktop_config.json`

## Web Interface

Access the web interface at `http://localhost:8080` to:

- Monitor server status and performance
- View real-time logs and metrics
- Manage child server configurations
- Explore available tools and their usage
- Test tool selection strategies

## Prerequisites

MCP Router handles most dependencies automatically, but you'll need:

- **Python 3.11+**: For running the server
- **Container Runtime**: Docker or Apple Container Framework (auto-configured)
- **uvx**: For package management (`pip install uvx` or `pipx install uv`)

Optional for enhanced features:
- **LM Studio**: For custom embeddings and LLM selection
- **Git**: For cloning and development

## Troubleshooting

### Common Issues

**Q: "uvx not found" error**
```bash
# Install uvx/uv
pip install uv
# or
pipx install uv
```

**Q: Container runtime errors**
- **macOS**: The tool will automatically try to set up Apple Container Framework
- **Other systems**: Install Docker and ensure it's running
- Use `--no-setup` to skip automatic setup if needed

**Q: Qdrant connection failed**
```bash
# Check if Qdrant is running
curl http://localhost:6333/collections

# Restart with setup
uvx mcp-router --setup
```

**Q: No MCP servers found**
- Create a `mcp-servers.json` file in your current directory
- Or point to an existing Claude Desktop config with `--mcp-servers-json`

**Q: Web UI not accessible**
- Check if port 8080 is available: `lsof -i :8080`
- Try a different port: `uvx mcp-router --port 8081`

**Q: Permission denied errors**
```bash
# Make sure you have write permissions in the current directory
# Or run from a directory where you have write access
cd ~/my-mcp-router-workspace
uvx mcp-router
```

### Debug Mode

For detailed troubleshooting:

```bash
uvx mcp-router --log-level DEBUG --web-ui
```

Check logs at `./logs/meta-server.log` for detailed error information.

## Architecture

MCP Router consists of:

- **Server Core**: Main MCP server handling client connections
- **Tool Router**: Implements intelligent tool selection strategies
- **Child Server Manager**: Manages lifecycle of child MCP servers
- **Vector Store**: Qdrant-based embedding storage and similarity search
- **Web Interface**: Real-time monitoring and configuration dashboard
- **Auto-Setup**: Infrastructure detection and configuration

## Security Considerations

- Run child servers with minimal privileges
- Use environment variables for sensitive configuration
- Review child server configurations before use
- Monitor logs for unusual activity
- Keep dependencies updated with `uvx` auto-updates

## Contributing

1. Fork the repository
2. Clone your fork and set up development environment:
   ```bash
   git clone https://github.com/yourusername/meta-mcp.git
   cd meta-mcp
   uv sync --dev  # Install dependencies
   uv run pre-commit install  # Set up pre-commit hooks
   ```

3. Create a feature branch:
   ```bash
   git checkout -b feature/amazing-feature
   ```

4. Make your changes with tests. Pre-commit hooks will automatically:
   - Format code with Ruff
   - Lint and fix issues
   - Check type annotations with mypy
   - Validate YAML/JSON files

5. Run all quality checks manually:
   ```bash
   ./scripts/check-all.sh
   # Or individually:
   uv run ruff format src/ tests/
   uv run ruff check src/ tests/ --fix
   uv run mypy src/
   uv run pytest
   ```

6. Run tests manually when needed:
   ```bash
   uv run pre-commit run pytest --hook-stage manual
   ```

7. Submit a pull request with a clear description of changes

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/meta-mcp.git
cd meta-mcp

# Install dependencies
uv sync --extra dev --extra web

# Run tests
uv run pytest

# Run the development version
uv run mcp-router start --log-level DEBUG
```

### Publishing

This project uses GitHub Actions for automated publishing to PyPI. To create a new release:

1. Create a new tag: `git tag v0.1.1`
2. Push the tag: `git push origin v0.1.1`
3. GitHub Actions will automatically build and publish to PyPI

## License

MIT License - see [LICENSE](LICENSE) file for details.
