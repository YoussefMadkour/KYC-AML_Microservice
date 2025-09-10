"""
Base repository class with common CRUD operations.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.base import BaseModel as DBBaseModel

ModelType = TypeVar("ModelType", bound=DBBaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Base repository class with common CRUD operations."""

    def __init__(self, model: Type[ModelType], db: Session):
        """
        Initialize repository with model and database session.

        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db

    def get(self, id: Any) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance if found, None otherwise
        """
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_by_id(self, id: str) -> Optional[ModelType]:
        """
        Get a single record by string ID.

        Args:
            id: Record ID as string

        Returns:
            Model instance if found, None otherwise
        """
        # Convert string UUID to UUID object if needed
        try:
            import uuid

            uuid_obj = uuid.UUID(id)
            return self.get(uuid_obj)
        except (ValueError, TypeError):
            # If conversion fails, try with original string
            return self.get(id)

    def get_multi(self, skip: int = 0, limit: int = 100, **filters) -> List[ModelType]:
        """
        Get multiple records with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filter criteria

        Returns:
            List of model instances
        """
        query = self.db.query(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.filter(getattr(self.model, key) == value)

        return query.offset(skip).limit(limit).all()

    def create(self, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new record.

        Args:
            obj_in: Pydantic schema with creation data

        Returns:
            Created model instance
        """
        obj_in_data = obj_in.dict()
        db_obj = self.model(**obj_in_data)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def create_from_dict(self, obj_in: Dict[str, Any]) -> ModelType:
        """
        Create a new record from dictionary.

        Args:
            obj_in: Dictionary with creation data

        Returns:
            Created model instance
        """
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def update(
        self, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Update an existing record.

        Args:
            db_obj: Existing model instance
            obj_in: Pydantic schema or dict with update data

        Returns:
            Updated model instance
        """
        obj_data = db_obj.__dict__

        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])

        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: Any) -> Optional[ModelType]:
        """
        Delete a record by ID.

        Args:
            id: Record ID

        Returns:
            Deleted model instance if found, None otherwise
        """
        obj = self.db.query(self.model).get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
        return obj

    def count(self, **filters) -> int:
        """
        Count records with optional filtering.

        Args:
            **filters: Filter criteria

        Returns:
            Number of matching records
        """
        query = self.db.query(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.filter(getattr(self.model, key) == value)

        return query.count()

    def exists(self, id: Any) -> bool:
        """
        Check if a record exists by ID.

        Args:
            id: Record ID

        Returns:
            True if record exists, False otherwise
        """
        return self.db.query(self.model).filter(self.model.id == id).first() is not None
