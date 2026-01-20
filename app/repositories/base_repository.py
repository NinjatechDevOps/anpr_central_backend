"""
Base repository with common CRUD operations.
"""
from typing import TypeVar, Generic, List, Optional, Dict, Any
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic repository with common CRUD operations."""

    def __init__(self, model: type[T], db: Session):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db

    def create(self, obj_in: Dict[str, Any]) -> T:
        """Create a new record."""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_id(self, id: int) -> Optional[T]:
        """Get record by ID."""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all records with pagination."""
        return self.db.query(self.model).order_by(
            self.model.id.desc()
        ).offset(skip).limit(limit).all()

    def update(self, id: int, obj_in: Dict[str, Any]) -> Optional[T]:
        """Update a record."""
        db_obj = self.get_by_id(id)
        if db_obj is None:
            return None

        for key, value in obj_in.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)

        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, id: int) -> bool:
        """Delete a record."""
        db_obj = self.get_by_id(id)
        if db_obj is None:
            return False

        self.db.delete(db_obj)
        self.db.commit()
        return True

    def count(self) -> int:
        """Count total records."""
        return self.db.query(self.model).count()

    def exists(self, id: int) -> bool:
        """Check if record exists."""
        return self.db.query(self.model).filter(self.model.id == id).first() is not None
