from app.services.celery_app import celery_app
from app.rag.file_processor import file_processor
import logging
from fastapi import HTTPException, UploadFile


logger = logging.getLogger(__name__)

# file_processor = FileProcessor()
@celery_app.task(name="task.process_and_store_task")
def process_and_store_task(file_content: bytes, filename: str, user_id: str):
    try:
        from fastapi import UploadFile
        from io import BytesIO
        import asyncio

        # Rebuild UploadFile from raw bytes
        file_obj = BytesIO(file_content)
        file_obj.seek(0)  # ✅ Ensure we're at the beginning
        upload_file = UploadFile(filename=filename, file=BytesIO(file_content))
        upload_file.file.seek(0)  # ✅ Reset file pointer to beginning
        # Better async handling
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(file_processor.process_and_store(upload_file, user_id))
        return result

    except Exception as e:
        logger.error(f"❌ Celery task failed for {filename}: {e}")
        return {"success": False, "filename": filename, "error": str(e)}