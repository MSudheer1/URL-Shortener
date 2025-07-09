import re
import string
import random
from datetime import timedelta, datetime
from fastapi import HTTPException
import pytz


class Validator:

    # === Password Validation ===
    @staticmethod
    def validate_password_strength(password: str):
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", password):
            raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", password):
            raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter.")
        if not re.search(r"\d", password):
            raise HTTPException(status_code=400, detail="Password must contain at least one digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise HTTPException(status_code=400, detail="Password must contain at least one special character.")
        if re.match(r"^[!@#$%^&*(),.?\":{}|<>_\-+=]", password):
            raise HTTPException(status_code=400, detail="Password should not start with a special character.")

    # === Expiry Format Validation ===
    @staticmethod
    def parse_duration_string(duration_str: str) -> timedelta:
        match = re.match(r"^(\d+)([mhdwy])$", duration_str)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid expiry format")
        value, unit = int(match[1]), match[2]
        if unit == "m": return timedelta(minutes=value)
        if unit == "h": return timedelta(hours=value)
        if unit == "d": return timedelta(days=value)
        if unit == "w": return timedelta(weeks=value)
        if unit == "y": return timedelta(days=365 * value)
        raise HTTPException(status_code=400, detail="Unsupported expiry format")

    # === URL Validations ===
    @staticmethod
    def add_http_prefix(url: str) -> str:
        if not re.match(r"^(http|https)://", url):
            return "http://" + url
        return url

    @staticmethod
    def validate_http_url(url: str) -> str:
        regex = re.compile(
            r"^(https?://)"                               # http or https
            r"((www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})"    # domain
            r"([/?].*)?$"                                  # optional path
        )
        if not regex.match(url):
            raise HTTPException(status_code=400, detail="Invalid main URL format")
        return url

    # === Slug Validation ===
    @staticmethod
    def validate_slug(slug: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]{5,30}$", slug):
            raise HTTPException(
                status_code=400,
                detail="Slug must be 5–30 characters and contain only a-z, A-Z, 0-9, -, _"
            )
        return slug

    # === Domain Validation ===
    @staticmethod
    def validate_domain(domain: str) -> str:
        regex = re.compile(
            r"^(http://|https://)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
        )
        if not regex.match(domain):
            raise HTTPException(status_code=400, detail="Invalid domain format")
        return domain

    # === Email Validation ===
    @staticmethod
    def validate_email_format(email: str) -> str:
        regex = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
        if not regex.match(email):
            raise HTTPException(status_code=400, detail="Invalid email format")
        return email

    # === Random Short Code Generation ===
    @staticmethod
    def generate_random_characters(length: int) -> str:
        if length < 2:
            raise ValueError("Length must be at least 2 to include both letter and digit.")
        char_set = string.ascii_letters + string.digits
        code = [random.choice(string.ascii_letters), random.choice(string.digits)]
        code += [random.choice(char_set) for _ in range(length - 2)]
        random.shuffle(code)
        return ''.join(code)

    # === Time Conversion ===
    @staticmethod
    def utc_to_ist(utc_dt: datetime) -> datetime:
        ist = pytz.timezone("Asia/Kolkata")
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        return utc_dt.astimezone(ist)

    # === Redis Helpers ===
    @staticmethod
    def build_redis_key(domain: str, short_code: str) -> str:
        clean_domain = domain.replace("http://", "").replace("https://", "").rstrip("/").lower()
        return f"{clean_domain}:{short_code}"

    # === Domain Normalization ===
    @staticmethod
    def normalize_domain(domain: str) -> str:
        return domain.replace("http://", "").replace("https://", "").split(":")[0].strip().lower()

    # === Domain Prefix ===
    @staticmethod
    def ensure_http_prefix(url: str) -> str:
        if not url.startswith("http://") and not url.startswith("https://"):
            return f"https://{url}"
        return url

    # === Ownership Permission Check ===
    @staticmethod
    def ensure_owner_permission(record, user_email: str):
        if record.owner_email != user_email:
            raise HTTPException(status_code=403, detail="You do not have permission to modify this URL")
