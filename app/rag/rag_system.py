from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
from typing import List, Dict, Optional
import logging
from .vector_db import text_chunker
from app.config import settings

logger = logging.getLogger(__name__)

class RAGSystem:
    """
    RAG (Retrieval Augmented Generation) system using Gemini LLM
    """
    
    def __init__(self):
        # Initialize Gemini LLM
        self.gemini_llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.1,
            google_api_key=settings.google_api_key
        )
        
        # System prompt for RAG
        self.system_prompt = """
You are an intelligent assistant that helps users find information from their uploaded documents. 

**Instructions:**
1. Use the provided context from the user's documents to answer questions accurately
2. If the information is not available in the provided context, clearly state that you don't have that information in the uploaded documents
3. Always cite which document or section the information comes from when possible
4. Be concise but comprehensive in your responses
5. If the user asks something unrelated to the documents, politely redirect them to document-related questions

**Context Guidelines:**
- Only use information from the provided context
- Don't make up information that's not in the documents
- If multiple documents contain relevant information, synthesize the information clearly
- Maintain a helpful and professional tone

**Format your responses clearly:**
- Start with a direct answer to the question
- Provide supporting details from the documents
- Include source references when available
"""

    async def generate_response(
        self, 
        query: str, 
        user_id: str, 
        conversation_history: List[Dict] = None
    ) -> Dict:
        """
        Generate response using RAG approach
        """
        try:
            # Search for relevant documents
            relevant_docs = await text_chunker.search_documents(
                query=query,
                user_id=user_id,
                limit=settings.top_k_results
            )
            
            if not relevant_docs:
                return {
                    "response": "I couldn't find any relevant information in your uploaded documents. Please make sure you've uploaded documents related to your question, or try rephrasing your query.",
                    "sources": [],
                    "confidence": "low"
                }
            
            # Prepare context from retrieved documents
            context = self._prepare_context(relevant_docs)
            
            # Prepare conversation history
            messages = [SystemMessage(content=self.system_prompt)]
            
            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history[-10:]:  # Last 10 messages for context
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg.get("content", "")))
                    # Note: We could add AIMessage here for assistant responses if needed
            
            # Add current query with context
            user_message = f"""
**Context from your documents:**
{context}

**Your question:**
{query}

Please answer based on the provided context from your documents.
"""
            
            messages.append(HumanMessage(content=user_message))
            
            # Generate response using Gemini
            response = await self.gemini_llm.ainvoke(messages)
            
            # Extract sources
            sources = self._extract_sources(relevant_docs)
            
            # Determine confidence based on document relevance
            confidence = self._calculate_confidence(relevant_docs)
            
            logger.info(f"✅ Generated RAG response for user {user_id}")
            
            return {
                "response": response.content,
                "sources": sources,
                "confidence": confidence,
                "retrieved_chunks": len(relevant_docs)
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating RAG response: {e}")
            return {
                "response": "I apologize, but I encountered an error while processing your question. Please try again or contact support if the issue persists.",
                "sources": [],
                "confidence": "error",
                "error": str(e)
            }

    def _prepare_context(self, relevant_docs: List[Dict]) -> str:
        """Prepare context string from retrieved documents"""
        context_parts = []
        
        for i, doc in enumerate(relevant_docs, 1):
            metadata = doc.get("metadata", {})
            source_info = ""
            
            # Add source information if available
            if metadata.get("filename"):
                source_info = f"[Source: {metadata.get('filename')}"
                if metadata.get("page_number"):
                    source_info += f", Page {metadata.get('page_number')}"
                source_info += "]"
            
            context_part = f"""
Document {i} {source_info}:
{doc.get('text', '')}
---
"""
            context_parts.append(context_part)
        
        return "\n".join(context_parts)

    def _extract_sources(self, relevant_docs: List[Dict]) -> List[Dict]:
        """Extract source information from relevant documents"""
        sources = []
        seen_sources = set()
        
        for doc in relevant_docs:
            metadata = doc.get("metadata", {})
            filename = metadata.get("filename", "Unknown")
            
            # Avoid duplicate sources
            source_key = f"{filename}_{metadata.get('chunk_index', 0)}"
            if source_key not in seen_sources:
                sources.append({
                    "filename": filename,
                    "chunk_index": metadata.get("chunk_index"),
                    "page_number": metadata.get("page_number"),
                    "score": doc.get("score", 0),
                    "upload_date": metadata.get("upload_date")
                })
                seen_sources.add(source_key)
        
        return sources

    def _calculate_confidence(self, relevant_docs: List[Dict]) -> str:
        """Calculate confidence level based on document relevance scores"""
        if not relevant_docs:
            return "low"
        
        avg_score = sum(doc.get("score", 0) for doc in relevant_docs) / len(relevant_docs)
        
        if avg_score >= 0.85:
            return "high"
        elif avg_score >= 0.7:
            return "medium"
        else:
            return "low"

    async def generate_summary(self, documents: List[str], user_id: str) -> str:
        """Generate a summary of uploaded documents"""
        try:
            # Combine documents for summary
            combined_text = "\n\n".join(documents[:5])  # Limit to first 5 docs
            
            summary_prompt = f"""
Please provide a concise summary of the following documents. Focus on:
1. Main topics covered
2. Key insights or findings
3. Document types and structure

Documents:
{combined_text[:4000]}  # Limit text length for LLM

Provide a structured summary that helps the user understand what information is available in their uploaded documents.
"""
            
            messages = [
                SystemMessage(content="You are a document analysis assistant that creates helpful summaries."),
                HumanMessage(content=summary_prompt)
            ]
            
            response = await self.gemini_llm.ainvoke(messages)
            
            logger.info(f"✅ Generated document summary for user {user_id}")
            return response.content
            
        except Exception as e:
            logger.error(f"❌ Error generating summary: {e}")
            return f"Error generating summary: {str(e)}"

# Create global instance
rag_system = RAGSystem()