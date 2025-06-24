from fastapi import FastAPI,Depends

from core import events
from core.router import initialize_routes

from middlewares.response_schema import response_schema_middleware

from core.config import redis_config 
from fastapi.middleware.cors import CORSMiddleware
from services.redis import get_redis

app = FastAPI()


from core.config import database_config, redis_config

print("DB CONFIG:")
print("  username:", database_config.username)
print("  password:", database_config.password)
print("  database:", database_config.database)
print("  host:", database_config.host)
print("  port:", database_config.port)
print("REDIS CONFIG:")
print("  host:", redis_config.host)
print("  port:", redis_config.port)
print("  database:", redis_config.database)
print("  max_connections:", redis_config.max_connections)

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
