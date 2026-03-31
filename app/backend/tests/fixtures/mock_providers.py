"""
Mock LLM Providers for Testing.

Provides test doubles for LLM providers that don't make real API calls.
"""

from typing import Optional, Dict, Any
from core.ports.llm_port import LLMPort, LLMRequest, LLMResponse


class MockLLMProvider(LLMPort):
    """
    Mock LLM provider for testing.
    
    Returns predefined responses without making real API calls.
    """
    
    def __init__(
        self,
        provider_name: str = "mock",
        model_name: str = "mock-model",
        responses: Optional[Dict[str, str]] = None,
        should_fail: bool = False,
        fail_after_attempts: int = 0
    ):
        """
        Initialize mock provider.
        
        Args:
            provider_name: Name of provider (for identification)
            model_name: Name of model (for identification)
            responses: Dict mapping prompt keywords to responses
            should_fail: If True, always raises error
            fail_after_attempts: Fail after N successful attempts (for retry testing)
        """
        self.provider_name = provider_name
        self.model_name = model_name
        self.responses = responses or {}
        self.should_fail = should_fail
        self.fail_after_attempts = fail_after_attempts
        
        # Statistics
        self.call_count = 0
        self.last_request: Optional[LLMRequest] = None
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Generate mock response.
        
        Args:
            request: LLM request
        
        Returns:
            Mock LLM response
        
        Raises:
            Exception if should_fail is True or fail_after_attempts reached
        """
        self.call_count += 1
        self.last_request = request
        
        # Check if should fail
        if self.should_fail:
            raise Exception(f"Mock provider {self.provider_name} configured to fail")
        
        if self.fail_after_attempts > 0 and self.call_count > self.fail_after_attempts:
            raise Exception(f"Mock provider {self.provider_name} failed after {self.fail_after_attempts} attempts")
        
        # Find matching response
        response_text = self._get_response(request.prompt)
        
        # Calculate mock tokens (simple approximation)
        tokens_used = len(response_text.split())
        
        return LLMResponse(
            text=response_text,
            tokens_used=tokens_used,
            model=self.model_name,
            provider=self.provider_name
        )
    
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self.provider_name
    
    async def is_available(self) -> bool:
        """Check if provider is available."""
        return not self.should_fail
    
    def _get_response(self, prompt: str) -> str:
        """
        Get response based on prompt content.
        
        Looks for keywords in prompt and returns matching response.
        """
        prompt_lower = prompt.lower()
        
        # Check for keyword matches
        for keyword, response in self.responses.items():
            if keyword.lower() in prompt_lower:
                return response
        
        # Default response
        return "Mock response"
    
    def reset_stats(self):
        """Reset statistics."""
        self.call_count = 0
        self.last_request = None


class MockExtractionProvider(MockLLMProvider):
    """
    Mock provider specialized for extraction responses.
    """
    
    def __init__(self, **kwargs):
        default_responses = {
            "extract": """## Metadata
Date: 2026-03-31
Time: 14:30
Location: Madrid, España
Source: El País
Author: Juan Pérez
Publication: El País

## Actors
- Name: Pedro Sánchez | Type: person | Role: President | Action: Announced measures
- Name: Spanish Government | Type: organization | Role: Executive | Action: Approved decree

## Events Timeline
- Event: Decree approval | When: 2026-03-31 14:00 | Where: Madrid | Who: Government

## Themes
Primary: Politics
Secondary: Economy, Legislation
Tags: decree, government, madrid

## Quotes
- "The measures will take effect tomorrow" - Pedro Sánchez

## Data Points
- Budget: 500 million euros
""",
            "default": "## Metadata\nDate: 2026-03-31\n\n## Actors\n- Name: Mock Actor | Type: person\n\n## Events\n- Event: Mock Event"
        }
        
        # Merge with provided responses
        responses = kwargs.pop('responses', {})
        default_responses.update(responses)
        
        super().__init__(
            provider_name=kwargs.pop('provider_name', 'mock-extraction'),
            model_name=kwargs.pop('model_name', 'mock-extraction-model'),
            responses=default_responses,
            **kwargs
        )


class MockAnalysisProvider(MockLLMProvider):
    """
    Mock provider specialized for analysis responses.
    """
    
    def __init__(self, **kwargs):
        default_responses = {
            "analyze": """## Significance
This decree represents a significant shift in economic policy, marking the government's 
commitment to fiscal stimulus in response to economic challenges.

## Historical Context
This measure builds upon previous economic reforms from 2024, but differs in scale and scope.
It represents the largest single economic intervention since the pandemic recovery.

## Key Perspectives
- Government: Views this as necessary stimulus for economic growth
- Opposition: Criticizes the timing and potential inflationary impact
- Economists: Mixed opinions on effectiveness

## Implications
Short-term: Immediate impact on consumer spending and business investment
Medium-term: Potential inflationary pressures if not managed carefully
Long-term: Could set precedent for future fiscal policy approaches

## Patterns Observed
This decision follows a pattern of government intervention during economic uncertainty,
similar to measures taken in 2020 and 2024.

## Expert Analysis
This policy shift indicates the government's prioritization of growth over fiscal 
consolidation in the current economic climate. The success will depend heavily on 
implementation and external economic factors.
""",
            "default": "## Significance\nThis is significant.\n\n## Context\nSome context.\n\n## Implications\nSome implications."
        }
        
        # Merge with provided responses
        responses = kwargs.pop('responses', {})
        default_responses.update(responses)
        
        super().__init__(
            provider_name=kwargs.pop('provider_name', 'mock-analysis'),
            model_name=kwargs.pop('model_name', 'mock-analysis-model'),
            responses=default_responses,
            **kwargs
        )


class FailingMockProvider(MockLLMProvider):
    """
    Mock provider that always fails (for error testing).
    """
    
    def __init__(self, error_message: str = "Mock provider failed", **kwargs):
        super().__init__(
            provider_name="mock-failing",
            should_fail=True,
            **kwargs
        )
        self.error_message = error_message
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Always raise error."""
        self.call_count += 1
        self.last_request = request
        raise Exception(self.error_message)
