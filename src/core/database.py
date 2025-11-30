"""
Database configuration and session management.
Supports SQLite for development and PostgreSQL for production.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine
connect_args = {}
poolclass = None

if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite specific settings
    connect_args = {"check_same_thread": False}
    poolclass = StaticPool

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    poolclass=poolclass,
    echo=settings.DEBUG and settings.LOG_LEVEL == "DEBUG"
)

# Enable foreign keys for SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.
    Ensures the session is closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize the database by creating all tables.
    Called on application startup.
    """
    # Import models to register them with Base
    from ..models import User, Job, JobMetrics
    
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created successfully")
    
    # Create default admin user if not exists
    db = SessionLocal()
    try:
        from ..models import User
        from .security import get_password_hash
        
        admin = db.query(User).filter(User.email == "admin@ensam.ma").first()
        if not admin:
            admin = User(
                email="admin@ensam.ma",
                password_hash=get_password_hash("admin123"),
                full_name="Admin ENSAM",
                is_active=True,
                is_admin=True
            )
            db.add(admin)
            db.commit()
            logger.info("✅ Default admin user created: admin@ensam.ma / admin123")
        
        # Create demo user
        demo = db.query(User).filter(User.email == "demo@ensam.ma").first()
        if not demo:
            demo = User(
                email="demo@ensam.ma",
                password_hash=get_password_hash("demo123"),
                full_name="Demo User",
                is_active=True,
                is_admin=False
            )
            db.add(demo)
            db.commit()
            logger.info("✅ Demo user created: demo@ensam.ma / demo123")
            
    except Exception as e:
        logger.error(f"Error creating default users: {e}")
        db.rollback()
    finally:
        db.close()


def drop_all():
    """Drop all tables. Use with caution!"""
    Base.metadata.drop_all(bind=engine)
    logger.warning("⚠️ All database tables dropped")








