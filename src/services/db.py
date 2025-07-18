from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

from core.config import database_config

# Main app DB engine (used by FastAPI APIs)
engine = create_async_engine(
    url=database_config.database_url,
    echo=database_config.echo,
    pool_size=database_config.pool_size,
    max_overflow=database_config.max_overflow,
)

Base = declarative_base()

# FastAPI dependency injection for routes
async def get_session() -> AsyncSession:
    session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session() as session:
        yield session

# Separate engine and session for bulk worker usage
bulk_engine = create_async_engine(
    url=database_config.database_url,
    echo=False,  # avoid printing during large jobs
    pool_size=5,
    max_overflow=10,
)

BulkSessionLocal = sessionmaker(
    bind=bulk_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# For Celery/standalone worker usage — returns AsyncSession directly
def get_bulk_session() -> AsyncSession:
    return BulkSessionLocal()
