# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Meta MCP Server is a Meta Model Context Protocol (MCP) server that intelligently routes requests to multiple child MCP servers. It acts as a proxy/router that optimizes LLM context usage by selectively exposing only relevant tools.

## Quick Start

### End Users (Production)
```bash
# One-command installation (auto-detects runtime)
./install.sh

# Server auto-starts when Claude Desktop connects
# Web UI available at http://localhost:8080
```

### Developers
```bash
# Install dependencies
uv sync --extra web --extra dev

# Auto-detect runtime and start everything
./scripts/start-meta-mcp.sh --web-ui

# Or manually with specific config
uv run meta-mcp run --config config/meta-server.yaml --web-ui
```

## Common Development Tasks

### Testing
```bash
# Run all tests
uv run pytest

# Run unit tests only
uv run pytest -m unit

# Run integration tests
uv run pytest -m integration

# Run specific test file
uv run pytest tests/test_server.py

# Run with coverage
uv run pytest --cov=src/meta_mcp --cov-report=term-missing
```

### Code Quality
```bash
# Format code
uv run ruff format src/ tests/

# Check linting
uv run ruff check src/ tests/

# Type checking
uv run mypy src/

# All checks in one command (use this before committing)
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest
```

### Development Mode
```bash
# Start server in development mode with auto-reload
uv run meta-mcp run --config config/meta-server.yaml --mcp-servers-json ~/.config/claude/claude_desktop_config.json --log-level debug --web-ui

# Watch logs
tail -f logs/meta-server.log

# Test child server directly
uv run python -m examples.echo_server.server
```

## Architecture

### Core Components

1. **Server (`src/meta_mcp/server/`)**: Main MCP server implementation
   - `mcp_server.py`: Protocol handling and request routing
   - `websocket_server.py`: WebSocket transport layer

2. **Routing (`src/meta_mcp/routing/`)**: Tool selection strategies
   - `vector_selection.py`: Fast semantic similarity search
   - `llm_selection.py`: AI-powered context analysis
   - `rag_selection.py`: Documentation-augmented selection

3. **Child Servers (`src/meta_mcp/child_servers/`)**: Process management
   - Manages lifecycle of child MCP servers
   - Health checks and automatic restarts

4. **Web UI (`src/meta_mcp/web_ui/`)**: Dashboard and monitoring
   - Real-time server status
   - Tool testing interface
   - Available at http://localhost:8080 when enabled

### Dependencies

- **Embeddings**: LM Studio (recommended) or sentence-transformers fallback
- **Vector Store**: Qdrant (runs in Docker)
- **LLM**: LM Studio for intelligent routing
- **Web**: FastAPI + Gradio for dashboard

## Configuration

### Main Configuration
Main configuration file: `config/meta-server.yaml` (server settings, embeddings, vector store, etc.)

### MCP Servers Configuration
MCP servers are configured separately using standard Claude Desktop JSON format:

```bash
# Use your existing Claude Desktop config
uv run meta-mcp run --config config/meta-server.yaml --mcp-servers-json ~/.config/claude/claude_desktop_config.json

# Or create a separate JSON file
uv run meta-mcp run --config config/meta-server.yaml --mcp-servers-json mcp-servers.json
```

Example `mcp-servers.json`:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "uvx",
      "args": ["@modelcontextprotocol/server-filesystem", "/path/to/files"],
      "env": {}
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

### Tool Selection Strategies

1. **Vector** (default): Fast, uses semantic similarity
   - Best for: General use, quick responses
   - Performance: ~50ms per selection

2. **LLM**: Intelligent context-aware selection
   - Best for: Complex queries, ambiguous requests
   - Performance: ~200-500ms per selection
   - Requires: LM Studio running

3. **RAG**: Documentation-enhanced selection
   - Best for: Highest accuracy, tool discovery
   - Performance: ~100-200ms per selection

## Docker Deployment

```bash
# Build image
docker build -t meta-mcp .

# Run with docker-compose (includes Qdrant)
docker-compose up -d

# View logs
docker-compose logs -f meta-mcp
```

## Troubleshooting

### Common Issues

1. **LM Studio not connected**:
   - Ensure LM Studio is running on port 1234
   - Falls back to sentence-transformers automatically

2. **Qdrant connection failed**:
   - Run `docker-compose up qdrant` separately
   - Check if port 6333 is available

3. **Child server not starting**:
   - Check logs in `logs/meta-server.log`
   - Test child server directly: `uv run python -m examples.echo_server.server`

### Debug Commands

```bash
# Check server health
curl http://localhost:5173/health

# View active child servers
curl http://localhost:5173/servers

# Test tool selection
curl -X POST http://localhost:5173/select-tools \
  -H "Content-Type: application/json" \
  -d '{"query": "list files in directory"}'
```

## Integration with Claude Desktop

### Automatic Setup (Recommended)
The `install.sh` script automatically configures Claude Desktop:

```bash
./install.sh  # Creates configuration automatically
```

### Manual Setup
Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "meta-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "meta_mcp.server_wrapper"],
      "cwd": "/path/to/meta-mcp",
      "env": {
        "UV_PROJECT_ROOT": "/path/to/meta-mcp"
      }
    }
  }
}
```

The wrapper automatically:
- Detects Docker or Apple Container runtime
- Starts Qdrant if needed
- Configures dynamic host detection
- Provides health monitoring

## Performance Tips

1. Use vector selection for general queries (fastest)
2. Enable caching in config for repeated queries
3. Run Qdrant locally for best performance
4. Limit child servers to only what's needed
5. Use `--log-level info` in production (less I/O)

## Project Structure

```
/src/meta_mcp/          # Core package
  /server/              # MCP protocol implementation
  /routing/             # Tool selection strategies
  /child_servers/       # Process management
  /embeddings/          # Embedding generation
  /vector_store/        # Qdrant integration
  /web_ui/              # Dashboard
/tests/                 # Test suite
/config/                # Example configurations
/examples/              # Example child servers
```

## Developer Best Practices

- Always use astral uv for package management and running the project.