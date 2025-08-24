"""
RAG (Retrieval Augmented Generation) System

This module provides a complete RAG implementation with:
- Document processing and chunking
- Vector storage with Qdrant
- Similarity search and retrieval
- LLM integration with Google Gemini
- File upload and processing
"""

from app.rag.vector_db import text_chunker
from app.rag.rag_system import rag_system
from app.rag.file_processor import file_processor

__all__ = [
    "text_chunker", 
    "rag_system",
    "file_processor"
]