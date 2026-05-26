from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, upload, checksheet
from app.config import ALLOWED_ORIGINS
import database.init_db

app = FastAPI(title="BEL Secure Checksheet API Portal")

# Initialize and seed database on application startup
@app.on_event("startup")
def on_startup():
    print("Initializing and seeding SQLite checksheet database...")
    database.init_db.init()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(checksheet.router, prefix="/api")

@app.get("/")
def home():
    return {"message": "BEL Secure Checksheet Processing Server running successfully"}