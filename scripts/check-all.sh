#!/bin/bash
# Run all quality checks for mcp-router

set -e

echo "🔍 Running all quality checks..."

echo "📝 Formatting code..."
uv run ruff format src/ tests/

echo "🔧 Linting and fixing..."
uv run ruff check src/ tests/ --fix

echo "🔍 Type checking..."
uv run mypy src/

echo "🧪 Running tests..."
uv run pytest

echo "✅ All checks passed!"
