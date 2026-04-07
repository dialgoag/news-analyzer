"""
Query router — RAG query with conversational memory.

Uses `import app as app_module` for rag_pipeline and user_conversations in app.py.
"""
import logging
import traceback
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import app as app_module
from middleware import CurrentUser, get_current_user

from adapters.driving.api.v1.schemas.query_schemas import (
    QueryRequest,
    QueryResponse,
    SourceInfo,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/query", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Main query - Complete RAG Pipeline WITH CONVERSATIONAL MEMORY

    Requires: Authentication (all roles can make queries)

    Processes:
    1. Retrieve conversation history for the user
    2. Query embedding
    3. Retrieval from Qdrant
    4. LLM generation with historical context
    5. Save response in memory
    6. Return answer + sources
    """

    user_id = str(current_user.user_id)
    rag_pipeline = app_module.rag_pipeline
    user_conversations = app_module.user_conversations

    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="RAG Pipeline not initialized")

    try:
        start_time = datetime.now()

        if user_id not in user_conversations:
            user_conversations[user_id] = []

        conversation_history = user_conversations[user_id]

        logger.info("=" * 80)
        logger.info(f"❓ QUERY (user: {user_id}): '{request.query}'")
        logger.info(f"   top_k: {request.top_k}")
        logger.info(f"   temperature: {request.temperature}")
        logger.info(f"   History length: {len(conversation_history)} exchanges")
        logger.info("=" * 80)

        answer, sources = rag_pipeline.query(
            query=request.query,
            top_k=request.top_k,
            temperature=request.temperature,
            history=conversation_history,
        )

        conversation_history.append(
            {
                "user": request.query,
                "assistant": answer,
            }
        )

        if len(conversation_history) > 20:
            user_conversations[user_id] = conversation_history[-20:]

        processing_time = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"✅ QUERY COMPLETED in {processing_time:.2f}s")
        logger.info(f"   Answer length: {len(answer)} chars")
        logger.info(f"   Sources: {len(sources)}")
        for src in sources:
            logger.info(f"     - {src['filename']} (relevance: {src['similarity_score']:.2%})")
        logger.info(f"   Conversation saved ({len(user_conversations[user_id])} exchanges)")
        logger.info("=" * 80)

        return QueryResponse(
            answer=answer,
            sources=[SourceInfo(**src) for src in sources],
            processing_time=processing_time,
            num_sources=len(sources),
        )

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ QUERY ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))
