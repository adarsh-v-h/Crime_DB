# ─── Themis's Domain Database Connection ─────────────────────────────────────────────────
# Manages a single MySQL connection pool used across the entire application.
# Every module imports `get_db` from here — never opens its own connection.
#
# Pool sizing note:
#   Each OS process (each Gunicorn worker) gets its OWN pool, so the total number
#   of connections opened against the database is:
#         (number of Gunicorn workers) × DB_POOL_SIZE
#   Keep that product under your database's max_connections. On the Aiven free
#   tier (~20 max) with the default single Gunicorn worker, a pool of 10 is safe
#   and leaves headroom for the background assignment-scheduler thread, which
#   also borrows from this pool.

import os

import mysql.connector
from mysql.connector import pooling

try:
    from .config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

_pool = None

# Configurable pool size (env-driven), clamped to a sane range so a typo can't
# exhaust the database's connection limit or create a uselessly tiny pool.
_MIN_POOL_SIZE = 1
_MAX_POOL_SIZE = 32
_DEFAULT_POOL_SIZE = 10


def _resolve_pool_size():
    try:
        size = int(os.getenv("DB_POOL_SIZE", _DEFAULT_POOL_SIZE))
    except (TypeError, ValueError):
        size = _DEFAULT_POOL_SIZE
    return max(_MIN_POOL_SIZE, min(size, _MAX_POOL_SIZE))


def init_pool():
    """
    Creates the connection pool on first call. Idempotent: if the pool already
    exists (e.g. startup runs twice), this is a no-op rather than leaking a
    second pool. Called once at startup from app.py.
    """
    global _pool
    if _pool is not None:
        return _pool

    pool_size = _resolve_pool_size()
    _pool = pooling.MySQLConnectionPool(
        pool_name="crms_pool",
        pool_size=pool_size,
        pool_reset_session=True,   # reset session state when a conn returns to the pool
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
        connection_timeout=10,     # fail fast instead of hanging if DB is unreachable
    )
    print(f"[DB] Connection pool initialised → {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} (pool_size={pool_size})")
    return _pool


def get_db():
    """
    Returns a connection from the pool.
    Callers are responsible for calling conn.close() to return it to the pool.

    If every pooled connection is currently checked out, mysql-connector raises
    PoolError here — that signals the pool is too small for the load (raise
    DB_POOL_SIZE, but mind the workers × pool_size ceiling noted above).
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialised. Call init_pool() first.")
    return _pool.get_connection()
