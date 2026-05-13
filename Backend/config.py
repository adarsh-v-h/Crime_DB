# ─── CRMS Backend Configuration ───────────────────────────────────────────────
# Edit these values to match your local MySQL setup before running the server.

DB_HOST     = "localhost"
DB_PORT     = 3306
DB_USER     = "adarsh"
DB_PASSWORD = "root"   # ← change this
DB_NAME     = "crms"

# Flask server settings
FLASK_HOST  = "0.0.0.0"
FLASK_PORT  = 5000
FLASK_DEBUG = True                   # Set False in production

# CORS — the origin where your HTML file is served from.
# If you're opening crms_frontend.html directly as a file, use "*".
CORS_ORIGIN = "*"
