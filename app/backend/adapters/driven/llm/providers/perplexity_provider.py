"""
Perplexity LLM Provider - Adapter implementing LLMPort.

This adapter wraps Perplexity API for web-search-enhanced LLM capabilities.
"""

import logging
from typing import Optional
import httpx
from core.ports.llm_port import LLMPort, LLMRequest, LLMResponse
from config import settings

logger = logging.getLogger(__name__)


class PerplexityProvider(LLMPort):
    """
    Perplexity provider for web-search-enhanced LLMs.
    
    Models: sonar, sonar-pro, sonar-reasoning
    Features: Automatic web search + citations in responses
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout: int = 120
    ):
        """
        Initialize Perplexity provider.
        
        Args:
            api_key: Perplexity API key (defaults to settings.PERPLEXITY_API_KEY)
            model: Model name (defaults to settings.PERPLEXITY_MODEL or 'sonar-pro')
            temperature: Temperature (defaults to settings.PERPLEXITY_TEMPERATURE)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or getattr(settings, 'PERPLEXITY_API_KEY', None)
        self.model = model or getattr(settings, 'PERPLEXITY_MODEL', 'sonar-pro')
        self.temperature = temperature if temperature is not None else getattr(settings, 'PERPLEXITY_TEMPERATURE', 0.2)
        self.timeout = timeout
        self.base_url = "https://api.perplexity.ai"
        
        if not self.api_key:
            raise ValueError("Perplexity API key not provided and not found in settings")
        
        logger.info(f"✅ Perplexity provider initialized: model={self.model}")
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text using Perplexity.
        
        Args:
            request: LLM request
        
        Returns:
            LLM response with citations from web search
        """
        try:
            # Build messages
            messages = []
            if request.system_message:
                messages.append({"role": "system", "content": request.system_message})
            messages.append({"role": "user", "content": request.prompt})
            
            # Override temperature if provided in request
            temperature = request.temperature if request.temperature is not None else self.temperature
            
            # Call Perplexity API
            logger.debug(f"🌐 Calling Perplexity {self.model} (temp={temperature})")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": request.max_tokens or 1000,
                        "stream": False
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            # Extract response
            text = data["choices"][0]["message"]["content"]
            
            # Extract token usage
            tokens_used = None
            if "usage" in data:
                usage = data["usage"]
                tokens_used = usage.get("total_tokens")
            
            logger.info(f"✅ Perplexity response: {len(text)} chars, tokens={tokens_used}")
            
            return LLMResponse(
                text=text,
                provider="perplexity",
                model=self.model,
                tokens_used=tokens_used,
                finish_reason=data["choices"][0].get("finish_reason", "stop"),
                metadata={
                    "citations": data.get("citations", []),
                    "url": data.get("url")
                }
            )
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error(f"❌ Perplexity rate limit: {e}")
                raise Exception(f"Perplexity rate limit: {e}")
            elif e.response.status_code >= 500:
                logger.error(f"❌ Perplexity server error: {e}")
                raise Exception(f"Perplexity server error: {e}")
            else:
                logger.error(f"❌ Perplexity HTTP error: {e}")
                raise Exception(f"Perplexity error: {e}")
        
        except httpx.TimeoutException as e:
            logger.error(f"❌ Perplexity timeout: {e}")
            raise Exception(f"Perplexity timeout: {e}")
        
        except Exception as e:
            logger.error(f"❌ Perplexity generation failed: {e}", exc_info=True)
            raise Exception(f"Perplexity error: {e}")
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return "perplexity"
    
    def get_model_name(self) -> str:
        """Get model name."""
        return self.model
    
    async def is_available(self) -> bool:
        """Check if Perplexity is available."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Perplexity not available: {e}")
            return False
