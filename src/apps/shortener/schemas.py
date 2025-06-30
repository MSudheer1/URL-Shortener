from pydantic import BaseModel, field_validator, Field
from typing import Optional
import re


class ShortenUrlRequest(BaseModel):
    main_url: str

    @field_validator("main_url", mode="before")
    def add_http_prefix_to_url(cls, value: str):
        if not re.match(r"^(http|https)://", value):
            value = "http://" + value
        return value

    @field_validator("main_url", mode="after")
    def validate_http_url(cls, value: str):
        url_regex = re.compile(
            r"^(https?://)"                               # Protocol
            r"((www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})"    # Domain
            r"([/?].*)?$"                                  # Optional path/query
        )
        if not url_regex.match(value):
            raise ValueError("Invalid main URL format")
        return value


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
    def validate_new_slug(cls, value: Optional[str]):
        if value and not re.match(r"^[a-zA-Z0-9_-]{5,30}$", value):
            raise ValueError("Slug must be 5–30 characters and use only a-z, A-Z, 0-9, -, _")
        return value

    @field_validator("new_domain")
    def validate_new_domain(cls, value: Optional[str]):
        if value:
            domain_regex = re.compile(
                r"^(http://|https://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
            )
            if not domain_regex.match(value):
                raise ValueError("Invalid domain format")
        return value


# class UpdateShortUrlRequest(BaseModel):
#     new_slug: Optional[str] = None
#     new_domain: Optional[str] = None

#     @field_validator("new_slug")
#     def validate_new_slug(cls, value: Optional[str]):
#         if value and not re.match(r"^[a-zA-Z0-9_-]{5,30}$", value):
#             raise ValueError("Slug must be 5–30 characters and use only a-z, A-Z, 0-9, -, _")
#         return value

#     @field_validator("new_domain")
#     def validate_new_domain(cls, value: Optional[str]):
#         if value:
#             domain_regex = re.compile(
#                 r"^(http://|https://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
#             )
#             if not domain_regex.match(value):
#                 raise ValueError("Invalid domain format")
#         return value




# 🆕 Patch Update Schemas

# class UpdateSlugRequest(BaseModel):
#     old_slug: str
#     new_slug: str
#     domain: Optional[str] = ""

#     @field_validator("new_slug")
#     def validate_new_slug(cls, value: str):
#         if not re.match(r"^[a-zA-Z0-9_-]{5,30}$", value):
#             raise ValueError("New slug must be 5–30 characters and use only a-z, A-Z, 0-9, -, _")
#         return value


# class UpdateDomainRequest(BaseModel):
#     slug: str
#     old_domain: Optional[str] = ""
#     new_domain: str

#     @field_validator("new_domain")
#     def validate_new_domain(cls, value: str):
#         domain_regex = re.compile(
#             r"^(http://|https://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
#         )
#         if not domain_regex.match(value):
#             raise ValueError("Invalid new domain format")
#         return value


# class UpdateSlugAndDomainRequest(BaseModel):
#     old_slug: str
#     old_domain: Optional[str] = ""
#     new_slug: str
#     new_domain: str

#     @field_validator("new_slug")
#     def validate_new_slug(cls, value: str):
#         if not re.match(r"^[a-zA-Z0-9_-]{5,30}$", value):
#             raise ValueError("New slug must be 5–30 characters and use only a-z, A-Z, 0-9, -, _")
#         return value

#     @field_validator("new_domain")
#     def validate_new_domain(cls, value: str):
#         domain_regex = re.compile(
#             r"^(http://|https://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
#         )
#         if not domain_regex.match(value):
#             raise ValueError("Invalid new domain format")
#         return value