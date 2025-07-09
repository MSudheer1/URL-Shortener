from typing import Optional, List
import csv
from io import StringIO
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
    UploadFile,
    File,
)
from fastapi.responses import StreamingResponse
from fastapi.params import Body
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
    UpdateDestinationRequest,
    UpdateShortenedUrlRequest,
    UpdateUrlSettingsRequest,
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
    tags=["Campaign"],
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
        current_user=current_user
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
        401: {"description": "Unauthorized (password required or incorrect)"},
        404: {"description": "Shortened URL not found or expired"},
    },
)
async def redirect_to_main_url(
    short_code: str,
    request: Request,
    domain: Optional[str] = Query(None, description="Custom domain if applicable"),
    password: Optional[str] = Query(None, description="Password if link is protected"),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    response = await shortener_controller.redirect_to_main_url(
        db=db,
        redis=redis,
        short_url=short_code,
        request=request,
        domain=domain,
        password=password  
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
    payload: UpdateShortenedUrlRequest = Body(...),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    current_user: str = Depends(get_current_user)  
):
    return await shortener_controller.update_short_url(
        db=db,
        short_code=short_code,
        payload=payload,
        redis=redis,
        user_email=current_user  
    )

@shortener_router.delete("/shorten/{short_code}")
async def delete_short_url(
    short_code: str,
    domain: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    current_user: str = Depends(get_current_user) 
):
    normalized_domain = shortener_controller.normalize_domain(domain or "")

    result = await db.exec(select(ShortenedUrl).where(
        ShortenedUrl.short_url == short_code,
        ShortenedUrl.custom_domain == normalized_domain
    ))
    record = result.first()

    if not record:
        raise HTTPException(status_code=404, detail="Shortened URL not found")


    if record.owner_email != current_user:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this URL")

    redis_key = shortener_controller.build_redis_key(normalized_domain, short_code)

    await db.delete(record)
    await db.commit()
    await redis.delete(redis_key)

    return {"message": "Shortened URL deleted successfully"}


@shortener_router.patch("/shorten/{short_code}/destination")
async def update_main_url(
    short_code: str,
    domain: Optional[str] = Query(None),
    payload: UpdateDestinationRequest = Body(...),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    current_user: str = Depends(get_current_user)
):
    return await shortener_controller.update_main_url(
        db=db,
        redis=redis,
        short_code=short_code,
        payload=payload,
        user_email=current_user,
        domain=domain
    )


@shortener_router.patch("/shorten/{short_code}/settings")
async def update_url_settings(
    short_code: str,
    domain: Optional[str] = Query(None),
    payload: UpdateUrlSettingsRequest = Body(...),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    current_user: str = Depends(get_current_user),
):
    return await shortener_controller.update_url_settings(
        db=db,
        redis=redis,
        short_code=short_code,
        domain=domain,
        payload=payload,
        user_email=current_user
    )


@shortener_router.post("/bulk-shorten", response_class=StreamingResponse)
async def bulk_shorten_urls(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    current_user: str = Depends(get_current_user),
):
    content = await file.read()
    decoded = content.decode("utf-8")
    csv_reader = csv.DictReader(StringIO(decoded))

    output = StringIO()
    fieldnames = ["row", "main_url", "short_url", "error", "status"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for idx, row in enumerate(csv_reader, start=1):
        try:
            payload = ShortenUrlRequest(
                main_url=row.get("main_url", "").strip(),
                custom_slug=row.get("custom_slug") or None,
                custom_domain=row.get("custom_domain") or None,
                expiry=row.get("expiry") or None,
                max_clicks=int(row.get("max_clicks")) if row.get("max_clicks") else None,
                password=row.get("password") or None,
                title=row.get("title") or None,
            )

            result = await shortener_controller.shorten(
                db=db,
                payload=payload,
                redis=redis,
                current_user=current_user,
                expiry=payload.expiry or "1h",
                max_clicks=payload.max_clicks or 5,
            )

            writer.writerow({
                "row": idx,
                "main_url": payload.main_url,
                "short_url": result.short_url,
                "error": "",
                "status": "success"
            })

        except Exception as e:
            writer.writerow({
                "row": idx,
                "main_url": row.get("main_url", "").strip(),
                "short_url": "",
                "error": str(e),
                "status": "failed"
            })

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bulk_result.csv"}
    )




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