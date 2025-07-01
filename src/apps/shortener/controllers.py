import random
import re
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse

from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
import pytz
import logging

from apps.shortener.schemas import ShortenUrlRequest, ShortenUrlResponse, UpdateShortenedUrlRequest
from apps.shortener.models import ShortenedUrl
from core.config import app_config
from sqlalchemy.exc import IntegrityError

from services.visit_service import visit_service

logger = logging.getLogger("uvicorn.error")

class ShortenerController:
    MAX_CACHE_TTL = 30 * 24 * 60 * 60

    def __init__(self):
        pass

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

    async def _get_record_and_validate(
        self,
        db: AsyncSession,
        short_url: str,
        domain: str
    ) -> ShortenedUrl:
        """Fetch URL record based on short_url and domain, raise 404 if not found."""
        domain = self.normalize_domain(domain)
        result = await db.exec(
            select(ShortenedUrl).where(
                ShortenedUrl.short_url == short_url,
                ShortenedUrl.custom_domain == domain
            )
        )
        record = result.first()
        if not record:
            raise HTTPException(status_code=404, detail="Record not found.")
        return record
    
    async def update_short_url(
        self,
        db: AsyncSession,
        short_code: str,
        payload: UpdateShortenedUrlRequest,
        redis: Redis,
    ):
        old_domain = self.normalize_domain(payload.old_domain)
        record = await self._get_record_and_validate(db, short_code, old_domain)

        new_slug = payload.new_slug or short_code
        new_domain = self.normalize_domain(payload.new_domain) if payload.new_domain else old_domain

        old_key = self.build_redis_key(old_domain, short_code)
        new_key = self.build_redis_key(new_domain, new_slug)
        main_url = record.main_url

        record.short_url = new_slug
        record.custom_domain = new_domain
        record.updated_at = datetime.utcnow()
        db.add(record)

        try:
            await db.commit()
            await redis.delete(old_key)
            await redis.set(new_key, main_url, ex=self.MAX_CACHE_TTL)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Slug and domain combination already exists."
            )

        return {
            "message": "Short URL updated successfully.",
            "new_slug": new_slug,
            "new_domain": new_domain,
        }


    # async def update_slug(self, db: AsyncSession, payload: UpdateSlugRequest, redis: Redis):
    #     domain = self.normalize_domain(payload.domain)
    #     record = await self._get_record_and_validate(db, payload.old_slug, domain)

    #     old_key = self.build_redis_key(domain, payload.old_slug)
    #     new_key = self.build_redis_key(domain, payload.new_slug)
    #     main_url = record.main_url

    #     record.short_url = payload.new_slug
    #     record.updated_at = datetime.utcnow()
    #     db.add(record)

    #     try:
    #         await db.commit()
    #         await redis.delete(old_key)
    #         await redis.set(new_key, main_url, ex=self.MAX_CACHE_TTL)
    #     except IntegrityError:
    #         await db.rollback()
    #         raise HTTPException(
    #             status_code=409,
    #             detail="Slug already in use for this domain."
    #         )

    #     return {"message": "Slug updated successfully."}

    # async def update_domain(self, db: AsyncSession, payload: UpdateDomainRequest, redis: Redis):
    #     old_domain = self.normalize_domain(payload.old_domain)
    #     new_domain = self.normalize_domain(payload.new_domain)
    #     record = await self._get_record_and_validate(db, payload.slug, old_domain)

    #     old_key = self.build_redis_key(old_domain, payload.slug)
    #     new_key = self.build_redis_key(new_domain, payload.slug)
    #     main_url = record.main_url

    #     record.custom_domain = new_domain
    #     record.updated_at = datetime.utcnow()
    #     db.add(record)

    #     try:
    #         await db.commit()
    #         await redis.delete(old_key)
    #         await redis.set(new_key, main_url, ex=self.MAX_CACHE_TTL)
    #     except IntegrityError:
    #         await db.rollback()
    #         raise HTTPException(
    #             status_code=409,
    #             detail="Slug already in use for this domain."
    #         )

    #     return {"message": "Domain updated successfully."}

    # async def update_slug_and_domain(self, db: AsyncSession, payload: UpdateSlugAndDomainRequest, redis: Redis):
    #     old_domain = self.normalize_domain(payload.old_domain)
    #     new_domain = self.normalize_domain(payload.new_domain)
    #     record = await self._get_record_and_validate(db, payload.old_slug, old_domain)

    #     old_key = self.build_redis_key(old_domain, payload.old_slug)
    #     new_key = self.build_redis_key(new_domain, payload.new_slug)
    #     main_url = record.main_url

    #     record.short_url = payload.new_slug
    #     record.custom_domain = new_domain
    #     record.updated_at = datetime.utcnow()
    #     db.add(record)

    #     try:
    #         await db.commit()
    #         await redis.delete(old_key)
    #         await redis.set(new_key, main_url, ex=self.MAX_CACHE_TTL)
    #     except IntegrityError:
    #         await db.rollback()
    #         raise HTTPException(
    #             status_code=409,
    #             detail="Slug and domain combination already exists."
    #         )

    #     return {"message": "Slug and domain updated successfully."}



    async def redirect_to_main_url(self, db: AsyncSession, redis: Redis, short_url: str, request: Request, domain: Optional[str]) -> RedirectResponse | JSONResponse:
        if domain:
            domain = self.normalize_domain(domain)
        else:
            raw_host = request.headers.get("host", "")
            domain = self.normalize_domain(raw_host)

        redis_key = self.build_redis_key(domain, short_url)

        # cached_url = await redis.get(redis_key)
        # if cached_url:
        #     return RedirectResponse(url=cached_url, status_code=302)

        result = await db.exec(select(ShortenedUrl).where(
            ShortenedUrl.short_url == short_url,
            ShortenedUrl.custom_domain == domain
        ))
        shortened_url = result.first()

        if not shortened_url:
            raise HTTPException(status_code=404, detail="Shortened URL not found")

        now = datetime.utcnow()
         
        # Check for expiry by click count
        if shortened_url.max_clicks and shortened_url.click_count >= shortened_url.max_clicks:
            await db.delete(shortened_url)
            await db.commit()
            await redis.delete(redis_key)
            raise HTTPException(status_code=404, detail="Shortened URL expired. Please upgrade to premium.")

        # Check for expiry by time
        if shortened_url.expires_at and shortened_url.expires_at < now:
            await db.delete(shortened_url)
            await db.commit()
            await redis.delete(redis_key)
            raise HTTPException(status_code=404, detail="Shortened URL expired. Please upgrade to premium.")
        
        # Increment click count
        shortened_url.click_count += 1
        shortened_url.updated_at = now
        db.add(shortened_url)
        await db.commit()

        if not await redis.get(redis_key):
            ttl = int((shortened_url.expires_at - now).total_seconds())
            ttl = min(ttl, self.MAX_CACHE_TTL)
            if ttl > 0:
                await redis.set(redis_key, shortened_url.main_url, ex=ttl)
                print(f"TTL for Redis key {redis_key} is {ttl} seconds")

        user_agent = request.headers.get("user-agent", "").lower()
        accept = request.headers.get("accept", "").lower()

        await visit_service.log_visit(
            db=db,
            request=request,
            short_code=shortened_url.short_url
        )
        

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
        # Perform actual redirection for browser
        return RedirectResponse(url=shortened_url.main_url, status_code=302)

shortener_controller = ShortenerController()