from pydantic import BaseModel, field_validator, HttpUrl, AnyHttpUrl
from datetime import datetime
from typing import Optional
from apps.shortener.enums import ExpirationUnitEnum

import re


class ShortenUrlRequest(BaseModel):
    main_url: str
    duration_value: int = 1 # Default to 1 hour
    duration_unit: ExpirationUnitEnum = ExpirationUnitEnum.hours
    max_clicks: Optional[int] = None
    custom_domain: Optional[str] = None
    custom_code: Optional[str] = None

    @field_validator("main_url", mode="before")
    def add_http_prefix_to_url(cls, value: str):
        if not re.match(r"^(http|https)://", value):
            value = "http://" + value
        return value

    @field_validator("main_url", mode="after")
    def validate_http_url(cls, value: str):
        url_regex = re.compile(
            r"^(https?://)"                              # Protocol
            r"((www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})"   # Domain
            r"([/?].*)?$"                                 # Optional path/query
        )
        if not url_regex.match(value):
            raise ValueError("Invalid main URL format")
        return value

    @field_validator("custom_domain", mode="after")
    def validate_custom_domain(cls, value: Optional[str]):
        if value:
            domain_regex = re.compile(
                r"^(http://|https://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
            )
            if not domain_regex.match(value):
                raise ValueError("Invalid custom domain format")
        return value


class ShortenUrlResponse(BaseModel):
    main_url: str
    short_url: str
    custom_domain: Optional[str] = None
    max_clicks: Optional[int] = None
    created_at: str
    updated_at: str
    expires_at: str
