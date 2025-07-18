import logging
import platform
import psutil
import uuid

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from sqlmodel import SQLModel

from services.db import engine
from services.scheduler import start_scheduler
from core import events
from core.router import initialize_routes, main_router
from apps.shortener.apis import shortener_router, campaign_router
from apps.qr.qr_apis import qr_router
from middlewares.response_schema import (
    global_exception_handler, 
    validation_exception_handler,
    response_schema_middleware,
)
from core.auth import router as auth_router
from apps.shortener.bulk_apis import router as bulk_router


# App Initialization
app = FastAPI()

# Include routers in correct order
app.include_router(auth_router)               # Auth comes first
initialize_routes(app)                        # Project-wide routes
app.include_router(main_router)
app.include_router(shortener_router)
app.include_router(campaign_router)
app.include_router(qr_router)
app.include_router(bulk_router)               # Bulk operations


# Events
app.add_event_handler("startup", events.startup_event_handler)
app.add_event_handler("shutdown", events.shutdown_event_handler)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Response Schema Middleware
response_schema_middleware(app)


# Exception Handlers
# Register centralized exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Startup & Shutdown Events
@app.on_event("startup")
async def startup() -> None:
    await events.startup_event_handler()
    start_scheduler()  # Background cleanup task

@app.on_event("shutdown")
async def shutdown_event() -> None:
    await events.shutdown_event_handler()


# Routes
@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/info/system")
def get_info():
    return get_system_info()


# Utility Functions
def create_tables():
    SQLModel.metadata.create_all(engine)

def get_system_info():
    print("[System Info] Fetching system information")
    return {
        "Device Name": platform.node(),
        "Processor": platform.processor(),
        "Architecture": platform.architecture()[0],
        "RAM (GB)": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "System Type": platform.machine(),
        "OS": f"{platform.system()} {platform.release()}",
        "Device ID": hex(uuid.getnode())
    }
