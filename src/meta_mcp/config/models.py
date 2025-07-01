"""Configuration models using Pydantic."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChildServerConfig(BaseModel):
    """Configuration for a child MCP server."""

    name: str = Field(..., description="Unique name for the server")
    command: list[str] = Field(..., description="Command to start the server")
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables"
    )
    documentation: str | None = Field(
        None, description="Path to documentation file for RAG"
    )
    enabled: bool = Field(True, description="Whether the server is enabled")


class EmbeddingConfig(BaseModel):
    """Configuration for embedding services."""

    lm_studio_endpoint: str | None = Field(
        None, description="LM Studio embeddings endpoint"
    )
    lm_studio_model: str = Field(
        "nomic-embed-text-v1.5", description="LM Studio embedding model name"
    )
    fallback_model: str = Field(
        "all-MiniLM-L6-v2", description="Local fallback embedding model"
    )
    batch_size: int = Field(32, description="Batch size for embedding generation")
    cache_dir: str = Field(
        "./embedding-models", description="Directory to cache models"
    )


class VectorStoreConfig(BaseModel):
    """Configuration for vector store."""

    type: str = Field("qdrant", description="Vector store type")
    host: str = Field("localhost", description="Vector store host")
    port: int = Field(6333, description="Vector store port")
    collection_prefix: str = Field("meta_mcp", description="Collection name prefix")
    url: str | None = Field(None, description="Full URL (overrides host:port)")


class LLMConfig(BaseModel):
    """Configuration for LLM service."""

    endpoint: str = Field("http://localhost:1234/v1", description="LLM API endpoint")
    model: str = Field("local-model", description="Model name")
    api_key: str | None = Field(None, description="API key if required")
    temperature: float = Field(0.3, description="Generation temperature")
    max_tokens: int = Field(1000, description="Maximum tokens in response")


class RAGConfig(BaseModel):
    """Configuration for RAG pipeline."""

    chunk_size: int = Field(500, description="Document chunk size")
    chunk_overlap: int = Field(50, description="Chunk overlap size")
    top_k: int = Field(5, description="Number of relevant docs to retrieve")
    score_threshold: float = Field(0.7, description="Relevance score threshold")
    include_examples: bool = Field(
        True, description="Include usage examples in context"
    )


class StrategyConfig(BaseModel):
    """Configuration for routing strategy."""

    primary: str = Field("vector", description="Primary routing strategy")
    fallback: str = Field("vector", description="Fallback routing strategy")
    vector_threshold: float = Field(0.4, description="Vector similarity threshold")
    max_tools: int = Field(10, description="Maximum tools to return")


class WebUIConfig(BaseModel):
    """Configuration for web UI."""

    enabled: bool = Field(True, description="Enable web UI")
    host: str = Field("localhost", description="Web UI host")
    port: int = Field(8080, description="Web UI port")
    auth_enabled: bool = Field(False, description="Enable authentication")
    username: str | None = Field(None, description="Auth username")
    password: str | None = Field(None, description="Auth password")


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field("INFO", description="Log level")
    file: str | None = Field("./logs/meta-server.log", description="Log file path")
    max_files: int = Field(5, description="Maximum log files to keep")
    max_size_mb: int = Field(10, description="Maximum log file size in MB")
    console: bool = Field(True, description="Enable console logging")


class ServerConfig(BaseModel):
    """Main server configuration."""

    name: str = Field("meta-mcp-server", description="Server name")
    port: int = Field(3456, description="Server port")
    host: str = Field("localhost", description="Server host")


class MetaMCPConfig(BaseModel):
    """Main configuration model."""

    server: ServerConfig = Field(default_factory=ServerConfig)
    web_ui: WebUIConfig = Field(default_factory=WebUIConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    embeddings: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Child servers are loaded separately from JSON config
    child_servers: list[ChildServerConfig] = Field(
        default_factory=list,
        description="List of child MCP servers (loaded from JSON config)",
        exclude=True,  # Exclude from YAML serialization
    )

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Tool(BaseModel):
    """Tool metadata model."""

    id: str = Field(..., description="Unique tool identifier")
    name: str = Field(..., description="Tool name")
    server_name: str = Field(..., description="Source server name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Tool parameters schema"
    )
    examples: list[str] = Field(default_factory=list, description="Usage examples")
    embedding: list[float] | None = Field(
        None, description="Tool description embedding"
    )
    usage_count: int = Field(0, description="Number of times tool has been used")
    last_used: str | None = Field(None, description="Last usage timestamp")


class Resource(BaseModel):
    """Resource metadata model."""

    uri: str = Field(..., description="Resource URI")
    name: str = Field(..., description="Resource name")
    server_name: str = Field(..., description="Source server name")
    description: str = Field(..., description="Resource description")
    mime_type: str | None = Field(None, description="MIME type")


class LogEntry(BaseModel):
    """Log entry model for web UI."""

    timestamp: str = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level")
    logger: str = Field(..., description="Logger name")
    message: str = Field(..., description="Log message")
    extra: dict[str, Any] = Field(default_factory=dict, description="Extra fields")


class MetricsData(BaseModel):
    """Metrics data model."""

    active_connections: int = Field(0, description="Active client connections")
    total_requests: int = Field(0, description="Total requests handled")
    avg_response_time: float = Field(0.0, description="Average response time (ms)")
    tool_usage: dict[str, int] = Field(
        default_factory=dict, description="Tool usage statistics"
    )
    strategy_usage: dict[str, int] = Field(
        default_factory=dict, description="Strategy usage statistics"
    )
    error_count: int = Field(0, description="Total error count")
    uptime_seconds: int = Field(0, description="Server uptime in seconds")
