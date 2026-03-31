"""
LLM Port - Interface for LLM providers.

This is a Hexagonal Architecture port (interface).
Adapters implement this interface for different LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    text: str
    provider: str
    model: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMRequest:
    """Request to LLM provider."""
    prompt: str
    system_message: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stop_sequences: Optional[list] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMPort(ABC):
    """
    Port (interface) for LLM providers.
    
    Implementations:
    - OpenAIProvider
    - PerplexityProvider
    - OllamaProvider
    """
    
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text from LLM.
        
        Args:
            request: LLM request with prompt and parameters
        
        Returns:
            LLM response with generated text
        
        Raises:
            RateLimitError: If rate limit is exceeded
            TimeoutError: If request times out
            ValueError: If request is invalid
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name (openai, perplexity, ollama)."""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get model name."""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is available."""
        pass


class LLMChainPort(ABC):
    """
    Port for LangChain chains.
    
    This allows us to abstract LangChain-specific logic.
    """
    
    @abstractmethod
    async def run(self, **kwargs) -> str:
        """
        Run the chain with given inputs.
        
        Returns:
            Generated text
        """
        pass
    
    @abstractmethod
    def get_chain_name(self) -> str:
        """Get chain name for logging."""
        pass
