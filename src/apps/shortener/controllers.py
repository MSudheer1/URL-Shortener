import random
import string
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
        self, db: AsyncSession, payload: ShortenUrlRequest
    ) -> ShortenUrlResponse:
        short_url = self.generate_random_characters(length=5)

        domain = (payload.custom_domain or app_config.default_domain).replace("http://", "").replace("https://", "").rstrip("/")
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
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        db.add(shortened_url)
        await db.commit()

        return ShortenUrlResponse(
            main_url=payload.main_url,
            short_url=short_url,
            custom_domain=domain,
            created_at=self.utc_to_ist(shortened_url.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            updated_at=self.utc_to_ist(shortened_url.updated_at).strftime("%Y-%m-%d %H:%M:%S"),
            expires_at=self.utc_to_ist(shortened_url.expires_at).strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def redirect_to_main_url(
        self, db: AsyncSession, redis: Redis, short_url: str, request: Request
    ) -> str:
        # Get domain from request
        host = request.headers.get("host", "").replace("http://", "").replace("https://", "").rstrip("/")
        redis_key = f"{host}/{short_url}"

        # Try Redis cache first
        cached_url = await redis.get(redis_key)
        if cached_url:
            return cached_url

        # Fallback to DB
        statement = select(ShortenedUrl).where(
            ShortenedUrl.short_url == short_url,
            ShortenedUrl.expired == False,
            ShortenedUrl.active == True,
            (ShortenedUrl.custom_domain == host) |
            (ShortenedUrl.custom_domain == '') |
            (ShortenedUrl.custom_domain.is_(None))
        )
        results = await db.exec(statement)
        shortened_url = results.first()

        if not shortened_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shortened URL not found",
            )

        # Check expiration
        if shortened_url.expires_at and shortened_url.expires_at < datetime.utcnow():
            shortened_url.expired = True
            shortened_url.updated_at = datetime.utcnow()
            db.add(shortened_url)
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shortened URL has expired",
            )

        # Cache if valid
        main_url = shortened_url.main_url
        if main_url:
            ttl = int((shortened_url.expires_at - datetime.utcnow()).total_seconds())
            ttl = min(ttl, self.MAX_CACHE_TTL)
            if ttl > 0:
                await redis.set(
                    name=redis_key,
                    value=main_url,
                    ex=ttl
                )

        return main_url


shortener_controller = ShortenerController()
