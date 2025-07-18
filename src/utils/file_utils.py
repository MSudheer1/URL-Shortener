import tempfile
import shutil
import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
RESULT_DIR = os.path.join(SRC_DIR, "results")
print(f"🧾 RESULT_DIR is: {RESULT_DIR}")
os.makedirs(RESULT_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def save_temp_file(file) -> str:
    try:
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
        with open(temp.name, "wb") as f:
            shutil.copyfileobj(file.file, f)
        abs_path = os.path.abspath(temp.name)
        logger.info(f"📁 Temp file saved: {abs_path}")
        return abs_path
    except Exception as e:
        logger.exception("❌ Failed to save temporary file")
        raise

def save_result_file(content: str, job_id: str) -> str:
    try:
        path = os.path.join(RESULT_DIR, f"bulk_result_{job_id}.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"✅ Result file saved: {path}")
        return path
    except Exception as e:
        logger.exception(f"❌ Failed to save result file for job_id={job_id}")
        raise

def get_result_file(job_id: str) -> str | None:
    path = os.path.join(RESULT_DIR, f"bulk_result_{job_id}.csv")
    if os.path.exists(path):
        return path
    logger.warning(f"⚠️ Result file not found for job_id={job_id}")
    return None