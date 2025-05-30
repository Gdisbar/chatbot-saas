# =============================================================================
# app/utils/logging.py - Logging Configuration
# =============================================================================
import logging
import sys
from typing import Dict, Any
from pathlib import Path
from app.config import settings

def setup_logging() -> None:
    """Configure application logging."""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure log level based on environment
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove default handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for all logs
    file_handler = logging.FileHandler(log_dir / "app.log")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = logging.FileHandler(log_dir / "error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Chat-specific logger
    chat_logger = logging.getLogger("chatbot.chat")
    chat_logger.setLevel(log_level)
    
    # RAG-specific logger
    rag_logger = logging.getLogger("chatbot.rag")
    rag_logger.setLevel(log_level)
    
    # Document processing logger
    doc_logger = logging.getLogger("chatbot.document")
    doc_logger.setLevel(log_level)
    
    logging.info("Logging configuration completed")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(f"chatbot.{name}")

# Pre-configured loggers for different modules
chat_logger = get_logger("chat")
rag_logger = get_logger("rag")
doc_logger = get_logger("document")
auth_logger = get_logger("auth")