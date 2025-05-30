
# =============================================================================
# app/chat/routes.py - Chat API Endpoints
# =============================================================================

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json

from app.database import get_db
from app.auth.models import User
from app.auth.routes import get_current_user
from app.chat.models import Conversation, Message, ConversationStatus, MessageRole
from app.chat.services import ChatService

chat_router = APIRouter()

# Pydantic models
class ConversationCreate(BaseModel):
    title: str
    llm_provider: Optional[str] = "openai"
    system_prompt: Optional[str] = None

class ConversationResponse(BaseModel):
    id: int
    title: str
    status: str
    llm_provider: str
    created_at: datetime
    updated_at: datetime
    message_count: int

class MessageCreate(BaseModel):
    content: str
    include_context: Optional[bool] = True

class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    token_count: Optional[int]

class ChatResponse(BaseModel):
    message: MessageResponse
    conversation_id: int
    tokens_used: int

@chat_router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    new_conversation = Conversation(
        title=conversation_data.title,
        user_id=current_user.id,
        llm_provider=conversation_data.llm_provider,
        system_prompt=conversation_data.system_prompt
    )
    
    db.add(new_conversation)
    await db.commit()
    await db.refresh(new_conversation)
    
    return ConversationResponse(
        id=new_conversation.id,
        title=new_conversation.title,
        status=new_conversation.status.value,
        llm_provider=new_conversation.llm_provider,
        created_at=new_conversation.created_at,
        updated_at=new_conversation.updated_at,
        message_count=0
    )

@chat_router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.status != ConversationStatus.DELETED
        )
        .order_by(desc(Conversation.updated_at))
        .offset(skip)
        .limit(limit)
        .options(selectinload(Conversation.messages))
    )
    conversations = result.scalars().all()
    
    return [
        ConversationResponse(
            id=conv.id,
            title=conv.title,
            status=conv.status.value,
            llm_provider=conv.llm_provider,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages)
        )
        for conv in conversations
    ]

@chat_router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    # Verify conversation ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    # Get messages
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .offset(skip)
        .limit(limit)
    )
    messages = result.scalars().all()
    
    return [
        MessageResponse(
            id=msg.id,
            role=msg.role.value,
            content=msg.content,
            created_at=msg.created_at,
            token_count=msg.token_count
        )
        for msg in messages
    ]

@chat_router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    conversation_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify conversation ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.status == ConversationStatus.ACTIVE
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or inactive"
        )
    
    # Create user message
    user_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=message_data.content
    )
    
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)
    
    # Generate AI response
    chat_service = ChatService(db)
    ai_response = await chat_service.generate_response(
        conversation=conversation,
        user_message=message_data.content,
        include_context=message_data.include_context
    )
    
    # Create AI message
    ai_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=ai_response["content"],
        token_count=ai_response["tokens_used"]
    )
    
    db.add(ai_message)
    await db.commit()
    await db.refresh(ai_message)
    
    return ChatResponse(
        message=MessageResponse(
            id=ai_message.id,
            role=ai_message.role.value,
            content=ai_message.content,
            created_at=ai_message.created_at,
            token_count=ai_message.token_count
        ),
        conversation_id=conversation_id,
        tokens_used=ai_response["tokens_used"]
    )

@chat_router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    conversation.status = ConversationStatus.DELETED
    await db.commit()
    
    return {"message": "Conversation deleted successfully"}

