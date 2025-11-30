"""
Application configuration using pydantic-settings.
All settings can be overridden via environment variables or .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Dict, Any, Union
import os
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # ==========================================================================
    # Application
    # ==========================================================================
    APP_NAME: str = "ENSAM Cloud Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # ==========================================================================
    # Security - JWT
    # ==========================================================================
    SECRET_KEY: str = "change-this-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # ==========================================================================
    # Database
    # ==========================================================================
    DATABASE_URL: str = "sqlite:///./data/cloud_platform.db"
    
    # ==========================================================================
    # Docker
    # ==========================================================================
    DOCKER_IMAGE_CPU: str = "python:3.11-slim"
    DOCKER_IMAGE_GPU: str = "tensorflow/tensorflow:2.15.0-gpu"  # Pre-installed: Python + TensorFlow + CUDA + cuDNN
    DOCKER_NETWORK: str = "cloud-platform-network"
    MAX_CONCURRENT_JOBS: int = 5
    
    # ==========================================================================
    # Resource Profiles
    # ==========================================================================
    RESOURCE_PROFILES: Dict[str, Dict[str, Any]] = {
        "small": {"cpu_shares": 512, "memory_mb": 512, "timeout": 60},
        "medium": {"cpu_shares": 1024, "memory_mb": 2048, "timeout": 300},
        "large": {"cpu_shares": 2048, "memory_mb": 4096, "timeout": 900},
        "gpu": {"cpu_shares": 2048, "memory_mb": 6144, "timeout": 1800, "gpu": True}  # Reduced from 8192 to 6144 MB
    }
    
    # ==========================================================================
    # Storage Paths
    # ==========================================================================
    SCRIPTS_DIR: str = "./data/scripts"
    LOGS_DIR: str = "./data/logs"
    RESULTS_DIR: str = "./data/results"
    
    # ==========================================================================
    # CORS
    # Set to "*" in .env to allow all origins (for development/testing)
    # ==========================================================================
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8080",
        "http://192.168.128.43:8080"
    ]
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from env variable."""
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            # Split by comma and strip whitespace
            origins = [origin.strip() for origin in v.split(",") if origin.strip()]
            return origins if origins else ["*"]
        return v
    
    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # ==========================================================================
    # Metrics
    # ==========================================================================
    METRICS_ENABLED: bool = True
    METRICS_PREFIX: str = "ensam_cloud"
    
    # ==========================================================================
    # GPU
    # ==========================================================================
    GPU_ENABLED: bool = True
    
    # ==========================================================================
    # Logging
    # ==========================================================================
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()

# Ensure directories exist
for dir_path in [settings.SCRIPTS_DIR, settings.LOGS_DIR, settings.RESULTS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# Ensure data directory exists for SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)




