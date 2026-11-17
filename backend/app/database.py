"""
Database engine and session management for GTA 6 AI Clip Factory.
Adapted from API-TASKFLOW (demo123) database.py and TETHR-Bluetooth-Payments patterns.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings
from app.core.logging import logger


def _build_engine():
    """Build SQLAlchemy engine with automatic local SQLite fallback if PostgreSQL is offline."""
    url = settings.DATABASE_URL

    # Normalize common PostgreSQL URL prefixes
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    is_sqlite = url.startswith("sqlite")

    # If PostgreSQL specified, verify reachability; fallback to SQLite if unreachable
    if not is_sqlite:
        try:
            import socket
            # Quick 0.5s socket check on database host/port before hanging SQLAlchemy
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((host, port))
            sock.close()
            if result != 0:
                logger.warning(
                    f"PostgreSQL at {host}:{port} is unreachable. "
                    f"Falling back to local SQLite database: ./data/gta6_clip_factory.db"
                )
                url = f"sqlite:///{settings.DATA_DIR}/gta6_clip_factory.db"
                is_sqlite = True
        except Exception as e:
            logger.warning(f"Error checking PostgreSQL ({e}); falling back to SQLite.")
            url = f"sqlite:///{settings.DATA_DIR}/gta6_clip_factory.db"
            is_sqlite = True

    connect_args = {}
    engine_kwargs = {
        "echo": settings.DEBUG,
    }

    if is_sqlite:
        connect_args["check_same_thread"] = False
    else:
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW

    engine = create_engine(
        url,
        connect_args=connect_args,
        **engine_kwargs
    )

    # Enable WAL mode for SQLite concurrency
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    logger.info(f"Database engine initialized: {'PostgreSQL' if not is_sqlite else 'SQLite (' + url + ')'}")
    return engine


engine = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """FastAPI dependency: yields a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_type() -> str:
    """Returns 'postgresql' or 'sqlite' based on active engine."""
    return "postgresql" if "postgresql" in str(engine.url) else "sqlite"

