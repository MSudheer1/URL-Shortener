from fastapi import FastAPI, APIRouter

from apps.shortener.apis import shortener_router, campaign_router
from core.auth import router as auth_router

main_router = APIRouter()


def initialize_routes(app: FastAPI):
    main_router.include_router(auth_router)
    main_router.include_router(shortener_router)
    app.include_router(campaign_router)
    app.include_router(main_router)
    # app.include_router(shortener_router)
    # app.include_router(auth_router)