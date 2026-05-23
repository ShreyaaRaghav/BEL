from fastapi import FastAPI
from app.api import upload

app = FastAPI()

app.include_router(upload.router, prefix="/api")
@app.get("/")
def home():
    return {"message": "Server running"}


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)