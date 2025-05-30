# =============================================================================
# app/rag/routes.py - RAG API Endpoints
# =============================================================================
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.utils import get_current_user
from app.auth.models import User
from app.rag.retrieval import RAGService
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStoreService
from app.llm.providers import get_llm_provider
from app.utils.rate_limiter import check_user_rate_limit
from app.config import settings
import logging

logger = logging.getLogger("chatbot.rag")

rag_router = APIRouter(prefix="/rag", tags=["rag"])

# Initialize services
embedding_service = EmbeddingService()
vector_store = VectorStoreService()

# Pydantic models for request/response
class RAGQueryRequest(BaseModel):
    query: str = Field(..., description="Search query", min_length=1, max_length=1000)
    collection_name: str = Field("documents", description="Collection to search in")
    top_k: Optional[int] = Field(None, description="Number of documents to retrieve", ge=1, le=20)
    similarity_threshold: Optional[float] = Field(None, description="Minimum similarity score", ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional metadata filters")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    include_sources: bool = Field(True, description="Include source information in response")

class DocumentSearchRequest(BaseModel):
    query: str = Field(..., description="Search query", min_length=1, max_length=1000)
    collection_name: str = Field("documents", description="Collection to search in")
    top_k: Optional[int] = Field(None, description="Number of documents to retrieve", ge=1, le=50)
    similarity_threshold: Optional[float] = Field(None, description="Minimum similarity score", ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional metadata filters")

class RAGResponse(BaseModel):
    response: str
    sources: List[str]
    retrieved_documents: int
    metadata: Dict[str, Any]

class DocumentSearchResponse(BaseModel):
    documents: List[Dict[str, Any]]
    total_found: int
    query: str

@rag_router.post("/query", response_model=RAGResponse)
async def rag_query(
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Perform RAG query: retrieve relevant documents and generate response.
    """
    from fastapi import Request
    http_request = Request({"type": "http", "method": "POST"})
    await check_user_rate_limit(http_request, current_user.id, cost=3)  # Higher cost for RAG queries
    
    try:
        # Get LLM provider
        llm_provider = await get_llm_provider(settings.DEFAULT_LLM_PROVIDER)
        
        # Initialize RAG service
        rag_service = RAGService(
            vector_store=vector_store,
            embedding_service=embedding_service,
            llm_provider=llm_provider
        )
        
        # Add user filter to ensure user can only access their documents
        user_filters = request.filters or {}
        user_filters["user_id"] = current_user.id
        
        # Perform RAG query
        result = await rag_service.ask(
            query=request.query,
            collection_name=request.collection_name,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            filters=user_filters,
            system_prompt=request.system_prompt
        )
        
        logger.info(f"RAG query processed for user {current_user.id}: {request.query[:100]}")
        
        return RAGResponse(**result)
        
    except Exception as e:
        logger.error(f"Error processing RAG query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process RAG query"
        )

@rag_router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    request: DocumentSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search for relevant documents without generating a response.
    """
    from fastapi import Request
    http_request = Request({"type": "http", "method": "POST"})
    await check_user_rate_limit(http_request, current_user.id, cost=1)
    
    try:
        # Initialize RAG service
        rag_service = RAGService(
            vector_store=vector_store,
            embedding_service=embedding_service
        )
        
        # Add user filter
        user_filters = request.filters or {}
        user_filters["user_id"] = current_user.id
        
        # Retrieve documents
        retrieved_docs = await rag_service.retrieve_documents(
            query=request.query,
            collection_name=request.collection_name,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            filters=user_filters
        )
        
        # Format response
        documents = []
        for doc in retrieved_docs:
            documents.append({
                "content": doc.content,
                "source": doc.source,
                "score": doc.score,
                "metadata": doc.metadata,
                "chunk_id": doc.chunk_id
            })
        
        logger.info(f"Document search completed for user {current_user.id}: found {len(documents)} documents")
        
        return DocumentSearchResponse(
            documents=documents,
            total_found=len(documents),
            query=request.query
        )
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search documents"
        )

@rag_router.get("/collections")
async def list_collections(
    current_user: User = Depends(get_current_user)
):
    """List available collections for the user."""
    try:
        # Get collection info from vector store
        collections = await vector_store.list_collections()
        
        # Filter collections that contain user's documents
        user_collections = []
        for collection in collections:
            # Check if collection has documents from this user
            stats = await vector_store.get_collection_info(collection["name"])
            if stats.get("document_count", 0) > 0:
                # You might want to add more sophisticated filtering here
                user_collections.append({
                    "name": collection["name"],
                    "document_count": stats.get("document_count", 0),
                    "created_at": collection.get("created_at")
                })
        
        return {"collections": user_collections}
        
    except Exception as e:
        logger.error(f"Error listing collections: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list collections"
        )

@rag_router.get("/collections/{collection_name}/stats")
async def get_collection_stats(
    collection_name: str,
    current_user: User = Depends(get_current_user)
):
    """Get statistics for a specific collection."""
    try:
        rag_service = RAGService(vector_store=vector_store)
        stats = await rag_service.get_collection_stats(collection_name)
        
        return {"collection_name": collection_name, "stats": stats}
        
    except Exception as e:
        logger.error(f"Error getting collection stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get collection statistics"
        )

@rag_router.delete("/collections/{collection_name}/documents")
async def delete_collection_documents(
    collection_name: str,
    document_ids: Optional[List[str]] = Query(None, description="Specific document IDs to delete"),
    source: Optional[str] = Query(None, description="Delete documents from specific source"),
    current_user: User = Depends(get_current_user)
):
    """Delete documents from a collection."""
    try:
        rag_service = RAGService(vector_store=vector_store)
        
        # Build filters
        filters = {"user_id": current_user.id}
        if source:
            filters["source"] = source
        
        # Delete documents
        if document_ids:
            result = await rag_service.delete_documents(
                collection_name=collection_name,
                document_ids=document_ids
            )
        else:
            result = await rag_service.delete_documents(
                collection_name=collection_name,
                filters=filters
            )
        
        logger.info(f"Deleted {result.get('deleted', 0)} documents from collection {collection_name}")
        
        return {
            "message": f"Deleted {result.get('deleted', 0)} documents",
            "deleted_count": result.get('deleted', 0)
        }
        
    except Exception as e:
        logger.error(f"Error deleting documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete documents"
        )

@rag_router.post("/test-embedding")
async def test_embedding(
    text: str = Query(..., description="Text to generate embedding for"),
    current_user: User = Depends(get_current_user)
):
    """Test endpoint to generate embedding for given text."""
    from fastapi import Request
    http_request = Request({"type": "http", "method": "POST"})
    await check_user_rate_limit(http_request, current_user.id, cost=1)
    
    try:
        embedding = await embedding_service.generate_embedding(text)
        
        return {
            "text": text,
            "embedding_length": len(embedding),
            "embedding_model": embedding_service.model_name,
            "sample_values": embedding[:5] if len(embedding) >= 5 else embedding
        }
        
    except Exception as e:
        logger.error(f"Error generating test embedding: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate embedding"
        )