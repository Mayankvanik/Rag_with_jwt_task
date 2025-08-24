from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile, Form,BackgroundTasks
from fastapi.responses import JSONResponse
from app.auth.auth_utils import get_current_user, get_current_admin_user
from app.rag.file_processor import file_processor
from app.rag.rag_system import rag_system
from app.rag.vector_db import text_chunker
from app.rag.models import (
    FileUploadResponse, 
    ChatRequest, 
    ChatResponse, 
    VectorDBHealth, 
    DeleteResponse,
    DocumentSummary,
    ChatHistoryRequest,
    Chat_history_Response
)
from app.services.database import upsert_message_in_session,fetch_message_history
from app.services.task import process_and_store_task
from typing import List
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["RAG Chat System"])

@router.post("/upload", response_model=FileUploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="Document to upload (PDF, TXT, or Markdown)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload and process documents (PDFs, TXT, or Markdown files) for RAG system
    """
    try:
        user_id = current_user.get("username")
        
        # Process and store the file
        result = await file_processor.process_and_store(file, user_id)
        
        logger.info(f"✅ Document uploaded successfully by user: {user_id}")
        
        return FileUploadResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Document upload error for user {current_user.get('username')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )

@router.post("/ask", response_model=ChatResponse)
async def chat_with_documents(
    chat_request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Chat with your uploaded documents using RAG
    """
    try:
        user_id = current_user.get("username")
        await upsert_message_in_session(user_id, chat_request.question, msg_type="user")
        
        # Generate conversation ID if not provided
        conversation_id = chat_request.conversation_id or str(uuid.uuid4())
        
        # Get response from RAG system
        rag_response = await rag_system.generate_response(
            query=chat_request.question,
            user_id=user_id,
            conversation_history=[]  # You can implement conversation history storage here
        )
        
        # Format sources if requested
        sources = []
        if chat_request.include_sources and rag_response.get("sources"):
            sources = [
                {
                    "filename": source.get("filename", "Unknown"),
                    "chunk_index": source.get("chunk_index"),
                    "page_number": source.get("page_number"),
                    "score": source.get("score", 0.0),
                    "upload_date": source.get("upload_date")
                }
                for source in rag_response["sources"]
            ]
        
        await upsert_message_in_session(user_id, rag_response["response"], msg_type="Ai_assistant")
        response = ChatResponse(
            response=rag_response["response"],
            sources=sources,
            confidence=rag_response.get("confidence", "medium"),
            retrieved_chunks=rag_response.get("retrieved_chunks", 0),
            conversation_id=conversation_id
        )
        
        logger.info(f"✅ Chat response generated for user: {user_id}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Chat error for user {current_user.get('username')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate response: {str(e)}"
        )


@router.post("/chat_history", response_model=Chat_history_Response)
async def get_chat_history(request: ChatHistoryRequest): #
    """
    Fetch chat history for a given session_id
    """
    try:
        history = await fetch_message_history(request.session_id)
        return Chat_history_Response(session_id=request.session_id, history=history)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch chat history: {str(e)}"
        )

@router.delete("/documents", response_model=DeleteResponse)
async def delete_user_documents(
    current_user: dict = Depends(get_current_user)
):
    """
    Delete all documents from vector database for current user
    """
    try:
        user_id = current_user.get("username")
        
        # Delete user's documents
        success = await text_chunker.delete_user_documents(user_id)
        
        if success:
            logger.info(f"✅ Documents deleted for user: {user_id}")
            return DeleteResponse(
                success=True,
                message="All your documents have been deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete documents"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Document deletion error for user {current_user.get('username')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete documents: {str(e)}"
        )

@router.delete("/vector-db", response_model=DeleteResponse)
async def delete_vector_database(
    current_user: dict = Depends(get_current_user)
):
    """
    Delete entire vector database collection (Admin only - be careful!)
    """
    try:
        # Check if user is admin
        if current_user.get("username") != "admin" and not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can delete the entire vector database"
            )
        
        # Delete entire collection
        success = await text_chunker.delete_collection()
        
        if success:
            logger.warning(f"⚠️ Vector database deleted by admin: {current_user.get('username')}")
            return DeleteResponse(
                success=True,
                message="Vector database has been completely deleted"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete vector database"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Vector DB deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete vector database: {str(e)}"
        )

@router.get("/health", response_model=VectorDBHealth)
async def check_vector_db_health(
    current_user: dict = Depends(get_current_user)
):
    """
    Check the health and status of the vector database
    """
    try:
        health_info = await text_chunker.get_collection_info()
        
        return VectorDBHealth(**health_info)
        
    except Exception as e:
        logger.error(f"❌ Health check error: {e}")
        return VectorDBHealth(
            collection_name="unknown",
            status="error",
            vector_count=0,
            indexed=False,
            error=str(e)
        )

@router.get("/documents/summary", response_model=DocumentSummary)
async def get_documents_summary(
    current_user: dict = Depends(get_current_user)
):
    """
    Get summary of user's uploaded documents
    """
    try:
        user_id = current_user.get("username")
        
        # Search for user's documents (get all with a generic query)
        user_docs = await text_chunker.search_documents(
            query="",  # Empty query to get all documents
            user_id=user_id,
            limit=1000  # High limit to get all documents
        )
        
        if not user_docs:
            return DocumentSummary(
                total_documents=0,
                total_chunks=0,
                file_types={},
                total_characters=0,
                upload_dates=[]
            )
        
        # Analyze documents
        file_types = {}
        upload_dates = set()
        total_characters = 0
        unique_files = set()
        
        for doc in user_docs:
            metadata = doc.get("metadata", {})
            filename = metadata.get("filename", "unknown")
            file_type = metadata.get("file_type", "unknown")
            upload_date = metadata.get("upload_date")
            chunk_size = metadata.get("chunk_size", 0)
            
            unique_files.add(filename)
            file_types[file_type] = file_types.get(file_type, 0) + 1
            total_characters += chunk_size
            
            if upload_date:
                upload_dates.add(upload_date)
        
        return DocumentSummary(
            total_documents=len(unique_files),
            total_chunks=len(user_docs),
            file_types=file_types,
            total_characters=total_characters,
            upload_dates=sorted(list(upload_dates))
        )
        
    except Exception as e:
        logger.error(f"❌ Document summary error for user {current_user.get('username')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document summary: {str(e)}"
        )

@router.post("/documents/batch-upload")
async def batch_upload_documents(
    files: List[UploadFile] = File(..., description="Multiple documents to upload"),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload multiple documents at once
    """
    try:
        user_id = current_user.get("username")
        results = []
        errors = []
        
        for file in files:
            try:
                result = await file_processor.process_and_store(file, user_id)
                results.append({
                    "filename": result["filename"],
                    "status": "success",
                    "chunks_created": result["chunks_created"]
                })
            except Exception as e:
                errors.append({
                    "filename": file.filename,
                    "status": "error",
                    "error": str(e)
                })
        
        logger.info(f"✅ Batch upload completed for user: {user_id}")
        
        return {
            "success": len(errors) == 0,
            "total_files": len(files),
            "successful_uploads": len(results),
            "failed_uploads": len(errors),
            "results": results,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"❌ Batch upload error for user {current_user.get('username')}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch upload failed: {str(e)}"
        )
    

@router.post("/documents/batch-upload-celery")
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        user_id = current_user.get("username")
        task_ids = []
        
        logger.info(f"📁 Starting batch upload of {len(files)} files for user {user_id}")

        for i, file in enumerate(files):
            file_content = await file.read()
            logger.info(f"📄 File {i+1}/{len(files)}: {file.filename}, size={len(file_content)} bytes")
            
            if len(file_content) == 0:
                logger.warning(f"⚠️ File {file.filename} is empty!")
                continue
                
            task = process_and_store_task.delay(file_content, file.filename, user_id)
            task_ids.append({
                "filename": file.filename,
                "task_id": task.id,
                "status": "queued"
            })
            logger.info(f"✅ Queued task {task.id} for {file.filename}")

        logger.info(f"🎉 Successfully queued {len(task_ids)} tasks")
        return {
            "success": True,
            "total_files": len(files),
            "queued_tasks": task_ids
        }

    except Exception as e:
        logger.error(f"❌ Batch upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")
