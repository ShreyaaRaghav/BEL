from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api import auth, upload, checksheet, sensor_upload
from app.config import ALLOWED_ORIGINS
from app.vapt import router as vapt_router
import database.init_db


class SecurityHeadersMiddleware:
    """Injects OWASP-recommended HTTP security headers on every response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                security_headers = {
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"x-xss-protection": b"1; mode=block",
                    b"referrer-policy": b"no-referrer",
                    b"content-security-policy": b"default-src 'self'",
                    b"cache-control": b"no-store",
                    b"permissions-policy": b"geolocation=(), microphone=()",
                }
                for k, v in security_headers.items():
                    headers.setdefault(k, v)
                message = {**message, "headers": list(headers.items())}
            await send(message)

        await self.app(scope, receive, send_with_headers)

app = FastAPI(title="BEL Secure Checksheet API Portal")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# Initialize and seed database on application startup
@app.on_event("startup")
def on_startup():
    print("Initializing and seeding SQLite checksheet database...")
    database.init_db.init()
    try:
        from database.init_db import prune_expired_tokens
        prune_expired_tokens()
        print("Expired revoked tokens pruned.")
    except Exception as e:
        print(f"Failed to prune expired tokens: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.include_router(auth.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(sensor_upload.router, prefix="/api")
app.include_router(checksheet.router, prefix="/api")
app.include_router(vapt_router.router, prefix="/api")

@app.get("/")
def home():
    return {"message": "BEL Secure Checksheet Processing Server running successfully"}
