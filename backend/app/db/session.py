import logging
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

logger = logging.getLogger("bhashalive.db")

engine = None
async_session_factory = None

if settings.enable_persistence and settings.database_url:
    try:
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    except Exception as e:
        logger.warning(f"Could not initialize async DB engine: {e}")


async def get_db_session() -> AsyncGenerator[Optional[AsyncSession], None]:
    """Dependency that yields an async database session if configured."""
    if not async_session_factory:
        yield None
        return

    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
