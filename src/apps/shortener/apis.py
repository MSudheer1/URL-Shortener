from redis.asyncio import Redis
from fastapi import Request, APIRouter, Depends, status, HTTPException 
from sqlmodel.ext.asyncio.session import AsyncSession

from fastapi.responses import RedirectResponse, JSONResponse

from apps.shortener.schemas import ShortenUrlRequest, ShortenUrlResponse
from apps.shortener.controllers import shortener_controller

from services.db import get_session
from services.redis import get_redis

from sqlmodel import select
from apps.shortener.models import ShortenedUrl

shortener_router = APIRouter(
    tags=["Shortener"],
    prefix="",
)


@shortener_router.post(
    "/shorten",
    response_model=ShortenUrlResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Short URL created successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "main_url": "https://example.com",
                        "short_url": "abc123",
                        "custom_domain": "127.0.0.1:8000",
                        "max_clicks": 5,
                        "created_at": "2025-06-19 12:00:00",
                        "updated_at": "2025-06-19 12:00:00",
                        "expires_at": "2025-07-19 12:00:00"
                    }
                }
            }
        },
        400: {"description": "Bad Request (e.g. custom short code already exists)"},
    },
)
async def shorten(
    payload: ShortenUrlRequest,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),

):
    return await shortener_controller.shorten(
        db=db,
        redis=redis,
        payload=payload,
    )


@shortener_router.get(
    "/{short_url}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Redirection successful (returns JSON in Swagger)",
            "content": {
                "application/json": {
                    "example": {
                        "details": {
                            "message": "Redirection successful.",
                            "redirect_to": "https://example.com",
                            "short_code": "abc123",
                            "domain": "127.0.0.1:8000"
                        },
                        "status_code": 200
                    }
                }
            },
        },
        302: {"description": "Redirect to the original URL"},
        404: {"description": "Shortened URL not found or expired"},
    },
)
async def redirect_to_main_url(
    short_url: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
   # Call controller
    response = await shortener_controller.redirect_to_main_url(
        db=db,
        redis=redis,
        short_url=short_url,
        request=request
    )

    # If it's a RedirectResponse, Swagger fails — so we override only inside Swagger
    user_agent = request.headers.get("user-agent", "").lower()
    accept = request.headers.get("accept", "").lower()

    if isinstance(response, RedirectResponse):
        if "swagger" in user_agent or "json" in accept:
            return JSONResponse(
                status_code=200,
                content={
                    "details": {
                        "message": "Redirection successful.",
                        "redirect_to": response.headers.get("location"),
                        "short_code": short_url,
                        "domain": request.headers.get("host", "")
                    },
                    "status_code": 200
                }
            )
        return response
    return response

@shortener_router.get("/stats/{short_code}",
                      responses={
        200: {
            "description": "Click statistics for a short URL",
            "content": {
                "application/json": {
                    "example": {
                        "short_code": "abcd1",
                        "clicks": 12
                    }
                }
            },
        },
        404: {"description": "Shortened URL not found"},
    },
)
async def get_click_count(
    short_code: str,
    session: AsyncSession = Depends(get_session)
):
    result = await session.exec(
        select(ShortenedUrl).where(ShortenedUrl.short_url == short_code)
    )
    url = result.first()

    if not url:
        raise HTTPException(status_code=404, detail="Shortened URL not found")

    return {
        "short_code": short_code,
        "clicks": url.click_count
    }