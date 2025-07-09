from sqlmodel import Column, DateTime, Field, SQLModel, UniqueConstraint, func
from datetime import datetime
from typing import Optional
from utils.common_models import BaseModel
from sqlalchemy.orm import declarative_base


class User(SQLModel, table=True):
    __tablename__ = "users"  # Optional with SQLModel, included for clarity
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    verification_code: Optional[str] = Field(default=None)
    otp_secret: Optional[str] = Field(default=None)  # ✅ Properly typed
    url_limit: Optional[int] = Field(default=5)  # ✅ Properly typed

    
class ShortenedUrl(BaseModel, table=True):
    __table_args__ = (
        UniqueConstraint("short_url", "custom_domain", name="uix_short_url_custom_domain"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    main_url: str = Field(nullable=False, description="Original long URL")
    short_url: str = Field(nullable=False, description="Unique short code")
    custom_domain: Optional[str] = Field(default=None, index=True, description="Custom domain, if provided")
    title: Optional[str] = Field(default=None, description="Optional title for dashboard/metadata")
    click_count: int = Field(default=0, nullable=False, description="Total number of redirects")
    max_clicks: Optional[int] = Field(default=None, description="Maximum allowed clicks")
    active: bool = Field(default=True, description="Whether the link is active")
    expired: bool = Field(default=False, description="Whether the link is expired")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    expires_at: Optional[datetime] = Field(default=None, description="Expiry time of the short link")
    owner_email: Optional[str] = Field(default=None, index=True, description="Email of the user who owns this short URL")
    password_hash: Optional[str] = Field(default=None, nullable=True, description="Hashed password for protecting access to this short URL. If None, the URL is public.")
    
class VisitLog(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    short_url: str = Field(nullable=False)
    client_ip: str = Field(nullable=False)
    system_id: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device: Optional[str] = None
    os: Optional[str] = None
    browser: Optional[str] = None
    visited_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, nullable=False)

Base = declarative_base()


#-----------------------------Campaign Model-----------------------#

class CampaignSource(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "campaign_source_tag", name="uq_source_user_tag"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    unique_id: str = Field(max_length=6, index=True)
    user_id: str = Field(index=True)
    campaign_source_tag: str
    campaign_source_name: str
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now())
    )


class CampaignMedium(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "campaign_medium_tag", name="uq_medium_user_tag"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    unique_id: str = Field(max_length=6, index=True, nullable=False)
    user_id: str = Field(index=True, nullable=False)
    campaign_medium_tag: str = Field(nullable=False)
    campaign_medium_name: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()}
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()}
    )


class CampaignName(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("user_id", "campaign_name_tag", name="uq_name_user_tag"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    unique_id: str = Field(max_length=6, index=True, nullable=False)
    user_id: str = Field(index=True, nullable=False)
    campaign_name_tag: str = Field(nullable=False)
    campaign_name: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now()}
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()}
    )
