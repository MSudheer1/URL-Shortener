import re
from fastapi import HTTPException


def add_http_prefix(url: str) -> str:
    """Add http:// if protocol is missing."""
    if not re.match(r"^(http|https)://", url):
        return "http://" + url
    return url


def validate_http_url(url: str) -> str:
    """Check if the given URL is in valid HTTP/HTTPS format."""
    regex = re.compile(
        r"^(https?://)"                               # http or https
        r"((www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})"    # domain
        r"([/?].*)?$"                                  # optional path
    )
    if not regex.match(url):
        raise HTTPException(status_code=400, detail="Invalid main URL format")
    return url


def validate_slug(slug: str) -> str:
    """Check slug is alphanumeric and 5–30 characters."""
    if not re.match(r"^[a-zA-Z0-9_-]{5,30}$", slug):
        raise HTTPException(
            status_code=400,
            detail="Slug must be 5–30 characters and contain only a-z, A-Z, 0-9, -, _"
        )
    return slug


def validate_domain(domain: str) -> str:
    """Validate domain like madamanchi.com or sub.example.co.in."""
    regex = re.compile(
        r"^(http://|https://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
    )
    if not regex.match(domain):
        raise HTTPException(status_code=400, detail="Invalid domain format")
    return domain


def validate_email_format(email: str) -> str:
    """Simple email format validator."""
    regex = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
    if not regex.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    return email
