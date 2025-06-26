"""Pytest configuration and shared fixtures."""

import asyncio
import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    original_env = os.environ.copy()

    # Set test environment variables
    test_env = {
        "TEST_VAR": "test_value",
        "LM_STUDIO_ENDPOINT": "http://localhost:1234",
        "QDRANT_URL": "http://localhost:6333",
    }

    os.environ.update(test_env)

    yield test_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def sample_config_file(temp_dir) -> Path:
    """Create a sample configuration file for testing."""
    config_content = """
server:
  name: "test-meta-mcp-server"
  host: "127.0.0.1"
  port: 3456

strategy:
  primary: "vector"
  fallback: "llm"
  max_tools: 5

child_servers:
  - name: "test-server"
    command: ["python", "-m", "test_server"]
    enabled: true
    documentation: "docs/test-server.md"
    env:
      TEST_ENV: "value"

embeddings:
  lm_studio_endpoint: "http://localhost:1234"
  use_lm_studio: true
  fallback_model: "all-MiniLM-L6-v2"

vector_store:
  qdrant_url: "http://localhost:6333"
  collection_name: "test_tools"

llm:
  lm_studio_endpoint: "http://localhost:1234"
  model_name: "test-model"
  temperature: 0.7

rag:
  chunk_size: 500
  chunk_overlap: 50
  top_k: 5
  score_threshold: 0.7

web_ui:
  enabled: true
  host: "127.0.0.1"
  port: 8080
"""

    config_file = temp_dir / "test-config.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def sample_docs_dir(temp_dir) -> Path:
    """Create sample documentation directory."""
    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()

    # Create sample documentation files
    test_server_doc = docs_dir / "test-server.md"
    test_server_doc.write_text("""
# Test Server Documentation

## Overview
This is a test server for file operations.

## Tools

### read_file
Reads a file from the filesystem.

**Parameters:**
- path (string): Path to the file to read
- encoding (string, optional): File encoding, defaults to utf-8

**Example:**
```json
{
  "path": "/home/user/document.txt",
  "encoding": "utf-8"
}
```

### write_file
Writes content to a file.

**Parameters:**
- path (string): Path where to write the file
- content (string): Content to write
- mode (string, optional): Write mode, defaults to 'w'

## Error Handling
The server returns appropriate error codes for:
- File not found (404)
- Permission denied (403)
- Invalid parameters (400)
    """)

    web_server_doc = docs_dir / "web-server.md"
    web_server_doc.write_text("""
# Web Server Documentation

## Overview
Web scraping and HTTP request tools.

## Tools

### fetch_url
Fetches content from a URL.

**Parameters:**
- url (string): URL to fetch
- method (string, optional): HTTP method, defaults to GET
- headers (object, optional): HTTP headers

### search_web
Searches the web using a search engine.

**Parameters:**
- query (string): Search query
- limit (integer, optional): Number of results, defaults to 10
    """)

    return docs_dir


# Async test helpers
async def async_mock_context_manager(*args, **kwargs):
    """Helper for mocking async context managers."""
    return AsyncContextManagerMock()


class AsyncContextManagerMock:
    """Mock async context manager."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# Test markers for async support
pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="function")
def anyio_backend():
    """Use asyncio backend for async tests."""
    return "asyncio"
