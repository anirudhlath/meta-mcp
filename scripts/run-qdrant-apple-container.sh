#!/bin/bash
# Script to run Qdrant using Apple's container framework
# Requires Apple silicon Mac with macOS 26 beta (or later)

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up Qdrant with Apple Container Framework${NC}"

# Check if running on Apple Silicon
if [[ $(uname -m) != "arm64" ]]; then
    echo -e "${RED}Error: Apple container framework requires Apple Silicon Mac${NC}"
    exit 1
fi

# Create storage directory if it doesn't exist
STORAGE_DIR="./qdrant_storage"
if [ ! -d "$STORAGE_DIR" ]; then
    echo -e "${YELLOW}Creating storage directory: $STORAGE_DIR${NC}"
    mkdir -p "$STORAGE_DIR"
fi

# Pull the Qdrant image
echo -e "${GREEN}Pulling Qdrant image...${NC}"
container pull qdrant/qdrant:latest

# Run Qdrant container
echo -e "${GREEN}Starting Qdrant container...${NC}"
container run \
    --name qdrant-meta-mcp \
    --detach \
    --publish 6333:6333 \
    --publish 6334:6334 \
    --volume "$(pwd)/$STORAGE_DIR:/qdrant/storage" \
    --env QDRANT__SERVICE__HTTP_PORT=6333 \
    --env QDRANT__SERVICE__GRPC_PORT=6334 \
    qdrant/qdrant:latest

# Wait for Qdrant to be ready
echo -e "${YELLOW}Waiting for Qdrant to be ready...${NC}"
for i in {1..30}; do
    if curl -f -s http://localhost:6333/collections > /dev/null 2>&1; then
        echo -e "${GREEN}Qdrant is ready!${NC}"
        echo -e "Web UI available at: http://localhost:6333/dashboard"
        echo -e "API endpoint: http://localhost:6333"
        echo -e "gRPC endpoint: localhost:6334"
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo -e "${RED}Qdrant failed to start within 60 seconds${NC}"
exit 1