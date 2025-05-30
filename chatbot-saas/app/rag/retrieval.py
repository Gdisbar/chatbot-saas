# =============================================================================
# app/rag/retrieval.py - Document Retrieval Logic
# =============================================================================
from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from app.config import settings
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStoreService
from app.llm.providers import LLMProvider

logger = logging.getLogger("chatbot.rag")

@dataclass
class RetrievedDocument:
    """Represents a retrieved document with metadata."""
    content: str
    metadata: Dict[str, Any]
    score: float
    source: str
    chunk_id: Optional[str] = None

class RAGService:
    """RAG (Retrieval-Augmented Generation) service for document retrieval and response generation."""
    
    def __init__(
        self,
        vector_store: Optional[VectorStoreService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        llm_provider: Optional[LLMProvider] = None
    ):
        self.vector_store = vector_store or VectorStoreService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_provider = llm_provider
        
    async def retrieve_documents(
        self,
        query: str,
        collection_name: str = "documents",
        top_k: int = None,
        similarity_threshold: float = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedDocument]:
        """
        Retrieve relevant documents for a given query.
        
        Args:
            query: Search query
            collection_name: Vector store collection name
            top_k: Number of documents to retrieve
            similarity_threshold: Minimum similarity score
            filters: Additional metadata filters
            
        Returns:
            List of retrieved documents
        """
        try:
            # Use defaults from settings if not provided
            if top_k is None:
                top_k = settings.TOP_K_RESULTS
            if similarity_threshold is None:
                similarity_threshold = settings.SIMILARITY_THRESHOLD
            
            logger.info(f"Retrieving documents for query: {query[:100]}...")
            
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            # Search vector store
            search_results = await self.vector_store.similarity_search(
                embedding=query_embedding,
                collection_name=collection_name,
                top_k=top_k,
                distance_threshold=1.0 - similarity_threshold,  # Convert similarity to distance
                filters=filters
            )
            
            # Convert to RetrievedDocument objects
            retrieved_docs = []
            for result in search_results:
                doc = RetrievedDocument(
                    content=result.get("content", ""),
                    metadata=result.get("metadata", {}),
                    score=1.0 - result.get("distance", 0.0),  # Convert distance back to similarity
                    source=result.get("metadata", {}).get("source", "unknown"),
                    chunk_id=result.get("id")
                )
                retrieved_docs.append(doc)
            
            logger.info(f"Retrieved {len(retrieved_docs)} documents")
            return retrieved_docs
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {str(e)}")
            return []
    
    async def generate_response(
        self,
        query: str,
        retrieved_docs: List[RetrievedDocument],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generate response using retrieved documents and LLM.
        
        Args:
            query: User query
            retrieved_docs: Retrieved documents for context
            system_prompt: Custom system prompt
            max_tokens: Maximum tokens for response
            temperature: LLM temperature
            
        Returns:
            Generated response with metadata
        """
        if not self.llm_provider:
            raise ValueError("LLM provider not configured")
        
        try:
            # Prepare context from retrieved documents
            context = self._prepare_context(retrieved_docs)
            
            # Use default system prompt if not provided
            if system_prompt is None:
                system_prompt = self._get_default_system_prompt()
            
            # Create user message with context
            user_message = f"""Context information:
{context}

User question: {query}

Please provide a comprehensive answer based on the context provided. If the context doesn't contain enough information to answer the question, please say so."""
            
            # Generate response
            response = await self.llm_provider.generate_response(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=max_tokens or settings.MAX_TOKENS,
                temperature=temperature or settings.TEMPERATURE
            )
            
            return {
                "response": response.get("content", ""),
                "sources": [doc.source for doc in retrieved_docs],
                "retrieved_documents": len(retrieved_docs),
                "metadata": {
                    "model": response.get("model", ""),
                    "tokens_used": response.get("usage", {}).get("total_tokens", 0),
                    "sources_used": list(set(doc.source for doc in retrieved_docs))
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "response": "I'm sorry, I encountered an error while generating a response.",
                "sources": [],
                "retrieved_documents": 0,
                "metadata": {"error": str(e)}
            }
    
    async def ask(
        self,
        query: str,
        collection_name: str = "documents",
        top_k: int = None,
        similarity_threshold: float = None,
        filters: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        End-to-end RAG query: retrieve documents and generate response.
        
        Args:
            query: User query
            collection_name: Vector store collection name
            top_k: Number of documents to retrieve
            similarity_threshold: Minimum similarity score
            filters: Additional metadata filters
            system_prompt: Custom system prompt
            
        Returns:
            Complete RAG response
        """
        # Retrieve relevant documents
        retrieved_docs = await self.retrieve_documents(
            query=query,
            collection_name=collection_name,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters
        )
        
        # Generate response
        if retrieved_docs:
            response = await self.generate_response(
                query=query,
                retrieved_docs=retrieved_docs,
                system_prompt=system_prompt
            )
        else:
            response = {
                "response": "I couldn't find relevant information to answer your question.",
                "sources": [],
                "retrieved_documents": 0,
                "metadata": {"no_documents_found": True}
            }
        
        return response
    
    def _prepare_context(self, retrieved_docs: List[RetrievedDocument]) -> str:
        """Prepare context string from retrieved documents."""
        context_parts = []
        
        for i, doc in enumerate(retrieved_docs, 1):
            source_info = f"Source {i} ({doc.source}):"
            content = doc.content.strip()
            context_parts.append(f"{source_info}\n{content}")
        
        return "\n\n".join(context_parts)
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for RAG responses."""
        return """You are a helpful AI assistant that answers questions based on provided context information. 

Guidelines:
- Use only the information provided in the context to answer questions
- If the context doesn't contain enough information, clearly state this
- Cite sources when possible by referring to "Source 1", "Source 2", etc.
- Be concise but comprehensive in your responses
- If you're unsure about something, express uncertainty rather than guessing"""
    
    async def get_collection_stats(self, collection_name: str = "documents") -> Dict[str, Any]:
        """Get statistics about a document collection."""
        try:
            stats = await self.vector_store.get_collection_info(collection_name)
            return stats
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {"error": str(e)}
    
    async def delete_documents(
        self,
        collection_name: str = "documents",
        filters: Optional[Dict[str, Any]] = None,
        document_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Delete documents from the vector store."""
        try:
            if document_ids:
                result = await self.vector_store.delete_by_ids(collection_name, document_ids)
            elif filters:
                result = await self.vector_store.delete_by_filter(collection_name, filters)
            else:
                raise ValueError("Either document_ids or filters must be provided")
            
            return {"deleted": result.get("deleted", 0), "success": True}
        except Exception as e:
            logger.error(f"Error deleting documents: {str(e)}")
            return {"deleted": 0, "success": False, "error": str(e)}