"""Declarative base for application tables in PostgreSQL."""

from sqlalchemy.orm import DeclarativeBase


class AppBase(DeclarativeBase):
    """Base for application tables in PostgreSQL."""


# Backward-compatible alias
Base = AppBase
