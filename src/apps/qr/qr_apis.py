from fastapi import APIRouter, Body, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from redis.asyncio import Redis
from typing import Optional
import qrcode
import io
import re
from urllib.parse import urlparse
import hashlib

from apps.shortener.models import ShortenedUrl
from apps.shortener.controllers import shortener_controller
from services.db import get_session

qr_router = APIRouter(prefix="/qr", tags=["QR"])

url_regex = re.compile(
    r"^(https?://)"                                   # http:// or https://
    r"(([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}|localhost|"      # domain or localhost
    r"127\.0\.0\.1)(:\d+)?(\/[^\s]*)?$"                # optional port and path
)


@qr_router.post(
    "/generate",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Returns QR image for any long URL",
        }
    }
)
async def generate_qr_from_long_url(url: str = Body(..., embed=True)):
    if not url_regex.match(url):
        raise HTTPException(status_code=400, detail="Invalid URL format")

    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    domain = (urlparse(url).hostname or "qr").split(".")[0]
    hash_suffix = hashlib.md5(url.encode()).hexdigest()[:6]
    filename = f"qr-{domain}-{hash_suffix}.png"

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"'
    }

    return StreamingResponse(buffer, media_type="image/png", headers=headers)


@qr_router.get(
    "/{short_code}",
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Returns QR image for shortened URL"
        },
        404: {"description": "Shortened URL not found"},
    },
)
async def generate_qr_from_short_code(
    short_code: str,
    domain: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
):
    normalized_domain = shortener_controller.normalize_domain(domain or "")

    result = await db.exec(select(ShortenedUrl).where(
        ShortenedUrl.short_url == short_code,
        ShortenedUrl.custom_domain == normalized_domain
    ))
    record = result.first()
    if not record:
        raise HTTPException(status_code=404, detail="Shortened URL not found")

    img = qrcode.make(record.main_url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    domain = (urlparse(record.main_url).hostname or "qr").split(".")[0]
    hash_suffix = hashlib.md5(record.main_url.encode()).hexdigest()[:6]
    filename = f"qr-{domain}-{hash_suffix}.png"

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"'
    }

    return StreamingResponse(buffer, media_type="image/png", headers=headers)
