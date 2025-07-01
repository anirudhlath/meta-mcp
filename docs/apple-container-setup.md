# Running Qdrant with Apple Container Framework

This guide explains how to use Apple's new container framework as an alternative to Docker for running Qdrant with Meta MCP.

## Prerequisites

- **Apple Silicon Mac** (M1/M2/M3)
- **macOS 26 beta or later** (required for Apple container framework)
- Apple container framework installed from https://github.com/apple/container

## Quick Start

1. **Install Apple Container Framework**:
   ```bash
   # Clone and build from source
   git clone https://github.com/apple/container.git
   cd container
   swift build -c release
   sudo cp .build/release/container /usr/local/bin/
   ```

2. **Setup Apple Container System**:
   ```bash
   # Run the setup script (downloads kernel and starts system)
   ./scripts/setup-apple-container.sh
   ```

3. **Start Qdrant**:
   ```bash
   # Using the management script
   ./scripts/qdrant-apple-container.sh start
   
   # Check status
   ./scripts/qdrant-apple-container.sh status
   ```

4. **Run Meta MCP with Apple container config**:
   ```bash
   uv run meta-mcp run --config config/meta-server-apple.yaml --web-ui
   ```

## Important Notes

- **Container IP**: Apple container uses bridge networking. Qdrant runs on `192.168.64.2` (or similar), not localhost
- **Get Current IP**: Run `./scripts/get-qdrant-ip.sh` to get the current container IP
- **Web UI Access**: Access Qdrant at `http://192.168.64.2:6333/dashboard`

## Management Commands

The `qdrant-apple-container.sh` script provides full lifecycle management:

```bash
# Start Qdrant
./scripts/qdrant-apple-container.sh start

# Stop Qdrant
./scripts/qdrant-apple-container.sh stop

# Restart Qdrant
./scripts/qdrant-apple-container.sh restart

# Check status
./scripts/qdrant-apple-container.sh status

# View logs
./scripts/qdrant-apple-container.sh logs

# Open shell in container
./scripts/qdrant-apple-container.sh shell

# Clean up (removes container and data)
./scripts/qdrant-apple-container.sh clean
```

## Docker vs Apple Container Comparison

| Feature | Docker | Apple Container |
|---------|--------|-----------------|
| Platform Support | Cross-platform | Apple Silicon only |
| macOS Version | Any recent version | macOS 26 beta+ |
| OCI Compliance | ✅ Full | ✅ Full |
| Performance | Good | Better (native) |
| Resource Usage | Higher | Lower |
| Networking | Full support | Limited on macOS 15 |
| Ecosystem | Mature, extensive | New, growing |
| Setup Complexity | Medium | Simple |

## Configuration Files

### Apple Container Configuration
- `config/apple-container-qdrant.yaml` - Container definition
- `config/meta-server-apple.yaml` - Meta MCP config for Apple container

### Docker Configuration (existing)
- `docker-compose.yml` - Docker Compose setup
- `config/meta-server.yaml` - Meta MCP config for Docker

## Switching Between Docker and Apple Container

### From Docker to Apple Container:
```bash
# Stop Docker containers
docker-compose down

# Start with Apple container
./scripts/qdrant-apple-container.sh start
uv run meta-mcp --config config/meta-server-apple.yaml
```

### From Apple Container to Docker:
```bash
# Stop Apple container
./scripts/qdrant-apple-container.sh stop

# Start with Docker
docker-compose up -d
uv run meta-mcp --config config/meta-server.yaml
```

## Persistent Storage

Both setups use local volume mounts for persistence:
- **Docker**: `./qdrant_storage` (managed by Docker volumes)
- **Apple Container**: `./qdrant_storage` (direct mount)

Data is compatible between both systems since Qdrant uses the same storage format.

## Troubleshooting

### Apple Container Issues

1. **"container: command not found"**
   - Ensure Apple container framework is installed
   - Add to PATH: `export PATH="/usr/local/bin:$PATH"`

2. **"Requires Apple Silicon Mac"**
   - Apple container only works on M1/M2/M3 Macs
   - Use Docker on Intel Macs

3. **Network connectivity issues**
   - Known limitation on macOS 15
   - Upgrade to macOS 26 beta for full networking

### Qdrant Connection Issues

1. **Cannot connect to Qdrant**
   - Check if container is running: `./scripts/qdrant-apple-container.sh status`
   - Verify ports aren't in use: `lsof -i :6333`

2. **Data not persisting**
   - Check volume mount permissions
   - Ensure `./qdrant_storage` directory exists

## Performance Considerations

Apple container framework offers several advantages on Apple Silicon:

1. **Lower resource overhead** - No virtualization layer
2. **Faster startup times** - Native execution
3. **Better memory efficiency** - Shared system resources
4. **Native Apple Silicon optimization** - Full ARM64 performance

## Future Considerations

As Apple's container framework matures:
- Expect improved networking support
- More tools and integrations
- Better documentation and examples
- Potential for Apple-specific optimizations

## Recommendation

- **Use Apple Container if**:
  - You have an Apple Silicon Mac with macOS 26 beta
  - You want better performance and lower resource usage
  - You're comfortable with beta software

- **Use Docker if**:
  - You need cross-platform compatibility
  - You're on Intel Mac or macOS 15
  - You need mature tooling and extensive ecosystem
  - You require full networking capabilities

Both options are fully supported by Meta MCP and can be switched between as needed.