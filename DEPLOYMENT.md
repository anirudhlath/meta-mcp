# Meta MCP Server - Production Deployment Guide

This guide covers how to set up Meta MCP Server for production use with automatic dependency management.

## Overview

Meta MCP Server now includes:
- **Automatic runtime detection** - Works with Docker or Apple Container Framework
- **Zero-configuration setup** - Automatically detects and configures Qdrant
- **Health monitoring** - Built-in health checks and auto-recovery
- **One-command installation** - Single script sets everything up

## Quick Start for End Users

### 1. Install Meta MCP Server

```bash
# Clone and install
git clone <repository>
cd meta-mcp
./install.sh
```

The install script will:
- Detect your platform and available container runtimes
- Install Python dependencies
- Set up Qdrant (Docker or Apple Container)
- Configure Claude Desktop integration
- Test the installation

### 2. Configure Claude Desktop

The installation script automatically creates the Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Other**: `~/.config/claude-desktop/claude_desktop_config.json`

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

### 3. Usage

- **Restart Claude Desktop** - The MCP server will auto-start when needed
- **Access Web UI** - Visit http://localhost:8080 (when server is running)
- **Check Health** - Run `uv run meta-mcp health`

## Architecture

### Auto-Detection System

```
Claude Desktop → server_wrapper.py → Runtime Detection → Start Qdrant → Meta MCP Server
```

1. **server_wrapper.py** - Entry point that ensures all dependencies
2. **Runtime Detection** - Automatically chooses Docker or Apple Container
3. **Qdrant Management** - Starts and monitors vector database
4. **Dynamic Config** - Adjusts configuration based on detected runtime

### Container Runtime Priority

1. **Apple Container Framework** (macOS ARM64) - Preferred for performance
2. **Docker** (Cross-platform) - Fallback for compatibility
3. **Error** - Installation fails if neither available

### Configuration Management

- **auto-detect.yaml** - Uses runtime detection
- **meta-server.yaml** - Docker-specific
- **meta-server-apple.yaml** - Apple Container-specific

## Manual Setup (Advanced)

### Docker Setup

```bash
# Start Qdrant
docker-compose up -d qdrant

# Run Meta MCP
uv run meta-mcp run --config config/meta-server.yaml --web-ui
```

### Apple Container Setup

```bash
# Setup Apple Container (first time)
./scripts/setup-apple-container.sh

# Start Qdrant
./scripts/qdrant-apple-container.sh start

# Run Meta MCP
uv run meta-mcp run --config config/meta-server-apple.yaml --web-ui
```

### Unified Setup (Recommended)

```bash
# Automatically detects runtime and starts everything
./scripts/start-meta-mcp.sh --web-ui
```

## Troubleshooting

### Health Check

```bash
# Comprehensive health check
uv run meta-mcp health

# JSON output for automation
uv run meta-mcp health --json
```

### Common Issues

1. **"No container runtime detected"**
   - Install Docker or Apple Container Framework
   - Ensure Docker daemon is running

2. **"Qdrant not accessible"**
   - Check container status: `./scripts/qdrant-apple-container.sh status`
   - Restart containers: `docker-compose restart qdrant`

3. **"Python dependencies missing"**
   - Reinstall: `uv sync --extra web --extra dev`

4. **Apple Container networking issues**
   - Requires macOS 26 beta for full networking
   - Check IP: `./scripts/get-qdrant-ip.sh`

### Log Files

- **Meta MCP**: `logs/meta-server.log`
- **Container logs**: `./scripts/qdrant-apple-container.sh logs`
- **Docker logs**: `docker-compose logs qdrant`

## Production Considerations

### Security

- Vector database runs locally (no external access)
- No API keys required for basic functionality
- LM Studio connection is localhost-only

### Performance

- **Apple Container**: ~30% better performance on Apple Silicon
- **Docker**: More mature, better compatibility
- **Memory**: ~1GB for Qdrant, ~500MB for Meta MCP

### Monitoring

```bash
# Check overall health
curl http://localhost:3456/health

# Check Qdrant status
curl http://localhost:6333/collections  # Docker
curl http://$(./scripts/get-qdrant-ip.sh):6333/collections  # Apple Container

# Check Web UI
curl http://localhost:8080
```

## Distribution

For distributing Meta MCP Server:

1. **Package the project** with all scripts
2. **Include install.sh** for one-command setup
3. **Document requirements**:
   - Python 3.10+ with UV
   - Docker OR Apple Container Framework
   - 2GB free disk space

Example packaging:
```bash
# Create distribution package
tar -czf meta-mcp-server.tar.gz \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.uv' \
  .
```

## Integration Examples

### CI/CD

```yaml
# GitHub Actions example
- name: Test Meta MCP Server
  run: |
    ./install.sh
    uv run meta-mcp health
    timeout 30 uv run meta-mcp run &
    sleep 10
    curl -f http://localhost:3456/health
```

### Docker Distribution

```dockerfile
FROM python:3.11-slim
COPY . /app
WORKDIR /app
RUN ./install.sh
CMD ["uv", "run", "python", "-m", "meta_mcp.server_wrapper"]
```

## Support

For issues:
1. Run health check: `uv run meta-mcp health`
2. Check logs: `tail -f logs/meta-server.log`
3. Test containers: `./scripts/qdrant-apple-container.sh status`
4. Restart everything: `./install.sh`
