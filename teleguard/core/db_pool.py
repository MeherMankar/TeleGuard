"""Database connection pool and performance optimizations

This module is optional and depends on a SQL DATABASE_URL being set. If the
environment does not define DATABASE_URL, the pool will be a no-op so the
rest of the application (which mostly uses MongoDB) can function.
"""
import os
import asyncio
from typing import Optional
from .exceptions import DatabaseError

try:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import QueuePool
except Exception:
    async_sessionmaker = None  # type: ignore
    create_async_engine = None  # type: ignore

DATABASE_URL = os.getenv("DATABASE_URL")


class DatabasePool:
    def __init__(self):
        self.engine = None
        self.session_factory = None
        # Only create engine if DATABASE_URL is available and SQLAlchemy is installed
        if DATABASE_URL and create_async_engine is not None:
            try:
                self.engine = create_async_engine(
                    DATABASE_URL,
                    poolclass=QueuePool,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False,
                )
                self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
            except Exception:
                self.engine = None
                self.session_factory = None

    async def get_session(self):
        """Get database session (raises if SQL not configured)"""
        if self.session_factory is None:
            raise DatabaseError("SQL DATABASE_URL not configured or SQLAlchemy not available")
        try:
            return self.session_factory()
        except Exception as e:
            raise DatabaseError(f"Failed to create session: {e}")

    async def close(self):
        """Close database connections"""
        if self.engine is not None:
            await self.engine.dispose()


# Global pool instance (safe to import even when DATABASE_URL missing)
db_pool = DatabasePool()
