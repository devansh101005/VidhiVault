from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import declarative_base

from app.config import settings


# Database Engine
engine = create_async_engine(
    settings.database_url, # gets from .env 
    echo=False,          # set True only for debugging SQL queries
    pool_size=10,       # max persistant connections 
    max_overflow=20,      # extra burst connection 
)


# Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base (for models)
Base = declarative_base()

# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()