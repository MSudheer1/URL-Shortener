import random
import re
import string
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse

from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
import pytz
import logging

from apps.shortener.schemas import ShortenUrlRequest, ShortenUrlResponse, UpdateSlugRequest, UpdateDomainRequest, UpdateSlugAndDomainRequest
from apps.shortener.models import ShortenedUrl
from core.config import app_config
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("uvicorn.error")

class ShortenerController:
    MAX_CACHE_TTL = 30 * 24 * 60 * 60

    @staticmethod
    def generate_random_characters(length: int) -> str:
        if length < 2:
            raise ValueError("Length must be at least 2 to include both letter and digit.")
        char_set = string.ascii_letters + string.digits
        code = [random.choice(string.ascii_letters), random.choice(string.digits)]
        code += [random.choice(char_set) for _ in range(length - 2)]
        random.shuffle(code)
        return ''.join(code)

    @staticmethod
    def utc_to_ist(utc_dt):
        ist = pytz.timezone("Asia/Kolkata")
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        return utc_dt.astimezone(ist)

    @staticmethod
    def build_redis_key(domain: str, short_code: str) -> str:
        clean_domain = domain.replace("http://", "").replace("https://", "").rstrip("/").lower()
        return f"{clean_domain}:{short_code}"

    @staticmethod
    def normalize_domain(domain: str) -> str:
        return domain.replace("http://", "").replace("https://", "").split(":")[0].strip().lower()

    @staticmethod
    def ensure_http_prefix(url: str) -> str:
        if not url.startswith("http://") and not url.startswith("https://"):
            return f"https://{url}"
        return url

    async def shorten(self, db: AsyncSession, payload: ShortenUrlRequest, redis: Redis) -> ShortenUrlResponse:
        domain = self.normalize_domain(app_config.default_domain)

        while True:
            short_url = self.generate_random_characters(length=5)
            result = await db.exec(select(ShortenedUrl).where(
                ShortenedUrl.short_url == short_url,
                ShortenedUrl.custom_domain == domain
            ))
            if not result.first():
                break

        max_clicks = 5
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=1)

        shortened_url = ShortenedUrl(
            main_url=payload.main_url,
            short_url=short_url,
            custom_domain=domain,
            max_clicks=max_clicks,
            created_at=now,
            updated_at=now,
            expires_at=expires_at
        )
        db.add(shortened_url)
        await db.commit()

        return ShortenUrlResponse(
            main_url=payload.main_url,
            short_url=f"{self.ensure_http_prefix(app_config.default_domain).rstrip('/')}/{short_url}",
            custom_domain=domain,
            max_clicks=max_clicks,
            created_at=self.utc_to_ist(now).strftime("%Y-%m-%d %H:%M:%S"),
            updated_at=self.utc_to_ist(now).strftime("%Y-%m-%d %H:%M:%S"),
            expires_at=self.utc_to_ist(expires_at).strftime("%Y-%m-%d %H:%M:%S"),
        )

    

    async def update_slug(self, db: AsyncSession, payload: UpdateSlugRequest):
        domain = self.normalize_domain(payload.domain)
        result = await db.exec(select(ShortenedUrl).where(
            ShortenedUrl.short_url == payload.old_slug,
            ShortenedUrl.custom_domain == domain
        ))
        record = result.first()
        if not record:
            raise HTTPException(status_code=404, detail="Record not found.")

        record.short_url = payload.new_slug
        record.updated_at = datetime.utcnow()
        db.add(record)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Slug already in use for this domain."
            )

        return {"message": "Slug updated successfully."}


    async def update_domain(self, db: AsyncSession, payload: UpdateDomainRequest):
        result = await db.exec(select(ShortenedUrl).where(
            ShortenedUrl.short_url == payload.slug,
            ShortenedUrl.custom_domain == self.normalize_domain(payload.old_domain)
        ))
        record = result.first()
        if not record:
            raise HTTPException(status_code=404, detail="Record not found.")

        record.custom_domain = self.normalize_domain(payload.new_domain)
        record.updated_at = datetime.utcnow()
        db.add(record)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Slug already in use for this domain."
            )

        return {"message": "Domain updated successfully."}


    async def update_slug_and_domain(self, db: AsyncSession, payload: UpdateSlugAndDomainRequest):
        result = await db.exec(select(ShortenedUrl).where(
            ShortenedUrl.short_url == payload.old_slug,
            ShortenedUrl.custom_domain == self.normalize_domain(payload.old_domain)
        ))
        record = result.first()
        if not record:
            raise HTTPException(status_code=404, detail="Record not found.")

        record.short_url = payload.new_slug
        record.custom_domain = self.normalize_domain(payload.new_domain)
        record.updated_at = datetime.utcnow()
        db.add(record)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Slug and domain combination already exists."
            )

        return {"message": "Slug and domain updated successfully."}


    async def redirect_to_main_url(self, db: AsyncSession, redis: Redis, short_url: str, request: Request) -> RedirectResponse | JSONResponse:
        raw_host = request.headers.get("host", "")
        domain = self.normalize_domain(raw_host)
        redis_key = self.build_redis_key(domain, short_url)

        cached_url = await redis.get(redis_key)
        if cached_url:
            return RedirectResponse(url=cached_url, status_code=302)

        result = await db.exec(select(ShortenedUrl).where(
            ShortenedUrl.short_url == short_url,
            ShortenedUrl.custom_domain == domain
        ))
        shortened_url = result.first()

        if not shortened_url:
            raise HTTPException(status_code=404, detail="Shortened URL not found")

        now = datetime.utcnow()

        if shortened_url.max_clicks and shortened_url.click_count >= shortened_url.max_clicks:
            await db.delete(shortened_url)
            await db.commit()
            await redis.delete(redis_key)
            raise HTTPException(status_code=404, detail="Shortened URL expired (click limit)")

        if shortened_url.expires_at and shortened_url.expires_at < now:
            await db.delete(shortened_url)
            await db.commit()
            await redis.delete(redis_key)
            raise HTTPException(status_code=404, detail="Shortened URL expired")

        shortened_url.click_count += 1
        shortened_url.updated_at = now
        db.add(shortened_url)
        await db.commit()

        if not await redis.get(redis_key):
            ttl = int((shortened_url.expires_at - now).total_seconds())
            ttl = min(ttl, self.MAX_CACHE_TTL)
            if ttl > 0:
                await redis.set(redis_key, shortened_url.main_url, ex=ttl)

        user_agent = request.headers.get("user-agent", "").lower()
        accept = request.headers.get("accept", "").lower()
        if "swagger" in user_agent or "json" in accept:
            return JSONResponse(
                status_code=200,
                content={
                    "details": {
                        "message": "Redirection successful.",
                        "redirect_to": shortened_url.main_url,
                        "short_code": shortened_url.short_url,
                        "domain": domain
                    },
                    "status_code": 200
                }
            )

        return RedirectResponse(url=shortened_url.main_url, status_code=302)

shortener_controller = ShortenerController()