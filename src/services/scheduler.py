from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from sqlmodel import select
from services.db import get_session
from services.redis import get_redis
from apps.shortener.models import ShortenedUrl
from apps.shortener.controllers import shortener_controller

scheduler = AsyncIOScheduler()

async def cleanup_expired_urls():
    async with get_session() as db:
        async with get_redis() as redis:
            now = datetime.utcnow()
            result = await db.exec(select(ShortenedUrl).where(ShortenedUrl.expires_at < now))
            expired_urls = result.all()

            for url in expired_urls:
                redis_key = shortener_controller.build_redis_key(url.custom_domain, url.short_url)
                await redis.delete(redis_key)
                await db.delete(url)
            
            await db.commit()
            print(f"[Scheduler] Deleted {len(expired_urls)} expired records at {now}")

def start_scheduler():
    scheduler.add_job(cleanup_expired_urls, "interval", hours=1)
    scheduler.start()
