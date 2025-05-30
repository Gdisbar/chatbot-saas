# =============================================================================
# app/llm/providers.py - LLM Provider Implementations
# =============================================================================

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import openai
import anthropic
import cohere
import logging

from app.config import settings

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        user_input: str,
        context: str = "",
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        pass

class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        user_input: str,
        context: str = "",
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            # Build messages for OpenAI format
            openai_messages = []
            
            # Add system prompt
            system_content = system_prompt or "You are a helpful AI assistant."
            if context:
                system_content += f"\n\nRelevant context:\n{context}"
            
            openai_messages.append({
                "role": "system",
                "content": system_content
            })
            
            # Add conversation history
            for msg in messages:
                openai_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current user input
            openai_messages.append({
                "role": "user",
                "content": user_input
            })
            
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=openai_messages,
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE
            )
            
            return {
                "content": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens
            }
            
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

class AnthropicProvider(BaseLLMProvider):
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        user_input: str,
        context: str = "",
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            # Build conversation for Anthropic
            conversation = ""
            
            for msg in messages:
                if msg["role"] == "user":
                    conversation += f"Human: {msg['content']}\n\n"
                elif msg["role"] == "assistant":
                    conversation += f"Assistant: {msg['content']}\n\n"
            
            # Add current user input
            conversation += f"Human: {user_input}\n\nAssistant:"
            
            # Build system prompt
            system_content = system_prompt or "You are a helpful AI assistant."
            if context:
                system_content += f"\n\nRelevant context:\n{context}"
            
            response = await self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE,
                system=system_content,
                messages=[{"role": "user", "content": conversation}]
            )
            
            return {
                "content": response.content[0].text,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens
            }
            
        except Exception as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise

class CohereProvider(BaseLLMProvider):
    def __init__(self):
        self.client = cohere.AsyncClient(api_key=settings.COHERE_API_KEY)
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        user_input: str,
        context: str = "",
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            # Build conversation for Cohere
            conversation_history = []
            
            for msg in messages:
                conversation_history.append({
                    "role": "USER" if msg["role"] == "user" else "CHATBOT",
                    "message": msg["content"]
                })
            
            # Build preamble
            preamble = system_prompt or "You are a helpful AI assistant."
            if context:
                preamble += f"\n\nRelevant context:\n{context}"
            
            response = await self.client.chat(
                model="command-r-plus",
                message=user_input,
                chat_history=conversation_history,
                preamble=preamble,
                max_tokens=settings.MAX_TOKENS,
                temperature=settings.TEMPERATURE
            )
            
            return {
                "content": response.text,
                "tokens_used": response.meta.tokens.input_tokens + response.meta.tokens.output_tokens
            }
            
        except Exception as e:
            logger.error(f"Cohere API error: {str(e)}")
            raise

class LLMProviderFactory:
    _providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "cohere": CohereProvider
    }
    
    @classmethod
    def get_provider(cls, provider_name: str) -> BaseLLMProvider:
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        
        return cls._providers[provider_name]()

    
