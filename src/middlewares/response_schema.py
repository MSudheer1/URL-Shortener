import json
from typing import Callable

from fastapi import Request, FastAPI, status
from fastapi.responses import JSONResponse, Response
from fastapi.encoders import jsonable_encoder

from utils.responses import ResponseStructure

# Optional: Add paths that shouldn't be wrapped by the middleware
specific_paths = []


def response_schema_middleware(app: FastAPI):
    @app.middleware("http")
    async def wrap_response(request: Request, call_next: Callable):
        response = await call_next(request)

        # Skip middleware for FastAPI docs or excluded paths
        if request.url.path in [
            app.docs_url,
            app.openapi_url,
            app.redoc_url,
            app.swagger_ui_oauth2_redirect_url,
            *specific_paths,
        ]:
            return response

        # Don't wrap 3xx redirects or error responses
        if status.HTTP_300_MULTIPLE_CHOICES <= response.status_code < status.HTTP_400_BAD_REQUEST:
            return response

        # Collect response body content (only once!)
        body_chunks = [chunk async for chunk in response.body_iterator]
        full_body = b"".join(body_chunks)

        if not full_body:
            return Response(
                content=b"",
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        content_type = response.headers.get("content-type", "")
        headers = dict(response.headers)
        headers.pop("content-length", None)

        # If response is JSON, wrap it in ResponseStructure
        if content_type.startswith("application/json"):
            try:
                json_body = json.loads(full_body.decode())
                structured_response = ResponseStructure(
                    details=json_body,
                    status_code=response.status_code,
                )
                return JSONResponse(
                    content=jsonable_encoder(structured_response),
                    status_code=response.status_code,
                    headers=headers,
                )
            except json.JSONDecodeError:
                # Not a valid JSON, fallback to original
                return Response(
                    content=full_body,
                    status_code=response.status_code,
                    headers=headers,
                    media_type=response.media_type,
                )
        else:
            # For non-JSON (e.g., HTML, plain text, etc.), just return as-is
            return Response(
                content=full_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

    return app
