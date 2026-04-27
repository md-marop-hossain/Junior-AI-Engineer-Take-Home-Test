"""SQLAlchemy engine, session factory, and DB lifecycle helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agent.config import settings

engine = create_engine(settings.sqlalchemy_url, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a transactional session; commit on clean exit, rollback on error."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables that do not yet exist, and add any new columns."""
    from sqlalchemy import text
    from .models import Base

    Base.metadata.create_all(engine)
    # Safe migration: add agent_state column if this is an existing DB.
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE conversations "
            "ADD COLUMN IF NOT EXISTS agent_state JSONB NOT NULL DEFAULT '{}'"
        ))
        conn.commit()


def seed_db() -> None:
    """Insert sample listings if the table is empty."""
    from sqlalchemy import select, func
    from .models import Listing
    from .seed import SAMPLE_LISTINGS

    with get_session() as session:
        count = session.scalar(select(func.count()).select_from(Listing))
        if count == 0:
            session.add_all([Listing(**row) for row in SAMPLE_LISTINGS])
