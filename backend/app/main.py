from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api import auth, upload, checksheet
from app.config import ALLOWED_ORIGINS
import database.init_db

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(checksheet.router, prefix="/api")

@app.get("/")
def home():
    return {"message": "BEL Secure Checksheet Processing Server running successfully"}