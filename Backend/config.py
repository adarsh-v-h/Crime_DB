import os

DB_HOST     = os.environ.get("MYSQLHOST",     "localhost")
DB_PORT     = int(os.environ.get("MYSQLPORT", "3306"))
DB_USER     = os.environ.get("MYSQLUSER",     "adarsh")
DB_PASSWORD = os.environ.get("MYSQLPASSWORD", "root")
DB_NAME     = os.environ.get("MYSQLDATABASE", "crms")

FLASK_HOST  = "0.0.0.0"
FLASK_PORT  = int(os.environ.get("PORT", "5000"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

CORS_ORIGIN = "*"
