"""
Declarative base for application tables in PostgreSQL.

API Gateway reads from TimescaleDB using raw SQL (text()), so no ORM
base is needed for time-series tables. DB Writer owns those models.
"""

from sqlalchemy.orm import DeclarativeBase


class AppBase(DeclarativeBase):
    """Base for application tables in PostgreSQL."""

    pass


# Backward-compatible alias used by existing entity imports
Base = AppBase
