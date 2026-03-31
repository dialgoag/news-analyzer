"""
Ollama LLM Provider - Adapter implementing LLMPort.

This adapter wraps LangChain's Ollama integration for local LLMs.
"""

import logging
from typing import Optional
from langchain_community.llms import Ollama
from langchain_core.messages import HumanMessage, SystemMessage

from core.ports.llm_port import LLMPort, LLMRequest, LLMResponse
from config import settings

logger = logging.getLogger(__name__)


class OllamaProvider(LLMPort):
    """
    Ollama provider for local LLMs using LangChain.
    
    Models: mistral, qwen3:14b-q4_K_M, llama2, etc.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout: int = 120
    ):
        """
        Initialize Ollama provider.
        
        Args:
            base_url: Ollama base URL (defaults to settings.OLLAMA_HOST)
            model: Model name (defaults to settings.OLLAMA_LLM_MODEL)
            temperature: Temperature (defaults to settings.OLLAMA_TEMPERATURE)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or settings.OLLAMA_HOST
        self.model = model or settings.OLLAMA_LLM_MODEL
        self.temperature = temperature or settings.OLLAMA_TEMPERATURE
        self.timeout = timeout
        
        # Create LangChain Ollama instance
        self.llm = Ollama(
            base_url=self.base_url,
            model=self.model,
            temperature=self.temperature,
            timeout=self.timeout,
        )
        
        logger.info(f"✅ Ollama provider initialized: model={self.model}, url={self.base_url}")
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using Ollama.
        
        Args:
            request: LLM request
        
        Returns:
            LLM response
        """
        try:
            # Build prompt (Ollama doesn't use messages format in LangChain community)
            prompt = request.prompt
            if request.system_message:
                prompt = f"{request.system_message}\n\n{prompt}"
            
            # Override temperature if provided in request
            temperature = request.temperature if request.temperature is not None else self.temperature
            
            # Call Ollama via LangChain
            logger.debug(f"🤖 Calling Ollama {self.model} (temp={temperature})")
            
            response = await self.llm.ainvoke(
                prompt,
                temperature=temperature,
                stop=request.stop_sequences
            )
            
            # Ollama response is a string
            text = response if isinstance(response, str) else str(response)
            
            logger.info(f"✅ Ollama response: {len(text)} chars")
            
            return LLMResponse(
                text=text,
                provider="ollama",
                model=self.model,
                tokens_used=None,  # Ollama doesn't return token count
                finish_reason="stop",
                metadata={"base_url": self.base_url}
            )
        
        except Exception as e:
            logger.error(f"❌ Ollama generation failed: {e}", exc_info=True)
            
            # Re-raise with proper exception types
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                raise TimeoutError(f"Ollama timeout: {e}")
            elif "connection" in str(e).lower():
                raise ConnectionError(f"Ollama connection error: {e}")
            else:
                raise ValueError(f"Ollama error: {e}")
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return "ollama"
    
    def get_model_name(self) -> str:
        """Get model name."""
        return self.model
    
    async def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            import requests
            # Check /api/tags endpoint
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
