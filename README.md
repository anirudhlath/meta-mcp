# Meta MCP Server

A Meta MCP (Model Context Protocol) Server that intelligently routes requests to child MCP servers using advanced tool selection strategies. This server acts as a smart proxy, optimizing context length and reducing LLM confusion by selectively exposing only the most relevant tools based on the current context.

## =� Features

### Intelligent Tool Selection
- **Vector Search**: Fast semantic similarity using embeddings
- **LLM Selection**: AI-powered tool selection using local LLMs
- **RAG-Based Selection**: Context-augmented selection using retrieved documentation

### Automatic Fallbacks
- **Embedding Fallback**: Automatically falls back to local sentence-transformers if LM Studio is unavailable
- **Strategy Fallback**: Configurable fallback between selection strategies
- **Graceful Degradation**: Falls back to exposing all tools if selection fails

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

## =� Prerequisites

- Python 3.11 or higher
- [UV](https://github.com/astral-sh/uv) package manager
- [Qdrant](https://qdrant.tech/) vector database (Docker recommended)
- [LM Studio](https://lmstudio.ai/) (optional, for custom embeddings/LLM)

## =� Installation

### 1. Clone and Setup

```bash
git clone <repository-url>
cd meta-mcp
```

### 2. Install Dependencies

```bash
# Install core dependencies
uv sync

# Install with web UI support
uv sync --extra web

# Install development dependencies
uv sync --extra dev
```

### 3. Start Qdrant (Vector Database)

```bash
# Using Docker (recommended)
docker run -p 6333:6333 -v $(pwd)/qdrant_data:/qdrant/storage qdrant/qdrant

# Or using docker-compose (see docker-compose.yml)
docker-compose up -d qdrant
```

### 4. Configure the Server

```bash
# Copy and edit the configuration file
cp config/meta-server.yaml config/my-config.yaml
```

Edit the configuration to add your child servers and adjust settings as needed.

### 5. Run the Server

```bash
# Run with default config
uv run meta-mcp

# Run with custom config
uv run meta-mcp --config config/my-config.yaml

# Run with web UI
uv run meta-mcp --web-ui

# Development mode with auto-reload
uv run meta-mcp --config config/my-config.yaml --web-ui --reload
```

## =' Configuration

The server is configured via YAML files. See `config/meta-server.yaml` for a complete example with comments.

### Key Configuration Sections

#### Strategy Configuration
```yaml
strategy:
  primary: "vector"      # vector, llm, or rag
  fallback: "vector"     # fallback strategy
  vector_threshold: 0.75 # similarity threshold
  max_tools: 10         # max tools to return
```

#### Child Servers
```yaml
child_servers:
  - name: "github"
    command: ["uvx", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    documentation: "./docs/tools/github.md"
    enabled: true
```

#### Embedding Configuration
```yaml
embeddings:
  # Primary: LM Studio
  lm_studio_endpoint: "http://localhost:1234/v1/embeddings"
  lm_studio_model: "nomic-embed-text-v1.5"
  
  # Fallback: Local model
  fallback_model: "all-MiniLM-L6-v2"
```

## <� Tool Selection Strategies

### 1. Vector Search Strategy
- Generates embeddings for tool descriptions
- Uses semantic similarity to find relevant tools
- Fast and efficient for large tool sets
- Configurable similarity threshold

### 2. LLM Selection Strategy
- Sends all tools to a local LLM for intelligent selection
- Uses structured prompts for consistent output
- Best for complex context understanding
- Requires LM Studio or compatible API

### 3. RAG-Based Strategy
- Indexes tool documentation and examples
- Retrieves relevant context for each query
- Augments selection with retrieved information
- Most accurate for well-documented tools

## < Web Interface

Access the web interface at `http://localhost:8080` (configurable) to:

- Monitor server status and performance
- View real-time logs and metrics
- Manage child server configurations
- Explore available tools and their usage
- Test tool selection strategies

## = Integration with Claude Desktop

Add to your Claude Desktop configuration (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "meta-mcp": {
      "command": "uv",
      "args": ["run", "meta-mcp", "--config", "/path/to/your/config.yaml"],
      "cwd": "/path/to/meta-mcp"
    }
  }
}
```

## >� Development

### Code Quality

```bash
# Format and lint code
uv run ruff format src/ tests/
uv run ruff check src/ tests/

# Type checking
uv run mypy src/

# Run tests
uv run pytest

# All quality checks
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest
```

### Adding New Child Servers

1. Add server configuration to `child_servers` in your config file
2. Create documentation file in `docs/tools/` for RAG strategy
3. Restart the server to pick up the new configuration

### Extending Selection Strategies

1. Create a new router class in `src/meta_mcp/routing/`
2. Implement the `BaseRouter` interface
3. Register the strategy in the main server
4. Add configuration options as needed

## =� Performance and Monitoring

### Metrics Available
- Active client connections
- Request/response times
- Tool usage statistics
- Strategy effectiveness
- Error rates and patterns

### Optimization Tips
- Use vector search for fastest response times
- Enable embedding caching for better performance
- Monitor tool usage to optimize your child server set
- Use RAG strategy for highest accuracy when documentation is available

## =3 Docker Deployment

```bash
# Build the image
docker build -t meta-mcp .

# Run with docker-compose (includes Qdrant)
docker-compose up -d

# Run standalone
docker run -p 3456:3456 -p 8080:8080 -v $(pwd)/config:/app/config meta-mcp
```

## = Security Considerations

- Run child servers with minimal privileges
- Use environment variables for sensitive configuration
- Enable authentication for the web interface in production
- Regularly update dependencies and child servers
- Monitor logs for suspicious activity

## > Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the quality checks
5. Submit a pull request

## =� License

[Add your license here]

## <� Troubleshooting

### Common Issues

**Q: Child server fails to start**
- Check if the command path is correct
- Verify environment variables are set
- Check server logs for detailed error messages

**Q: Vector search not working**
- Ensure Qdrant is running and accessible
- Check if embeddings are being generated
- Verify vector store configuration

**Q: LM Studio integration fails**
- Confirm LM Studio is running with server enabled
- Check the API endpoint configuration
- Verify the embedding model is loaded in LM Studio

**Q: Web UI not accessible**
- Check if the web UI is enabled in configuration
- Verify the port is not in use by another service
- Check firewall settings

For more help, check the logs at `./logs/meta-server.log` or open an issue on GitHub.

---

## <� Architecture Overview

The Meta MCP Server consists of several key components:

- **Server Core**: Main MCP server handling client connections
- **Child Server Manager**: Spawns and manages child MCP servers
- **Routing Engine**: Implements the three selection strategies
- **Embedding Service**: Handles both LM Studio and local embeddings
- **Vector Store**: Manages tool embeddings and similarity search
- **Web Interface**: Provides monitoring and configuration UI
- **Configuration System**: YAML-based configuration with validation

Each component is designed to be modular and extensible, allowing for easy customization and enhancement.