
# =============================================================================
# app/chat/services.py - Chat Business Logic
# =============================================================================

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, List, Any
import json
import logging

from app.chat.models import Conversation, Message
from app.llm.providers import LLMProviderFactory
from app.rag.retrieval import RAGService
from app.config import settings

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rag_service = RAGService()
    
    async def generate_response(
        self,
        conversation: Conversation,
        user_message: str,
        include_context: bool = True
    ) -> Dict[str, Any]:
        try:
            # Get conversation history
            history = await self._get_conversation_history(conversation.id)
            
            # Get relevant context if requested
            context = ""
            if include_context:
                context = await self.rag_service.retrieve_relevant_context(
                    query=user_message,
                    top_k=settings.TOP_K_RESULTS
                )
            
            # Get LLM provider
            llm_provider = LLMProviderFactory.get_provider(conversation.llm_provider)
            
            # Generate response
            response = await llm_provider.generate_response(
                messages=history,
                user_input=user_message,
                context=context,
                system_prompt=conversation.system_prompt
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "content": "I apologize, but I encountered an error while processing your request. Please try again.",
                "tokens_used": 0
            }
    
    async def _get_conversation_history(self, conversation_id: int, limit: int = 20) -> List[Dict[str, str]]:
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        
        # Reverse to get chronological order
        messages = list(reversed(messages))
        
        return [
            {
                "role": msg.role.value,
                "content": msg.content
            }
            for msg in messages
        ]

