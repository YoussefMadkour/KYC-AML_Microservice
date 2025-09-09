"""
API dependencies for authentication and database sessions.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db

# Re-export common dependencies
__all__ = ["get_db"]