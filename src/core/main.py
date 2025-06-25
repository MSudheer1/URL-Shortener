from fastapi import FastAPI,Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core import events
from core.router import initialize_routes

from middlewares.response_schema import response_schema_middleware

from core.config import redis_config 
from fastapi.middleware.cors import CORSMiddleware
from services.redis import get_redis
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Extract the first error message, or use a default
    msg = "Invalid input"
    if exc.errors():
        msg = exc.errors()[0].get("msg", msg)
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"status_code": 422, "msg": msg},
    )

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


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await events.shutdown_event_handler()


@app.get("/ping")
def ping():
    return "pong!"


initialize_routes(app=app)
