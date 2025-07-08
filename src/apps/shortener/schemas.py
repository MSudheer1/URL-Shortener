from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional
from utils.validators import (
    add_http_prefix,
    validate_http_url,
    validate_slug,
    validate_domain,
    validate_email_format,  # in case you need for user fields
)



class ShortenUrlRequest(BaseModel):
    main_url: str
    password: Optional[str] = None

    @field_validator("main_url", mode="before")
    def add_prefix(cls, value: str):
        return add_http_prefix(value)

    @field_validator("main_url", mode="after")
    def validate_url(cls, value: str):
        return validate_http_url(value)


class ShortenUrlResponse(BaseModel):
    main_url: str
    short_url: str
    custom_domain: Optional[str] = None
    max_clicks: int
    created_at: str
    updated_at: str
    expires_at: str


class UpdateShortenedUrlRequest(BaseModel):
    old_domain: str = Field(..., description="Current domain of the shortened URL")
    new_slug: Optional[str] = Field(None, description="New slug (short code)")
    new_domain: Optional[str] = Field(None, description="New domain")

    @field_validator("new_slug")
    def validate_slug_field(cls, value):
        return validate_slug(value)

    @field_validator("new_domain")
    def validate_domain_field(cls, value):
        return validate_domain(value)


class UpdateDestinationRequest(BaseModel):
    new_url: HttpUrl


class UpdateUrlSettingsRequest(BaseModel):
    expiry: Optional[str] = Field(None, description="Expiry duration like '30m', '2h', '1d', '1w', '1mo', '1y'")
    max_clicks: Optional[int] = Field(None, gt=0, description="Maximum allowed clicks before link expires")
    password: Optional[str] = Field(default=None, description="Optional password to protect access to the shortened URL. Set to empty string ('') to remove existing password.")

# ---------- Campaign Models ----------
class CampaignSourceCreate(BaseModel):
    user_id: str
    campaign_source_tag: str
    campaign_source_name: str

class CampaignMediumCreate(BaseModel):
    user_id: str
    campaign_medium_tag: str
    campaign_medium_name: str

class CampaignNameCreate(BaseModel):
    user_id: str
    campaign_name_tag: str
    campaign_name: str

class CampaignSourceUpdate(BaseModel):
    campaign_source_tag: Optional[str] = None
    campaign_source_name: Optional[str] = None

class CampaignMediumUpdate(BaseModel):
    campaign_medium_tag: Optional[str] = None
    campaign_medium_name: Optional[str] = None

class CampaignNameUpdate(BaseModel):
    campaign_name_tag: Optional[str] = None
    campaign_name: Optional[str] = None
