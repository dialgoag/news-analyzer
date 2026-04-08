"""
Web Enrichment Chain - Optional step: Enrich insights with web sources.

This chain uses Perplexity Sonar (includes web search + citations)
to find verified information from credible sources.
"""

import logging
from typing import List, Dict, Any, Optional

from core.ports.llm_port import LLMPort, LLMChainPort, LLMRequest, LLMResponse
from shared.exceptions import RateLimitError, TimeoutError

logger = logging.getLogger(__name__)


# Web enrichment prompt - Focus on SOURCES
WEB_ENRICHMENT_PROMPT_TEMPLATE = """Search for additional verified information about this news story:

**TITLE**: {title}

**KEY ACTORS AND EVENTS** (from article):
{extracted_data}

---

**TASK**: Find recent, credible information from official sources.

**FOCUS ON**:
- Official statements from credible news agencies (AP, Reuters, AFP, EFE, BBC, etc.)
- Government/institutional press releases
- Recent developments (last 7-14 days)

**PROVIDE ONLY**:
1. Source name
2. Key fact or quote (one sentence)
3. URL (if available)
4. Publication date

**FORMAT**:
## Additional Sources
- [Source Name]: [Key fact or quote] ([URL if available]) - [Date]
- [Source Name]: [Key fact or quote] ([URL if available]) - [Date]

**IMPORTANT**:
- Only include information from credible, verifiable sources
- Do NOT include speculation or analysis
- Limit to 3-5 most relevant sources
- If no credible sources found, respond with: "No additional sources found"
"""


def should_enrich_with_web(extracted_data: str, title: str) -> bool:
    """
    Decide if news needs web enrichment based on content.
    
    Criteria:
    - International keywords
    - Important actors (governments, institutions)
    - Significant events
    
    Args:
        extracted_data: Extracted structured data from article
        title: Article title
    
    Returns:
        True if enrichment recommended, False otherwise
    """
    text_lower = (extracted_data + " " + title).lower()
    
    # International/global keywords
    international_keywords = [
        'internacional', 'global', 'mundial', 'países', 'naciones',
        'organización', 'tratado', 'acuerdo', 'cumbre',
        'guerra', 'conflicto', 'crisis', 'emergencia'
    ]
    
    # Important actors/institutions
    important_actors = [
        'presidente', 'ministro', 'gobierno', 'parlamento',
        'tribunal supremo', 'corte', 'fiscal',
        'onu', 'otan', 'ue', 'unión europea', 'fmi', 'oms',
        'banco central', 'comisión europea'
    ]
    
    has_intl_keyword = any(kw in text_lower for kw in international_keywords)
    has_important_actor = any(actor in text_lower for actor in important_actors)
    
    return has_intl_keyword or has_important_actor


class WebEnrichmentChain(LLMChainPort):
    """
    Web enrichment chain - Optional step in insights pipeline.
    
    Searches web for additional credible sources using Perplexity Sonar.
    Only called for relevant news (international, important actors, etc.)
    
    Temperature: 0.1 (low for factual queries)
    Max tokens: 500 (just sources, not full articles)
    """
    
    def __init__(self, providers: Optional[List[LLMPort]] = None):
        """
        Initialize web enrichment chain.
        
        Args:
            providers: List of LLM providers (should include Perplexity)
        """
        self.providers = providers or []
        
        # Verify at least one provider supports web search (Perplexity)
        has_perplexity = any(
            p.get_provider_name() == "perplexity" 
            for p in self.providers
        )
        
        if not has_perplexity:
            logger.warning(
                "⚠️ WebEnrichmentChain initialized without Perplexity provider. "
                "Web enrichment will be skipped."
            )
        
        logger.info(f"✅ WebEnrichmentChain initialized with {len(self.providers)} providers")
    
    async def run(self, extracted_data: str, title: str = "") -> Dict[str, Any]:
        """
        Enrich extracted data with web sources.
        
        Args:
            extracted_data: Structured data from ExtractionChain
            title: Article title
        
        Returns:
            Dict with enrichment, tokens_used, provider, model
        
        Raises:
            Exception if all providers fail (gracefully handled by caller)
        """
        # Check if enrichment is needed
        if not should_enrich_with_web(extracted_data, title):
            logger.info("ℹ️ Web enrichment not needed (local/routine news)")
            return {
                'enrichment': None,
                'tokens_used': 0,
                'provider': 'none',
                'model': 'none',
                'skipped': True,
                'reason': 'Not international/important news'
            }
        
        # Format prompt
        formatted_prompt = WEB_ENRICHMENT_PROMPT_TEMPLATE.format(
            extracted_data=extracted_data[:1000],  # Limit to first 1000 chars
            title=title
        )
        
        # Try providers in order (prefer Perplexity)
        last_error = None
        for provider in self.providers:
            try:
                provider_name = provider.get_provider_name()
                
                # Skip non-Perplexity providers (they don't have web search)
                if provider_name != "perplexity":
                    continue
                
                logger.info(f"🌐 Searching web for additional sources with {provider_name}")
                
                request = LLMRequest(
                    prompt=formatted_prompt,
                    temperature=0.1,  # Low temperature for factual queries
                    max_tokens=500     # Just sources, not full analysis
                )
                
                response = await provider.generate(request)
                
                logger.info(
                    f"✅ Web sources found: {len(response.text)} chars, "
                    f"tokens={response.tokens_used}, provider={provider_name}"
                )
                
                return {
                    'enrichment': response.text,
                    'tokens_used': response.tokens_used,
                    'provider': provider_name,
                    'model': response.model,
                    'citations': response.metadata.get('citations', [])
                }
                
            except (RateLimitError, TimeoutError) as e:
                logger.warning(f"⚠️ {provider_name} failed: {e}, trying next provider...")
                last_error = e
                continue
            except Exception as e:
                logger.error(f"❌ {provider_name} error: {e}")
                last_error = e
                continue
        
        # All providers failed or no Perplexity available
        logger.warning(f"⚠️ Web enrichment skipped (no available provider)")
        return {
            'enrichment': None,
            'tokens_used': 0,
            'provider': 'none',
            'model': 'none',
            'skipped': True,
            'reason': f'All providers failed: {last_error}'
        }
    
    def get_chain_name(self) -> str:
        """Get chain name."""
        return "WebEnrichmentChain"
