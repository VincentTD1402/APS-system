"""Mixins for Database Models"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_mixin


@declarative_mixin
class IntegrationMixin:
    """Mixin for tables receiving data from external systems
    
    Provides source system tracking and external ID reference.
    """
    source_system = Column(String(50), nullable=False, default="gsystem")
    external_id = Column(String(100), nullable=False)
    
    # Audit timestamps with timezone support
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


@declarative_mixin
class AuditMixin:
    """Mixin for tables with basic audit tracking
    
    Use this for internal tables that don't need source system tracking.
    """
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())