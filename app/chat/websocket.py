
# =============================================================================
# app/chat/websocket.py - WebSocket Chat Handler
# =============================================================================

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, List
import json
import logging

from app.database import get_db
from app.auth.models import User
from app.chat.models import Conversation, Message, MessageRole, ConversationStatus
from app.chat.services import ChatService
from app.auth.utils import verify_token

websocket_router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, conversation_id: int):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, conversation_id: int):
        if conversation_id in self.active_connections:
            self.active_connections[conversation_id].remove(websocket)
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast_to_conversation(self, message: str, conversation_id: int):
        if conversation_id in self.active_connections:
            for connection in self.active_connections[conversation_id]:
                await connection.send_text(message)

manager = ConnectionManager()

async def get_user_from_token(token: str, db: AsyncSession) -> User:
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")

@websocket_router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: int,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Authenticate user
        user = await get_user_from_token(token, db)
        
        # Verify conversation ownership
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
                Conversation.status == ConversationStatus.ACTIVE
            )
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            await websocket.close(code=4004, reason="Conversation not found or access denied")
            return
        
        await manager.connect(websocket, conversation_id)
        chat_service = ChatService(db)
        
        try:
            while True:
                # Receive message from WebSocket
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                if message_data.get("type") == "chat_message":
                    user_content = message_data.get("content", "")
                    include_context = message_data.get("include_context", True)
                    
                    # Save user message
                    user_message = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.USER,
                        content=user_content
                    )
                    
                    db.add(user_message)
                    await db.commit()
                    await db.refresh(user_message)
                    
                    # Send user message confirmation
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "message_saved",
                            "message": {
                                "id": user_message.id,
                                "role": "user",
                                "content": user_content,
                                "created_at": user_message.created_at.isoformat()
                            }
                        }),
                        websocket
                    )
                    
                    # Generate AI response
                    ai_response = await chat_service.generate_response(
                        conversation=conversation,
                        user_message=user_content,
                        include_context=include_context
                    )
                    
                    # Save AI message
                    ai_message = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=ai_response["content"],
                        token_count=ai_response["tokens_used"]
                    )
                    
                    db.add(ai_message)
                    await db.commit()
                    await db.refresh(ai_message)
                    
                    # Send AI response
                    await manager.send_personal_message(
                        json.dumps({
                            "type": "ai_response",
                            "message": {
                                "id": ai_message.id,
                                "role": "assistant",
                                "content": ai_message.content,
                                "created_at": ai_message.created_at.isoformat(),
                                "token_count": ai_message.token_count
                            },
                            "tokens_used": ai_response["tokens_used"]
                        }),
                        websocket
                    )
                
        except WebSocketDisconnect:
            manager.disconnect(websocket, conversation_id)
            logger.info(f"WebSocket disconnected for conversation {conversation_id}")
            
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.close(code=4000, reason="Internal server error")