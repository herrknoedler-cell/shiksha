from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Integer, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

DATABASE_URL = "postgresql://shiksha:shiksha2026@localhost/shiksha"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Entity(Base):
    __tablename__ = "entities"
    id          = Column(String, primary_key=True)
    entity_type = Column(String, nullable=False)
    edition_id  = Column(String, nullable=False)
    data        = Column(JSON, nullable=False)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class MemoryRecord(Base):
    __tablename__ = "memory_records"
    id           = Column(String, primary_key=True)
    level        = Column(String, nullable=False)
    edition_id   = Column(String, nullable=False)
    session_id   = Column(String)
    source_type  = Column(String)
    source_id    = Column(String)
    content      = Column(JSON, nullable=False)
    confidence   = Column(Float, default=0.0)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class EventRecord(Base):
    __tablename__ = "event_records"
    id         = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    edition_id = Column(String, nullable=False)
    session_id = Column(String)
    data       = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    Base.metadata.create_all(engine)
    print("Datenbank-Schema erstellt.")

if __name__ == "__main__":
    init_db()
