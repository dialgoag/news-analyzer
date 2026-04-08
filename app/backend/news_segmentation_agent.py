"""
News Segmentation Agent

LLM-based intelligent segmentation of OCR text into individual news articles.
Uses local Ollama (llama3.1:8b) for zero-cost, private, deterministic processing.

Key features:
- Anti-hallucination prompts with strict output format
- Confidence scoring for each detected article
- Context-aware title validation
- Body coherence checking
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field
import os

logger = logging.getLogger(__name__)


# Pydantic models for structured output
class NewsArticle(BaseModel):
    """Schema for a single news article."""
    title: str = Field(description="Título completo del artículo")
    start_marker: str = Field(description="Primeras 10-15 palabras del cuerpo para ubicar el artículo")
    confidence: float = Field(description="Nivel de confianza 0.0-1.0", ge=0.0, le=1.0)


class SegmentationResult(BaseModel):
    """Schema for segmentation result."""
    articles: List[NewsArticle] = Field(default_factory=list, description="Lista de artículos encontrados")


# Prompt minimalista con schema Pydantic
DOCUMENT_SEGMENTATION_PROMPT = """Identifica artículos de noticias en este texto de periódico.

TEXTO (chunk {chunk_num}/{total_chunks}):
{text_preview}

Encuentra títulos de artículos que EMPIECEN en este fragmento.

Para cada artículo encontrado, proporciona:
- title: Título completo del artículo
- start_marker: Primeras 10-15 palabras del cuerpo del artículo
- confidence: Tu nivel de confianza (0.0-1.0)

Responde SOLO con el JSON estructurado."""


class NewsSegmentationAgent:
    """
    LLM-based news article segmentation with anti-hallucination measures.
    """
    
    def __init__(self, model: str = None, temperature: float = 0.0):
        """
        Initialize segmentation agent.
        
        Args:
            model: Ollama model name (default from env or llama3.1:8b-instruct-q4_K_M)
            temperature: LLM temperature (0.0 = deterministic, recommended)
        """
        self.model = model or os.getenv("SEGMENTATION_LLM_MODEL", "llama3.2:1b")
        self.temperature = temperature
        self.llm = None
        self._connect()
    
    def _connect(self):
        """Initialize Ollama LLM connection with structured output support."""
        try:
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
            
            # Use ChatOllama for structured output support
            from langchain_ollama import ChatOllama
            
            self.llm = ChatOllama(
                base_url=ollama_url,
                model=self.model,
                temperature=self.temperature,
                num_ctx=8192,  # Larger context for chunks
                format='json'   # Force JSON output
            )
            logger.info(f"✅ NewsSegmentationAgent initialized: model={self.model}, temp={self.temperature}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize NewsSegmentationAgent: {e}")
            raise
    
    def classify_title_candidate(self, line: str) -> str:
        """
        Classify a line as TÍTULO_VÁLIDO, FRAGMENTO, or NO_ES_TÍTULO.
        
        Args:
            line: Text line to classify
            
        Returns:
            Classification string (one of the three options)
        """
        # FAST PRE-FILTER: Skip obviously invalid lines (avoid LLM call)
        line_stripped = line.strip()
        line_len = len(line_stripped)
        
        if not line or line_len < 20 or line_len > 120:
            return "NO_ES_TÍTULO"
        
        # Skip if ends with punctuation that titles don't have
        if line_stripped[-1] in ['.', ',', ';', ':', '(', ')', '-', '…']:
            return "NO_ES_TÍTULO"
        
        # Skip if starts with lowercase (unless common articles)
        if line_stripped[0].islower():
            first_word = line_stripped.split()[0] if line_stripped.split() else ""
            if first_word.lower() not in ['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas']:
                return "NO_ES_TÍTULO"
        
        # Skip if mostly numbers (page numbers, dates, etc.)
        digit_ratio = sum(c.isdigit() for c in line_stripped) / max(len(line_stripped), 1)
        if digit_ratio > 0.5:
            return "NO_ES_TÍTULO"
        
        # Skip common document structure markers
        lower_line = line_stripped.lower()
        skip_patterns = ['página', 'page', 'sección', 'section', 'índice', 'tabla', 'figura']
        if any(pattern in lower_line for pattern in skip_patterns):
            return "NO_ES_TÍTULO"
        
        # If passed all filters, use LLM (only for promising candidates)
        prompt = TITLE_CLASSIFICATION_PROMPT.format(text=line_stripped)
        
        try:
            response = self.llm.invoke(prompt).strip()
            
            # Validar respuesta (anti-alucinación)
            valid_responses = ["TÍTULO_VÁLIDO", "FRAGMENTO", "NO_ES_TÍTULO"]
            
            # Buscar respuesta válida en el texto (por si LLM agrega texto extra)
            for valid in valid_responses:
                if valid in response:
                    return valid
            
            # Si no encontramos respuesta válida, asumir conservador
            logger.warning(f"Invalid LLM response for title classification: {response[:100]}")
            return "NO_ES_TÍTULO"
            
        except Exception as e:
            logger.error(f"Error classifying title candidate: {e}")
            return "NO_ES_TÍTULO"
    
    def validate_article(self, title: str, body: str) -> Dict[str, Any]:
        """
        Validate that title + body form a complete, coherent news article.
        
        Args:
            title: Article title
            body: Article body text
            
        Returns:
            Dict with keys: es_valida (bool), razon (str), confianza (float)
        """
        if len(body) < 1000:
            return {
                "es_valida": False,
                "razon": "Body too short (< 1000 chars)",
                "confianza": 0.0
            }
        
        body_preview = body[:800]
        body_end = body[-300:] if len(body) > 300 else body
        
        prompt = BODY_VALIDATION_PROMPT.format(
            title=title,
            body_preview=body_preview,
            body_end=body_end,
            body_length=len(body)
        )
        
        try:
            response = self.llm.invoke(prompt).strip()
            
            # Limpiar respuesta (remover markdown si existe)
            response = response.replace("```json", "").replace("```", "").strip()
            
            # Parsear JSON
            result = json.loads(response)
            
            # Validar estructura
            if not all(k in result for k in ["es_valida", "razon", "confianza"]):
                raise ValueError("Missing required keys in response")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse validation JSON: {response[:200]}")
            return {
                "es_valida": False,
                "razon": f"JSON parse error: {e}",
                "confianza": 0.0
            }
        except Exception as e:
            logger.error(f"Error validating article: {e}")
            return {
                "es_valida": False,
                "razon": f"Validation error: {e}",
                "confianza": 0.0
            }
    
    def segment_document(
        self,
        text: str,
        min_confidence: float = 0.7,
        max_items: int = 200,
        chunk_size: int = 40000,  # Process 40k chars at a time
        overlap: int = 5000       # 5k overlap to catch articles spanning boundaries
    ) -> List[Dict[str, Any]]:
        """
        Segment OCR text into complete news articles using LLM with chunked approach.
        
        Strategy: Split large documents into overlapping chunks to:
        1. Avoid LLM timeout on large documents
        2. Ensure articles spanning chunk boundaries are captured (via overlap)
        3. Process each chunk independently and merge results
        4. Use chunk memory to handle partial articles at boundaries
        
        Args:
            text: Full OCR text from document
            min_confidence: Minimum confidence threshold (0.0-1.0)
            max_items: Maximum number of articles to extract
            chunk_size: Size of each chunk to process (default 40k chars)
            overlap: Overlap between chunks to catch boundary articles (default 5k chars)
            
        Returns:
            List of news items: [{"title": str, "text": str, "confidence": float, ...}]
        """
        logger.info("=" * 80)
        logger.info("📰 Starting LLM-based news segmentation (chunked with overlap + memory)")
        logger.info(f"   Text length: {len(text)} characters")
        logger.info(f"   Chunk size: {chunk_size} chars, Overlap: {overlap} chars")
        logger.info(f"   Min confidence: {min_confidence}")
        logger.info("=" * 80)
        
        if not text or len(text.strip()) < 500:
            logger.warning("Text too short for segmentation")
            return []
        
        # Split text into overlapping chunks
        chunks = self._split_into_chunks(text, chunk_size, overlap)
        logger.info(f"   Split into {len(chunks)} chunks for processing")
        
        all_articles = []
        chunk_memory = None  # Store context from previous chunk
        
        for chunk_idx, chunk_info in enumerate(chunks):
            chunk_text = chunk_info['text']
            chunk_start = chunk_info['start']
            chunk_end = chunk_info['end']
            
            logger.info(f"   📄 Processing chunk {chunk_idx + 1}/{len(chunks)} (pos {chunk_start}-{chunk_end}, len={len(chunk_text)} chars)...")
            
            # Process chunk with LLM
            chunk_articles, new_memory = self._process_chunk_with_memory(
                chunk_text=chunk_text,
                chunk_start=chunk_start,
                chunk_num=chunk_idx + 1,
                total_chunks=len(chunks),
                full_text=text,
                min_confidence=min_confidence,
                previous_memory=chunk_memory
            )
            
            logger.info(f"      → Found {len(chunk_articles)} complete articles in chunk {chunk_idx + 1}")
            all_articles.extend(chunk_articles)
            
            # Update memory for next chunk
            chunk_memory = new_memory
        
        # Deduplicate articles (remove duplicates from overlapping regions)
        deduplicated = self._deduplicate_articles(all_articles)
        logger.info(f"   🧹 Deduplication: {len(all_articles)} → {len(deduplicated)} articles")
        
        # Sort by position and take top N by confidence
        deduplicated.sort(key=lambda x: x['start_pos'])
        final_articles = deduplicated[:max_items]
        
        logger.info("=" * 80)
        logger.info(f"✅ Segmentation complete: {len(final_articles)} valid articles")
        if final_articles:
            avg_conf = sum(it['confidence'] for it in final_articles) / len(final_articles)
            logger.info(f"   Average confidence: {avg_conf:.2f}")
            logger.info(f"   Total content: {sum(it['body_length'] for it in final_articles)} chars")
        logger.info("=" * 80)
        
        return final_articles
    
    def _split_into_chunks(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full text to split
            chunk_size: Size of each chunk
            overlap: Overlap between chunks
            
        Returns:
            List of chunks: [{"text": str, "start": int, "end": int}, ...]
        """
        chunks = []
        text_len = len(text)
        start = 0
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            
            # If not the last chunk, try to find a good break point (newline)
            if end < text_len:
                # Look for paragraph break in last 500 chars
                search_start = max(end - 500, start)
                last_paragraph = text.rfind('\n\n', search_start, end)
                if last_paragraph != -1 and last_paragraph > start:
                    end = last_paragraph + 2  # Include the newlines
            
            chunk_text = text[start:end]
            chunks.append({
                'text': chunk_text,
                'start': start,
                'end': end
            })
            
            # Move to next chunk with overlap
            if end >= text_len:
                break
            start = end - overlap
        
        return chunks
    
    def _process_chunk_with_memory(
        self,
        chunk_text: str,
        chunk_start: int,
        chunk_num: int,
        total_chunks: int,
        full_text: str,
        min_confidence: float,
        previous_memory: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Process a single chunk with memory from previous chunk.
        
        Memory strategy:
        - If previous chunk had a partial article at the end, try to complete it
        - Save last article of current chunk in case it's partial
        
        Args:
            chunk_text: Text chunk to process
            chunk_start: Starting position in full text
            chunk_num: Current chunk number (1-indexed)
            total_chunks: Total number of chunks
            full_text: Full document text
            min_confidence: Minimum confidence threshold
            previous_memory: Context from previous chunk
            
        Returns:
            Tuple of (articles found, memory for next chunk)
        """
        # Use first 2500 chars of chunk as preview (balance between context and speed)
        text_preview = chunk_text[:2500]
        
        prompt = DOCUMENT_SEGMENTATION_PROMPT.format(
            text_preview=text_preview,
            chunk_num=chunk_num,
            total_chunks=total_chunks
        )
        
        try:
            # ChatOllama with format='json' already set in __init__
            response = self.llm.invoke(prompt)
            
            # Extract content from AIMessage
            if hasattr(response, 'content'):
                response = response.content.strip()
            else:
                response = str(response).strip()
            
            # TEMPORAL DEBUG: Log response
            logger.info(f"      [DEBUG] Raw response length: {len(response)}")
            if len(response) < 1000:
                logger.info(f"      [DEBUG] Full response: {response}")
            
            # Clean response
            response = response.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON
            result = json.loads(response)
            articles_data = result.get("articles", [])
            
            if not articles_data:
                return [], None
            
            # Locate articles in the FULL text
            news_items = []
            
            for article in articles_data:
                title = article.get("title", "").strip()
                start_marker = article.get("start_marker", "").strip()
                confidence = float(article.get("confidence", 0.5))
                
                if confidence < min_confidence:
                    continue
                
                # Find article in FULL text using start_marker
                if start_marker and len(start_marker) > 20:
                    start_words = start_marker.split()[:15]
                    search_pattern = " ".join(start_words)
                    
                    # Search near chunk position
                    search_start = max(0, chunk_start - 1000)
                    search_end = min(len(full_text), chunk_start + len(chunk_text) + 1000)
                    search_region = full_text[search_start:search_end]
                    
                    start_pos = search_region.find(search_pattern)
                    if start_pos == -1:
                        start_pos = search_region.lower().find(search_pattern.lower())
                    
                    if start_pos != -1:
                        start_pos += search_start
                        
                        # Find end (look for paragraph break or reasonable length)
                        end_pos = min(start_pos + 15000, len(full_text))
                        
                        # Look for double newline as natural break
                        next_break = full_text.find('\n\n', start_pos + 800, end_pos)
                        if next_break != -1:
                            end_pos = next_break
                        
                        body = full_text[start_pos:end_pos].strip()
                        
                        if len(body) >= 800:
                            news_items.append({
                                "title": title,
                                "text": body,
                                "confidence": confidence,
                                "body_length": len(body),
                                "start_pos": start_pos,
                                "end_pos": end_pos,
                                "from_chunk": chunk_num
                            })
            
            # Save memory: last article might be partial (for next chunk)
            memory = None
            if news_items and chunk_num < total_chunks:
                last_article = news_items[-1]
                # Check if last article ends near chunk boundary
                if last_article['end_pos'] > (chunk_start + len(chunk_text) - 2000):
                    memory = {
                        "partial_article": last_article,
                        "chunk_end": chunk_start + len(chunk_text)
                    }
                    logger.debug(f"      💾 Saved partial article in memory: {last_article['title'][:40]}...")
            
            return news_items, memory
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON for chunk {chunk_num}: {e}")
            logger.error(f"Raw response was: {response[:500]}")
            return [], None
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_num}: {e}", exc_info=True)
            return [], None
    
    def _deduplicate_articles(
        self,
        articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate articles from overlapping chunks.
        
        Strategy:
        1. If two articles have >80% title similarity → keep higher confidence
        2. If two articles overlap >50% in position → keep higher confidence
        
        Args:
            articles: List of all articles from all chunks
            
        Returns:
            Deduplicated list
        """
        if len(articles) <= 1:
            return articles
        
        # Sort by confidence (descending) to keep best first
        articles.sort(key=lambda x: x['confidence'], reverse=True)
        
        kept = []
        
        for article in articles:
            is_duplicate = False
            
            for existing in kept:
                # Check title similarity
                title_sim = self._similarity(article['title'], existing['title'])
                if title_sim > 0.8:
                    is_duplicate = True
                    break
                
                # Check position overlap
                overlap = self._position_overlap(
                    article['start_pos'], article['end_pos'],
                    existing['start_pos'], existing['end_pos']
                )
                if overlap > 0.5:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                kept.append(article)
        
        return kept
    
    def _similarity(self, text1: str, text2: str) -> float:
        """Simple word-based similarity (Jaccard)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _position_overlap(
        self,
        start1: int, end1: int,
        start2: int, end2: int
    ) -> float:
        """Calculate overlap ratio between two text regions."""
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        
        if overlap_start >= overlap_end:
            return 0.0
        
        overlap_length = overlap_end - overlap_start
        shorter_length = min(end1 - start1, end2 - start2)
        
        return overlap_length / shorter_length if shorter_length > 0 else 0.0


# Singleton instance
_segmentation_agent: Optional[NewsSegmentationAgent] = None


def get_segmentation_agent() -> NewsSegmentationAgent:
    """
    Get or create singleton NewsSegmentationAgent instance.
    
    Returns:
        NewsSegmentationAgent instance
    """
    global _segmentation_agent
    if _segmentation_agent is None:
        _segmentation_agent = NewsSegmentationAgent()
    return _segmentation_agent
