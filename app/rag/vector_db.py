from qdrant_client import QdrantClient, models
from qdrant_client.models import PointStruct, VectorParams, Distance
import asyncio
from typing import List, Dict, Optional
from dotenv import load_dotenv
from qdrant_client.models import Filter, FilterSelector, FieldCondition, MatchValue
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain.text_splitter import MarkdownHeaderTextSplitter, CharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import Qdrant
from langchain_openai import ChatOpenAI
import os
from app.config import settings
import sys
import logging
import uuid

load_dotenv(override=True)

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TextChunker:
    """
    Handles text chunking and metadata enrichment for document processing.
    Uses Document objects with Qdrant vectorstore (file_b style) while retaining file_a functionality.
    """

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.embedding_model = OpenAIEmbeddings(model='text-embedding-ada-002', api_key=settings.openai_api_key)
        self.openai_llm = ChatOpenAI(model="gpt-4o", temperature=0.4)
        self.collection_name = settings.collection_name

        # Initialize Qdrant client
        if settings.qdrant_api_key:
            self.qdrant_client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key
            )
        else:
            self.qdrant_client = QdrantClient(url=settings.qdrant_url)

        # Initialize multiple text splitters (from file_b)
        self.SemanticChunk_splitter = SemanticChunker(
            embeddings=self.embedding_model,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=0.98,
            number_of_chunks=self.chunk_size, 
        )

        self.Character_splitter = CharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separator=" ",
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
        )

        self.markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on = [
            ("##", "section"),
        ])

        # Initialize Qdrant vectorstore with the new import (file_b style)
        self.vectorstore = Qdrant(
            client=self.qdrant_client,
            collection_name=self.collection_name,
            embeddings=self.embedding_model
        )

    async def initialize_collection(self) -> bool:
        """Initialize Qdrant collection if it doesn't exist"""
        try:
            # Check if collection exists
            collection_exists = self.qdrant_client.collection_exists(collection_name=self.collection_name)
            
            if not collection_exists:
                # Create collection
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=settings.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Created collection: {self.collection_name}")
            else:
                logger.info(f"✅ Collection already exists: {self.collection_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing collection: {e}")
            return False

    async def chunk_text(self, text: str, metadata: Dict = None, chunking_method: str = "recursive") -> List[Document]:
        """
        Chunk text into smaller pieces with metadata using Document objects
        
        Args:
            text: Input text to chunk
            metadata: Additional metadata to include
            chunking_method: Type of chunking ("recursive", "semantic", "character", "markdown")
        """
        try:
            # Select chunking method
            if chunking_method == "semantic":
                chunks = self.SemanticChunk_splitter.split_text(text)
            elif chunking_method == "character":
                chunks = self.Character_splitter.split_text(text)
            elif chunking_method == "markdown":
                chunks = self.markdown_splitter.split_text(text)
            else:  # default recursive
                chunks = self.text_splitter.split_text(text)
            
            documents = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk),
                    "chunking_method": chunking_method,
                    **(metadata or {})
                }
                
                documents.append(Document(
                    page_content=chunk,
                    metadata=chunk_metadata
                ))
            
            logger.info(f"✅ Created {len(documents)} chunks using {chunking_method} method")
            return documents
            
        except Exception as e:
            logger.error(f"❌ Error chunking text: {e}")
            return []

    async def store_documents(self, documents: List[Document], user_id: str = None) -> bool:
        """
        Store documents in Qdrant vector database using vectorstore
        """
        try:
            await self.initialize_collection()
            
            # Add user_id to metadata if provided
            if user_id:
                for doc in documents:
                    doc.metadata["user_id"] = user_id
                    doc.metadata["point_id"] = str(uuid.uuid4())
            
            # Store using vectorstore (file_b style)
            self.vectorstore.add_documents(documents)
            
            logger.info(f"✅ Stored {len(documents)} documents in vector database")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing documents: {e}")
            return False

    async def process_and_store_pdf(self, text: str, file_name: str, website_url: str = None, 
                                  tag: str = None, title: str = None, user_id: str = None) -> Dict:
        """
        Process PDF text using semantic chunking and store in Qdrant
        """
        try:
            metadata = {
                "file_name": file_name,
                "website_url": website_url,
                "tag": tag,
                "title": title,
                "document_type": "pdf"
            }
            
            documents = await self.chunk_text(text, metadata, "semantic")
            
            if not documents:
                return {"success": False, "error": "Failed to chunk text"}
            
            success = await self.store_documents(documents, user_id)
            
            if success:
                return {"success": True, "message": f"PDF documents stored in Qdrant collection '{self.collection_name}'."}
            else:
                return {"success": False, "error": "Failed to store documents"}
                
        except Exception as e:
            logger.error(f"Error processing and storing PDF: {str(e)}")
            return {"success": False, "error": str(e)}

    async def process_and_store_webpage(self, text: str, file_name: str, website_url: str = None,
                                      tag: str = None, title: str = None, user_id: str = None) -> Dict:
        """
        Process webpage text using recursive chunking and store in Qdrant
        """
        try:
            metadata = {
                "file_name": file_name,
                "website_url": website_url,
                "tag": tag,
                "title": title,
                "document_type": "webpage"
            }
            
            documents = await self.chunk_text(text, metadata, "recursive")
            
            if not documents:
                return {"success": False, "error": "Failed to chunk text"}
            
            success = await self.store_documents(documents, user_id)
            
            if success:
                return {"success": True, "message": f"Webpage documents stored in Qdrant collection '{self.collection_name}'."}
            else:
                return {"success": False, "error": "Failed to store documents"}
                
        except Exception as e:
            logger.error(f"Error processing and storing webpage: {str(e)}")
            return {"success": False, "error": str(e)}

    async def update_documents_by_filename(self, text: str, file_name: str, website_url: str = None,
                                         tag: str = None, title: str = None, user_id: str = None) -> Dict:
        """
        Delete all existing documents with the specified filename and insert new chunks
        """
        try:
            # 1. Delete existing documents with matching filename
            try:
                self.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=FilterSelector(
                        filter=Filter(
                            must=[
                                FieldCondition(
                                    key="metadata.file_name",
                                    match=MatchValue(value=file_name)
                                )
                            ]
                        )
                    )
                )
                logger.info(f"✅ Deleted existing documents for file: {file_name}")
            except Exception as e:
                logger.error(f"Error deleting existing documents: {str(e)}")

            # 2. Create and store new documents
            metadata = {
                "file_name": file_name,
                "website_url": website_url,
                "tag": tag,
                "title": title,
                "document_type": "updated"
            }
            
            documents = await self.chunk_text(text, metadata, "recursive")
            
            if not documents:
                return {"success": False, "error": "Failed to chunk text"}
            
            success = await self.store_documents(documents, user_id)
            
            if success:
                return {"success": True, "message": f"Documents updated in Qdrant collection '{self.collection_name}'."}
            else:
                return {"success": False, "error": "Failed to store updated documents"}
                
        except Exception as e:
            logger.error(f"Error updating documents: {str(e)}")
            return {"success": False, "error": str(e)}

    async def search_documents(self, query: str, user_id: str = None, limit: int = 5, 
                             collection_name: str = None) -> List[Dict]:
        """
        Search for similar documents in the vector database
        Enhanced version supporting both old and new search methods
        """
        try:
            collection_name = collection_name or self.collection_name
            
            # Generate query embedding
            query_embedding = await asyncio.to_thread(
                self.embedding_model.embed_query, query
            )
            
            # Prepare filter for user-specific search
            search_filter = None
            if user_id:
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="metadata.user_id",
                            match=MatchValue(value=user_id)
                        )
                    ]
                )
            
            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                
                limit=limit,
                score_threshold=getattr(settings, 'similarity_threshold', 0.7)
            ) #query_filter=search_filter,
            print('➡ search_results:', search_results)
            
            # Format results
            results = []
            for result in search_results:
                # Handle both payload structures (file_a and file_b compatibility)
                content = result.payload.get("page_content") or result.payload.get("text", "")
                metadata = result.payload.get("metadata", result.payload)
                
                results.append({
                    "text": content,
                    "metadata": metadata,
                    "score": result.score
                })
            
            logger.info(f"✅ Found {len(results)} similar documents")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error searching documents: {e}")
            return []

    async def search_QnA_chunks(self, query: str, collection_name: str = None, top_k: int = 5) -> List[Dict]:
        """
        Search for most relevant chunks for Q&A (file_b compatibility)
        """
        collection_name = collection_name or self.collection_name
        results = await self.search_documents(query, limit=top_k, collection_name=collection_name)
        
        return [{"text": result["text"]} for result in results]

    async def search_pdf_chunks(self, query: str, collection_name: str = None, top_k: int = 5) -> List[Dict]:
        """
        Search for most relevant PDF chunks (file_b compatibility)
        """
        collection_name = collection_name or self.collection_name
        return await self.search_documents(query, limit=top_k, collection_name=collection_name)

    async def delete_user_documents(self, user_id: str) -> bool:
        """Delete all documents for a specific user"""
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="metadata.user_id",
                                match=MatchValue(value=user_id)
                            )
                        ]
                    )
                )
            )
            
            logger.info(f"✅ Deleted documents for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting user documents: {e}")
            return False

    async def delete_documents_by_filename(self, file_identifier: str, identifier_type: str = "file_name") -> Dict:
        """
        Delete documents by filename or website_url
        
        Args:
            file_identifier: The identifier value (filename or website_url)
            identifier_type: Type of identifier ("file_name" or "website_url")
        """
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key=f"metadata.{identifier_type}",
                                match=MatchValue(value=file_identifier)
                            )
                        ]
                    )
                )
            )

            return {
                "success": True,
                "message": f"Deleted documents for {identifier_type}: {file_identifier}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error deleting documents for '{file_identifier}': {str(e)}"
            }

    async def clear_all_data(self) -> Dict:
        """Clear all data from the collection"""
        try:
            self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(filter=Filter())
            )
            return {
                "success": True,
                "message": f"All data cleared from Qdrant collection '{self.collection_name}'."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to clear data from Qdrant: {str(e)}"
            }

    async def delete_collection(self) -> bool:
        """Delete the entire collection"""
        try:
            self.qdrant_client.delete_collection(self.collection_name)
            logger.info(f"✅ Deleted collection: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting collection: {e}")
            return False

    async def get_collection_info(self) -> Dict:
        """Get collection information and health status"""
        try:
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            
            # Count points
            count_result = self.qdrant_client.count(
                collection_name=self.collection_name
            )
            
            health_info = {
                "collection_name": self.collection_name,
                "status": "healthy",
                "vector_count": count_result.count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.name,
                "indexed": collection_info.status == "green"
            }
            
            logger.info(f"✅ Collection health check completed")
            return health_info
            
        except Exception as e:
            logger.error(f"❌ Error getting collection info: {e}")
            return {
                "collection_name": self.collection_name,
                "status": "error",
                "error": str(e)
            }

# Create global instance
text_chunker = TextChunker()