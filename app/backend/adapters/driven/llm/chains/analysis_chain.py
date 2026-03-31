"""
Analysis Chain - Second step: Generate insights from extracted data.

This chain takes structured extracted data and generates expert analysis.
"""

import logging
from typing import List, Dict, Any, Optional

from core.ports.llm_port import LLMPort, LLMChainPort, LLMRequest, LLMResponse
from shared.exceptions import RateLimitError, TimeoutError

logger = logging.getLogger(__name__)


# Analysis prompt - Focus on INSIGHTS
ANALYSIS_PROMPT_TEMPLATE = """You are an expert news analyst. You have been provided with structured, factual information extracted from a news article.

Your task is to provide expert analysis and insights based on this extracted data.

ANALYZE AND PROVIDE INSIGHTS ON:

1. **SIGNIFICANCE**
   - Why is this news important?
   - What is the broader impact?
   - Who is affected and how?

2. **CONTEXT & CONNECTIONS**
   - How does this relate to historical events or trends?
   - What similar events have occurred recently?
   - How does this fit into larger patterns?

3. **PERSPECTIVES & IMPLICATIONS**
   - What are the different viewpoints on this issue?
   - What are the short-term implications?
   - What are the long-term consequences?
   - What conflicts or alignments exist between actors?

4. **PATTERNS & TRENDS**
   - What patterns emerge from the facts?
   - Are there recurring themes or actors?
   - What trends does this indicate?

5. **EXPERT PERSPECTIVE**
   - What should readers understand about this?
   - What questions does this raise?
   - What should we watch for next?

FORMAT YOUR ANALYSIS:

## Significance
[2-3 sentences on why this matters]

## Historical Context
[How this relates to past events or ongoing trends]

## Key Perspectives
- [Actor/Group]: [Their perspective and why they hold it]
- [Actor/Group]: [Their perspective and why they hold it]

## Implications
Short-term: [immediate effects]
Long-term: [lasting consequences]

## Patterns Observed
[What patterns or trends this reveals]

## Expert Analysis
[2-3 paragraphs synthesizing the above into comprehensive insight]

IMPORTANT:
- Base your analysis ONLY on the extracted data provided
- Be analytical, not descriptive
- Focus on "why" and "what it means", not "what happened"
- Connect dots between facts to reveal insights
- Maintain objectivity while providing expert perspective

---

EXTRACTED DATA:
{extracted_data}

ORIGINAL ARTICLE TITLE: {title}

ANALYTICAL INSIGHTS:"""


class AnalysisChain(LLMChainPort):
    """
    Analysis chain - Second step in insights pipeline.
    
    Generates expert insights from structured extracted data.
    
    Temperature: 0.7 (higher for creative analysis)
    Max tokens: 1000
    """
    
    def __init__(self, providers: Optional[List[LLMPort]] = None):
        """
        Initialize analysis chain.
        
        Args:
            providers: List of LLM providers to try (with fallback)
        """
        self.providers = providers or []
        logger.info(f"✅ AnalysisChain initialized with {len(self.providers)} providers")
    
    async def run(self, extracted_data: str, title: str = "") -> Dict[str, Any]:
        """
        Generate insights from extracted data.
        
        Args:
            extracted_data: Structured data from ExtractionChain
            title: Article title
        
        Returns:
            Dict with analysis, tokens_used, provider, model
        
        Raises:
            Exception if all providers fail
        """
        # Format prompt
        formatted_prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            extracted_data=extracted_data,
            title=title
        )
        
        # Try providers in order with fallback
        last_error = None
        for provider in self.providers:
            try:
                provider_name = provider.get_provider_name()
                logger.info(f"🧠 Generating insights with {provider_name}")
                
                request = LLMRequest(
                    prompt=formatted_prompt,
                    temperature=0.7,  # Higher temperature for creative analysis
                    max_tokens=1000
                )
                
                response = await provider.generate(request)
                
                logger.info(
                    f"✅ Insights generated: {len(response.text)} chars, "
                    f"tokens={response.tokens_used}, provider={provider_name}"
                )
                
                return {
                    'analysis': response.text,
                    'tokens_used': response.tokens_used,
                    'provider': provider_name,
                    'model': response.model
                }
                
            except (RateLimitError, TimeoutError) as e:
                logger.warning(f"⚠️ {provider_name} failed: {e}, trying next provider...")
                last_error = e
                continue
            except Exception as e:
                logger.error(f"❌ {provider_name} error: {e}")
                last_error = e
                continue
        
        # All providers failed
        raise Exception(f"All {len(self.providers)} providers failed. Last error: {last_error}")
    
    def get_chain_name(self) -> str:
        """Get chain name."""
        return "AnalysisChain"
