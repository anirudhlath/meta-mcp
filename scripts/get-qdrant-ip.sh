#!/bin/bash
# Get the current IP address of the Qdrant container

CONTAINER_NAME="qdrant-meta-mcp"

# Check if container exists and is running
if container list | grep -q "$CONTAINER_NAME"; then
    IP=$(container inspect "$CONTAINER_NAME" 2>/dev/null | grep -o '"address":"[^"]*"' | sed 's/"address":"\([^\/]*\).*/\1/' | head -1)
    if [ -n "$IP" ]; then
        echo "$IP"
    else
        echo "Unable to get container IP" >&2
        exit 1
    fi
else
    echo "Container $CONTAINER_NAME is not running" >&2
    exit 1
fi