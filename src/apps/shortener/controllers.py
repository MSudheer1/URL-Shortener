import logging
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from redis.asyncio import Redis
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.shortener.schemas import (
    ShortenUrlRequest,
    ShortenUrlResponse,
    UpdateDestinationRequest,
    UpdateShortenedUrlRequest,
    UpdateUrlSettingsRequest,
)
from apps.shortener.models import ShortenedUrl, User
from core.config import app_config
from services.visit_service import visit_service
from sqlalchemy.exc import IntegrityError
from utils.validators import Validator

logger = logging.getLogger("uvicorn.error")


class ShortenerController:
    MAX_CACHE_TTL = 30 * 24 * 60 * 60
    MAX_ATTEMPTS = 3
    BLOCK_TIME_SECONDS = 600  # 10 minutes

    def __init__(self):
        pass

    async def shorten(
        self,
        db: AsyncSession,
        payload: ShortenUrlRequest,
        redis: Redis,
        current_user: str,
        max_clicks: Optional[int] = 5,
        expiry: Optional[str] = "1h"
    ) -> ShortenUrlResponse:
        if payload.custom_domain:
            Validator.validate_domain(payload.custom_domain)

        domain = Validator.normalize_domain(payload.custom_domain or app_config.default_domain)
        short_url = payload.custom_slug or Validator.generate_random_characters(length=5)

        if payload.custom_slug:
            Validator.validate_slug(payload.custom_slug)

        while True:
            result = await db.exec(select(ShortenedUrl).where(
                ShortenedUrl.short_url == short_url,
                ShortenedUrl.custom_domain == domain
            ))
            if not result.first():
                break
            if not payload.custom_slug:
                short_url = Validator.generate_random_characters(length=5)
            else:
                raise HTTPException(status_code=409, detail="Custom slug already exists for this domain")

        now = datetime.utcnow()
        try:
            expires_at = now + Validator.parse_duration_string(expiry)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid expiry string format")

        user_result = await db.exec(select(User).where(User.email == current_user))
        user = user_result.first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        password_hash = None
        if payload.password:
            Validator.validate_password_strength(payload.password)
            password_hash = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()

        shortened_url = ShortenedUrl(
            main_url=payload.main_url,
            short_url=short_url,
            custom_domain=domain,
            max_clicks=max_clicks or 5,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            owner_email=current_user,
            password_hash=password_hash,
            title=payload.title
        )
        db.add(shortened_url)
        await db.commit()

        return ShortenUrlResponse(
            main_url=payload.main_url,
            short_url=f"{Validator.ensure_http_prefix(domain).rstrip('/')}/{short_url}",
            custom_domain=domain,
            max_clicks=max_clicks or 5,
            created_at=Validator.utc_to_ist(now).strftime("%Y-%m-%d %H:%M:%S"),
            updated_at=Validator.utc_to_ist(now).strftime("%Y-%m-%d %H:%M:%S"),
            expires_at=Validator.utc_to_ist(expires_at).strftime("%Y-%m-%d %H:%M:%S"),
        )

    async def _get_record_and_validate(self, db: AsyncSession, short_url: str, domain: str) -> ShortenedUrl:
        domain = Validator.normalize_domain(domain)
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
        user_email: str
    ):
        old_domain = Validator.normalize_domain(payload.old_domain)
        record = await self._get_record_and_validate(db, short_code, old_domain)

        Validator.ensure_owner_permission(record, user_email)

        new_slug = payload.new_slug or short_code
        new_domain = Validator.normalize_domain(payload.new_domain) if payload.new_domain else old_domain

        if payload.new_slug:
            Validator.validate_slug(payload.new_slug)
        if payload.new_domain:
            Validator.validate_domain(payload.new_domain)

        old_key = Validator.build_redis_key(old_domain, short_code)
        new_key = Validator.build_redis_key(new_domain, new_slug)
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

    async def redirect_to_main_url(
        self,
        db: AsyncSession,
        redis: Redis,
        short_url: str,
        request: Request,
        domain: Optional[str] = None,
        password: Optional[str] = None
    ) -> RedirectResponse | JSONResponse:
        domain = Validator.normalize_domain(domain or request.headers.get("host", ""))

        redis_key = Validator.build_redis_key(domain, short_url)
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
            raise HTTPException(status_code=404, detail="Shortened URL expired. Please upgrade to premium.")

        if shortened_url.expires_at and shortened_url.expires_at < now:
            await db.delete(shortened_url)
            await db.commit()
            await redis.delete(redis_key)
            raise HTTPException(status_code=404, detail="Shortened URL expired. Please upgrade to premium.")

        if shortened_url.password_hash:
            ip_address = request.client.host
            fail_key = f"fail:{short_url}:{ip_address}"
            fail_count = await redis.get(fail_key)

            if fail_count and int(fail_count) >= self.MAX_ATTEMPTS:
                raise HTTPException(status_code=429, detail="Too many failed attempts. Please try again later.")

            if not password or not bcrypt.checkpw(password.encode(), shortened_url.password_hash.encode()):
                await redis.incr(fail_key)
                await redis.expire(fail_key, self.BLOCK_TIME_SECONDS)
                raise HTTPException(status_code=401, detail="Password required or incorrect")

            await redis.delete(fail_key)

        shortened_url.click_count += 1
        shortened_url.updated_at = now
        db.add(shortened_url)
        await db.commit()

        if not await redis.get(redis_key):
            ttl = int((shortened_url.expires_at - now).total_seconds())
            await redis.set(redis_key, shortened_url.main_url, ex=min(ttl, self.MAX_CACHE_TTL))

        await visit_service.log_visit(db=db, request=request, short_code=shortened_url.short_url)

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

    async def update_main_url(
        self,
        db: AsyncSession,
        redis: Redis,
        short_code: str,
        domain: Optional[str],
        payload: UpdateDestinationRequest,
        user_email: str
    ):
        domain = Validator.normalize_domain(domain)
        Validator.validate_http_url(str(payload.new_url))

        record = await self._get_record_and_validate(db, short_code, domain)
        Validator.ensure_owner_permission(record, user_email)

        record.main_url = str(payload.new_url)
        record.updated_at = datetime.utcnow()
        db.add(record)

        try:
            await db.commit()
            redis_key = Validator.build_redis_key(domain, short_code)
            await redis.set(redis_key, str(payload.new_url), ex=self.MAX_CACHE_TTL)
        except Exception:
            await db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update main URL")

        return {"message": "Main URL updated successfully"}

    async def update_url_settings(
        self,
        db: AsyncSession,
        redis: Redis,
        short_code: str,
        domain: Optional[str],
        payload: UpdateUrlSettingsRequest,
        user_email: str
    ):
        domain = Validator.normalize_domain(domain or app_config.default_domain)
        record = await self._get_record_and_validate(db, short_code, domain)
        Validator.ensure_owner_permission(record, user_email)

        if payload.expiry:
            delta = Validator.parse_duration_string(payload.expiry)
            record.expires_at = datetime.utcnow() + delta

        if payload.max_clicks is not None:
            record.max_clicks = payload.max_clicks

        if payload.password is not None:
            if payload.password == "":
                record.password_hash = None
            else:
                Validator.validate_password_strength(payload.password)
                record.password_hash = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()

        record.updated_at = datetime.utcnow()
        db.add(record)
        await db.commit()

        redis_key = Validator.build_redis_key(domain, short_code)
        await redis.set(redis_key, record.main_url, ex=self.MAX_CACHE_TTL)

        return {"message": "Short URL settings updated successfully"}


# ✅ Create instance
shortener_controller = ShortenerController()
