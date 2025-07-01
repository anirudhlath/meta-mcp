#!/bin/bash
# Unified startup script for Meta MCP Server
# Automatically handles Qdrant setup with Docker or Apple Container

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default settings
QDRANT_TIMEOUT=60
QDRANT_HOST=""
CONFIG_FILE=""
LOG_LEVEL="INFO"
WEB_UI=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --web-ui)
            WEB_UI=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${BLUE}Meta MCP Server Startup${NC}"

# Detect container runtime
echo -e "${YELLOW}Detecting container runtime...${NC}"
RUNTIME=$("$SCRIPT_DIR/detect-container-runtime.sh" || echo "none")

if [ "$RUNTIME" = "none" ]; then
    echo -e "${RED}No container runtime detected!${NC}"
    echo "Please install either Docker or Apple Container Framework"
    echo "See: https://docs.docker.com/get-docker/ or https://github.com/apple/container"
    exit 1
fi

echo -e "${GREEN}✓ Using $RUNTIME runtime${NC}"

# Start Qdrant based on runtime
start_qdrant_docker() {
    echo -e "${YELLOW}Starting Qdrant with Docker...${NC}"
    
    # Check if Qdrant is already running
    if docker ps | grep -q "qdrant/qdrant"; then
        echo -e "${GREEN}✓ Qdrant is already running${NC}"
        QDRANT_HOST="localhost"
        return 0
    fi
    
    # Start using docker-compose
    cd "$PROJECT_ROOT"
    docker-compose up -d qdrant
    
    # Wait for Qdrant
    echo -e "${YELLOW}Waiting for Qdrant to be ready...${NC}"
    for i in $(seq 1 $QDRANT_TIMEOUT); do
        if curl -f -s http://localhost:6333/collections > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Qdrant is ready${NC}"
            QDRANT_HOST="localhost"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    echo -e "${RED}Qdrant failed to start${NC}"
    return 1
}

start_qdrant_apple() {
    echo -e "${YELLOW}Starting Qdrant with Apple Container...${NC}"
    
    # Ensure Apple container system is running
    if ! container system status 2>/dev/null | grep -q "running"; then
        echo -e "${YELLOW}Starting Apple container system...${NC}"
        "$SCRIPT_DIR/setup-apple-container.sh" || {
            echo -e "${RED}Failed to setup Apple container system${NC}"
            return 1
        }
    fi
    
    # Check if Qdrant container exists
    if container list | grep -q "qdrant-meta-mcp"; then
        echo -e "${GREEN}✓ Qdrant container exists${NC}"
        # Get IP
        QDRANT_HOST=$(container inspect qdrant-meta-mcp 2>/dev/null | grep -o '"address":"[^"]*"' | sed 's/"address":"\([^\/]*\).*/\1/' | head -1)
    else
        # Start Qdrant
        "$SCRIPT_DIR/qdrant-apple-container.sh" start
        # Get IP after starting
        QDRANT_HOST=$("$SCRIPT_DIR/get-qdrant-ip.sh" || echo "192.168.64.2")
    fi
    
    # Verify Qdrant is accessible
    if curl -f -s "http://$QDRANT_HOST:6333/collections" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Qdrant is ready at $QDRANT_HOST${NC}"
        return 0
    else
        echo -e "${RED}Qdrant is not accessible at $QDRANT_HOST${NC}"
        return 1
    fi
}

# Start Qdrant
if [ "$RUNTIME" = "docker" ]; then
    start_qdrant_docker || exit 1
else
    start_qdrant_apple || exit 1
fi

# Determine config file
if [ -z "$CONFIG_FILE" ]; then
    if [ "$RUNTIME" = "docker" ]; then
        CONFIG_FILE="$PROJECT_ROOT/config/meta-server.yaml"
    else
        CONFIG_FILE="$PROJECT_ROOT/config/meta-server-apple.yaml"
    fi
fi

# Update config with detected Qdrant host if needed
if [ "$RUNTIME" = "apple" ] && [ -n "$QDRANT_HOST" ]; then
    # Create temporary config with updated host
    TEMP_CONFIG=$(mktemp)
    sed "s/host: \".*\"/host: \"$QDRANT_HOST\"/" "$CONFIG_FILE" > "$TEMP_CONFIG"
    CONFIG_FILE="$TEMP_CONFIG"
fi

# Build Meta MCP command
CMD="uv run meta-mcp run --config $CONFIG_FILE --log-level $LOG_LEVEL"
if [ "$WEB_UI" = true ]; then
    CMD="$CMD --web-ui"
fi

# Start Meta MCP Server
echo -e "${YELLOW}Starting Meta MCP Server...${NC}"
echo -e "${BLUE}Configuration: $CONFIG_FILE${NC}"
echo -e "${BLUE}Qdrant: http://$QDRANT_HOST:6333${NC}"
if [ "$WEB_UI" = true ]; then
    echo -e "${BLUE}Web UI: http://localhost:8080${NC}"
fi

cd "$PROJECT_ROOT"
exec $CMD