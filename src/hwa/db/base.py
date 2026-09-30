"""Declarative database base."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for all HWA ORM models."""
