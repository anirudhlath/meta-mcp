#!/bin/bash
# Setup script for Apple Container Framework

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Apple Container Framework Setup${NC}"

# Check platform
if [[ $(uname -m) != "arm64" ]]; then
    echo -e "${RED}Error: Apple container framework requires Apple Silicon Mac${NC}"
    exit 1
fi

# Check if container command exists
if ! command -v container &> /dev/null; then
    echo -e "${RED}Error: container command not found${NC}"
    echo "Please install from: https://github.com/apple/container"
    exit 1
fi

# Download and install Kata kernel
KERNEL_VERSION="3.17.0"
KERNEL_URL="https://github.com/kata-containers/kata-containers/releases/download/${KERNEL_VERSION}/kata-static-${KERNEL_VERSION}-arm64.tar.xz"
KERNEL_DIR="$HOME/.container/kata"

echo -e "${YELLOW}Setting up Kata kernel...${NC}"
mkdir -p "$KERNEL_DIR"

# Download kernel if not exists
if [ ! -f "$KERNEL_DIR/vmlinux.container" ]; then
    echo -e "${GREEN}Downloading Kata kernel...${NC}"
    curl -L "$KERNEL_URL" -o "$KERNEL_DIR/kata.tar.xz"
    
    echo -e "${GREEN}Extracting kernel...${NC}"
    cd "$KERNEL_DIR"
    tar -xf kata.tar.xz
    
    # Find and copy the kernel
    find . -name "vmlinux.container" -exec cp {} . \; 2>/dev/null || \
    find . -name "vmlinux" -exec cp {} vmlinux.container \; 2>/dev/null
    
    echo -e "${GREEN}✓ Kernel installed${NC}"
fi

# Start container system with kernel
echo -e "${YELLOW}Starting container system...${NC}"
container system start --kernel "$KERNEL_DIR/vmlinux.container" || {
    echo -e "${YELLOW}System may already be running${NC}"
}

# Verify system is running
echo -e "${YELLOW}Verifying system...${NC}"
if container system status 2>/dev/null | grep -q "running"; then
    echo -e "${GREEN}✓ Container system is running${NC}"
else
    echo -e "${YELLOW}Starting system service...${NC}"
    container system start --kernel "$KERNEL_DIR/vmlinux.container"
fi

# Pull Qdrant image
echo -e "${YELLOW}Pulling Qdrant image...${NC}"
container images pull qdrant/qdrant:latest || {
    echo -e "${RED}Failed to pull image. This might be due to networking limitations.${NC}"
    echo -e "${YELLOW}You may need macOS 26 beta for full networking support.${NC}"
}

echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""
echo "You can now run Qdrant with:"
echo "  ./scripts/qdrant-apple-container.sh start"