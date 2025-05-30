
# =============================================================================
# app/config.py - Configuration and Environment Variables
# =============================================================================

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/chatbot_db"
    REDIS_URL: str = "redis://localhost:6379"
    
    # LLM Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    COHERE_API_KEY: str = ""
    
    # Vector Database
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: str = ""
    
    # Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # File Upload
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    UPLOAD_DIR: str = "uploads"
    
    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = "openai"
    MAX_TOKENS: int = 4000
    TEMPERATURE: float = 0.7
    
    # RAG Settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_RESULTS: int = 5
    SIMILARITY_THRESHOLD: float = 0.7
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()

