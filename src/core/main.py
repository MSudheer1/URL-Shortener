from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from core import events
from core.router import initialize_routes
from middlewares.response_schema import response_schema_middleware
from core.config import database_config, redis_config

# --------------------------------------
# ✅ Constants
ALLOWED_DOMAINS = ["localhost", "127.0.0.1", "surl.signitivessoft.com"]
PROTECTED_PATHS = ["/docs", "/openapi.json", "/redoc", "/"]
# --------------------------------------

# ✅ FastAPI app (without default docs)
app = FastAPI(
    title="ShortURL",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# ✅ Log DB and Redis Config
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

# ✅ CORS for all origins (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Middleware to block docs and homepage on customer domains
@app.middleware("http")
async def block_docs_on_custom_domains(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0]
    print(f"🔍 Host Header = {request.headers.get('host')}, Base = {host}, Path = {request.url.path}")

    if host not in ALLOWED_DOMAINS and request.url.path in PROTECTED_PATHS:
        return JSONResponse(
            status_code=403,
            content={
                "details": {"detail": f"Access forbidden on custom domain: {host}"},
                "status_code": 403
            }
        )
    return await call_next(request)

# ✅ Custom Swagger UI route
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui(request: Request):
    host = request.headers.get("host", "").split(":")[0]
    if host not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=403, detail="Docs not available on custom domains")
    return get_swagger_ui_html(openapi_url="/openapi.json", title="ShortURL Swagger")

# ✅ Custom OpenAPI schema route
@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema(request: Request):
    host = request.headers.get("host", "").split(":")[0]
    if host not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=403, detail="Forbidden")
    schema = get_openapi(
        title="ShortURL",
        version="1.0.0",
        routes=app.routes,
    )
    return JSONResponse(content=schema)

# ✅ Homepage route
@app.get("/")
def read_root(request: Request):
    host = request.headers.get("host", "").split(":")[0]
    if host not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=403, detail="Homepage not available on custom domains")
    return {"Hello": "World"}

# ✅ Health check
@app.get("/ping")
def ping():
    return "pong!"

# ✅ Register all routers
initialize_routes(app=app)

# ✅ Add response formatting middleware
response_schema_middleware(app)

# ✅ Startup & shutdown handlers
@app.on_event("startup")
async def startup() -> None:
    await events.startup_event_handler()

@app.on_event("shutdown")
async def shutdown_event() -> None:
    await events.shutdown_event_handler()
