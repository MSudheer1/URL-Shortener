from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.params import Depends
from fastapi.responses import FileResponse
from dependencies import get_current_user
from tasks.workers import bulk_shorten_worker
from utils.file_utils import save_temp_file, get_result_file
from uuid import uuid4
import os
import logging

router = APIRouter(prefix="/bulk", tags=["Bulk Operations"])
logger = logging.getLogger(__name__)

@router.post("/shorten")
async def trigger_bulk_shorten(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported.")

        path = save_temp_file(file)
        print(f"✅ Path being sent to Celery: {path}")
        assert os.path.exists(path), f"🚨 File does not exist: {path}"
        job_id = uuid4().hex
        user_email = current_user

        logger.info(f"📤 Bulk shorten job started by {user_email} | job_id={job_id}")
        assert os.path.exists(path), f"File does not exist: {path}"

        bulk_shorten_worker.apply_async(args=[path, job_id, user_email], queue="bulk")
        return {"message": "Shorten job started", "job_id": job_id}

    except Exception as e:
        logger.exception("Failed to trigger bulk shorten")
        raise HTTPException(status_code=500, detail="Bulk shorten failed")

@router.get("/result/{job_id}")
async def get_result(job_id: str):
    path = get_result_file(job_id)
    if not path:
        raise HTTPException(status_code=404, detail="Result file not ready yet")

    return FileResponse(
        path,
        filename=f"bulk_result_{job_id}.csv",
        media_type="text/csv"
    )