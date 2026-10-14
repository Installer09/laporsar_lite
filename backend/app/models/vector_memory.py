import json
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator
from pgvector.sqlalchemy import Vector
from app.db.session import Base

class EmbeddingVector(TypeDecorator):
    """
    Transparent embedding column type supporting both:
    1. Native PostgreSQL pgvector (when installed)
    2. Fallback TEXT column storing JSON string of floats (when pgvector is absent)
    Always accepts Python list[float] or JSON string, and returns Python list[float].
    """
    impl = Text
    comparator_factory = Vector.comparator_factory
    cache_ok = True

    def __init__(self, dim=1024, *args, **kwargs):
        self.dim = dim
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        from app.db.session import is_vector_extension_available
        if is_vector_extension_available():
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        from app.db.session import is_vector_extension_available
        if not is_vector_extension_available():
            if isinstance(value, (list, tuple)):
                return json.dumps(value)
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                try:
                    cleaned = value.strip("[]")
                    return [float(x.strip()) for x in cleaned.split(",") if x.strip()]
                except Exception:
                    return value
        return value

class VectorMemory(Base):
    __tablename__ = "vector_memory"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, index=True, nullable=True) # Optional link to reports
    content = Column(Text, nullable=False) # The actual text content
    embedding = Column(EmbeddingVector(1024), nullable=True) # Resilient Vector / Text
    metadata_json = Column(Text, default="{}") # JSON metadata (e.g., date, location)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

