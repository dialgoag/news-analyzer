"""
RAG Pipeline - LangChain + Qdrant Integration
Orchestrates: Retrieval + LLM Generation with Source Attribution
"""

import json
import logging
import os
import random
import time
from typing import List, Tuple, Dict, Optional
import requests as _requests
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)


def _format_bytes(n: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _format_eta(seconds: float) -> str:
    """Format seconds into human-readable ETA."""
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = int(minutes // 60)
    mins = minutes % 60
    return f"{hours}h {mins}m"


def wait_for_ollama(base_url: str, timeout: int = 300):
    """
    Wait for Ollama server to be ready.

    Args:
        base_url: Ollama base URL (e.g. http://ollama:11434)
        timeout: Maximum seconds to wait
    """
    logger.info(f"⏳ Waiting for Ollama at {base_url} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = _requests.get(f"{base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                logger.info(f"✅ Ollama is ready ({time.time() - start:.0f}s)")
                return
        except _requests.ConnectionError:
            pass
        except Exception as exc:
            logger.debug(f"Ollama not ready yet: {exc}")
        time.sleep(3)
    raise RuntimeError(
        f"Ollama not reachable at {base_url} after {timeout}s. "
        "Make sure the Ollama container is running."
    )


def ensure_model(base_url: str, model: str):
    """
    Check if a model is available in Ollama; if not, pull it with progress.

    Args:
        base_url: Ollama base URL
        model: Model name (e.g. qwen3:14b-q4_K_M)
    """
    base_url = base_url.rstrip("/")

    # Check existing models
    resp = _requests.get(f"{base_url}/api/tags", timeout=10)
    resp.raise_for_status()
    available = [m["name"] for m in resp.json().get("models", [])]

    # Ollama sometimes stores names with :latest suffix
    if model in available or f"{model}:latest" in available:
        logger.info(f"✅ Model '{model}' already available in Ollama")
        return

    # Model not found — pull it
    logger.info("=" * 70)
    logger.info(f"⬇️  Model '{model}' not found in Ollama — downloading now")
    logger.info(f"   This may take several minutes depending on your connection speed")
    logger.info("=" * 70)

    pull_resp = _requests.post(
        f"{base_url}/api/pull",
        json={"name": model, "stream": True},
        stream=True,
        timeout=3600,  # 1 hour timeout for large models
    )
    pull_resp.raise_for_status()

    start_time = time.time()
    last_log_time = 0.0
    last_status = ""

    for line in pull_resp.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        status = data.get("status", "")
        total = data.get("total", 0)
        completed = data.get("completed", 0)

        # Show download progress every 5 seconds to avoid log spam
        now = time.time()
        if total and completed:
            pct = (completed / total) * 100
            elapsed = now - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            remaining = total - completed
            eta = remaining / speed if speed > 0 else 0

            if now - last_log_time >= 5 or pct >= 100:
                logger.info(
                    f"   ⬇️  {status}: {pct:.1f}% "
                    f"({_format_bytes(completed)}/{_format_bytes(total)}) "
                    f"- Speed: {_format_bytes(speed)}/s "
                    f"- ETA: {_format_eta(eta)}"
                )
                last_log_time = now
        elif status and status != last_status:
            logger.info(f"   📦 {status}")
            last_status = status

        # Check for errors
        if "error" in data:
            raise RuntimeError(f"Ollama pull failed: {data['error']}")

    elapsed_total = time.time() - start_time
    logger.info("=" * 70)
    logger.info(
        f"✅ Model '{model}' downloaded successfully "
        f"(took {_format_eta(elapsed_total)})"
    )
    logger.info("=" * 70)


class RateLimitError(Exception):
    """Raised when OpenAI returns 429 after quick retries are exhausted.
    This is NOT a real error — the item should be re-enqueued as pending."""

    def __init__(self, message: str, retry_after: float = 0, rate_snapshot: Optional[Dict] = None, request_id: Optional[str] = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.rate_snapshot = rate_snapshot or {}
        self.request_id = request_id


class OpenAIChatClient:
    """OpenAI-compatible API client. Works with OpenAI, Azure, Perplexity, and compatible APIs."""

    QUICK_RETRIES = int(os.getenv("LLM_429_QUICK_RETRIES", "3"))
    QUICK_RETRY_BASE_WAIT = float(os.getenv("LLM_429_BASE_WAIT", "5.0"))
    WARN_REQUEST_THRESHOLD = int(os.getenv("LLM_RATELIMIT_WARN_REQUESTS", "5"))
    WARN_TOKEN_THRESHOLD = int(os.getenv("LLM_RATELIMIT_WARN_TOKENS", "5000"))
    LOG_SUCCESS_LIMITS = os.getenv("LLM_LOG_RATE_LIMIT_SUCCESS", "false").strip().lower() in ("1", "true", "yes")

    def __init__(self, model: str, api_key: str, temperature: float = 0.0,
                 timeout: int = 120, base_url: str = "https://api.openai.com/v1",
                 chat_path: str = "chat/completions"):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout
        self.base_url = base_url.rstrip("/")
        self.chat_path = chat_path.lstrip("/")
        self._session = _requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        self._last_limit_warning = 0.0

    def __call__(self, prompt: str) -> str:
        return self.invoke(prompt)

    def _safe_int(self, value: Optional[str]) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _rate_limit_snapshot(self, resp: _requests.Response) -> Optional[Dict]:
        if not resp or not resp.headers:
            return None
        headers = resp.headers
        snapshot = {
            "limit_requests": self._safe_int(headers.get("x-ratelimit-limit-requests")),
            "remaining_requests": self._safe_int(headers.get("x-ratelimit-remaining-requests")),
            "reset_requests": headers.get("x-ratelimit-reset-requests"),
            "limit_tokens": self._safe_int(headers.get("x-ratelimit-limit-tokens")),
            "remaining_tokens": self._safe_int(headers.get("x-ratelimit-remaining-tokens")),
            "reset_tokens": headers.get("x-ratelimit-reset-tokens"),
            "request_id": headers.get("x-request-id"),
        }
        if all(value is None for value in snapshot.values()):
            return None
        return snapshot

    def _log_rate_limit(self, snapshot: Optional[Dict], *, status: str, attempt: int = 0):
        if not snapshot:
            return
        remaining_req = snapshot.get("remaining_requests")
        remaining_tokens = snapshot.get("remaining_tokens")
        should_warn = status == "429"
        warn_reasons = []
        if remaining_req is not None and remaining_req <= self.WARN_REQUEST_THRESHOLD:
            should_warn = True
            warn_reasons.append(f"requests≈{remaining_req}")
        if remaining_tokens is not None and remaining_tokens <= self.WARN_TOKEN_THRESHOLD:
            should_warn = True
            warn_reasons.append(f"tokens≈{remaining_tokens}")

        msg = (
            f"LLM rate state ({status}) — "
            f"req {remaining_req}/{snapshot.get('limit_requests')} "
            f"tok {remaining_tokens}/{snapshot.get('limit_tokens')} "
            f"reset_req={snapshot.get('reset_requests')} "
            f"reset_tok={snapshot.get('reset_tokens')} "
            f"req_id={snapshot.get('request_id') or 'n/a'} "
            f"attempt={attempt}"
        )

        if should_warn:
            now = time.time()
            # Avoid spamming warnings if multiple workers hit the same threshold simultaneously.
            if now - self._last_limit_warning > 5:
                logger.warning(msg + (f" (near limit: {', '.join(warn_reasons)})" if warn_reasons else ""))
                self._last_limit_warning = now
        elif self.LOG_SUCCESS_LIMITS:
            logger.info(msg)

    def invoke(self, prompt: str) -> str:
        retry_after = 0.0
        for attempt in range(1 + self.QUICK_RETRIES):
            resp = self._session.post(
                f"{self.base_url}/{self.chat_path}",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                },
                timeout=self.timeout,
            )
            snapshot = self._rate_limit_snapshot(resp)

            if resp.status_code != 429:
                resp.raise_for_status()
                self._log_rate_limit(snapshot, status="success", attempt=attempt)
                return resp.json()["choices"][0]["message"]["content"]

            # 429: use Retry-After header if present, else exponential backoff
            self._log_rate_limit(snapshot, status="429", attempt=attempt + 1)
            retry_after = float(resp.headers.get("Retry-After", 0))
            if retry_after <= 0:
                retry_after = self.QUICK_RETRY_BASE_WAIT * (2 ** attempt) + random.uniform(0, 2)
            else:
                retry_after = min(retry_after, 120)  # cap at 2 min
            if attempt < self.QUICK_RETRIES:
                logger.warning(
                    f"LLM 429 — retry {attempt + 1}/{self.QUICK_RETRIES} in {retry_after:.1f}s"
                )
                time.sleep(retry_after)
            else:
                break

        raise RateLimitError(
            f"LLM 429 after {1 + self.QUICK_RETRIES} attempts",
            retry_after=retry_after,
            rate_snapshot=snapshot,
            request_id=snapshot.get("request_id") if snapshot else None,
        )


class OllamaChatDirect:
    """Direct Ollama /api/chat client with think=false support."""

    def __init__(self, model: str, base_url: str, temperature: float = 0.0,
                 timeout: int = 120):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout
        self._session = _requests.Session()

    def __call__(self, prompt: str) -> str:
        return self.invoke(prompt)

    def invoke(self, prompt: str) -> str:
        resp = self._session.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"temperature": self.temperature},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class RAGPipeline:
    """
    Main RAG Pipeline with Source Attribution
    - Manages retrieval from Qdrant
    - Generates responses with LLM
    - Returns sources with relevance scoring
    - Orchestrates everything with LangChain
    """
    
    def __init__(
        self,
        qdrant_connector,
        embeddings_service,
        llm_model: str = "mistral",
        ollama_base_url: str = "http://ollama:11434",
        chunk_size: int = 2000,
        chunk_overlap: int = 400,
        relevance_threshold: float = 0.30,
        llm_provider: str = "ollama",
        openai_api_key: str = "",
    ):
        self.qdrant_connector = qdrant_connector
        self.embeddings_service = embeddings_service
        self.llm_model = llm_model
        self.llm_provider = llm_provider
        self.relevance_threshold = relevance_threshold
        self._ollama_base_url = ollama_base_url.rstrip("/")
        self._openai_api_key = openai_api_key or ""

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )

        if llm_provider == "openai":
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            self.llm = OpenAIChatClient(
                model=self.llm_model,
                api_key=openai_api_key,
                temperature=0.0,
                base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1"),
            )
            logger.info(f"🔑 Using OpenAI API (model: {llm_model})")
        elif llm_provider == "perplexity":
            perplexity_key = os.getenv("PERPLEXITY_API_KEY", openai_api_key)
            if not perplexity_key:
                raise ValueError("PERPLEXITY_API_KEY is required when LLM_PROVIDER=perplexity")
            self.llm = OpenAIChatClient(
                model=self.llm_model or "sonar-pro",
                api_key=perplexity_key,
                temperature=0.0,
                base_url="https://api.perplexity.ai",
                chat_path="v1/sonar",
            )
            logger.info(f"🔍 Using Perplexity API (model: {llm_model or 'sonar-pro'})")
        else:
            self.llm = OllamaChatDirect(
                model=self.llm_model,
                base_url=ollama_base_url,
                temperature=0.0,
            )
            logger.info(f"🦙 Using Ollama (model: {llm_model})")

        self.qa_prompt = PromptTemplate(
            template=self._get_prompt_template(),
            input_variables=["context", "question"]
        )

        # Build LLM chain for fallback (primary + fallbacks on 429)
        self.llm_chain = self._build_llm_chain(
            llm_provider=llm_provider,
            llm_model=llm_model,
            ollama_base_url=ollama_base_url,
            openai_api_key=openai_api_key,
        )
        logger.info(f"✅ RAG Pipeline initialized (provider: {llm_provider}, model: {llm_model}, fallbacks: {[n for n, _ in self.llm_chain[1:]]})")

    def _build_llm_chain(
        self,
        llm_provider: str,
        llm_model: str,
        ollama_base_url: str,
        openai_api_key: str,
    ) -> List[Tuple[str, object]]:
        """Build [(provider_name, llm_instance), ...] for primary + fallbacks."""
        chain = []
        fallback_str = os.getenv("LLM_FALLBACK_PROVIDERS", "").strip().lower()
        fallbacks = [p.strip() for p in fallback_str.split(",") if p.strip()] if fallback_str else []

        def add_openai():
            if openai_api_key:
                chain.append(("openai", OpenAIChatClient(
                    model=llm_model,
                    api_key=openai_api_key,
                    temperature=0.0,
                    base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1"),
                )))

        def add_perplexity():
            key = os.getenv("PERPLEXITY_API_KEY", openai_api_key)
            if key:
                pplx_model = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
                chain.append(("perplexity", OpenAIChatClient(
                    model=pplx_model,
                    api_key=key,
                    temperature=0.0,
                    base_url="https://api.perplexity.ai",
                    chat_path="v1/sonar",
                )))

        def add_ollama():
            chain.append(("ollama", OllamaChatDirect(
                model=llm_model,
                base_url=ollama_base_url,
                temperature=0.0,
            )))

        # Primary
        if llm_provider == "openai":
            add_openai()
        elif llm_provider == "perplexity":
            add_perplexity()
        else:
            add_ollama()

        # Fallbacks (only add if not already primary)
        for fb in fallbacks:
            if fb == "openai" and not any(n == "openai" for n, _ in chain):
                add_openai()
            elif fb == "perplexity" and not any(n == "perplexity" for n, _ in chain):
                add_perplexity()
            elif fb == "ollama" and not any(n == "ollama" for n, _ in chain):
                add_ollama()

        return chain if chain else [(llm_provider, self.llm)]

    def _effective_insights_ollama_model(self, runtime_override: Optional[str]) -> str:
        """Model name for Ollama in insights: UI/runtime, then OLLAMA_LLM_MODEL, else LLM_MODEL if primary is ollama, else mistral."""
        o = (runtime_override or "").strip()
        if o:
            return o
        alt = os.getenv("OLLAMA_LLM_MODEL", "").strip()
        if alt:
            return alt
        if (self.llm_provider or "").lower() in ("ollama", "local"):
            return (self.llm_model or "").strip() or "mistral"
        return "mistral"

    def _build_insights_chain_ordered(
        self,
        ordered_providers: List[str],
        insights_ollama_model: Optional[str] = None,
    ) -> List[Tuple[str, object]]:
        """Build LLM chain for insights in explicit order (openai / perplexity / ollama). Skips missing credentials."""
        chain: List[Tuple[str, object]] = []
        llm_model = self.llm_model
        ollama_base_url = self._ollama_base_url
        openai_api_key = self._openai_api_key
        ollama_name = self._effective_insights_ollama_model(insights_ollama_model)

        def add_openai():
            if openai_api_key:
                chain.append(("openai", OpenAIChatClient(
                    model=llm_model,
                    api_key=openai_api_key,
                    temperature=0.0,
                    base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1"),
                )))

        def add_perplexity():
            key = os.getenv("PERPLEXITY_API_KEY", openai_api_key)
            if key:
                pplx_model = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
                chain.append(("perplexity", OpenAIChatClient(
                    model=pplx_model,
                    api_key=key,
                    temperature=0.0,
                    base_url="https://api.perplexity.ai",
                    chat_path="v1/sonar",
                )))

        def add_ollama():
            chain.append(("ollama", OllamaChatDirect(
                model=ollama_name,
                base_url=ollama_base_url,
                temperature=0.0,
            )))

        for name in ordered_providers:
            n = (name or "").strip().lower()
            if n in ("local", "ollama"):
                n = "ollama"
            if n == "openai":
                add_openai()
            elif n == "perplexity":
                add_perplexity()
            elif n == "ollama":
                add_ollama()
        return chain

    def _get_prompt_template(self) -> str:
        """Optimized template for better extraction and accuracy"""
        return """You are a precise research assistant. Your task is to find and extract specific information from the provided documents.

INSTRUCTIONS:
1. Read ALL document chunks carefully - information may be spread across multiple chunks
2. Extract and combine relevant information from different chunks when needed
3. Quote specific names, dates, numbers, and facts exactly as they appear
4. If you find partial information, provide what you found and note what's missing
5. Only say "I don't have this information" if NONE of the chunks contain relevant data

{history_section}

DOCUMENTS:
{context}

QUESTION: {question}

ANSWER (be specific, quote facts from documents):"""
    
    
    def _format_history(self, history: List[Dict] = None) -> str:
        """
        Format conversational history - ONLY QUESTIONS

        Anti-hallucination fix: Include only user questions,
        NOT assistant responses (which could be wrong
        and create hallucination loops)
        """
        if not history or len(history) == 0:
            return ""

        history_text = "USER'S PREVIOUS QUESTIONS (for context):\n"
        for i, msg in enumerate(history[-5:], 1):  # Last 5 exchanges for better context
            user_msg = msg.get("user", "")
            if user_msg:  # Only if there's actually a question
                history_text += f"{i}. {user_msg}\n"

        return history_text + "\n"
    
    
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 2000,
        overlap: int = 400
    ) -> List[str]:
        """
        Split text into chunks

        Args:
            text: Text to split
            chunk_size: Maximum chunk size
            overlap: Overlap between chunks

        Returns:
            List of chunks
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap
        )
        chunks = splitter.split_text(text)
        logger.info(f"📊 Text split into {len(chunks)} chunks (size={chunk_size}, overlap={overlap})")
        return chunks
    
    
    def index_chunks(
        self,
        chunks: List[str],
        document_id: str,
        filename: str,
        document_type: str = "GENERIC_DOCUMENT",
        structured_fields: dict = None,
        news_item_id: Optional[str] = None,
        news_title: Optional[str] = None,
        news_item_index: Optional[int] = None,
    ):
        if structured_fields is None:
            structured_fields = {}

        """
        Index chunks on Qdrant
        1. Generate embeddings for each chunk
        2. Save on Qdrant with complete metadata

        Args:
            chunks: List of text chunks
            document_id: Unique document ID
            filename: Original file name
        """
        try:
            if not chunks:
                logger.warning(f"⚠️  No chunks to index for {filename}")
                return

            logger.info(f"📇 Indexing {len(chunks)} chunks for '{filename}'")
            
            # 1. Generate embeddings
            logger.debug(f"  1/2 Generating embeddings...")
            embeddings = self.embeddings_service.embed_texts(chunks)

            if not embeddings:
                logger.error(f"❌ Embedding service returned empty list!")
                return

            logger.info(f"      ✅ {len(embeddings)} embeddings generated")

            metadatas = []
            for i, chunk in enumerate(chunks):
                md = {
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": i,
                    "text": chunk,
                    "chunk_size": len(chunk),
                    "document_type": document_type,
                    "structured_fields": str(structured_fields),
                }
                if news_item_id is not None:
                    md["news_item_id"] = news_item_id
                if news_title is not None:
                    md["news_title"] = news_title
                if news_item_index is not None:
                    md["news_item_index"] = int(news_item_index)
                metadatas.append(md)

            logger.debug(f"  2/2 Saving on Qdrant...")

            # 3. Save on Qdrant
            self.qdrant_connector.insert_vectors(
                vectors=embeddings,
                metadatas=metadatas
            )

            logger.info(f"✅ Indexing completed for '{filename}' ({len(chunks)} chunks)")

        except Exception as e:
            logger.error(f"❌ Indexing error: {str(e)}")
            raise

    def index_chunk_records(self, records: List[Dict]):
        """Index already-built chunk records (each record must include 'text' and source metadata).
        For large docs (>100 chunks), processes in batches to avoid timeout."""
        try:
            if not records:
                return
            texts = [r.get("text", "") for r in records]
            if not any(texts):
                logger.warning("⚠️  index_chunk_records: all texts empty")
                return
            import os
            batch_limit = int(os.getenv("INDEXING_BATCH_SIZE", "100"))  # Smaller = less timeout risk
            total = len(records)
            logger.info(f"📇 Indexing {total} chunk record(s)" + (f" (batches of {batch_limit})" if total > batch_limit else ""))
            for start in range(0, total, batch_limit):
                batch = records[start:start + batch_limit]
                batch_texts = [r.get("text", "") for r in batch]
                embeddings = self.embeddings_service.embed_texts(batch_texts)
                if not embeddings:
                    raise RuntimeError("Embedding service returned empty list")
                self.qdrant_connector.insert_vectors(vectors=embeddings, metadatas=batch)
                if total > batch_limit:
                    logger.info(f"   ✓ Batch {start // batch_limit + 1}: {len(batch)} chunks")
            logger.info("✅ Chunk records indexed")
        except Exception as e:
            logger.error(f"❌ index_chunk_records error: {str(e)}")
            raise
    
    
    def query(
        self,
        query: str,
        top_k: int = 15,
        temperature: float = 0.7,
        history: List[Dict] = None
    ) -> Tuple[str, List[Dict]]:
        """
        Execute complete RAG query
        1. Retrieval from Qdrant with relevance scoring
        2. LLM generation
        3. Return answer + filtered sources

        Args:
            query: Query text
            top_k: Maximum number of documents to retrieve
            temperature: LLM temperature (0.0-1.0)

        Returns:
            Tuple (answer_text, list_of_sources)
        """
        try:
            logger.info(f"❓ RAG Query: '{query}' (top_k={top_k}, threshold={self.relevance_threshold})")
            
            # 1. Retrieval from Qdrant
            logger.debug("  1/3 Retrieval from Qdrant...")
            query_embedding = self.embeddings_service.embed_text(query, is_query=True)

            if query_embedding is None:
                logger.error("❌ Query embedding is None!")
                return "Error during query processing", []

            retrieved_docs = self.qdrant_connector.search(
                query_vector=query_embedding,
                top_k=top_k,
                score_threshold=self.relevance_threshold  # ✅ FIX: Filter upstream in Qdrant
            )

            logger.info(f"      ✅ Retrieved {len(retrieved_docs)} documents (already filtered by Qdrant with threshold={self.relevance_threshold})")

            # Detailed log of retrieved documents
            if retrieved_docs:
                logger.info("      📊 Similarity scores:")
                for i, doc in enumerate(retrieved_docs, 1):
                    filename = doc["metadata"].get("filename", "unknown")
                    similarity = doc.get("similarity", 0)
                    logger.info(f"         {i}. {filename}: {similarity:.3f} ({similarity:.1%})")
            
            if not retrieved_docs:
                logger.warning("⚠️  Qdrant returned no results above threshold!")
                logger.warning(f"⚠️  Possible causes: threshold too high ({self.relevance_threshold}) or non-relevant documents")
                return "I haven't found relevant documents to answer this question.", []

            # 🎯 Keep more documents for complex queries - less aggressive filtering
            # Only filter if there's a VERY clear winner with huge gap
            if len(retrieved_docs) > 1:
                first_score = retrieved_docs[0].get("similarity", 0)
                second_score = retrieved_docs[1].get("similarity", 0)
                gap = first_score - second_score

                # Only filter if gap is very large (>0.15) AND top score is high (>0.65)
                # This preserves more context for complex questions
                if first_score >= 0.65 and gap > 0.15:
                    logger.info(f"      🎯 Gap filtering activated: top_score={first_score:.3f}, gap={gap:.3f}")
                    relevant_docs = [doc for doc in retrieved_docs if doc.get("similarity", 0) >= 0.40]
                    logger.info(f"      ✅ Gap filtering: {len(retrieved_docs)} → {len(relevant_docs)} documents (filtered < 0.40)")

                    # Safety check: keep at least top 3 documents
                    if len(relevant_docs) < 3:
                        logger.warning("⚠️  Gap filtering too aggressive, keeping top 3")
                        relevant_docs = retrieved_docs[:3]
                else:
                    relevant_docs = retrieved_docs
                    logger.info(f"      ✅ Keeping all {len(relevant_docs)} documents for comprehensive context")
            else:
                relevant_docs = retrieved_docs
                logger.info(f"      ✅ {len(relevant_docs)} relevant document")
            
            # 3. Build context from search
            logger.debug("  2/3 Creating context...")
            context_parts = []
            for i, doc in enumerate(relevant_docs, 1):
                text = doc["metadata"].get("text", "")
                filename = doc["metadata"].get("filename", "unknown")
                similarity = doc.get("similarity", 0)

                context_parts.append(
                    f"[{i}] ({filename} - relevance: {similarity:.2%})\n{text}"
                )

            context = "\n\n---\n\n".join(context_parts)
            logger.debug(f"      Context length: {len(context)} chars")

            # 4. LLM Generation
            logger.debug("  3/3 LLM Generation...")

            # Format conversational history
            history_section = self._format_history(history)

            prompt = self.qa_prompt.format(
                history_section=history_section,
                context=context,
                question=query
            )

            logger.debug(f"      Prompt length: {len(prompt)} chars")

            # Call LLM
            answer = self.llm(prompt)
            logger.info(f"      ✅ Response generated ({len(answer)} characters)")

            # 5. Format sources - DEDUPLICATED per document
            logger.debug("  Formatting sources...")
            sources_dict = {}  # Use dict for deduplication

            for doc in relevant_docs:
                doc_id = doc["metadata"].get("document_id", "unknown")
                filename = doc["metadata"].get("filename", "unknown")
                similarity = doc.get("similarity", 0)

                # Use the document with highest similarity
                if doc_id not in sources_dict or similarity > sources_dict[doc_id]["similarity_score"]:
                    sources_dict[doc_id] = {
                        "filename": filename,
                        "document_id": doc_id,
                        "similarity_score": round(similarity, 3),
                        "chunk_index": doc["metadata"].get("chunk_index", 0),
                        "text": doc["metadata"].get("text", "")
                    }

            sources = list(sources_dict.values())
            # Sort by descending similarity
            sources.sort(key=lambda x: x["similarity_score"], reverse=True)

            logger.info(f"✅ Query completed - {len(sources)} unique sources returned")

            return answer, sources
            
        except Exception as e:
            logger.error(f"❌ Query error: {str(e)}", exc_info=True)
            raise

    def generate_report_from_context(self, context: str, report_date: str) -> str:
        """
        Generate a daily report (markdown) from pre-built context. Used for reporte diario by news_date.
        """
        prompt = f"""You are a news analyst. Based on the following document excerpts from news dated {report_date}, produce a short daily report in Markdown.

REQUIREMENTS:
- Summarize the main themes and topics covered.
- Note any clear editorial stances or postures when evident.
- Keep the report concise and structured with clear sections (e.g. ## Temas, ## Resumen, ## Posturas).
- Write in the same language as the source documents.
- Use only information from the provided context; do not invent facts.

DOCUMENT EXCERPTS (date: {report_date}):
---
{context}
---

DAILY REPORT (Markdown):"""
        return self.llm(prompt)

    def generate_weekly_report_from_context(self, context: str, week_start: str, week_end: str) -> str:
        """Generate a weekly report (markdown): themes across days, patterns, postures."""
        prompt = f"""You are a news analyst. Based on the following document excerpts from news between {week_start} and {week_end}, produce a weekly summary report in Markdown.

REQUIREMENTS:
- Identify themes that appeared on multiple days or evolved during the week.
- Note patterns: recurring topics, how themes developed, similarities across sources.
- Summarize editorial stances or postures when evident.
- Structure with sections (e.g. ## Temas de la semana, ## Patrones, ## Resumen por tema, ## Posturas).
- Write in the same language as the source documents. Use only information from the context.

DOCUMENT EXCERPTS (week {week_start} to {week_end}):
---
{context}
---

WEEKLY REPORT (Markdown):"""
        return self.llm(prompt)

    def generate_insights_from_context(self, context: str, filename: str) -> str:
        """Generate per-document insights/summary (markdown). Used for reporte por archivo."""
        prompt = f"""You are a news analyst. Based on the following document excerpts from "{filename}", produce a structured insights report in Markdown.

EXTRACT AND INCLUDE (use only information from the context; do not invent):

1. **Tema**: Main topic or theme of the news.
2. **Autor**: Who wrote it (if identifiable).
3. **Periódico/Fuente**: Newspaper or source (if identifiable).
4. **Postura**: Editorial stance or posture (neutral, critical, supportive, etc.).
5. **Resumen**: Brief summary of the content.
6. **Contexto IA**: What the AI can infer — verificado o no, relevante o no, sesgada o hechos.

Write in the same language as the source.

DOCUMENT EXCERPTS:
---
{context[:80000]}
---

INSIGHTS REPORT (Markdown):"""
        return self.llm(prompt)

    def generate_insights_with_fallback(
        self,
        context: str,
        label: str,
        provider_order: Optional[List[str]] = None,
        insights_ollama_model: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Generate insights trying each LLM in chain. On 429, try next. Returns (content, llm_source).

        If provider_order is set (e.g. from runtime admin UI), only those providers are tried in order.
        insights_ollama_model: runtime Ollama tag for insights (from admin UI); else env heuristics.
        """
        prompt = f"""You are a news analyst. Based on the following document excerpts from "{label}", produce a structured insights report in Markdown.

EXTRACT AND INCLUDE (use only information from the context; do not invent):

1. **Tema**: Main topic or theme of the news.
2. **Autor**: Who wrote it (if identifiable).
3. **Periódico/Fuente**: Newspaper or source (if identifiable).
4. **Postura**: Editorial stance or posture (neutral, critical, supportive, etc.).
5. **Resumen**: Brief summary of the content.
6. **Contexto IA**: What the AI can infer from the text — indicate:
   - Verificado o no (facts that can be verified vs. opinions/claims)
   - Relevante o no (relevance of the information)
   - Sesgada o hechos (biased narrative vs. factual reporting)

Write in the same language as the source. Use only information from the context.

DOCUMENT EXCERPTS:
---
{context[:80000]}
---

INSIGHTS REPORT (Markdown):"""
        chain = self.llm_chain
        if provider_order:
            custom = self._build_insights_chain_ordered(
                provider_order,
                insights_ollama_model=insights_ollama_model,
            )
            if custom:
                chain = custom
        elif insights_ollama_model:
            om = self._effective_insights_ollama_model(insights_ollama_model)
            rebuilt: List[Tuple[str, object]] = []
            for name, llm in self.llm_chain:
                if name == "ollama":
                    rebuilt.append(
                        (
                            name,
                            OllamaChatDirect(
                                model=om,
                                base_url=self._ollama_base_url,
                                temperature=0.0,
                            ),
                        )
                    )
                else:
                    rebuilt.append((name, llm))
            chain = rebuilt
        last_error = None
        for name, llm in chain:
            try:
                content = llm(prompt)
                return (content, name)
            except RateLimitError as e:
                last_error = e
                logger.warning(f"LLM {name} 429, trying fallback: {e}")
            except Exception as e:
                last_error = e
                logger.warning(f"LLM {name} failed: {e}, trying fallback")
        raise last_error or RuntimeError("No LLM in chain")

    def reindex_all_documents(self):
        """Reindex all documents (if needed)"""
        try:
            logger.info("📄 Reindexing all documents...")
            # Implementation depends on how you save the originals
            # This is a skeleton for future implementations
            logger.info("✅ Reindexing completed")
        except Exception as e:
            logger.error(f"❌ Reindexing error: {str(e)}")
            raise
