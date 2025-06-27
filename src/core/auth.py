from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from jose import jwt
from datetime import datetime, timedelta
import random
import os
from email.message import EmailMessage
import aiosmtplib
import pyotp  # ✅ OTP library


from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from core.db import get_db
from apps.shortener.models import User

auth_router = APIRouter()
router = APIRouter()

# # === Mailtrap Config ===
# MAILTRAP_HOST = "smtp.mailtrap.io"
# MAILTRAP_PORT = 587
# MAILTRAP_USERNAME = os.getenv("MAILTRAP_USERNAME", "your_mailtrap_username")
# MAILTRAP_PASSWORD = os.getenv("MAILTRAP_PASSWORD", "your_mailtrap_password")
# FROM_EMAIL = "no-reply@example.com"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.mailgun.fit4hire.ai")  # <-- Replace this
SMTP_PORT = os.getenv("SMTP_PORT", 587)  # <-- Replace this
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")

# === Schemas ===
class EmailRequest(BaseModel):
    email: EmailStr

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

# === JWT Generation ===
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# === Email Sender ===
# async def send_verification_email(recipient: str, code: str):
    # message = EmailMessage()
    # message["From"] = FROM_EMAIL
    # message["To"] = recipient
    # message["Subject"] = "Your Verification Code"
    # message.set_content(f"Your verification code is: {code}")

    # await aiosmtplib.send(
    #     message,
    #     hostname=MAILTRAP_HOST,
    #     port=MAILTRAP_PORT,
    #     username=MAILTRAP_USERNAME,
    #     password=MAILTRAP_PASSWORD,
    #     start_tls=True
    # )
    # try:
    #     message = EmailMessage()
    #     message["From"] = FROM_EMAIL
    #     message["To"] = user.email
    #     message["Subject"] = "Your One-Time Password (OTP)"
    #     message.set_content(f"Your OTP is: {otp}")

    #     await aiosmtplib.send(
    #         message,
    #         hostname=SMTP_HOST,
    #         port=SMTP_PORT,
    #         username=SMTP_USERNAME,
    #         password=SMTP_PASSWORD,
    #         start_tls=True
    #     )
    #     print(SMTP_HOST)
    #     print(f"OTP email sent to {user.email}")
    # except Exception as e:
    #     print(f"OTP email sending failed: {e}")
    #     raise HTTPException(status_code=500, detail="Failed to send OTP email.")

    # return {"message": "OTP sent to your email."}

# === Endpoints ===
@auth_router.get("/auth/ping")
def ping_auth():
    return {"message": "Auth router works!"}

@router.post("/auth/request-verification")
async def request_verification(email_request: EmailRequest, db: Session = Depends(get_db)):
    code = str(random.randint(1000, 9999))
    print(f"Generated verification code: {code}")
    print(f"SMTP_HOST: {SMTP_HOST}",{"SMTP_PORT": SMTP_PORT, "SMTP_USERNAME": SMTP_USERNAME, "SMTP_PASSWORD": SMTP_PASSWORD})  # Debugging info


    user = db.query(User).filter(User.email == email_request.email).first()

    if user:
        user.verification_code = code
    else:
        user = User(email=email_request.email, verification_code=code, url_limit=5)
        db.add(user)

    db.commit()

    try:
        # await send_verification_email(user.email, code)
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
        print(SMTP_HOST)
        print(f"OTP email sent to {user.email}")
        print(f"Email sent to {user.email} with code: {code}")
        return {"message": "OTP sent to your email."}
    except Exception as e:
        print(f"Email sending failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification email.")

    return {"message": "Verification code sent."}

@router.post("/auth/verify-code")
def verify_code(request: VerifyCodeRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if not user or user.verification_code != request.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    user.verification_code = None
    db.commit()

    token = create_access_token(data={"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}

# === OTP-based login ===
# @router.post("/auth/request-otp")
# async def request_otp(email_request: EmailRequest, db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.email == email_request.email).first()

#     if not user:
#         secret = pyotp.random_base32()
#         user = User(email=email_request.email, otp_secret=secret)
#         db.add(user)
#         db.commit()
#     elif not user.otp_secret:
#         user.otp_secret = pyotp.random_base32()
#         db.commit()

#     totp = pyotp.TOTP(user.otp_secret)
#     otp = totp.now()
#     print(f"Generated OTP for {user.email}: {otp}")

#     # ✅ Send OTP via email
#     try:
#         await send_verification_email(user.email, otp)
#         print(f"OTP email sent to {user.email}")
#     except Exception as e:
#         print(f"OTP email sending failed: {e}")
#         raise HTTPException(status_code=500, detail="Failed to send OTP email.")

#     return {"message": "OTP sent to your email."}



@router.post("/auth/request-otp")
async def request_otp(email_request: EmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email_request.email).first()

    if not user:
        secret = pyotp.random_base32()
        user = User(email=email_request.email, otp_secret=secret)
        db.add(user)
        db.commit()
    elif not user.otp_secret:
        user.otp_secret = pyotp.random_base32()
        db.commit()

    totp = pyotp.TOTP(user.otp_secret)
    otp = totp.now()
    print(f"Generated OTP for {user.email}: {otp}")

    # ✅ Send OTP via email using hardcoded SMTP
    try:
        message = EmailMessage()
        message["From"] = FROM_EMAIL
        message["To"] = user.email
        message["Subject"] = "Your One-Time Password (OTP)"
        message.set_content(f"Your OTP is: {otp}")

        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USERNAME,
            password=SMTP_PASSWORD,
            start_tls=True
        )
        print(SMTP_HOST)
        print(f"OTP email sent to {user.email}")
    except Exception as e:
        print(f"OTP email sending failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send OTP email.")

    return {"message": "OTP sent to your email."}

# @router.post("/auth/verify-otp")
# def verify_otp(request: OTPVerifyRequest, db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.email == request.email).first()

#     if not user or not user.otp_secret:
#         raise HTTPException(status_code=404, detail="User not found or OTP not setup")

#     totp = pyotp.TOTP(user.otp_secret)

#     if not totp.verify(request.otp):
#         raise HTTPException(status_code=400, detail="Invalid or expired OTP")

#     token = create_access_token(data={"sub": user.email})
#     return {"access_token": token, "token_type": "bearer"}


@router.post("/auth/verify-otp")
def verify_otp(request: OTPVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not user.verification_code:
        raise HTTPException(status_code=404, detail="User not found or verification code missing")

    if user.verification_code != request.otp:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    # Clear verification code after successful use
    user.verification_code = None
    db.commit()

    # ✅ Generate JWT
    token = create_access_token(data={"sub": user.email})

    return {
        "access_token": token,
        "token_type": "bearer",
        "email": user.email  # Optional: return email for frontend use
    }
