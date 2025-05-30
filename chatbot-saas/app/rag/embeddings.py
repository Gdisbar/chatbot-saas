
# =============================================================================
# app/rag/embeddings.py - Embedding Generation
# =============================================================================

import openai
import numpy as np
from typing import List, Dict, Any
import logging

from app.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"
        