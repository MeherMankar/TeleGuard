"""Database connection pool and performance optimizations"""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import QueuePool

from .config import DATABASE_URL
from .exceptions import DatabaseError


class DatabasePool:
    def __init__(self):
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

    async def get_session(self):
        """Get database session"""
        try:
            return self.session_factory()
        except Exception as e:
            raise DatabaseError(f"Failed to create session: {e}")

    async def close(self):
        """Close database connections"""
        await self.engine.dispose()


# Global pool instance
db_pool = DatabasePool()
