"""
Centralized configuration using Pydantic Settings.
All environment variables are loaded here.
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", description="API host")
    API_PORT: int = Field(default=8000, description="API port")
    API_RELOAD: bool = Field(default=False, description="Auto-reload on code changes")
    
    # Database Configuration
    DB_HOST: str = Field(default="postgres", description="PostgreSQL host")
    DB_PORT: int = Field(default=5432, description="PostgreSQL port")
    DB_NAME: str = Field(default="rag_enterprise", description="Database name")
    DB_USER: str = Field(default="raguser", description="Database user")
    DB_PASSWORD: str = Field(default="ragpassword", description="Database password")
    
    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection string."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Qdrant Configuration
    QDRANT_HOST: str = Field(default="qdrant", description="Qdrant host")
    QDRANT_PORT: int = Field(default=6333, description="Qdrant port")
    QDRANT_COLLECTION: str = Field(default="rag_documents", description="Qdrant collection name")
    
    # LLM Configuration
    LLM_PROVIDER: str = Field(default="openai", description="LLM provider: openai, perplexity, ollama")
    LLM_FALLBACK_PROVIDERS: str = Field(default="", description="Comma-separated fallback providers")
    LLM_MODEL: str = Field(default="gpt-4o", description="Default LLM model")
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    OPENAI_LLM_MODEL: str = Field(default="gpt-4o", description="OpenAI model")
    OPENAI_TEMPERATURE: float = Field(default=0.7, description="OpenAI temperature")
    OPENAI_MAX_RETRIES: int = Field(default=3, description="OpenAI max retries")
    OPENAI_TIMEOUT: int = Field(default=60, description="OpenAI timeout (seconds)")
    
    # Perplexity
    PERPLEXITY_API_KEY: Optional[str] = Field(default=None, description="Perplexity API key")
    PERPLEXITY_LLM_MODEL: str = Field(default="sonar-pro", description="Perplexity model")
    PERPLEXITY_TEMPERATURE: float = Field(default=0.7, description="Perplexity temperature")
    
    # Ollama (Local LLM)
    OLLAMA_HOST: str = Field(default="http://ollama:11434", description="Ollama host URL")
    OLLAMA_LLM_MODEL: str = Field(default="mistral", description="Ollama model")
    OLLAMA_TEMPERATURE: float = Field(default=0.7, description="Ollama temperature")
    OLLAMA_TIMEOUT: int = Field(default=120, description="Ollama timeout (seconds)")
    
    # Embeddings Configuration
    EMBEDDING_MODEL: str = Field(default="BAAI/bge-m3", description="Embedding model")
    EMBEDDING_DEVICE: str = Field(default="cpu", description="Device for embeddings: cpu, cuda")
    EMBEDDING_BATCH_SIZE: int = Field(default=16, description="Batch size for embeddings")
    
    # OCR Configuration
    OCR_ENGINE: str = Field(default="ocrmypdf", description="OCR engine: ocrmypdf, tika")
    OCR_SERVICE_HOST: str = Field(default="ocr-service", description="OCR service host")
    OCR_SERVICE_PORT: int = Field(default=5000, description="OCR service port")
    OCR_TIMEOUT: int = Field(default=1200, description="OCR timeout (seconds)")
    OCR_PARALLEL_WORKERS: int = Field(default=3, description="Max parallel OCR workers")
    
    # Chunking Configuration
    CHUNK_SIZE: int = Field(default=1000, description="Chunk size for text splitting")
    CHUNK_OVERLAP: int = Field(default=200, description="Chunk overlap")
    
    # Insights Configuration
    INSIGHTS_QUEUE_ENABLED: bool = Field(default=True, description="Enable insights queue")
    INSIGHTS_PARALLEL_WORKERS: int = Field(default=3, description="Max parallel insights workers")
    INSIGHTS_THROTTLE_SECONDS: int = Field(default=60, description="Throttle seconds for insights")
    INSIGHTS_MAX_RETRIES: int = Field(default=5, description="Max retries for insights")
    
    # Worker Configuration
    WORKER_POOL_SIZE: int = Field(default=25, description="Total worker pool size")
    WORKER_HEARTBEAT_INTERVAL: int = Field(default=30, description="Worker heartbeat interval (seconds)")
    
    # Scheduler Configuration
    MASTER_SCHEDULER_INTERVAL: int = Field(default=10, description="Master scheduler interval (seconds)")
    BACKUP_SCHEDULER_ENABLED: bool = Field(default=True, description="Enable backup scheduler")
    
    # JWT Configuration
    JWT_SECRET_KEY: str = Field(default="change-this-secret-key-in-production", description="JWT secret key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_EXPIRATION_HOURS: int = Field(default=24, description="JWT expiration (hours)")
    
    # Cache Configuration
    CACHE_TTL_DASHBOARD: int = Field(default=15, description="Cache TTL for dashboard (seconds)")
    CACHE_TTL_DOCUMENTS: int = Field(default=10, description="Cache TTL for documents (seconds)")
    
    # File Paths
    UPLOAD_DIR: str = Field(default="/app/uploads", description="Upload directory")
    INBOX_DIR: str = Field(default="/app/inbox", description="Inbox directory")
    PROCESSED_DIR: str = Field(default="/app/inbox/processed", description="Processed directory")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Helper functions
def get_llm_provider_order() -> List[str]:
    """Get LLM provider order from settings."""
    providers = [settings.LLM_PROVIDER]
    if settings.LLM_FALLBACK_PROVIDERS:
        providers.extend([p.strip() for p in settings.LLM_FALLBACK_PROVIDERS.split(",")])
    return providers


def get_database_url() -> str:
    """Get database URL."""
    return settings.database_url


def get_qdrant_url() -> str:
    """Get Qdrant URL."""
    return f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"


def is_gpu_available() -> bool:
    """Check if GPU is available."""
    return settings.EMBEDDING_DEVICE.lower() == "cuda"
