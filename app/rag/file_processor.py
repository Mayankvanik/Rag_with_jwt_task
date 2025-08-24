import os
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import HTTPException, UploadFile
import PyPDF2
import io
from app.config import settings
settings
from .vector_db import text_chunker

logger = logging.getLogger(__name__)

class FileProcessor:
    """
    Handles file upload, processing, and text extraction
    """
    
    def __init__(self):
        self.max_file_size = settings.max_file_size
        self.allowed_extensions = settings.allowed_file_types
    
    def validate_file(self, file: UploadFile) -> bool:
        """Validate uploaded file"""
        try:
            # Check file size
            if file.size and file.size > self.max_file_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {self.max_file_size / (1024*1024):.1f}MB"
                )
            
            # Check file extension
            if file.filename:
                extension = file.filename.split('.')[-1].lower()
                if extension not in self.allowed_extensions:
                    raise HTTPException(
                        status_code=400,
                        detail=f"File type not supported. Allowed types: {', '.join(self.allowed_extensions)}"
                    )
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ File validation error: {e}")
            raise HTTPException(status_code=400, detail="File validation failed")
    
    async def extract_text_from_file(self, file: UploadFile) -> Dict:
        """Extract text content from uploaded file"""
        try:
            self.validate_file(file)
            
            # Read file content
            content = await file.read()
            filename = file.filename
            file_extension = filename.split('.')[-1].lower() if filename else ""
            
            # Extract text based on file type
            if file_extension == 'pdf':
                text = await self._extract_from_pdf(content)
            elif file_extension in ['txt', 'md']:
                text = await self._extract_from_text(content)
            else:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file type: {file_extension}"
                )
            
            # Prepare metadata
            metadata = {
                "filename": filename,
                "file_type": file_extension,
                "file_size": len(content),
                "upload_date": datetime.utcnow().isoformat(),
                "character_count": len(text),
                "word_count": len(text.split())
            }
            
            logger.info(f"✅ Extracted text from {filename}: {len(text)} characters")
            
            return {
                "text": text,
                "metadata": metadata
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Text extraction error: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to extract text from file: {str(e)}"
            )
    
    async def _extract_from_pdf(self, content: bytes) -> str:
        """Extract text from PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            text_parts = []
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():
                    # Add page number information
                    text_parts.append(f"[Page {page_num}]\n{page_text}")
            
            full_text = "\n\n".join(text_parts)
            
            if not full_text.strip():
                raise HTTPException(
                    status_code=400, 
                    detail="Could not extract text from PDF. The PDF might be image-based or corrupted."
                )
            
            return full_text
            
        except Exception as e:
            logger.error(f"❌ PDF extraction error: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to extract text from PDF: {str(e)}"
            )
    
    async def _extract_from_text(self, content: bytes) -> str:
        """Extract text from TXT or Markdown file"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    text = content.decode(encoding)
                    return text
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail
            raise HTTPException(
                status_code=400, 
                detail="Could not decode text file. Please ensure it's in UTF-8 format."
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Text extraction error: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to extract text: {str(e)}"
            )
    
    async def process_and_store(
        self, 
        file: UploadFile, 
        user_id: str
    ) -> Dict:
        """Process file and store in vector database"""
        try:
            # Extract text from file
            extraction_result = await self.extract_text_from_file(file)
            text = extraction_result["text"]
            metadata = extraction_result["metadata"]
            
            # Add user ID to metadata
            metadata["user_id"] = user_id
            
            # Chunk the text
            chunks = await text_chunker.chunk_text(text, metadata)
            
            if not chunks:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to create text chunks from the document"
                )
            
            # Store chunks in vector database
            success = await text_chunker.store_documents(chunks, user_id)
            
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to store document in vector database"
                )
            
            logger.info(f"✅ Processed and stored {file.filename} for user {user_id}")
            
            return {
                "success": True,
                "filename": metadata["filename"],
                "chunks_created": len(chunks),
                "total_characters": metadata["character_count"],
                "total_words": metadata["word_count"],
                "file_size": metadata["file_size"],
                "upload_date": metadata["upload_date"]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ File processing error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process and store file: {str(e)}"
            )

# Create global instance
file_processor = FileProcessor()