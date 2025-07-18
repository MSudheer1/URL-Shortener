import csv
import os
import asyncio
from datetime import datetime
from sqlalchemy.future import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.shortener.models import ShortenedUrl
from utils.password_utils import hash_password
from utils.validators import Validator
from tasks.celery_app import celery_app
from services.db import get_bulk_session  
from utils.file_utils import RESULT_DIR
from core.config import app_config

FIELDNAMES = ["row", "input", "status", "error"]

@celery_app.task(name="tasks.workers.bulk_shorten_worker", queue="bulk")
def bulk_shorten_worker(file_path: str, job_id: str, user_email: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_bulk_task(file_path, job_id, user_email, task_type="shorten"))


async def run_bulk_task(file_path: str, job_id: str, user_email: str, task_type: str):
    print(f"📥 Celery received file_path: {file_path}")
    print(f"🧪 Exists? {os.path.exists(file_path)}")

    result_path = os.path.join(RESULT_DIR, f"bulk_result_{job_id}.csv")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found at: {file_path}")

    with open(file_path, "r", newline="", encoding="utf-8") as infile, \
         open(result_path, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=FIELDNAMES)
        writer.writeheader()

        async with get_bulk_session() as session:
            for idx, row in enumerate(reader, start=1):
                try:
                    if task_type == "shorten":
                        await process_shorten(session, row, writer, idx, user_email=user_email)
                except Exception as e:
                    await session.rollback()
                    writer.writerow({
                        "row": idx,
                        "input": row.get("main_url", ""),
                        "status": "failed",
                        "error": str(e),
                    })

async def process_shorten(session: AsyncSession, row: dict, writer, idx: int, user_email: str):
    input_url = row.get("main_url", "").strip()
    custom_slug = row.get("custom_slug", "").strip() or None
    custom_domain = row.get("custom_domain", "").strip() or app_config.default_domain
    expiry_str = row.get("expiry", "").strip() or "1h"
    
    try:
        max_clicks = int(row.get("max_clicks", "").strip() or 5)
    except ValueError:
        max_clicks = 5  # default fallback

    password = row.get("password", "").strip() or None
    title = row.get("title", "").strip() or None
    owner_email = row.get("user_email", "").strip() or user_email

    if not input_url:
        writer.writerow({
            "row": idx,
            "input": input_url,
            "status": "failed",
            "error": "Missing 'main_url'"
        })
        return

    if not owner_email:
        writer.writerow({
            "row": idx,
            "input": input_url,
            "status": "failed",
            "error": "Missing 'user_email'"
        })
        return

    try:
        short_code = custom_slug
        for _ in range(5):
            candidate_code = short_code or Validator.generate_random_characters(5)
            stmt = select(ShortenedUrl).where(ShortenedUrl.short_url == candidate_code)
            result = await session.execute(stmt)
            existing_url = result.scalar_one_or_none()
            if not existing_url:
                short_code = candidate_code
                break
            if custom_slug:
                raise ValueError(f"Custom slug '{custom_slug}' already exists")

        now = datetime.utcnow()
        expires_at = now + Validator.parse_duration_string(expiry_str)
        password_hash = hash_password(password) if password else None

        new_url = ShortenedUrl(
            main_url=input_url,
            short_url=short_code,
            custom_domain=custom_domain,
            title=title,
            click_count=0,
            max_clicks=max_clicks,
            active=True,
            expired=False,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            owner_email=owner_email,
            password_hash=password_hash,
        )

        session.add(new_url)
        await session.commit()

        writer.writerow({
            "row": idx,
            "input": input_url,
            "status": "success",
            "error": ""
        })

    except Exception as e:
        await session.rollback()
        writer.writerow({
            "row": idx,
            "input": input_url,
            "status": "failed",
            "error": str(e)
        })
