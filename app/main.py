# =============================================================================
# app/main.py - FastAPI Application Entry Point
# =============================================================================

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import logging

from app.config import settings
from app.database import engine, Base
from app.auth.routes import auth_router
from app.chat.routes import chat_router
from app.chat.websocket import websocket_router
from app.document.routes import document_router
from app.rag.routes import rag_router
from app.utils.rate_limiter import RateLimiter
from app.utils.logging import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting up Chatbot SaaS Backend...")
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")
    yield
    
    logger.info("Shutting down Chatbot SaaS Backend...")

# Create FastAPI app
app = FastAPI(
    title="AI Chatbot SaaS Backend",
    description="Production-ready chatbot backend with RAG capabilities",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

# Rate limiting middleware
rate_limiter = RateLimiter()

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    if not await rate_limiter.is_allowed(request):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    response = await call_next(request)
    return response

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(chat_router, prefix="/chat", tags=["Chat"])
app.include_router(websocket_router, prefix="/chat", tags=["WebSocket"])
app.include_router(document_router, prefix="/documents", tags=["Documents"])
app.include_router(rag_router, prefix="/rag", tags=["RAG"])

@app.get("/")
async def root():
    return {"message": "AI Chatbot SaaS Backend", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
