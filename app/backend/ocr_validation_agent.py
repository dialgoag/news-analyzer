"""
OCR Validation Agent - Local LLM (Ollama)

Purpose: 
- Fix OCR errors (hyphenated words)
- Validate text completeness
- Fast, local, $0 cost

Always uses: Ollama local (never OpenAI/Perplexity)
"""

import logging
from typing import Tuple
from langchain_community.llms import Ollama
import os

logger = logging.getLogger(__name__)


class OCRValidationAgent:
    """
    Specialized agent for OCR validation using local Ollama.
    
    Features:
    - Fixes hyphenated words from OCR errors
    - Detects if text is complete or fragmented
    - Runs entirely on local LLM (no API costs)
    - Fast (~1-2 seconds)
    """
    
    def __init__(self, model: str = None):
        """
        Initialize validation agent with local Ollama.
        
        Args:
            model: Ollama model name (defaults to env LLM_MODEL or 'mistral')
        """
        ollama_host = os.getenv("OLLAMA_HOST", "ollama")
        ollama_port = os.getenv("OLLAMA_PORT", "11434")
        self.model = model or os.getenv("LLM_MODEL", "mistral")
        
        self.llm = Ollama(
            base_url=f"http://{ollama_host}:{ollama_port}",
            model=self.model,
            temperature=0.1,  # Low temp for factual tasks
            timeout=30
        )
        
        logger.info(f"✅ OCR Validation Agent initialized (model: {self.model}, local)")
    
    async def validate_and_clean(self, text: str) -> Tuple[bool, str, str]:
        """
        Validate and clean OCR text.
        
        Args:
            text: Raw OCR text
        
        Returns:
            (is_complete, cleaned_text, reason)
        """
        try:
            prompt = self._build_prompt(text)
            
            logger.debug(f"🔍 Validating {len(text)} chars with local LLM...")
            
            response = await self.llm.ainvoke(prompt)
            
            # Parse response
            is_complete, cleaned_text, reason = self._parse_response(response, text)
            
            logger.info(f"{'✅' if is_complete else '⚠️'} Validation: {reason}")
            
            return is_complete, cleaned_text, reason
            
        except Exception as e:
            logger.warning(f"⚠️ Validation failed: {e}, assuming fragmented")
            return False, text, f"Validation error: {str(e)}"
    
    def _build_prompt(self, text: str) -> str:
        """Build validation prompt"""
        return f"""Analiza este texto de {len(text)} caracteres extraído por OCR.

TAREAS:
1. Corrige palabras cortadas por guiones al final de línea (ej: "Papa-tan" → "Papatan")
2. Detecta si es noticia COMPLETA o FRAGMENTADA

Indicadores de FRAGMENTADA:
- Muchas palabras cortadas a mitad (> 5% del texto)
- Frases sin sentido o mezcladas
- Texto claramente incompleto

TEXTO:
{text}

RESPONDE EN ESTE FORMATO:
ESTADO: [COMPLETA/FRAGMENTADA]
RAZON: [breve explicación]
TEXTO_CORREGIDO:
[texto con correcciones]"""
    
    def _parse_response(self, response: str, original: str) -> Tuple[bool, str, str]:
        """Parse LLM response"""
        lines = response.strip().split('\n')
        
        status = "FRAGMENTADA"
        reason = "No se pudo parsear respuesta"
        cleaned = original
        
        for i, line in enumerate(lines):
            if line.startswith("ESTADO:"):
                status = line.split(":", 1)[1].strip().upper()
            elif line.startswith(("RAZON:", "RAZÓN:")):
                reason = line.split(":", 1)[1].strip()
            elif line.startswith("TEXTO_CORREGIDO:"):
                cleaned = '\n'.join(lines[i+1:]).strip()
                break
        
        is_complete = "COMPLETA" in status
        
        return is_complete, cleaned, reason


# Global instance (singleton)
_validation_agent = None

def get_validation_agent() -> OCRValidationAgent:
    """Get or create validation agent singleton"""
    global _validation_agent
    if _validation_agent is None:
        _validation_agent = OCRValidationAgent()
    return _validation_agent
