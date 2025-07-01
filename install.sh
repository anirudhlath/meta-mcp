#!/bin/bash
# Meta MCP Server Installation Script
# Automatically sets up Meta MCP with the best available container runtime

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Meta MCP Server Installation${NC}"
echo "This script will install Meta MCP with automatic container runtime detection"
echo ""

# Check platform
PLATFORM=$(uname -s)
ARCH=$(uname -m)

echo -e "${YELLOW}Platform: $PLATFORM $ARCH${NC}"

# Check if we're on macOS
if [[ "$PLATFORM" != "Darwin" ]]; then
    echo -e "${YELLOW}Note: Apple Container Framework is only available on macOS${NC}"
    echo -e "${YELLOW}Will use Docker as container runtime${NC}"
fi

# Check Python/UV
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: UV package manager not found${NC}"
    echo "Please install UV from: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

echo -e "${GREEN}✓ UV found${NC}"

# Install Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
uv sync --extra web --extra dev

# Detect and setup container runtime
echo -e "${YELLOW}Detecting container runtime...${NC}"

DOCKER_AVAILABLE=false
APPLE_CONTAINER_AVAILABLE=false

# Check Docker
if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
    DOCKER_AVAILABLE=true
    echo -e "${GREEN}✓ Docker detected and running${NC}"
fi

# Check Apple Container (macOS only)
if [[ "$PLATFORM" == "Darwin" && "$ARCH" == "arm64" ]]; then
    if command -v container &> /dev/null; then
        APPLE_CONTAINER_AVAILABLE=true
        echo -e "${GREEN}✓ Apple Container Framework detected${NC}"
    fi
fi

# Determine runtime to use
RUNTIME=""
if [[ "$APPLE_CONTAINER_AVAILABLE" == true ]]; then
    RUNTIME="apple"
    echo -e "${BLUE}Selected runtime: Apple Container Framework${NC}"
elif [[ "$DOCKER_AVAILABLE" == true ]]; then
    RUNTIME="docker"
    echo -e "${BLUE}Selected runtime: Docker${NC}"
else
    echo -e "${RED}No suitable container runtime found!${NC}"
    echo ""
    echo "Please install one of the following:"
    echo "  - Docker: https://docs.docker.com/get-docker/"
    if [[ "$PLATFORM" == "Darwin" && "$ARCH" == "arm64" ]]; then
        echo "  - Apple Container Framework: https://github.com/apple/container"
    fi
    exit 1
fi

# Setup container runtime
if [[ "$RUNTIME" == "apple" ]]; then
    echo -e "${YELLOW}Setting up Apple Container Framework...${NC}"
    ./scripts/setup-apple-container.sh
elif [[ "$RUNTIME" == "docker" ]]; then
    echo -e "${YELLOW}Setting up Docker containers...${NC}"
    docker-compose pull qdrant
fi

# Create MCP configuration directory if it doesn't exist
MCP_CONFIG_DIR="$HOME/.config/claude-desktop"
if [[ "$PLATFORM" == "Darwin" ]]; then
    MCP_CONFIG_DIR="$HOME/Library/Application Support/Claude"
fi

mkdir -p "$MCP_CONFIG_DIR"

# Generate MCP configuration
CONFIG_FILE="$MCP_CONFIG_DIR/claude_desktop_config.json"
PROJECT_DIR="$(pwd)"

echo -e "${YELLOW}Generating MCP configuration...${NC}"

# Check if config file exists
if [[ -f "$CONFIG_FILE" ]]; then
    echo -e "${YELLOW}Existing MCP configuration found${NC}"
    echo "Creating backup: ${CONFIG_FILE}.backup"
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
fi

# Create or update config
cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {
    "meta-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "meta_mcp.server_wrapper"],
      "cwd": "$PROJECT_DIR",
      "env": {
        "UV_PROJECT_ROOT": "$PROJECT_DIR"
      }
    }
  }
}
EOF

echo -e "${GREEN}✓ MCP configuration created at: $CONFIG_FILE${NC}"

# Test installation
echo -e "${YELLOW}Testing installation...${NC}"

# Start Qdrant
if [[ "$RUNTIME" == "apple" ]]; then
    ./scripts/qdrant-apple-container.sh start > /dev/null 2>&1
else
    docker-compose up -d qdrant > /dev/null 2>&1
fi

# Test server
if timeout 10 uv run meta-mcp health &> /dev/null; then
    echo -e "${GREEN}✓ Installation test passed${NC}"
else
    echo -e "${YELLOW}⚠ Installation test inconclusive (this is often normal)${NC}"
fi

echo ""
echo -e "${GREEN}Installation Complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Restart Claude Desktop application"
echo "2. Meta MCP will automatically start when Claude needs it"
echo ""
echo "Useful commands:"
echo "  - Check status: ./scripts/start-meta-mcp.sh --web-ui"
echo "  - View logs: tail -f logs/meta-server.log"
if [[ "$RUNTIME" == "apple" ]]; then
    echo "  - Manage Qdrant: ./scripts/qdrant-apple-container.sh status"
else
    echo "  - Manage Qdrant: docker-compose ps"
fi
echo ""
echo -e "${BLUE}Configuration file: $CONFIG_FILE${NC}"
echo -e "${BLUE}Project directory: $PROJECT_DIR${NC}"
