# ─── CRMS Database Connection ─────────────────────────────────────────────────
# Manages a single MySQL connection pool used across the entire application.
# Every module imports `get_db` from here — never opens its own connection.

import mysql.connector
from mysql.connector import pooling
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

_pool = None

def init_pool():
    """
    Creates the connection pool on first call.
    Called once at startup from app.py.
    """
    global _pool
    _pool = pooling.MySQLConnectionPool(
        pool_name="crms_pool",
        pool_size=5,
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )
    print(f"[DB] Connection pool initialised → {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def get_db():
    """
    Returns a connection from the pool.
    Callers are responsible for calling conn.close() to return it to the pool.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialised. Call init_pool() first.")
    return _pool.get_connection()
