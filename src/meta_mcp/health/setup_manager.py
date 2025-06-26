"""System setup and initialization for Meta MCP Server."""

import asyncio
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from ..config.models import MetaMCPConfig
from ..utils.logging import get_logger


class SetupManager:
    """Manages system setup and initialization."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def create_directories(self, config: MetaMCPConfig) -> dict[str, bool]:
        """Create required directories.
        
        Args:
            config: Meta MCP configuration.
            
        Returns:
            Dict mapping directory paths to creation success.
        """
        required_dirs = [
            Path(config.logging.file).parent,
            Path(config.embeddings.cache_dir),
            Path("./docs"),
            Path("./logs") if not Path(config.logging.file).parent.exists() else None,
        ]

        # Filter out None values
        required_dirs = [d for d in required_dirs if d is not None]

        results = {}
        
        for dir_path in required_dirs:
            try:
                if not dir_path.exists():
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"Created directory: {dir_path}")
                    results[str(dir_path)] = True
                else:
                    results[str(dir_path)] = True
            except Exception as e:
                self.logger.error(f"Failed to create directory {dir_path}: {e}")
                results[str(dir_path)] = False

        return results

    async def initialize_qdrant_collections(self, config: MetaMCPConfig) -> dict[str, bool]:
        """Initialize Qdrant collections.
        
        Args:
            config: Meta MCP configuration.
            
        Returns:
            Dict mapping collection names to creation success.
        """
        results = {}
        
        try:
            # Create Qdrant client
            if config.vector_store.url:
                client = QdrantClient(url=config.vector_store.url)
            else:
                client = QdrantClient(
                    host=config.vector_store.host,
                    port=config.vector_store.port,
                )

            # Define collections to create
            collections = [
                {
                    "name": f"{config.vector_store.collection_prefix}_tools",
                    "vector_size": 384,  # Default for sentence-transformers
                    "distance": models.Distance.COSINE,
                },
                {
                    "name": f"{config.vector_store.collection_prefix}_docs",
                    "vector_size": 384,
                    "distance": models.Distance.COSINE,
                },
            ]

            # Create each collection
            for collection_config in collections:
                try:
                    collection_name = collection_config["name"]
                    
                    # Check if collection already exists
                    existing_collections = await asyncio.get_event_loop().run_in_executor(
                        None, client.get_collections
                    )
                    
                    collection_exists = any(
                        col.name == collection_name 
                        for col in existing_collections.collections
                    )
                    
                    if not collection_exists:
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: client.create_collection(
                                collection_name=collection_name,
                                vectors_config=models.VectorParams(
                                    size=collection_config["vector_size"],
                                    distance=collection_config["distance"],
                                ),
                            )
                        )
                        self.logger.info(f"Created Qdrant collection: {collection_name}")
                        results[collection_name] = True
                    else:
                        self.logger.info(f"Qdrant collection already exists: {collection_name}")
                        results[collection_name] = True
                        
                except Exception as e:
                    self.logger.error(f"Failed to create collection {collection_name}: {e}")
                    results[collection_name] = False

        except Exception as e:
            self.logger.error(f"Failed to initialize Qdrant collections: {e}")
            # Mark all collections as failed
            collection_names = [
                f"{config.vector_store.collection_prefix}_tools",
                f"{config.vector_store.collection_prefix}_docs",
            ]
            for name in collection_names:
                results[name] = False

        return results

    async def download_fallback_models(self, model_names: list[str], cache_dir: str) -> dict[str, bool]:
        """Download fallback embedding models.
        
        Args:
            model_names: List of model names to download.
            cache_dir: Directory to cache models.
            
        Returns:
            Dict mapping model names to download success.
        """
        results = {}
        
        try:
            # Import sentence-transformers here to avoid import errors if not installed
            from sentence_transformers import SentenceTransformer
            
            # Ensure cache directory exists
            cache_path = Path(cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)
            
            for model_name in model_names:
                try:
                    self.logger.info(f"Downloading model: {model_name}")
                    
                    # Download model (this will cache it automatically)
                    model = SentenceTransformer(model_name, cache_folder=str(cache_path))
                    
                    # Test the model with a simple encoding
                    test_embedding = model.encode(["test sentence"])
                    
                    if len(test_embedding) > 0 and len(test_embedding[0]) > 0:
                        self.logger.info(f"Successfully downloaded and tested model: {model_name}")
                        results[model_name] = True
                    else:
                        self.logger.error(f"Model download succeeded but test failed: {model_name}")
                        results[model_name] = False
                        
                except Exception as e:
                    self.logger.error(f"Failed to download model {model_name}: {e}")
                    results[model_name] = False
                    
        except ImportError:
            self.logger.error("sentence-transformers not installed, cannot download models")
            results = {name: False for name in model_names}
        except Exception as e:
            self.logger.error(f"Failed to download models: {e}")
            results = {name: False for name in model_names}

        return results

    async def create_example_config(self, output_path: str, include_examples: bool = True) -> bool:
        """Create an example configuration file.
        
        Args:
            output_path: Path to create the config file.
            include_examples: Include example child servers.
            
        Returns:
            True if config was created successfully.
        """
        try:
            from ..config.loader import save_config
            from ..config.models import ChildServerConfig
            
            # Create default config
            config = MetaMCPConfig()
            
            if include_examples:
                # Add some example child servers
                example_servers = [
                    ChildServerConfig(
                        name="filesystem-server",
                        command=["uvx", "mcp-server-filesystem", "--no-ignore-files"],
                        enabled=False,
                        documentation="Built-in filesystem operations server",
                        env={"HOME": "${HOME}"},
                    ),
                    ChildServerConfig(
                        name="git-server",
                        command=["uvx", "mcp-server-git"],
                        enabled=False,
                        documentation="Git operations server",
                    ),
                    ChildServerConfig(
                        name="sqlite-server",
                        command=["uvx", "mcp-server-sqlite", "--db-path", "./data.db"],
                        enabled=False,
                        documentation="SQLite database operations server",
                    ),
                ]
                config.child_servers = example_servers

            # Save configuration
            save_config(config, output_path)
            self.logger.info(f"Created example configuration: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create example config: {e}")
            return False

    async def verify_system_requirements(self) -> dict[str, Any]:
        """Verify system requirements are met.
        
        Returns:
            Dict with system requirement check results.
        """
        requirements = {
            "python_version": await self._check_python_version(),
            "disk_space": await self._check_disk_space(),
            "memory": await self._check_memory(),
            "network": await self._check_network_access(),
        }
        
        return requirements

    async def _check_python_version(self) -> dict[str, Any]:
        """Check Python version requirements."""
        import sys
        
        version = sys.version_info
        required_major, required_minor = 3, 11
        
        meets_requirement = (
            version.major > required_major or 
            (version.major == required_major and version.minor >= required_minor)
        )
        
        return {
            "current": f"{version.major}.{version.minor}.{version.micro}",
            "required": f"{required_major}.{required_minor}+",
            "meets_requirement": meets_requirement,
        }

    async def _check_disk_space(self) -> dict[str, Any]:
        """Check available disk space."""
        try:
            import shutil
            
            # Check space in current directory
            total, used, free = shutil.disk_usage(".")
            
            # Require at least 1GB free space
            required_bytes = 1024 * 1024 * 1024  # 1GB
            
            return {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "required_gb": 1.0,
                "meets_requirement": free >= required_bytes,
            }
        except Exception as e:
            return {
                "error": str(e),
                "meets_requirement": False,
            }

    async def _check_memory(self) -> dict[str, Any]:
        """Check available memory."""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            
            # Require at least 2GB total memory
            required_bytes = 2 * 1024 * 1024 * 1024  # 2GB
            
            return {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": memory.percent,
                "required_gb": 2.0,
                "meets_requirement": memory.total >= required_bytes,
            }
        except ImportError:
            return {
                "error": "psutil not available",
                "meets_requirement": True,  # Assume it's fine if we can't check
            }
        except Exception as e:
            return {
                "error": str(e),
                "meets_requirement": False,
            }

    async def _check_network_access(self) -> dict[str, Any]:
        """Check network access to common services."""
        import httpx
        
        test_urls = [
            "https://api.github.com",  # GitHub for packages
            "https://huggingface.co",  # HuggingFace for models
            "https://pypi.org",        # PyPI for packages
        ]
        
        results = {}
        overall_success = True
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in test_urls:
                try:
                    response = await client.get(url)
                    success = response.status_code < 400
                    results[url] = success
                    if not success:
                        overall_success = False
                except Exception:
                    results[url] = False
                    overall_success = False

        return {
            "test_results": results,
            "meets_requirement": overall_success,
        }

    async def run_setup_wizard(self, config_path: str = "meta-server.yaml") -> dict[str, Any]:
        """Run interactive setup wizard.
        
        Args:
            config_path: Path for the configuration file.
            
        Returns:
            Setup results.
        """
        setup_results = {
            "config_created": False,
            "directories_created": False,
            "collections_initialized": False,
            "models_downloaded": False,
            "overall_success": False,
        }
        
        try:
            # Create example configuration
            config_created = await self.create_example_config(config_path, include_examples=True)
            setup_results["config_created"] = config_created
            
            if config_created:
                # Load the created config
                from ..config.loader import load_config
                config = load_config(config_path)
                
                # Create directories
                dir_results = await self.create_directories(config)
                setup_results["directories_created"] = all(dir_results.values())
                
                # Try to initialize Qdrant collections (may fail if Qdrant not running)
                try:
                    collection_results = await self.initialize_qdrant_collections(config)
                    setup_results["collections_initialized"] = any(collection_results.values())
                except Exception:
                    setup_results["collections_initialized"] = False
                
                # Try to download fallback models
                try:
                    model_results = await self.download_fallback_models(
                        [config.embeddings.fallback_model],
                        config.embeddings.cache_dir
                    )
                    setup_results["models_downloaded"] = any(model_results.values())
                except Exception:
                    setup_results["models_downloaded"] = False
                
                # Overall success if config and directories are good
                setup_results["overall_success"] = (
                    setup_results["config_created"] and 
                    setup_results["directories_created"]
                )
                
        except Exception as e:
            self.logger.error(f"Setup wizard failed: {e}")
            setup_results["error"] = str(e)

        return setup_results