#!/bin/bash
# Detect available container runtime (Docker or Apple Container)

set -e

# Check for Docker
check_docker() {
    if command -v docker &> /dev/null; then
        if docker info &> /dev/null; then
            echo "docker"
            return 0
        fi
    fi
    return 1
}

# Check for Apple Container
check_apple_container() {
    if command -v container &> /dev/null; then
        # Check if on Apple Silicon
        if [[ $(uname -m) == "arm64" ]]; then
            # Check if system is running
            if container system status 2>/dev/null | grep -q "running"; then
                echo "apple"
                return 0
            fi
        fi
    fi
    return 1
}

# Main detection logic
if check_docker; then
    exit 0
elif check_apple_container; then
    exit 0
else
    # No runtime detected
    echo "none"
    exit 1
fi
