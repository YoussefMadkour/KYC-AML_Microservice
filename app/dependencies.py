"""
FastAPI dependency injection utilities.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db

__all__ = ["get_db"]