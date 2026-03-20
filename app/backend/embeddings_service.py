"""
Embeddings Service - Sentence-Transformers or Perplexity API
Generates embeddings for texts (queries and documents)
"""

import base64
import logging
import os
import time
from typing import List, Union
import numpy as np
import requests
from sentence_transformers import SentenceTransformer
import torch

logger = logging.getLogger(__name__)


class PerplexityEmbeddingsService:
    """
    Embeddings via Perplexity API (https://docs.perplexity.ai/docs/embeddings/quickstart).
    Models: pplx-embed-v1-0.6b (1024d), pplx-embed-v1-4b (2560d).
    Use dimensions=1024 for compatibility with existing Qdrant collections.
    """

    def __init__(self, model: str = "pplx-embed-v1-4b", api_key: str = None, dimensions: int = 1024):
        self.model = model
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY", "")
        self.dimensions = dimensions
        self.embedding_dim = dimensions
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        logger.info(f"✅ Perplexity Embeddings (model={model}, dim={dimensions})")

    def embed_text(self, text: str, is_query: bool = False) -> List[float]:
        result = self.embed_texts([text], is_query=is_query)
        return result[0] if result else []

    def embed_texts(self, texts: List[str], batch_size: int = None, is_query: bool = False) -> List[List[float]]:
        batch_size = batch_size or 32
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {
                "input": batch,
                "model": self.model,
                "dimensions": self.dimensions,
                "encoding_format": "base64_int8",
            }
            resp = self._session.post(
                "https://api.perplexity.ai/v1/embeddings",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            for obj in sorted(data.get("data", []), key=lambda x: x["index"]):
                b64 = obj.get("embedding", "")
                arr = np.frombuffer(base64.b64decode(b64), dtype=np.int8)
                vec = arr.astype(np.float32) / 127.0
                all_embeddings.append(vec.tolist())
        return all_embeddings

    def get_embedding_dimension(self) -> int:
        return self.embedding_dim


class EmbeddingsService:
    """
    Embeddings Service with Sentence-Transformers
    - Open-source models
    - Multilingual
    - GPU-accelerated with automatic memory management
    """

    # Available models with recommended batch sizes
    MODELS = {
        "all-MiniLM-L6-v2": {
            "description": "English, 22MB, fast",
            "lang": "en",
            "dim": 384,
            "gpu_batch_size": 32,
            "cpu_batch_size": 16
        },
        "multilingual-MiniLM-L6-v2": {
            "description": "Multilingual, 61MB",
            "lang": "multilingual",
            "dim": 384,
            "gpu_batch_size": 32,
            "cpu_batch_size": 16
        },
        "all-mpnet-base-v2": {
            "description": "English, high quality, 430MB",
            "lang": "en",
            "dim": 768,
            "gpu_batch_size": 16,
            "cpu_batch_size": 8
        },
        "multilingual-e5-large": {
            "description": "Multilingual, high quality, 1.3GB",
            "lang": "multilingual",
            "dim": 1024,
            "gpu_batch_size": 8,
            "cpu_batch_size": 4
        },
        "deepseek-ai/deepseek-coder-6.7b-base": {
            "description": "DeepSeek Coder, high performance for code, 13GB",
            "lang": "multilingual",
            "dim": 4096,
            "gpu_batch_size": 2,
            "cpu_batch_size": 1
        },
        "BAAI/bge-large-en-v1.5": {
            "description": "BGE Large English, SOTA performance, 1.3GB",
            "lang": "en",
            "dim": 1024,
            "gpu_batch_size": 8,
            "cpu_batch_size": 4
        },
        "BAAI/bge-m3": {
            "description": "BGE M3 Multilingual, SOTA, dense+sparse+colbert, 2.3GB",
            "lang": "multilingual",
            "dim": 1024,
            "gpu_batch_size": 4,  # Conservative for large model
            "cpu_batch_size": 4   # 2→4: ~2x faster indexing on CPU (was bottleneck)
        },
        "intfloat/e5-large-v2": {
            "description": "E5 Large v2, high performance multilingual, 1.3GB",
            "lang": "multilingual",
            "dim": 1024,
            "gpu_batch_size": 8,
            "cpu_batch_size": 4
        },
        "sentence-transformers/all-roberta-large-v1": {
            "description": "RoBERTa Large, high quality English, 1.3GB",
            "lang": "en",
            "dim": 1024,
            "gpu_batch_size": 8,
            "cpu_batch_size": 4
        }
    }

    # Time to wait before retrying GPU after fallback (seconds)
    GPU_RETRY_INTERVAL = 60
    
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = None,
    ):
        """
        Initialize Embeddings Service

        Args:
            model_name: Sentence-Transformers model name
            device: 'cuda' or 'cpu'. None = auto (EMBEDDING_DEVICE env or cuda if available)
        """
        import os
        env_device = os.getenv("EMBEDDING_DEVICE", "").lower()
        if device is None:
            device = env_device if env_device in ("cuda", "cpu") else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        self.device = device
        self.original_device = device  # Remember original device for retry
        self.last_fallback_time = 0  # Track when we fell back to CPU
        self.cuda_available = torch.cuda.is_available()

        if model_name not in self.MODELS:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(self.MODELS.keys())}")

        # Env override for batch size (indexing bottleneck)
        import os
        env_cpu = os.getenv("EMBEDDING_BATCH_SIZE_CPU")
        env_gpu = os.getenv("EMBEDDING_BATCH_SIZE_GPU")
        if env_cpu:
            self.MODELS[model_name]["cpu_batch_size"] = max(1, min(int(env_cpu), 32))
        if env_gpu:
            self.MODELS[model_name]["gpu_batch_size"] = max(1, min(int(env_gpu), 64))

        logger.info(f"Loading embeddings model: {model_name} (device: {device})...")

        try:
            self.model = SentenceTransformer(model_name, device=device)
            self.embedding_dim = self.MODELS[model_name]["dim"]

            # Get optimal batch size for this model
            model_config = self.MODELS[model_name]
            self.gpu_batch_size = model_config.get("gpu_batch_size", 8)
            self.cpu_batch_size = model_config.get("cpu_batch_size", 4)

            logger.info(f"✅ Model loaded (dim: {self.embedding_dim}, device: {device})")
            logger.info(f"   Batch sizes: GPU={self.gpu_batch_size}, CPU={self.cpu_batch_size}")

            if device == "cuda":
                self._log_gpu_memory("after model load")

        except Exception as e:
            logger.error(f"❌ Error loading model: {str(e)}")
            raise

    def _log_gpu_memory(self, context: str = ""):
        """Log current GPU memory usage"""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            logger.info(f"   GPU Memory ({context}): {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")

    def _clear_gpu_memory(self):
        """Aggressively clear GPU memory"""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

    def _maybe_retry_gpu(self):
        """Try to switch back to GPU if we fell back to CPU and enough time has passed"""
        if self.device == "cpu" and self.original_device == "cuda" and self.cuda_available:
            time_since_fallback = time.time() - self.last_fallback_time
            if time_since_fallback > self.GPU_RETRY_INTERVAL:
                logger.info(f"🔄 Attempting to restore GPU after {time_since_fallback:.0f}s on CPU...")
                try:
                    self._clear_gpu_memory()
                    del self.model
                    self.model = SentenceTransformer(self.model_name, device="cuda")
                    self.device = "cuda"
                    logger.info("✅ Successfully restored GPU!")
                    self._log_gpu_memory("after GPU restore")
                    return True
                except Exception as e:
                    logger.warning(f"⚠️ GPU restore failed: {e}")
                    self.model = SentenceTransformer(self.model_name, device="cpu")
                    self.last_fallback_time = time.time()
        return False
    
    
    def _instruction_prefix(self, text: str, is_query: bool) -> str:
        """Add instruction prefix for BGE/E5 models (improves retrieval quality)."""
        if not text or not text.strip():
            return text
        name = self.model_name.lower()
        if "bge" in name:
            return f"Represent this sentence for retrieving relevant passages: {text}"
        if "e5" in name or "intfloat" in name:
            prefix = "query: " if is_query else "passage: "
            return f"{prefix}{text}"
        return text

    def embed_text(self, text: str, is_query: bool = False) -> List[float]:
        """
        Generate embedding for single text.

        Args:
            text: Text to embed
            is_query: True for search queries, False for documents (BGE/E5 use different prefixes)
        """
        text = self._instruction_prefix(text, is_query)
        self._maybe_retry_gpu()
        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return embedding.tolist()
        except RuntimeError as e:
            error_str = str(e)
            # CUDA error - fallback to CPU
            if "CUDA" in error_str or "out of memory" in error_str.lower():
                logger.warning(f"⚠️ CUDA error in embed_text, falling back to CPU...")
                self._fallback_to_cpu()

                embedding = self.model.encode(
                    text,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
                return embedding.tolist()
            else:
                logger.error(f"❌ Error embedding text: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"❌ Error embedding text: {str(e)}")
            raise

    def _fallback_to_cpu(self):
        """Reload model on CPU as fallback when CUDA fails"""
        if self.device != "cpu":
            logger.warning("🔄 Reloading model on CPU due to CUDA errors...")
            logger.warning("   (Will retry GPU in 60 seconds)")
            del self.model
            self._clear_gpu_memory()
            self.model = SentenceTransformer(self.model_name, device="cpu")
            self.device = "cpu"
            self.last_fallback_time = time.time()
            logger.info("✅ Model reloaded on CPU successfully")

    def embed_texts(self, texts: List[str], batch_size: int = None, is_query: bool = False) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts
            batch_size: Batch size (auto-selected based on device if None)

        Returns:
            List of embeddings
        """
        # Try to restore GPU if we fell back to CPU
        self._maybe_retry_gpu()

        # Use optimal batch size for current device
        if batch_size is None:
            batch_size = self.gpu_batch_size if self.device == "cuda" else self.cpu_batch_size

        texts = [self._instruction_prefix(t, is_query) for t in texts]
        logger.info(f"📝 Embedding {len(texts)} texts (device: {self.device}, batch: {batch_size})")

        try:
            if self.device == "cuda":
                self._clear_gpu_memory()
                self._log_gpu_memory("before embedding")
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=True
            )

            # Clear GPU memory after processing
            if self.device == "cuda":
                self._clear_gpu_memory()
                self._log_gpu_memory("after embedding")

            logger.info(f"✅ Embedded {len(texts)} texts successfully")
            return embeddings.tolist()

        except RuntimeError as e:
            error_str = str(e)
            # CUDA error - fallback to CPU
            if "CUDA" in error_str or "out of memory" in error_str.lower():
                logger.warning(f"⚠️ CUDA error detected: {error_str[:100]}...")
                self._fallback_to_cpu()

                # Use CPU batch size
                cpu_batch = self.cpu_batch_size
                logger.info(f"🔄 Retrying on CPU with batch_size={cpu_batch}...")

                embeddings = self.model.encode(
                    texts,
                    batch_size=cpu_batch,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=True
                )
                logger.info(f"✅ Embedded {len(texts)} texts on CPU")
                return embeddings.tolist()
            else:
                logger.error(f"❌ Error embedding texts: {error_str}")
                raise
        except Exception as e:
            logger.error(f"❌ Error embedding texts: {str(e)}")
            raise
    
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between two texts

        Returns:
            Value between 0 and 1
        """
        try:
            embeddings = self.model.encode([text1, text2])
            
            # Cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"❌ Error calculating similarity: {str(e)}")
            raise
    
    
    def get_embedding_dimension(self) -> int:
        """Embedding dimensionality"""
        return self.embedding_dim


    @staticmethod
    def list_available_models() -> dict:
        """List available models"""
        return EmbeddingsService.MODELS
