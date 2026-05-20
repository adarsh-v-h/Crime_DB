import os
from dotenv import load_dotenv

# Load environment variables from .env (if present)
load_dotenv()

# Database configuration (use DB_ names for clarity)
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "3306"))
DB_USER     = os.getenv("DB_USER", "adarsh")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME     = os.getenv("DB_NAME", "crms")

# Flask server configuration
FLASK_HOST  = os.getenv("FLASK_HOST", "0.0.0.0")
# Allow either PORT or FLASK_PORT to be set
FLASK_PORT  = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5000")))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

CORS_ORIGIN = os.getenv("CORS_ORIGIN", "*")

# reCAPTCHA v2 (Invisible) configuration
# All secret/site keys should come from environment variables.
# Defaults are empty to avoid committing secrets in code.
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_PUBLIC_KEY = os.getenv("RECAPTCHA_PUBLIC_KEY", "")

# Note: RECAPTCHA_THRESHOLD is relevant for v3 scoring only
RECAPTCHA_THRESHOLD = float(os.getenv("RECAPTCHA_THRESHOLD", "0.5"))
