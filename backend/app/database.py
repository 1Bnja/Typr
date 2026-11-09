from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def execute_sql(
    db: Session, statement: str, parameters: dict[str, object]
) -> CursorResult:
    """Run parameterized driver SQL in the caller's existing transaction."""
    return db.connection().exec_driver_sql(statement, parameters)
