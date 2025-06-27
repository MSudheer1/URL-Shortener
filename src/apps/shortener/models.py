from sqlmodel import Field, SQLModel, UniqueConstraint
from datetime import datetime
from typing import Optional
from utils.common_models import BaseModel


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
    short_url: str = Field(index=True, nullable=False, description="Unique short code")
    custom_domain: Optional[str] = Field(default=None, index=True, description="Custom domain, if provided")
    click_count: int = Field(default=0, nullable=False, description="Total number of redirects")
    max_clicks: Optional[int] = Field(default=None, description="Maximum allowed clicks")
    active: bool = Field(default=True, description="Whether the link is active")
    expired: bool = Field(default=False, description="Whether the link is expired")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    expires_at: Optional[datetime] = Field(default=None, description="Expiry time of the short link")
