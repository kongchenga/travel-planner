import os
import warnings

from fastapi import Request
from fastapi.responses import JSONResponse

AUTH_TOKEN = os.getenv("API_AUTH_TOKEN")

if not AUTH_TOKEN:
    warnings.warn(
        "API_AUTH_TOKEN \u672a\u8bbe\u7f6e\uff0cAPI \u7aef\u70b9\u65e0\u9274\u6743\u4fdd\u62a4\uff01"
        " \u751f\u4ea7\u73af\u5883\u8bf7\u8bbe\u7f6e\u6b64\u73af\u5883\u53d8\u91cf\u3002"
    )


async def verify_token(request: Request, call_next):
    if request.url.path.startswith("/api/") and AUTH_TOKEN:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token != AUTH_TOKEN:
            return JSONResponse(
                status_code=401,
                content={"error": "unauthorized", "message": "Missing or invalid API token"},
            )
    return await call_next(request)
