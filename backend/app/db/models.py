import datetime
import uuid
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    provider = Column(String(50), default="sarvam")
    status = Column(String(20), default="connected")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    segments = relationship("SegmentModel", back_populates="session", cascade="all, delete-orphan")
    metrics = relationship("MetricModel", back_populates="session", cascade="all, delete-orphan")


class SegmentModel(Base):
    __tablename__ = "segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    sequence_no = Column(Integer, nullable=False, default=1)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)
    stability_score = Column(Float, default=1.0)
    rewrite_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("SessionModel", back_populates="segments")


class MetricModel(Base):
    __tablename__ = "metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    segment_id = Column(String(36), nullable=True)
    kind = Column(String(50), nullable=False)
    value_ms = Column(Float, nullable=False)
    provider = Column(String(50), default="sarvam")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("SessionModel", back_populates="metrics")


class GlossaryTermModel(Base):
    __tablename__ = "glossary_terms"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    term = Column(String(255), nullable=False)
    preferred_translation = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
