# app/config.py

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database connection string
    database_url: str

    # Redis connection string
    redis_url: str

    # Optional API key (can be empty for now)
    groq_api_key: Optional[str] = None

    groq_model: str = "llama-3.3-70b-versatile"
    # Default embedding model
    embedding_model: str = "all-MiniLM-L6-v2"





    class Config:
        # Tells Pydantic where to read environment variables from
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a single global settings object
settings = Settings()