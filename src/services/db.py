from sqlmodel.ext.asyncio.session import AsyncSession

from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from core.config import database_config
from sqlalchemy.orm import declarative_base

engine = create_async_engine(
    url=database_config.database_url,
    echo=database_config.echo,
    pool_size=database_config.pool_size,
    max_overflow=database_config.max_overflow,
)

Base = declarative_base()

async def get_session() -> AsyncSession:
    session = sessionmaker(  # noqa
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session() as session:
        yield session
