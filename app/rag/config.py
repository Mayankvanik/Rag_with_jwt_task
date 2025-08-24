# from pydantic_settings import BaseSettings
# import os
# from dotenv import load_dotenv

# load_dotenv()

# class RAGSettings(BaseSettings):
#     # Qdrant Configuration
#     qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
#     qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    
#     # LLM Configuration
#     google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
#     openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    
#     # RAG Settings
#     collection_name: str = os.getenv("COLLECTION_NAME", "rag_documents")
#     chunk_size: int = int(os.getenv("CHUNK_SIZE", 1000))
#     chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", 100))
    
#     # File Upload Settings
#     max_file_size: int = int(os.getenv("MAX_FILE_SIZE", 10485760))  # 10MB
#     allowed_file_types: list = os.getenv("ALLOWED_FILE_TYPES", "pdf,txt,md").split(",")
    
#     # Vector Search Settings
#     vector_size: int = 1536  # OpenAI ada-002 embedding size
#     top_k_results: int = 5
#     similarity_threshold: float = 0.7

#     class Config:
#         env_file = ".env"

# rag_settings = RAGSettings()