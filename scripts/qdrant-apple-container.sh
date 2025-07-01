#!/bin/bash
# Qdrant management script for Apple Container Framework

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

CONTAINER_NAME="qdrant-meta-mcp"
IMAGE_NAME="qdrant/qdrant:latest"
STORAGE_DIR="./qdrant_storage"

# Function to show usage
usage() {
    echo -e "${BLUE}Qdrant Apple Container Manager${NC}"
    echo ""
    echo "Usage: $0 {start|stop|restart|status|logs|shell|clean}"
    echo ""
    echo "Commands:"
    echo "  start    - Start Qdrant container"
    echo "  stop     - Stop Qdrant container"
    echo "  restart  - Restart Qdrant container"
    echo "  status   - Show container status"
    echo "  logs     - Show container logs"
    echo "  shell    - Open shell in container"
    echo "  clean    - Remove container and storage"
    exit 1
}

# Check Apple Silicon
check_platform() {
    if [[ $(uname -m) != "arm64" ]]; then
        echo -e "${RED}Error: Apple container framework requires Apple Silicon Mac${NC}"
        exit 1
    fi
}

# Start Qdrant
start_qdrant() {
    echo -e "${GREEN}Starting Qdrant...${NC}"

    # Create storage directory
    mkdir -p "$STORAGE_DIR"

    # Check if container already exists
    if container list --all | grep -q "$CONTAINER_NAME"; then
        echo -e "${YELLOW}Container already exists. Starting it...${NC}"
        container start "$CONTAINER_NAME"
    else
        echo -e "${GREEN}Creating new container...${NC}"
        # Note: Apple container framework has different networking than Docker
        # Using default network with container's internal ports
        container run \
            --name "$CONTAINER_NAME" \
            --detach \
            --network default \
            --volume "$(pwd)/$STORAGE_DIR:/qdrant/storage" \
            --env QDRANT__SERVICE__HTTP_PORT=6333 \
            --env QDRANT__SERVICE__GRPC_PORT=6334 \
            "$IMAGE_NAME"
    fi

    # Get container IP
    CONTAINER_IP=$(container inspect "$CONTAINER_NAME" 2>/dev/null | grep -o '"address":"[^"]*"' | sed 's/"address":"\([^\/]*\).*/\1/' | head -1 || echo "192.168.64.2")

    # Wait for readiness
    echo -e "${YELLOW}Waiting for Qdrant to be ready...${NC}"
    for i in {1..30}; do
        if curl -f -s http://$CONTAINER_IP:6333/collections > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Qdrant is ready!${NC}"
            echo -e "  Web UI: http://$CONTAINER_IP:6333/dashboard"
            echo -e "  API: http://$CONTAINER_IP:6333"
            echo -e "  gRPC: $CONTAINER_IP:6334"
            echo -e "${YELLOW}Note: With Apple container, Qdrant runs on $CONTAINER_IP not localhost${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
    done

    echo -e "${RED}Qdrant failed to start${NC}"
    return 1
}

# Stop Qdrant
stop_qdrant() {
    echo -e "${YELLOW}Stopping Qdrant...${NC}"
    container stop "$CONTAINER_NAME" 2>/dev/null || echo "Container not running"
    echo -e "${GREEN}✓ Stopped${NC}"
}

# Restart Qdrant
restart_qdrant() {
    stop_qdrant
    sleep 2
    start_qdrant
}

# Show status
show_status() {
    echo -e "${BLUE}Qdrant Container Status:${NC}"
    container list --all | grep "$CONTAINER_NAME" || echo "Container not found"

    # Get container IP
    CONTAINER_IP=$(container inspect "$CONTAINER_NAME" 2>/dev/null | grep -o '"address":"[^"]*"' | sed 's/"address":"\([^\/]*\).*/\1/' | head -1 || echo "unknown")

    # Check if API is responding
    if [ "$CONTAINER_IP" != "unknown" ] && curl -f -s http://$CONTAINER_IP:6333/collections > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API is responding at http://$CONTAINER_IP:6333${NC}"

        # Get collections count
        COLLECTIONS=$(curl -s http://$CONTAINER_IP:6333/collections | grep -o '"result":\[.*\]' | grep -o '\[.*\]' | tr ',' '\n' | wc -l)
        echo -e "  Collections: $COLLECTIONS"
    else
        echo -e "${RED}✗ API is not responding${NC}"
    fi
}

# Show logs
show_logs() {
    echo -e "${BLUE}Qdrant Container Logs:${NC}"
    container logs "$CONTAINER_NAME" --tail 50 --follow
}

# Open shell
open_shell() {
    echo -e "${BLUE}Opening shell in Qdrant container...${NC}"
    container exec -it "$CONTAINER_NAME" /bin/bash
}

# Clean up
clean_up() {
    echo -e "${RED}This will remove the Qdrant container and all stored data!${NC}"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Removing container...${NC}"
        container stop "$CONTAINER_NAME" 2>/dev/null || true
        container rm "$CONTAINER_NAME" 2>/dev/null || true

        echo -e "${YELLOW}Removing storage...${NC}"
        rm -rf "$STORAGE_DIR"

        echo -e "${GREEN}✓ Cleanup complete${NC}"
    else
        echo "Cancelled"
    fi
}

# Main script
check_platform

case "$1" in
    start)
        start_qdrant
        ;;
    stop)
        stop_qdrant
        ;;
    restart)
        restart_qdrant
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    shell)
        open_shell
        ;;
    clean)
        clean_up
        ;;
    *)
        usage
        ;;
esac
