# =============================================================================
# app/auth/models.py - Authentication Database Models
# =============================================================================

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import BaseModel

class User(BaseModel):
    __tablename__ = "users"
    
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="user")
    documents = relationship("Document", back_populates="user")

class RefreshToken(BaseModel):
    __tablename__ = "refresh_tokens"
    
    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)


