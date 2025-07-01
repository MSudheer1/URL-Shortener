import logging
from fastapi import FastAPI,Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel
from services.scheduler import start_scheduler
from core import events
from core.router import initialize_routes
from services.db import engine
from middlewares.response_schema import validation_exception_handler
from middlewares.response_schema import response_schema_middleware

from fastapi.middleware.cors import CORSMiddleware
from core.router import main_router
from core.auth import auth_router
from apps.shortener.apis import shortener_router,campaign_router

app = FastAPI()


app.include_router(auth_router)  # 👈 Auth first, to appear at top of docs
initialize_routes(app)

app.include_router(main_router)

app.add_event_handler("startup", events.startup_event_handler)
app.add_event_handler("shutdown", events.shutdown_event_handler)

app.include_router(shortener_router)
app.include_router(campaign_router)

def create_tables():
    SQLModel.metadata.create_all(engine)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
    )

app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # In production, replace with frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"Hello":"World"}

response_schema_middleware(app)


@app.on_event("startup")
async def startup() -> None:
    await events.startup_event_handler()
    start_scheduler() # Starts your background cleanup scheduler


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await events.shutdown_event_handler()


@app.get("/ping")
def ping():
    return "pong!"


initialize_routes(app=app)
