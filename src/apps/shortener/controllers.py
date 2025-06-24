import random
import re
import string
from fastapi.responses import RedirectResponse, JSONResponse
import pytz
from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta
from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.shortener.schemas import ShortenUrlRequest, ShortenUrlResponse
from apps.shortener.models import ShortenedUrl
from core.config import app_config


class ShortenerController:
    MAX_CACHE_TTL = 30 * 24 * 60 * 60  # 30 days in seconds

    @staticmethod
    def generate_random_characters(length: int) -> str:
        if length < 2:
            raise ValueError("Length must be at least 2 to include both letter and digit.")
        letters = string.ascii_letters
        digits = string.digits
        char_set = letters + digits
        code = [random.choice(letters), random.choice(digits)] + \
               [random.choice(char_set) for _ in range(length - 2)]
        random.shuffle(code)
        return ''.join(code)

    @staticmethod
    def utc_to_ist(utc_dt):
        ist = pytz.timezone("Asia/Kolkata")
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        return utc_dt.astimezone(ist)

    async def shorten(
        self, db: AsyncSession, payload: ShortenUrlRequest, redis: Redis
    ) -> ShortenUrlResponse:
        # Determine final domain (remove http/https and trailing slash)
        domain = (payload.custom_domain or app_config.default_domain).replace("http://", "").replace("https://", "").rstrip("/")
        
        if payload.custom_code:
            if not re.match(r'^[a-zA-Z0-9_-]{5,30}$', payload.custom_code):
                raise HTTPException(
                    status_code=400,
                    detail="Custom short code must be 5-30 characters and only use letters, digits, hyphens, or underscores."
                )

            # Check if code already exists for that domain
            statement = select(ShortenedUrl).where(
                ShortenedUrl.short_url == payload.custom_code,
                ShortenedUrl.custom_domain == domain
            )
            print("Requested short_url:", payload.custom_code)

            result = await db.exec(statement)
            existing_url = result.first()

            if existing_url:
                now = datetime.utcnow()
                is_time_expired = existing_url.expires_at and existing_url.expires_at < now
                is_clicks_expired = (
                    existing_url.max_clicks is not None and 
                    existing_url.click_count >= existing_url.max_clicks
                )

                if is_time_expired or is_clicks_expired:
                    await db.delete(existing_url)  # Deleted expired entry from DB
                    await db.commit()
                    await redis.delete(payload.custom_code)  # Deleted expired entry from Redis
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Custom short code already exists."
                    )

            short_url = payload.custom_code  # Reused custom short code
        else:
            while True:
                short_url = self.generate_random_characters(length=5)
                statement = select(ShortenedUrl).where(
                    ShortenedUrl.short_url == short_url,
                    ShortenedUrl.custom_domain == domain
                )
                result = await db.exec(statement)
                if not result.first():
                    break

        
        full_short_url = f"{domain}/{short_url}"
        now = datetime.utcnow()
           


        # Calculate expiry
        duration = payload.duration_value
        unit = payload.duration_unit

        if unit == "minutes":
            expires_at = now + timedelta(minutes=duration)
        elif unit == "hours":
            expires_at = now + timedelta(hours=duration)
        elif unit == "days":
            expires_at = now + timedelta(days=duration)
        elif unit == "months":
            expires_at = now + timedelta(days=duration * 30)
        elif unit == "years":
            expires_at = now + timedelta(days=duration * 365)
        else:
            raise ValueError("Unsupported duration unit")

        shortened_url = ShortenedUrl(
            main_url=payload.main_url,
            short_url=short_url,
            custom_domain=domain,
            max_clicks=payload.max_clicks,
            created_at=now,
            updated_at=now,
            expires_at=expires_at
        )
        db.add(shortened_url)
        await db.commit()

        return ShortenUrlResponse(
            main_url=payload.main_url,
            short_url=short_url,
            custom_domain=domain,
            max_clicks=payload.max_clicks,
            created_at=self.utc_to_ist(shortened_url.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            updated_at=self.utc_to_ist(shortened_url.updated_at).strftime("%Y-%m-%d %H:%M:%S"),
            expires_at=self.utc_to_ist(shortened_url.expires_at).strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def redirect_to_main_url(
        self, db: AsyncSession, redis: Redis, short_url: str, request: Request
    ) -> RedirectResponse | JSONResponse:
        # Get domain from request
        host = request.headers.get("host", "").replace("http://", "").replace("https://", "").rstrip("/")
        redis_key = f"{short_url}"

                
            # Always fetch from DB first to ensure click count can be updated
        statement = select(ShortenedUrl).where(
            ShortenedUrl.short_url == short_url,
            ShortenedUrl.custom_domain == host
        )
        result = await db.exec(statement)
        shortened_url = result.first()

        # If no URL found
        if not shortened_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shortened URL not found",
            )
        now = datetime.utcnow()

        # Click limit check
        if shortened_url.max_clicks and shortened_url.max_clicks > 0:
            if shortened_url.click_count >= shortened_url.max_clicks:
                await db.delete(shortened_url)  # Deleted expired (click limit) from DB
                await db.commit()
                await redis.delete(short_url)  # Deleted expired (click limit) from Redis
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Shortened URL has expired (click limit reached)",
                )

        if shortened_url.expires_at and shortened_url.expires_at < now:
            await db.delete(shortened_url)  # Deleted expired (time limit) from DB
            await db.commit()
            await redis.delete(short_url)  # Deleted expired (time limit) from Redis
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shortened URL has expired",
            )
        
        # Increment click count
        shortened_url.click_count += 1
        shortened_url.updated_at = datetime.utcnow()
        db.add(shortened_url)
        await db.commit()

        # Cache
        if not await redis.get(redis_key):
            ttl = int((shortened_url.expires_at - now).total_seconds())
            ttl = min(ttl, self.MAX_CACHE_TTL)
            if ttl > 0:
                await redis.set(redis_key, shortened_url.main_url, ex=ttl)
        user_agent = request.headers.get("user-agent", "").lower()
        accept = request.headers.get("accept", "").lower()

        is_swagger = "swagger" in user_agent or "json" in accept
        if is_swagger:
            return JSONResponse(
                status_code=200,
                content={
                    "details": {
                        "message": "Redirection successful.",
                        "redirect_to": shortened_url.main_url,
                        "short_code": shortened_url.short_url,
                        "domain": host
                    },
                    "status_code": 200
                }
            )
        return RedirectResponse(url=shortened_url.main_url, status_code=302)


shortener_controller = ShortenerController()