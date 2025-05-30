
# =============================================================================
# app/llm/chains.py - LangChain Conversation Chains
# =============================================================================

from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.llms import Cohere
from typing import List, Dict, Any, Optional

from app.config import settings

class ConversationChainManager:
    def __init__(self, provider: str = "openai"):
        self.provider = provider
        self.llm = self._initialize_llm()
        self.memory = ConversationBufferWindowMemory(
            k=10,  # Keep last 10 exchanges
            return_messages=True
        )
    
    def _initialize_llm(self):
        if self.provider == "openai":
            return ChatOpenAI(
                model_name="gpt-4",
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
                openai_api_key=settings.OPENAI_API_KEY
            )
        elif self.provider == "cohere":
            return Cohere(
                model="command-r-plus",
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
                cohere_api_key=settings.COHERE_API_KEY
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def create_chain(self, system_prompt: Optional[str] = None) -> ConversationChain:
        prompt_template = """
                {system_prompt}

                Current conversation:
                {history}
                Human: {input}
                Assistant:"""
        
        prompt = PromptTemplate(
            input_variables=["system_prompt", "history", "input"],
            template=prompt_template
        )
        
        return ConversationChain(
            llm=self.llm,
            memory=self.memory,
            prompt=prompt,
            verbose=True
        )
    
    def load_conversation_history(self, messages: List[Dict[str, str]]):
        """Load existing conversation history into memory"""
        self.memory.clear()
        
        for msg in messages:
            if msg["role"] == "user":
                self.memory.chat_memory.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                self.memory.chat_memory.add_ai_message(msg["content"])


