from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db.session import Base

class VectorMemory(Base):
    __tablename__ = "vector_memory"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, index=True, nullable=True) # Optional link to reports
    content = Column(Text, nullable=False) # The actual text content
    embedding = Column(Vector(1024)) # Dimension size for qwen3-embedding:0.6b (1024)
    metadata_json = Column(Text, default="{}") # JSON metadata (e.g., date, location)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
