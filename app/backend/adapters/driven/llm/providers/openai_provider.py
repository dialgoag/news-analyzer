"""
OpenAI LLM Provider - Adapter implementing LLMPort.

This adapter wraps LangChain's OpenAI integration.
"""

import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from core.ports.llm_port import LLMPort, LLMRequest, LLMResponse
from config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMPort):
    """
    OpenAI provider using LangChain.
    
    Models: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_retries: int = 3,
        timeout: int = 60
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
            model: Model name (defaults to settings.OPENAI_LLM_MODEL)
            temperature: Temperature (defaults to settings.OPENAI_TEMPERATURE)
            max_retries: Max retries for rate limits
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_LLM_MODEL
        self.temperature = temperature or settings.OPENAI_TEMPERATURE
        self.max_retries = max_retries
        self.timeout = timeout
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        # Create LangChain ChatOpenAI instance
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            max_retries=self.max_retries,
            request_timeout=self.timeout,
        )
        
        logger.info(f"✅ OpenAI provider initialized: model={self.model}")
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using OpenAI.
        
        Args:
            request: LLM request
        
        Returns:
            LLM response
        
        Raises:
            RateLimitError: If rate limit exceeded (429)
            TimeoutError: If request times out
        """
        try:
            # Build messages
            messages = []
            if request.system_message:
                messages.append(SystemMessage(content=request.system_message))
            messages.append(HumanMessage(content=request.prompt))
            
            # Override temperature if provided in request
            temperature = request.temperature if request.temperature is not None else self.temperature
            
            # Call OpenAI via LangChain
            logger.debug(f"🤖 Calling OpenAI {self.model} (temp={temperature})")
            
            response = await self.llm.ainvoke(
                messages,
                temperature=temperature,
                max_tokens=request.max_tokens,
                stop=request.stop_sequences
            )
            
            # Extract response
            text = response.content
            tokens = response.response_metadata.get("token_usage", {}).get("total_tokens")
            finish_reason = response.response_metadata.get("finish_reason")
            
            logger.info(f"✅ OpenAI response: {len(text)} chars, {tokens} tokens")
            
            return LLMResponse(
                text=text,
                provider="openai",
                model=self.model,
                tokens_used=tokens,
                finish_reason=finish_reason,
                metadata=response.response_metadata
            )
        
        except Exception as e:
            logger.error(f"❌ OpenAI generation failed: {e}", exc_info=True)
            
            # Re-raise with proper exception types
            if "429" in str(e) or "rate_limit" in str(e).lower():
                from shared.exceptions import RateLimitError
                raise RateLimitError(f"OpenAI rate limit: {e}")
            elif "timeout" in str(e).lower():
                raise TimeoutError(f"OpenAI timeout: {e}")
            else:
                raise ValueError(f"OpenAI error: {e}")
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return "openai"
    
    def get_model_name(self) -> str:
        """Get model name."""
        return self.model
    
    async def is_available(self) -> bool:
        """Check if OpenAI is available."""
        try:
            # Simple test call
            test_request = LLMRequest(
                prompt="test",
                max_tokens=5
            )
            await self.generate(test_request)
            return True
        except Exception as e:
            logger.warning(f"OpenAI not available: {e}")
            return False
