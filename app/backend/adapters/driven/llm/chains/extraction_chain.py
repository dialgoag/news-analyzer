"""
Extraction Chain - First step: Extract structured data from news articles.

This chain focuses ONLY on extracting factual, structured information.
No analysis or insights - just facts, entities, and metadata.
"""

import logging
from typing import List, Dict, Any, Optional

from core.ports.llm_port import LLMPort, LLMChainPort, LLMRequest, LLMResponse
from shared.exceptions import RateLimitError, TimeoutError

logger = logging.getLogger(__name__)


# Extraction prompt - Focus on FACTS only
EXTRACTION_PROMPT_TEMPLATE = """You are a precise information extraction system. Your ONLY task is to extract factual, structured data from news articles.

Do NOT provide analysis, opinions, or interpretations. Extract ONLY verifiable information present in the text.

EXTRACT THE FOLLOWING:

1. **METADATA**
   - Date: [When did the event occur? Extract exact date/time if mentioned, otherwise "Not specified"]
   - Time: [Specific time if mentioned]
   - Location: [City, Region, Country - be specific]
   - Source: [Newspaper/Magazine/Agency name]
   - Author: [Journalist name if mentioned, otherwise "Not specified"]

2. **KEY ACTORS** (People and Organizations)
   For each actor, extract:
   - Name: [Full name]
   - Type: [Person/Organization/Institution]
   - Role/Title: [Their official role]
   - Actions: [What they did or said - use quotes when available]

3. **FACTS & EVENTS** (Timeline)
   List each fact with:
   - What happened: [Specific event description]
   - When: [Date/time if mentioned]
   - Where: [Location if mentioned]
   - Who: [Actors involved]
   - Numbers/Data: [Any statistics, amounts, counts]

4. **THEMES & CATEGORIES**
   - Primary topic: [Main subject]
   - Secondary topics: [Related subjects]
   - Tags: [Keywords that describe the article]

5. **QUOTES** (Direct quotes only)
   - "[Quote text]" - [Speaker name]

6. **DATA POINTS**
   Extract any numbers, statistics, or quantifiable data:
   - [Description]: [Number/Value] [Unit]

FORMAT YOUR RESPONSE AS STRUCTURED JSON-LIKE TEXT:

## Metadata
Date: [date]
Time: [time or "Not specified"]
Location: [location hierarchy: City, Region, Country]
Source: [source name]
Author: [author name or "Not specified"]

## Actors
- Name: [name] | Type: [person/organization/institution] | Role: [role] | Action: [what they did/said]
- Name: [name] | Type: [person/organization/institution] | Role: [role] | Action: [what they did/said]

## Events Timeline
- Event: [description] | When: [date/time] | Where: [location] | Who: [actors] | Data: [numbers]
- Event: [description] | When: [date/time] | Where: [location] | Who: [actors] | Data: [numbers]

## Themes
Primary: [main topic]
Secondary: [topic 1], [topic 2], [topic 3]
Tags: [tag1], [tag2], [tag3]

## Quotes
- "[quote]" - [Speaker]
- "[quote]" - [Speaker]

## Data Points
- [Description]: [Number] [Unit]
- [Description]: [Number] [Unit]

IMPORTANT RULES:
- Extract ONLY information explicitly stated in the text
- Use "Not specified" when information is not available
- Do NOT infer, interpret, or add information
- Keep speaker names exactly as they appear
- Preserve exact numbers and units

---

NEWS ARTICLE:
{context}

ARTICLE TITLE: {title}

EXTRACTED INFORMATION:"""


class ExtractionChain(LLMChainPort):
    """
    Extraction chain - First step in insights pipeline.
    
    Extracts structured, factual information from news articles.
    This data is then used by AnalysisChain to generate insights.
    
    Temperature: 0.1 (low for factual precision)
    Max tokens: 1200
    """
    
    def __init__(self, providers: Optional[List[LLMPort]] = None):
        """
        Initialize extraction chain.
        
        Args:
            providers: List of LLM providers to try (with fallback)
        """
        self.providers = providers or []
        logger.info(f"✅ ExtractionChain initialized with {len(self.providers)} providers")
    
    async def run(self, context: str, title: str = "") -> Dict[str, Any]:
        """
        Extract structured data from article.
        
        Args:
            context: News article text
            title: Article title
        
        Returns:
            Dict with extracted_data, tokens_used, provider, model
        
        Raises:
            Exception if all providers fail
        """
        # Format prompt
        formatted_prompt = EXTRACTION_PROMPT_TEMPLATE.format(
            context=context,
            title=title
        )
        
        # Try providers in order with fallback
        last_error = None
        for provider in self.providers:
            try:
                provider_name = provider.get_provider_name()
                logger.info(f"📊 Extracting structured data with {provider_name}")
                
                request = LLMRequest(
                    prompt=formatted_prompt,
                    temperature=0.1,  # Low temperature for factual extraction
                    max_tokens=1200
                )
                
                response = await provider.generate(request)
                
                logger.info(
                    f"✅ Data extracted: {len(response.text)} chars, "
                    f"tokens={response.tokens_used}, provider={provider_name}"
                )
                
                return {
                    'extracted_data': response.text,
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
        return "ExtractionChain"
