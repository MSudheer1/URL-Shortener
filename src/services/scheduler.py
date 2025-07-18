from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from sqlmodel import select
from services.db import get_session
from services.redis import get_redis
from apps.shortener.models import ShortenedUrl
from utils.validators import Validator

scheduler = AsyncIOScheduler()

async def cleanup_expired_urls():
    # Correctly handle get_session() as an async generator
    session_gen = get_session()
    db = await anext(session_gen)

    # Just await this since get_redis is a coroutine
    redis = await get_redis()

    try:
        now = datetime.utcnow()
        result = await db.exec(select(ShortenedUrl).where(ShortenedUrl.expires_at < now))
        expired_urls = result.all()

        for url in expired_urls:
            redis_key = Validator.build_redis_key(url.custom_domain, url.short_url)
            await redis.delete(redis_key)
            await db.delete(url)

        await db.commit()
        print(f"[Scheduler] Deleted {len(expired_urls)} expired records at {now}")

    finally:
        await session_gen.aclose()

def start_scheduler():
    scheduler.add_job(
        cleanup_expired_urls,
        "interval",
        hours=1,
        next_run_time=datetime.utcnow()
    )
    scheduler.start()