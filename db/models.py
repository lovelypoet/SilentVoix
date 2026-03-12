from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="guest")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    datasets: Mapped[List["Dataset"]] = relationship(back_populates="owner")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(50), default="v1")
    
    # Storage info
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Metadata Split: core fields in columns, complex metadata in JSONB
    modality: Mapped[str] = mapped_column(String(50))  # cv, sensor, fusion
    hand_mode: Mapped[str] = mapped_column(String(50)) # single, dual
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Complex validation results, schema info, etc.
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    owner: Mapped["User"] = relationship(back_populates="datasets")
    models: Mapped[List["Model"]] = relationship(back_populates="training_dataset")


class Model(Base):
    __tablename__ = "models"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    family: Mapped[str] = mapped_column(String(100)) # lstm, transformer, etc.
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Artifact info
    artifact_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    export_format: Mapped[str] = mapped_column(String(50), nullable=False) # pytorch, tflite, yolo
    
    # Performance metrics (High-level)
    accuracy: Mapped[Optional[float]] = mapped_column(Float)
    f1_score: Mapped[Optional[float]] = mapped_column(Float)
    
    # Extended metrics and input spec
    config_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    training_dataset_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("datasets.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    training_dataset: Mapped[Optional["Dataset"]] = relationship(back_populates="models")
