"""Durable login coordination and credential delivery; no credential copies."""
from sqlalchemy import String, Text, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class LoginLease(Base):
    __tablename__ = 'integration_login_leases'
    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64))
    source_key: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[float] = mapped_column(Float)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class CredentialState(Base):
    __tablename__ = 'integration_credentials'
    source_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    cookie_hash: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[float] = mapped_column(Float)

class CredentialDelivery(Base):
    __tablename__ = 'integration_deliveries'
    key: Mapped[str] = mapped_column(String(180), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(100), index=True)
    site_id: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allow_create: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(32), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_at: Mapped[float] = mapped_column(Float, default=0)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    message: Mapped[str] = mapped_column(String(255), default='等待同步')
    updated_at: Mapped[float] = mapped_column(Float)
    receipt: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class RecoveryJob(Base):
    __tablename__ = 'integration_recovery_jobs'
    automatic: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), index=True)
    target: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(32), default='queued', index=True)
    code: Mapped[str] = mapped_column(String(40), default='')
    message: Mapped[str] = mapped_column(String(255), default='等待登录')
    created_at: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)
