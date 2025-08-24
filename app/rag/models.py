from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class FileUploadResponse(BaseModel):
    success: bool
    filename: str
    chunks_created: int
    total_characters: int
    total_words: int
    file_size: int
    upload_date: str
    message: str = "File uploaded and processed successfully"

class ChatHistoryRequest(BaseModel):
    session_id: str

class Chat_history_Response(BaseModel):
    session_id: str
    history: str
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000, description="User's question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    include_sources: bool = Field(True, description="Include source information in response")

class ChatSource(BaseModel):
    filename: str
    chunk_index: Optional[int] = None
    page_number: Optional[int] = None
    score: float
    upload_date: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[ChatSource]
    confidence: str = Field(..., description="Confidence level: high, medium, low, or error")
    retrieved_chunks: int
    conversation_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class VectorDBHealth(BaseModel):
    collection_name: str
    status: str
    vector_count: int
    vector_size: Optional[int] = None
    distance_metric: Optional[str] = None
    indexed: bool = False
    error: Optional[str] = None

class DeleteResponse(BaseModel):
    success: bool
    message: str
    deleted_count: Optional[int] = None

class DocumentSummary(BaseModel):
    total_documents: int
    total_chunks: int
    file_types: Dict[str, int]
    total_characters: int
    upload_dates: List[str]
    summary_text: Optional[str] = None