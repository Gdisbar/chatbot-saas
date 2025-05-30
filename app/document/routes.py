# =============================================================================
# app/document/routes.py - Document Upload Endpoints
# =============================================================================
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.database import get_db
from app.auth.utils import get_current_user
from app.auth.models import User
from app.document.models import Document
from app.document.processors import DocumentProcessor
from app.document.loaders import DocumentLoader
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStoreService
from app.utils.rate_limiter import check_user_rate_limit
from app.config import settings
import logging

logger = logging.getLogger("chatbot.document")
security = HTTPBearer()

document_router = APIRouter(prefix="/documents", tags=["documents"])

# Initialize services
document_processor = DocumentProcessor()
document_loader = DocumentLoader()
embedding_service = EmbeddingService()
vector_store = VectorStoreService()

@document_router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection_name: str = Form("documents"),
    chunk_size: Optional[int] = Form(None),
    chunk_overlap: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload and process a document."""
    
    # Rate limiting
    from fastapi import Request
    request = Request({"type": "http", "method": "POST"})
    await check_user_rate_limit(request, current_user.id, cost=5)  # Higher cost for uploads
    
    # Validate file size
    if file.size and file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE} bytes"
        )
    
    # Validate file type
    allowed_extensions = {'.txt', '.pdf', '.docx', '.doc', '.md', '.csv', '.json'}
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_extension} not supported. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Create upload directory if it doesn't exist
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)
        
        # Save uploaded file
        file_path = upload_dir / f"{current_user.id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create document record
        document = Document(
            filename=file.filename,
            file_path=str(file_path),
            file_size=file.size or 0,
            content_type=file.content_type,
            user_id=current_user.id,
            status="processing"
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        # Process document in background
        background_tasks.add_task(
            process_document_background,
            document.id,
            str(file_path),
            collection_name,
            chunk_size or settings.CHUNK_SIZE,
            chunk_overlap or settings.CHUNK_OVERLAP
        )
        
        logger.info(f"Document uploaded: {file.filename} by user {current_user.id}")
        
        return {
            "message": "Document uploaded successfully",
            "document_id": document.id,
            "filename": document.filename,
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        
        # Clean up file if it was created
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )

@document_router.get("/")
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's documents."""
    
    stmt = select(Document).where(Document.user_id == current_user.id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    documents = result.scalars().all()
    
    return {
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "content_type": doc.content_type,
                "status": doc.status,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at
            }
            for doc in documents
        ],
        "total": len(documents)
    }

@document_router.get("/{document_id}")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get document details."""
    
    stmt = select(Document).where(
        Document.id == document_id,
        Document.user_id == current_user.id
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return {
        "id": document.id,
        "filename": document.filename,
        "file_path": document.file_path,
        "file_size": document.file_size,
        "content_type": document.content_type,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "error_message": document.error_message,
        "created_at": document.created_at,
        "updated_at": document.updated_at
    }

@document_router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    collection_name: str = "documents",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document and its embeddings."""
    
    # Get document
    stmt = select(Document).where(
        Document.id == document_id,
        Document.user_id == current_user.id
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    try:
        # Delete from vector store
        await vector_store.delete_by_filter(
            collection_name,
            {"document_id": document_id}
        )
        
        # Delete file if it exists
        if document.file_path and Path(document.file_path).exists():
            Path(document.file_path).unlink()
        
        # Delete from database
        await db.delete(document)
        await db.commit()
        
        logger.info(f"Document deleted: {document.filename} by user {current_user.id}")
        
        return {"message": "Document deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )

@document_router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    collection_name: str = Form("documents"),
    chunk_size: Optional[int] = Form(None),
    chunk_overlap: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reprocess an existing document."""
    
    # Get document
    stmt = select(Document).where(
        Document.id == document_id,
        Document.user_id == current_user.id
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    if not Path(document.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found"
        )
    
    # Update status
    document.status = "processing"
    document.error_message = None
    await db.commit()
    
    # Process document in background
    background_tasks.add_task(
        process_document_background,
        document.id,
        document.file_path,
        collection_name,
        chunk_size or settings.CHUNK_SIZE,
        chunk_overlap or settings.CHUNK_OVERLAP
    )
    
    return {
        "message": "Document reprocessing started",
        "document_id": document.id,
        "status": "processing"
    }

async def process_document_background(
    document_id: int,
    file_path: str,
    collection_name: str,
    chunk_size: int,
    chunk_overlap: int
):
    """Background task to process document."""
    
    # Create new database session for background task
    from app.database import async_session
    
    async with async_session() as db:
        try:
            # Get document
            stmt = select(Document).where(Document.id == document_id)
            result = await db.execute(stmt)
            document = result.scalar_one_or_none()
            
            if not document:
                logger.error(f"Document {document_id} not found for processing")
                return
            
            # Load document content
            content = await document_loader.load_document(file_path)
            
            # Process and chunk document
            chunks = await document_processor.process_document(
                content=content,
                filename=document.filename,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            # Generate embeddings and store in vector database
            for i, chunk in enumerate(chunks):
                embedding = await embedding_service.generate_embedding(chunk["content"])
                
                # Store in vector database
                await vector_store.add_document(
                    collection_name=collection_name,
                    content=chunk["content"],
                    embedding=embedding,
                    metadata={
                        "document_id": document_id,
                        "filename": document.filename,
                        "chunk_index": i,
                        "user_id": document.user_id,
                        "source": document.filename,
                        **chunk.get("metadata", {})
                    }
                )
            
            # Update document status
            document.status = "completed"
            document.chunk_count = len(chunks)
            await db.commit()
            
            logger.info(f"Document processed successfully: {document.filename} ({len(chunks)} chunks)")
            
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {str(e)}")
            
            # Update document status with error
            if document:
                document.status = "failed"
                document.error_message = str(e)
                await db.commit()