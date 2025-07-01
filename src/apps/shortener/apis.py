from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse

from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from apps.shortener import schemas as campaign_schemas
from apps.shortener.schemas import (
    CampaignMediumCreate,
    CampaignMediumUpdate,
    CampaignNameCreate,
    CampaignNameUpdate,
    CampaignSourceCreate,
    CampaignSourceUpdate,
    ShortenUrlRequest,
    ShortenUrlResponse,
    UpdateShortenedUrlRequest,
)
from apps.shortener.models import ShortenedUrl, User
from apps.shortener.controllers import shortener_controller

from dependencies import get_current_user
from services.visit_service import visit_service 
from services import campaign_services
from services.db import get_session
from services.redis import get_redis



shortener_router = APIRouter(
    prefix="",
    tags=["Shortener"]
)

campaign_router = APIRouter(
    tags=["Campaign"],  # 👈 this controls the heading in Swagger UI
    prefix="/campaign"
)

utm_router = APIRouter(prefix="/utm", tags=["UTM"])


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

# --- Visit Logs by Client IP API ---
@shortener_router.get("/visitlogs/client/{client_ip}")
async def get_visits_by_client_ip(
    client_ip: str,
    db: AsyncSession = Depends(get_session)
):
    visits = await visit_service.get_visits_by_client_ip(db, client_ip)
    if visits:
        return {"client_ip": client_ip, "visit_logs": visits}

    raise HTTPException(status_code=404, detail="No visit logs found for this client IP")


#-------------Campaign------------------#

@campaign_router.post("/campaign/source")
async def create_campaign_source(
    payload: CampaignSourceCreate,
    db: AsyncSession = Depends(get_session)
):
    return await campaign_services.create_campaign_source(
        db,
        payload.user_id,
        payload.campaign_source_tag,
        payload.campaign_source_name
    )

@campaign_router.get("/campaign/source/{user_id}")
async def get_campaign_sources(user_id: str, db: AsyncSession = Depends(get_session)):
    return await campaign_services.get_campaign_sources_by_user(db, user_id)


@campaign_router.put("/campaign/source/{user_id}/{unique_id}")
async def update_campaign_source(
    user_id: str,
    unique_id: str,
    payload: CampaignSourceUpdate,
    db: AsyncSession = Depends(get_session)
):
    return await campaign_services.update_campaign_source(
        db,
        user_id,
        unique_id,
        payload
    )

@campaign_router.delete("/campaign/source/{user_id}/{unique_id}")
async def delete_campaign_source(user_id: str, unique_id: str, db: AsyncSession = Depends(get_session)):
    return await campaign_services.delete_campaign_source(db, user_id, unique_id)

# ===========================
# Campaign Medium APIs
# ===========================

@campaign_router.post("/campaign/medium")
async def create_campaign_medium(

    payload: CampaignMediumCreate,
    db: AsyncSession = Depends(get_session)
):
    return await campaign_services.create_campaign_medium(
        db,
        payload.user_id,
        payload.campaign_medium_tag,
        payload.campaign_medium_name
    )

@campaign_router.get("/campaign/medium/{user_id}")
async def get_campaign_mediums(user_id: str, db: AsyncSession = Depends(get_session)):
    return await campaign_services.get_campaign_mediums_by_user(db, user_id)


@campaign_router.put("/campaign/medium/{user_id}/{unique_id}")
async def update_campaign_medium(
    user_id: str,
    unique_id: str,
    payload: CampaignMediumUpdate,
    db: AsyncSession = Depends(get_session)
):
    return await campaign_services.update_campaign_medium(
        db,
        user_id,
        unique_id,
        payload
    )


@campaign_router.delete("/campaign/medium/{user_id}/{unique_id}")
async def delete_campaign_medium(user_id: str, unique_id: str, db: AsyncSession = Depends(get_session)):
    return await campaign_services.delete_campaign_medium(db, user_id, unique_id)

# ===========================
# Campaign Name APIs
# ===========================

@campaign_router.post("/campaign/name")
async def create_campaign_name(
    payload: CampaignNameCreate,
    db: AsyncSession = Depends(get_session)
):
    return await campaign_services.create_campaign_name(
        db,
        payload.user_id,
        payload.campaign_name_tag,
        payload.campaign_name
    )


@campaign_router.get("/campaign/name/{user_id}")
async def get_campaign_names(user_id: str, db: AsyncSession = Depends(get_session)):
    return await campaign_services.get_campaign_names_by_user(db, user_id)


@campaign_router.put("/campaign/name/{user_id}/{unique_id}")
async def update_campaign_name(
    user_id: str,
    unique_id: str,
    payload: CampaignNameUpdate,
    db: AsyncSession = Depends(get_session)
):
    return await campaign_services.update_campaign_name(
        db,
        user_id,
        unique_id,
        payload
    )



@campaign_router.delete("/campaign/name/{user_id}/{unique_id}")
async def delete_campaign_name(user_id: str, unique_id: str, db: AsyncSession = Depends(get_session)):
    return await campaign_services.delete_campaign_name(db, user_id, unique_id)

# ===========================
# UTM URL Builder API
# ===========================

# @campaign_router.post("/campaign_utm_url")
# async def campaign_utm_url(payload: campaign_schemas.UTMBuildRequest, db: AsyncSession = Depends(get_session)):
#     sources = await campaign_services.get_campaign_sources(db, payload.user_id)
#     mediums = await campaign_services.get_campaign_mediums(db, payload.user_id)
#     names = await campaign_services.get_campaign_names(db, payload.user_id)

#     if not (sources and mediums and names):
#         raise HTTPException(status_code=404, detail="Campaign details not found for user")

#     # Pick the latest one (or apply your logic here)
#     source = sources[-1]
#     medium = mediums[-1]
#     name = names[-1]

#     # Build UTM URL
#     campaign_url = (
#         f"{payload.main_url}?"
#         f"campaign_source_tag={source.campaign_source_tag}&campaign_source_name={source.campaign_source_name}"
#         f"&campaign_medium_tag={medium.campaign_medium_tag}&campaign_medium_name={medium.campaign_medium_name}"
#         f"&campaign_name_tag={name.campaign_name_tag}&campaign_name={name.campaign_name}"
#     )
#     return {"campaign_url": campaign_url}



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