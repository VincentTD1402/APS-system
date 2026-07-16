from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Create SQLAlchemy engine — pool params only apply to PostgreSQL, not SQLite
_is_sqlite = settings.APS_DB_URL.startswith("sqlite")
engine = create_engine(
    settings.APS_DB_URL,
    **({"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20} if not _is_sqlite else {}),
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all APS tables if they do not exist.

    Import all models before calling so their metadata is registered on Base.
    Called by seed_mock_data.py and run_pipeline.py on startup.
    """
    import app.models  # noqa: F401 — registers all model metadata
    Base.metadata.create_all(bind=engine)
