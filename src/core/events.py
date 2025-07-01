from sqlmodel import SQLModel
from services.redis import redis_pool
from services.db import engine


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("✅ Database tables created successfully on startup!")
    
async def startup_event_handler() -> None:
    await init_db()


async def shutdown_event_handler() -> None:
    await redis_pool.disconnect()
    await engine.dispose()
