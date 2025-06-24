from sqlmodel import Field
from datetime import datetime
from typing import Optional
from utils.common_models import BaseModel


class ShortenedUrl(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    main_url: str = Field(nullable=False)
    short_url: str = Field(index=True, nullable=False)
    custom_domain: Optional[str] = Field(default=None, index=True)
    click_count: int = Field(default=0, nullable=False)
    max_clicks: Optional[int] = Field(default=None)
    active: bool = Field(default=True)
    expired: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    expires_at: Optional[datetime] = Field(default=None)