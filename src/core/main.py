from fastapi import FastAPI,Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core import events
from core.router import initialize_routes

from middlewares.response_schema import validation_exception_handler
from middlewares.response_schema import response_schema_middleware

from fastapi.middleware.cors import CORSMiddleware
from core.router import main_router

from core.auth import auth_router

app = FastAPI()
app.include_router(auth_router)  # 👈 Auth first, to appear at top of docs
initialize_routes(app)

app.include_router(main_router)

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


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await events.shutdown_event_handler()


@app.get("/ping")
def ping():
    return "pong!"


initialize_routes(app=app)
