from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from .db import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    officer_id = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(120), nullable=False)
    role = Column(String(64), nullable=False, default='Border Officer')
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ScreeningCase(Base):
    __tablename__ = 'screening_cases'
    id = Column(Integer, primary_key=True)
    case_id = Column(String(40), unique=True, nullable=False)
    officer_id = Column(String(64), nullable=False)
    document_type = Column(String(64), nullable=False)
    original_filename = Column(String(255), default='')
    document_path = Column(String(500), default='')
    selfie_path = Column(String(500), default='')
    document_sha256 = Column(String(64), default='')
    status = Column(String(32), default='CREATED')
    risk_score = Column(Float, default=0)
    decision = Column(String(64), default='PENDING')
    action = Column(String(64), default='PENDING')
    result_json = Column(Text, default='{}')
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id = Column(Integer, primary_key=True)
    case_id = Column(String(40), nullable=False)
    actor = Column(String(64), nullable=False)
    event_type = Column(String(80), nullable=False)
    details_json = Column(Text, default='{}')
    event_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class WatchlistEntry(Base):
    __tablename__ = 'watchlist_entries'
    id = Column(Integer, primary_key=True)
    identifier_type = Column(String(32), nullable=False)
    identifier_value = Column(String(120), unique=True, nullable=False)
    subject_name = Column(String(160), nullable=False)
    category = Column(String(64), default='REVIEW')
    status = Column(String(32), default='REVIEW')
    notes = Column(Text, default='')
    created_at = Column(DateTime, default=datetime.utcnow)
