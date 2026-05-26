import os

# Change SECRET_KEY via environment variable in production
SECRET_KEY = os.getenv("BEL_SECRET_KEY", "bel-dev-secret-key-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30

# Password rules
PASSWORD_MIN_LENGTH = 12
PASSWORD_NEEDS_UPPER = True
PASSWORD_NEEDS_LOWER = True
PASSWORD_NEEDS_DIGIT = True
PASSWORD_NEEDS_SPECIAL = True

# Brute force protection
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# CORS — add your production domain here
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
