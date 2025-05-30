
# =============================================================================
# app/chat/models.py - Chat Database Models
# =============================================================================

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import BaseModel

class ConversationStatus(enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class MessageRole(enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Conversation(BaseModel):
    __tablename__ = "conversations"
    
    title = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(ConversationStatus), default=ConversationStatus.ACTIVE)
    llm_provider = Column(String, default="openai")
    system_prompt = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(BaseModel):
    __tablename__ = "messages"
    
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    metadata = Column(Text, nullable=True)  # JSON string for additional data
    token_count = Column(Integer, nullable=True)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

