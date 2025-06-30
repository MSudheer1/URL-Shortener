from typing import Optional
from redis.asyncio import Redis
from fastapi import Request, APIRouter, Depends, status, HTTPException, Path, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from apps.shortener.schemas import ShortenUrlRequest, ShortenUrlResponse, UpdateShortenedUrlRequest
from apps.shortener.controllers import shortener_controller
from apps.shortener.models import ShortenedUrl, User
from dependencies import get_current_user
from services.db import get_session
from services.redis import get_redis

shortener_router = APIRouter(
    prefix="",
    tags=["Shortener"]
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
    current_user: str = Depends(get_current_user),  
):
    print("Authenticated user:", current_user)
    result = await db.execute(select(User).where(User.email == current_user))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.url_limit or user.url_limit <= 0:
        raise HTTPException(status_code=403, detail="Subscription expired or limit reached")

    response = await shortener_controller.shorten(
        db=db,
        redis=redis,
        payload=payload,
    )

    user.url_limit -= 1
    db.add(user)
    await db.commit()

    return response


@shortener_router.get(
    "/{short_code}",
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
    short_code: str,
    request: Request,
    domain: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    response = await shortener_controller.redirect_to_main_url(
        db=db,
        redis=redis,
        short_url=short_code,
        request=request,
        domain=domain
    )

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
                        "short_code": short_code,
                        "domain": request.headers.get("host", "")
                    },
                    "status_code": 200
                }
            )
        return response
    return response

@shortener_router.patch("/shorten/{short_code}")
async def update_short_url(
    short_code: str = Path(..., description="Existing short code"),
    payload: UpdateShortenedUrlRequest = Depends(),
    db=Depends(get_session),
    redis=Depends(get_redis)
):
    return await shortener_controller.update_short_url(
        db=db,
        short_code=short_code,
        payload=payload,
        redis=redis
    )


@shortener_router.delete("/shorten/{short_code}")
async def delete_short_url(
    short_code: str,
    domain: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis)
):
    normalized_domain = shortener_controller.normalize_domain(domain or "")
    result = await db.exec(select(ShortenedUrl).where(
        ShortenedUrl.short_url == short_code,
        ShortenedUrl.custom_domain == normalized_domain
    ))
    record = result.first()
    if not record:
        raise HTTPException(status_code=404, detail="Shortened URL not found")

    redis_key = shortener_controller.build_redis_key(normalized_domain, short_code)

    await db.delete(record)
    await db.commit()
    await redis.delete(redis_key)

    return {"message": "Shortened URL deleted successfully"}


@shortener_router.get("/analytics/{short_code}",
    responses={
        200: {
            "description": "Click statistics for a short URL",
            "content": {
                "application/json": {
                    "example": {
                        "short_code": "abc12",
                        "domain": "surl.signitivessoft.com",
                        "clicks": 5
                    }
                }
            },
        },
        404: {"description": "Shortened URL not found"},
    },
)
async def get_click_count(
    short_code: str,
    domain: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session)
):
    normalized_domain = shortener_controller.normalize_domain(domain or "")

    result = await session.exec(
        select(ShortenedUrl).where(
            ShortenedUrl.short_url == short_code,
            ShortenedUrl.custom_domain == normalized_domain
        )
    )
    url = result.first()

    if not url:
        raise HTTPException(status_code=404, detail="Shortened URL not found")

    return {
        "short_code": short_code,
        "domain": normalized_domain,
        "clicks": url.click_count
    }




# @shortener_router.patch("/shorten/{short_code}")
# async def update_shortened_url(
#     short_code: str,
#     payload: UpdateShortUrlRequest,
#     request: Request,
#     db: AsyncSession = Depends(get_session),
# ):
#     return await shortener_controller.update_short_url(
#         db=db,
#         short_code=short_code,
#         domain=None,  # Let it fall back to request host
#         payload=payload,
#         request=request
#     )

# @shortener_router.patch("/update/slug")
# async def update_slug(
#     payload: UpdateSlugRequest,
#     db: AsyncSession = Depends(get_session)
# ):
#     return await shortener_controller.update_slug(db=db, payload=payload)


# @shortener_router.patch("/update/domain")
# async def update_domain(
#     payload: UpdateDomainRequest,
#     db: AsyncSession = Depends(get_session)
# ):
#     return await shortener_controller.update_domain(db=db, payload=payload)


# @shortener_router.patch("/update/slug-and-domain")
# async def update_slug_and_domain(
#     payload: UpdateSlugAndDomainRequest,
#     db: AsyncSession = Depends(get_session)
# ):
#     return await shortener_controller.update_slug_and_domain(db=db, payload=payload)