from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from jose import jwt
from datetime import datetime, timedelta
import os
from email.message import EmailMessage
import aiosmtplib
import pyotp

from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from core.db import get_db
from apps.shortener.models import User

router = APIRouter()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.mailgun.fit4hire.ai")
SMTP_PORT = os.getenv("SMTP_PORT", 587)
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")

class EmailRequest(BaseModel):
    email: EmailStr

class VerifyCodeOrOtpRequest(BaseModel):
    email: EmailStr
    code: str  # Can be either OTP or 4-digit code

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/auth/request-code")
async def request_code(email_request: EmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email_request.email).first()

    if not user:
        secret = pyotp.random_base32()
        user = User(email=email_request.email, otp_secret=secret, url_limit=5)
        db.add(user)
        db.commit()
    elif not user.otp_secret:
        user.otp_secret = pyotp.random_base32()
        db.commit()

    totp = pyotp.TOTP(user.otp_secret)
    code = totp.now()

    user.verification_code = code
    db.commit()

    try:
        message = EmailMessage()
        message["From"] = FROM_EMAIL
        message["To"] = user.email
        message["Subject"] = "Your One-Time Password (OTP)"
        message.set_content(f"Your OTP is: {code}")

        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USERNAME,
            password=SMTP_PASSWORD,
            start_tls=True
        )
        return {"message": "OTP sent to your email."}
    except Exception as e:
        print(f"Email sending failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send OTP email.")

@router.post("/auth/verify-code")
def verify_code(request: VerifyCodeOrOtpRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not user.verification_code:
        raise HTTPException(status_code=404, detail="User not found or verification code missing")

    if user.verification_code != request.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    user.verification_code = None
    db.commit()

    token = create_access_token(data={"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "email": user.email
    }
