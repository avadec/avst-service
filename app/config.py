"""
Configuration management for the transcriber service.
Loads settings from environment variables using Pydantic.
"""
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Redis configuration
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Callback configuration
    DEFAULT_CALLBACK_URL: Optional[str] = None
    CALLBACK_TIMEOUT_SECONDS: int = 30
    CALLBACK_RETRY_COUNT: int = 3
    CALLBACK_RETRY_DELAY_SECONDS: int = 3
    
    # Whisper STT configuration (GPU 0)
    WHISPER_MODEL: str = "large-v3"
    WHISPER_DEVICE: str = "cuda:0"
    WHISPER_COMPUTE_TYPE: str = "float16"
    
    # Future LLM configuration (GPU 1)
    LLM_DEVICE: str = "cuda:1"
    
    # Pipeline step toggles
    ENABLE_STT: bool = True
    ENABLE_SUMMARIZATION: bool = True
    ENABLE_CALLBACK: bool = True
    
    # Testing mode configuration
    TESTING_MODE: bool = False
    TESTING_LOG_FILE: str = "/app/testing_output.log"
    
    # Remote file download configuration
    TEMP_DOWNLOAD_DIR: str = "/tmp/audio_downloads"
    DOWNLOAD_TIMEOUT_SECONDS: int = 300  # 5 minutes for large files
    DOWNLOAD_CHUNK_SIZE: int = 8192  # 8KB chunks for streaming
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton settings instance
settings = Settings()
