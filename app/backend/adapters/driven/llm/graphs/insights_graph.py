"""
LangGraph Workflow for Insights Generation.

This module implements a stateful, multi-step workflow for generating insights
with validation, retry logic, and error recovery.

Architecture: Hexagonal (Adapter - Driven - LLM - Graphs)
Integration: Uses LangGraph for state management and conditional flows
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Literal, Optional, TypedDict, List

from langgraph.graph import StateGraph, END

from adapters.driven.llm.chains.extraction_chain import ExtractionChain
from adapters.driven.llm.chains.analysis_chain import AnalysisChain
from adapters.driven.llm.providers.openai_provider import OpenAIProvider
from adapters.driven.llm.providers.ollama_provider import OllamaProvider
from shared.exceptions import RateLimitError, TimeoutError, ValidationError
from config import get_llm_provider_order, settings as app_settings

try:
    import insights_pipeline_control as _ipc
except Exception:  # pragma: no cover - fallback cuando no existe módulo
    _ipc = None

logger = logging.getLogger(__name__)


# ============================================================================
# State Definition
# ============================================================================

class InsightState(TypedDict):
    """
    State for the insights generation workflow.
    
    This state is passed between nodes and tracks the entire workflow progress.
    """
    # Input (immutable)
    news_item_id: str
    document_id: str
    context: str
    title: str
    
    # Extracted data (step 1)
    extracted_data: Optional[str]
    extraction_tokens: int
    
    # Analysis (step 2)
    analysis: Optional[str]
    analysis_tokens: int
    
    # Validation flags
    extraction_valid: bool
    analysis_valid: bool
    
    # Retry tracking
    extraction_attempts: int
    analysis_attempts: int
    max_attempts: int
    
    # Provider tracking
    provider_used: Optional[str]
    model_used: Optional[str]
    
    # Final output
    full_text: Optional[str]
    success: bool
    
    # Error handling
    error: Optional[str]
    error_step: Optional[str]


# ============================================================================
# Workflow Nodes
# ============================================================================

async def extract_node(state: InsightState) -> InsightState:
    """
    Node: Extract structured data from news context.
    
    Calls ExtractionChain with appropriate provider.
    """
    logger.info(
        f"🔍 [extract_node] Attempt {state['extraction_attempts'] + 1}/"
        f"{state['max_attempts']} for news_item={state['news_item_id']}"
    )
    
    state['extraction_attempts'] += 1
    
    try:
        # Initialize chain with providers
        providers = _get_providers()
        chain = ExtractionChain(providers=providers)
        
        # Run extraction
        result = await chain.run(
            context=state['context'],
            title=state['title']
        )
        
        # Update state
        state['extracted_data'] = result['extracted_data']
        state['extraction_tokens'] = result['tokens_used']
        state['provider_used'] = result['provider']
        state['model_used'] = result['model']
        
        logger.info(
            f"✅ [extract_node] Extraction complete: "
            f"{len(result['extracted_data'])} chars, "
            f"provider={result['provider']}, "
            f"tokens={result['tokens_used']}"
        )
        
    except (RateLimitError, TimeoutError) as e:
        logger.warning(f"⚠️ [extract_node] Retriable error: {e}")
        state['error'] = str(e)
        state['error_step'] = 'extraction'
        
    except Exception as e:
        logger.error(f"❌ [extract_node] Fatal error: {e}", exc_info=True)
        state['error'] = str(e)
        state['error_step'] = 'extraction'
    
    return state


async def validate_extraction_node(state: InsightState) -> InsightState:
    """
    Node: Validate that extracted data has required fields.
    
    Checks for minimum requirements:
    - Has metadata section
    - Has at least one actor or event
    - Minimum length (>100 chars)
    """
    logger.info(f"✓ [validate_extraction_node] Validating extraction for news_item={state['news_item_id']}")
    
    extracted = state.get('extracted_data', '')
    
    # Basic validation checks
    has_metadata = '## Metadata' in extracted or '## METADATA' in extracted
    has_actors = '## Actors' in extracted or '## ACTORS' in extracted
    has_events = '## Events' in extracted or '## EVENTS' in extracted or '## Timeline' in extracted
    has_minimum_length = len(extracted) > 100
    
    # Valid if has metadata and (actors or events) and minimum length
    is_valid = has_metadata and (has_actors or has_events) and has_minimum_length
    
    state['extraction_valid'] = is_valid
    
    if is_valid:
        logger.info(
            f"✅ [validate_extraction_node] Validation passed: "
            f"metadata={has_metadata}, actors={has_actors}, "
            f"events={has_events}, length={len(extracted)}"
        )
    else:
        logger.warning(
            f"⚠️ [validate_extraction_node] Validation failed: "
            f"metadata={has_metadata}, actors={has_actors}, "
            f"events={has_events}, length={len(extracted)}"
        )
    
    return state


async def analyze_node(state: InsightState) -> InsightState:
    """
    Node: Generate expert analysis based on extracted data.
    
    Calls AnalysisChain with extracted data as input.
    """
    logger.info(
        f"🧠 [analyze_node] Attempt {state['analysis_attempts'] + 1}/"
        f"{state['max_attempts']} for news_item={state['news_item_id']}"
    )
    
    state['analysis_attempts'] += 1
    
    try:
        # Initialize chain with providers
        providers = _get_providers()
        chain = AnalysisChain(providers=providers)
        
        # Run analysis
        result = await chain.run(
            extracted_data=state['extracted_data'],
            title=state['title']
        )
        
        # Update state
        state['analysis'] = result['analysis']
        state['analysis_tokens'] = result['tokens_used']
        # Keep same provider/model from extraction if possible
        if not state.get('provider_used'):
            state['provider_used'] = result['provider']
            state['model_used'] = result['model']
        
        logger.info(
            f"✅ [analyze_node] Analysis complete: "
            f"{len(result['analysis'])} chars, "
            f"provider={result['provider']}, "
            f"tokens={result['tokens_used']}"
        )
        
    except (RateLimitError, TimeoutError) as e:
        logger.warning(f"⚠️ [analyze_node] Retriable error: {e}")
        state['error'] = str(e)
        state['error_step'] = 'analysis'
        
    except Exception as e:
        logger.error(f"❌ [analyze_node] Fatal error: {e}", exc_info=True)
        state['error'] = str(e)
        state['error_step'] = 'analysis'
    
    return state


async def validate_analysis_node(state: InsightState) -> InsightState:
    """
    Node: Validate that analysis meets quality requirements.
    
    Checks for:
    - Has significance section
    - Has context or implications
    - Minimum length (>200 chars)
    """
    logger.info(f"✓ [validate_analysis_node] Validating analysis for news_item={state['news_item_id']}")
    
    analysis = state.get('analysis', '')
    
    # Basic validation checks
    has_significance = '## Significance' in analysis or '## SIGNIFICANCE' in analysis
    has_context = '## Context' in analysis or '## CONTEXT' in analysis or '## Historical Context' in analysis
    has_implications = '## Implications' in analysis or '## IMPLICATIONS' in analysis
    has_minimum_length = len(analysis) > 200
    
    # Valid if has significance and (context or implications) and minimum length
    is_valid = has_significance and (has_context or has_implications) and has_minimum_length
    
    state['analysis_valid'] = is_valid
    
    if is_valid:
        logger.info(
            f"✅ [validate_analysis_node] Validation passed: "
            f"significance={has_significance}, context={has_context}, "
            f"implications={has_implications}, length={len(analysis)}"
        )
    else:
        logger.warning(
            f"⚠️ [validate_analysis_node] Validation failed: "
            f"significance={has_significance}, context={has_context}, "
            f"implications={has_implications}, length={len(analysis)}"
        )
    
    return state


async def finalize_node(state: InsightState) -> InsightState:
    """
    Node: Finalize workflow by combining results.
    
    Combines extracted_data + analysis into full_text.
    """
    logger.info(f"📝 [finalize_node] Finalizing insight for news_item={state['news_item_id']}")
    
    # Combine extraction and analysis
    full_text = f"{state['extracted_data']}\n\n{state['analysis']}"
    
    state['full_text'] = full_text
    state['success'] = True
    
    logger.info(
        f"✅ [finalize_node] Workflow complete: "
        f"total_length={len(full_text)} chars, "
        f"total_tokens={state['extraction_tokens'] + state['analysis_tokens']}, "
        f"provider={state['provider_used']}"
    )
    
    return state


async def error_node(state: InsightState) -> InsightState:
    """
    Node: Handle workflow failure.
    
    Logs error and marks workflow as failed.
    """
    logger.error(
        f"❌ [error_node] Workflow failed for news_item={state['news_item_id']}: "
        f"error_step={state.get('error_step')}, error={state.get('error')}"
    )
    
    state['success'] = False
    
    return state


# ============================================================================
# Conditional Edges (Routing Logic)
# ============================================================================

def should_retry_extraction(state: InsightState) -> Literal["retry", "continue", "fail"]:
    """
    Decide what to do after extraction validation.
    
    Returns:
        - "retry": Try extraction again (if attempts < max)
        - "continue": Proceed to analysis (if valid)
        - "fail": Give up (if max attempts reached)
    """
    if state['extraction_valid']:
        return "continue"
    
    if state['extraction_attempts'] < state['max_attempts']:
        logger.info(f"🔄 Retrying extraction (attempt {state['extraction_attempts']}/{state['max_attempts']})")
        return "retry"
    
    logger.error(f"❌ Max extraction attempts reached ({state['max_attempts']})")
    return "fail"


def should_retry_analysis(state: InsightState) -> Literal["retry", "continue", "fail"]:
    """
    Decide what to do after analysis validation.
    
    Returns:
        - "retry": Try analysis again (if attempts < max)
        - "continue": Proceed to finalize (if valid)
        - "fail": Give up (if max attempts reached)
    """
    if state['analysis_valid']:
        return "continue"
    
    if state['analysis_attempts'] < state['max_attempts']:
        logger.info(f"🔄 Retrying analysis (attempt {state['analysis_attempts']}/{state['max_attempts']})")
        return "retry"
    
    logger.error(f"❌ Max analysis attempts reached ({state['max_attempts']})")
    return "fail"


# ============================================================================
# Graph Construction
# ============================================================================

def create_insights_graph() -> StateGraph:
    """
    Create the insights generation workflow graph.
    
    Flow:
        START → extract → validate_extraction
                              ↓ (retry if needed)
                           analyze → validate_analysis
                              ↓ (retry if needed)
                           finalize → END
                              ↓ (on error)
                            error → END
    
    Returns:
        StateGraph configured with nodes and edges
    """
    # Create graph
    graph = StateGraph(InsightState)
    
    # Add nodes
    graph.add_node("extract", extract_node)
    graph.add_node("validate_extraction", validate_extraction_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("validate_analysis", validate_analysis_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("error", error_node)
    
    # Set entry point
    graph.set_entry_point("extract")
    
    # Add edges
    # extract → validate_extraction
    graph.add_edge("extract", "validate_extraction")
    
    # validate_extraction → (conditional)
    graph.add_conditional_edges(
        "validate_extraction",
        should_retry_extraction,
        {
            "retry": "extract",      # Try extraction again
            "continue": "analyze",   # Proceed to analysis
            "fail": "error"          # Give up
        }
    )
    
    # analyze → validate_analysis
    graph.add_edge("analyze", "validate_analysis")
    
    # validate_analysis → (conditional)
    graph.add_conditional_edges(
        "validate_analysis",
        should_retry_analysis,
        {
            "retry": "analyze",      # Try analysis again
            "continue": "finalize",  # Proceed to finalize
            "fail": "error"          # Give up
        }
    )
    
    # finalize → END
    graph.add_edge("finalize", END)
    
    # error → END
    graph.add_edge("error", END)
    
    return graph


# ============================================================================
# Public API
# ============================================================================

async def run_insights_workflow(
    news_item_id: str,
    document_id: str,
    context: str,
    title: str,
    max_attempts: int = 3
) -> InsightState:
    """
    Run the complete insights generation workflow.
    
    Args:
        news_item_id: ID of news item
        document_id: ID of document
        context: Full text context for analysis
        title: Title of news article
        max_attempts: Maximum retry attempts per step (default: 3)
    
    Returns:
        Final InsightState with results or error
    
    Example:
        >>> result = await run_insights_workflow(
        ...     news_item_id="news_123",
        ...     document_id="doc_456",
        ...     context="News article text...",
        ...     title="Breaking News",
        ...     max_attempts=3
        ... )
        >>> if result['success']:
        ...     print(f"Insight: {result['full_text']}")
        ... else:
        ...     print(f"Failed: {result['error']}")
    """
    logger.info(
        f"🚀 Starting insights workflow: news_item={news_item_id}, "
        f"document={document_id}, max_attempts={max_attempts}"
    )
    
    # Initialize state
    initial_state: InsightState = {
        # Input
        'news_item_id': news_item_id,
        'document_id': document_id,
        'context': context,
        'title': title,
        
        # Outputs (to be filled)
        'extracted_data': None,
        'extraction_tokens': 0,
        'analysis': None,
        'analysis_tokens': 0,
        
        # Validation
        'extraction_valid': False,
        'analysis_valid': False,
        
        # Retry tracking
        'extraction_attempts': 0,
        'analysis_attempts': 0,
        'max_attempts': max_attempts,
        
        # Provider
        'provider_used': None,
        'model_used': None,
        
        # Final
        'full_text': None,
        'success': False,
        
        # Error
        'error': None,
        'error_step': None
    }
    
    # Create and compile graph
    graph = create_insights_graph()
    app = graph.compile()
    
    # Run workflow
    final_state = await app.ainvoke(initial_state)
    
    # Log result
    if final_state['success']:
        logger.info(
            f"✅ Workflow succeeded: "
            f"extraction_attempts={final_state['extraction_attempts']}, "
            f"analysis_attempts={final_state['analysis_attempts']}, "
            f"total_tokens={final_state['extraction_tokens'] + final_state['analysis_tokens']}"
        )
    else:
        logger.error(
            f"❌ Workflow failed: "
            f"error_step={final_state['error_step']}, "
            f"error={final_state['error']}"
        )
    
    return final_state


# ============================================================================
# Utilities
# ============================================================================

def _get_providers() -> List:
    """
    Get list of LLM providers in fallback order honoring runtime configuration.
    
    Preference order:
      1. Admin overrides from insights_pipeline_control (manual mode)
      2. Static LLM_PROVIDER + LLM_FALLBACK_PROVIDERS from config
    Providers without credenciales/config se omiten.
    """
    runtime_order: Optional[List[str]] = None
    runtime_ollama_model: Optional[str] = None
    if _ipc:
        try:
            runtime_order = _ipc.provider_order_for_rag()
        except Exception as exc:  # pragma: no cover - log y continuar
            logger.warning("insights_pipeline_control.provider_order_for_rag failed: %s", exc)
        try:
            runtime_ollama_model = _ipc.ollama_model_for_insights()
        except Exception as exc:  # pragma: no cover
            logger.warning("insights_pipeline_control.ollama_model_for_insights failed: %s", exc)
    order = runtime_order or get_llm_provider_order()
    
    normalized: List[str] = []
    for provider_name in order:
        name = (provider_name or "").strip().lower()
        if name in ("local", "ollama"):
            name = "ollama"
        if name and name not in normalized:
            normalized.append(name)
    
    providers: List = []
    for provider_name in normalized:
        if provider_name == "openai":
            if app_settings.OPENAI_API_KEY:
                try:
                    providers.append(OpenAIProvider())
                except ValueError as exc:
                    logger.warning("Skipping OpenAI provider: %s", exc)
            else:
                logger.info("Skipping OpenAI provider because OPENAI_API_KEY is not set")
        elif provider_name == "ollama":
            model_override = runtime_ollama_model or app_settings.OLLAMA_LLM_MODEL or app_settings.LLM_MODEL
            try:
                providers.append(OllamaProvider(model=model_override) if model_override else OllamaProvider())
            except Exception as exc:
                logger.warning("Skipping Ollama provider: %s", exc)
        elif provider_name == "perplexity":
            logger.warning("Perplexity provider not implemented yet in LangGraph workflow - skipping")
        else:
            logger.warning("Unknown LLM provider '%s' - skipping", provider_name)
    
    if not providers:
        logger.warning("No configured LLM providers available for insights workflow - defaulting to Ollama")
        providers.append(OllamaProvider())
    
    return providers
