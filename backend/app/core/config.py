"""
Application configuration settings.
Uses pydantic-settings for environment variable management.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "JaguarMed Private Cloud"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # JWT Configuration
    SECRET_KEY: str = "your-super-secret-key-change-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Database
    DATABASE_URL: str = "sqlite:///./jaguarmed.db"
    # For PostgreSQL: "postgresql://user:password@localhost:5432/jaguarmed"
    
    # Docker Configuration
    DOCKER_IMAGE_CPU: str = "python:3.11-slim"
    DOCKER_IMAGE_GPU: str = "nvidia/cuda:12.0-runtime-ubuntu22.04"
    DOCKER_NETWORK: str = "jaguarmed-network"
    
    # Resource Profiles (CPU shares, Memory limit in MB, Timeout in seconds)
    RESOURCE_PROFILES: dict = {
        "small": {"cpu_shares": 512, "memory_mb": 512, "timeout": 60},
        "medium": {"cpu_shares": 1024, "memory_mb": 2048, "timeout": 300},
        "large": {"cpu_shares": 2048, "memory_mb": 4096, "timeout": 900}
    }
    
    # Paths
    SCRIPTS_DIR: str = "./scripts"
    LOGS_DIR: str = "./logs"
    RESULTS_DIR: str = "./results"
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:4200", "http://localhost:8000", "http://127.0.0.1:4200"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.SCRIPTS_DIR, exist_ok=True)
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs(settings.RESULTS_DIR, exist_ok=True)








