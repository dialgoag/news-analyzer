"""
Insights Chain - Two-step LangChain pipeline for news insights.

This chain orchestrates a two-step process:
1. ExtractionChain: Extracts structured, factual data (metadata, actors, events, etc.)
2. AnalysisChain: Generates expert insights and analysis from the extracted data

This separation enables:
- Knowledge graph construction from structured data
- Temporal analysis of events
- Actor network analysis
- Theme tracking across articles
- Cross-document connection discovery
- High-quality analysis based on verified facts

The output includes both structured data AND expert analysis, making it
ideal for both machine processing (graphs) and human consumption (insights).
"""

import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from core.ports.llm_port import LLMPort, LLMChainPort, LLMRequest, LLMResponse
from adapters.driven.llm.providers.openai_provider import OpenAIProvider
from adapters.driven.llm.providers.ollama_provider import OllamaProvider
from adapters.driven.llm.chains.extraction_chain import ExtractionChain
from adapters.driven.llm.chains.analysis_chain import AnalysisChain
from config import settings, get_llm_provider_order

logger = logging.getLogger(__name__)


@dataclass
class InsightResult:
    """
    Result from insights pipeline.
    
    Contains both structured extraction and expert analysis.
    """
    # Structured data (for knowledge graph)
    extracted_data: str
    
    # Expert analysis and insights
    analysis: str
    
    # Combined text (for storage/display)
    full_text: str
    
    # Metadata
    provider_used: str
    model_used: str
    extraction_tokens: Optional[int] = None
    analysis_tokens: Optional[int] = None


class InsightsChain(LLMChainPort):
    """
    Two-step LangChain pipeline for generating structured insights.
    
    Pipeline:
    1. ExtractionChain → Structured factual data
    2. AnalysisChain → Expert insights from extracted data
    
    Features:
    - Structured extraction for knowledge graphs
    - Expert analysis for human consumption
    - Multiple LLM provider support with fallback
    - Retry logic for rate limits
    - Token tracking
    """
    
    def __init__(
        self,
        providers: Optional[List[LLMPort]] = None
    ):
        """
        Initialize insights chain.
        
        Args:
            providers: List of LLM providers (in priority order)
        """
        # Setup providers with fallback
        if providers is None:
            providers = self._create_default_providers()
        
        self.providers = providers
        logger.info(f"✅ InsightsChain initialized with {len(self.providers)} providers")
    
    def _create_default_providers(self) -> List[LLMPort]:
        """Create default providers from settings."""
        provider_order = get_llm_provider_order()
        providers = []
        
        for provider_name in provider_order:
            try:
                if provider_name == "openai":
                    providers.append(OpenAIProvider())
                elif provider_name == "ollama":
                    providers.append(OllamaProvider())
                # Add Perplexity when implemented
                # elif provider_name == "perplexity":
                #     providers.append(PerplexityProvider())
                else:
                    logger.warning(f"Unknown provider: {provider_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize {provider_name}: {e}")
        
        if not providers:
            raise ValueError("No LLM providers available")
        
        return providers
    
    async def run(self, context: str, title: str = "") -> str:
        """
        Generate insight for a news article (compatibility method).
        
        Returns full_text for backward compatibility.
        
        Args:
            context: News article text
            title: Article title
        
        Returns:
            Combined insights text
        """
        result = await self.run_full(context=context, title=title)
        return result.full_text
    
    async def run_full(self, context: str, title: str = "") -> InsightResult:
        """
        Generate full structured insight for a news article.
        
        This is the main method that runs the two-step pipeline.
        
        Args:
            context: News article text
            title: Article title
        
        Returns:
            InsightResult with both extraction and analysis
        
        Raises:
            ValueError: If all providers fail
        """
        # Try providers in order with fallback
        last_error = None
        for i, provider in enumerate(self.providers):
            provider_name = provider.get_provider_name()
            model_name = provider.get_model_name()
            
            try:
                logger.info(
                    f"🤖 Running insights pipeline with {provider_name}/{model_name} "
                    f"(provider {i+1}/{len(self.providers)})"
                )
                
                # STEP 1: Extract structured data
                extraction_chain = ExtractionChain(provider)
                extracted_data = await extraction_chain.run(
                    context=context,
                    title=title
                )
                
                logger.info(f"✅ Step 1/2: Data extraction complete")
                
                # STEP 2: Generate insights from extracted data
                analysis_chain = AnalysisChain(provider)
                analysis = await analysis_chain.run(
                    extracted_data=extracted_data,
                    title=title
                )
                
                logger.info(f"✅ Step 2/2: Analysis complete")
                
                # Combine results
                full_text = self._combine_results(extracted_data, analysis)
                
                logger.info(
                    f"✅ Full insights pipeline complete: "
                    f"{len(full_text)} chars, provider={provider_name}"
                )
                
                return InsightResult(
                    extracted_data=extracted_data,
                    analysis=analysis,
                    full_text=full_text,
                    provider_used=provider_name,
                    model_used=model_name
                )
            
            except Exception as e:
                logger.warning(
                    f"⚠️ Provider {provider_name} failed: {e}. "
                    f"Trying next provider ({i+2}/{len(self.providers)})..."
                )
                last_error = e
                continue
        
        # All providers failed
        error_msg = f"All {len(self.providers)} providers failed. Last error: {last_error}"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    def _combine_results(self, extracted_data: str, analysis: str) -> str:
        """
        Combine extraction and analysis into single document.
        
        Args:
            extracted_data: Structured extraction
            analysis: Expert analysis
        
        Returns:
            Combined markdown document
        """
        return f"""# News Insight Report

## Part 1: Structured Data Extraction

{extracted_data}

---

## Part 2: Expert Analysis & Insights

{analysis}

---

Generated by InsightsChain (Two-Step Pipeline)
"""
    
    def get_chain_name(self) -> str:
        """Get chain name for logging."""
        return "InsightsChain (Two-Step)"
    
    def get_active_providers(self) -> List[str]:
        """Get list of active provider names."""
        return [p.get_provider_name() for p in self.providers]


async def generate_insight(context: str, title: str = "") -> Tuple[str, str]:
    """
    Convenience function to generate insight.
    
    Args:
        context: News article text
        title: Article title
    
    Returns:
        Tuple of (insight_full_text, provider_used)
    """
    chain = InsightsChain()
    result = await chain.run_full(context=context, title=title)
    
    return result.full_text, result.provider_used


async def generate_insight_structured(
    context: str,
    title: str = ""
) -> Tuple[str, str, str]:
    """
    Generate insight with separate extraction and analysis.
    
    Args:
        context: News article text
        title: Article title
    
    Returns:
        Tuple of (extracted_data, analysis, provider_used)
    """
    chain = InsightsChain()
    result = await chain.run_full(context=context, title=title)
    
    return result.extracted_data, result.analysis, result.provider_used
