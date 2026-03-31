#!/usr/bin/env python3
"""Utility to compare the insights prompt across local Ollama vs API providers."""

from __future__ import annotations

import argparse
import json
import os
import textwrap
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv


PROMPT_TEMPLATE = textwrap.dedent(
    """You are a news analyst. Based on the following document excerpts from "{label}", produce a structured insights report in Markdown.

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
{context}
---

INSIGHTS REPORT (Markdown):"""
)


def build_prompt(label: str, context: str) -> str:
    return PROMPT_TEMPLATE.format(label=label, context=context[:80000])


def resolve_ollama_base_url(host: str, port: str) -> str:
    host = (host or "").strip()
    port = (port or "11434").strip()
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    if host in {"ollama", "rag-ollama", "localhost"}:
        return f"http://127.0.0.1:{port}"
    return f"http://{host}:{port}"


def resolve_ollama_model(
    cli_model: Optional[str], env: Dict[str, str]
) -> str:
    if cli_model:
        return cli_model
    for key in ("INSIGHTS_OLLAMA_MODEL", "OLLAMA_LLM_MODEL", "LLM_MODEL"):
        val = (env.get(key) or "").strip()
        if val:
            return val
    return "mistral"


def evaluate_markdown_sections(markdown: str) -> Dict[str, object]:
    required = [
        "**Tema**",
        "**Autor**",
        "**Periódico/Fuente**",
        "**Postura**",
        "**Resumen**",
        "**Contexto IA**",
    ]
    missing = [label for label in required if label not in markdown]
    return {
        "missing_sections": missing,
        "section_count": len(required) - len(missing),
        "complete": not missing,
        "char_length": len(markdown),
    }


def call_openai(prompt: str, model: str, base_url: str, api_key: str, timeout: int) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_perplexity(prompt: str, model: str, api_key: str, timeout: int) -> str:
    resp = requests.post(
        "https://api.perplexity.ai/v1/sonar",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_ollama(prompt: str, model: str, base_url: str, timeout: int) -> str:
    resp = requests.post(
        base_url.rstrip("/") + "/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare insights generation results across providers",
    )
    parser.add_argument("--context-file", required=True, help="Path to plain-text context excerpt")
    parser.add_argument("--label", required=True, help="Label shown to the model (e.g. filename + title)")
    parser.add_argument(
        "--providers",
        default="ollama,openai,perplexity",
        help="Comma-separated providers to run (ollama, openai, perplexity)",
    )
    parser.add_argument(
        "--output-dir",
        default="benchmark/insights_results/runs",
        help="Directory where outputs will be written",
    )
    parser.add_argument("--dotenv", default=".env", help=".env file with API keys")
    parser.add_argument("--ollama-model", help="Override Ollama model name")
    parser.add_argument("--ollama-url", help="Override Ollama base URL (default derives from env)")
    parser.add_argument("--openai-model", help="Override OpenAI model")
    parser.add_argument("--openai-base", help="Custom OpenAI base URL")
    parser.add_argument("--perplexity-model", help="Override Perplexity model tag")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per request in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dotenv_path = Path(args.dotenv)
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    env = dict(os.environ)
    context_path = Path(args.context_file)
    context = context_path.read_text().strip()
    label = args.label
    prompt = build_prompt(label, context)

    providers = [p.strip().lower() for p in args.providers.split(",") if p.strip()]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary: List[Dict[str, object]] = []

    ollama_url = args.ollama_url or resolve_ollama_base_url(
        env.get("OLLAMA_BASE_URL") or env.get("OLLAMA_HOST") or "ollama",
        env.get("OLLAMA_PORT") or "11434",
    )
    ollama_model = resolve_ollama_model(args.ollama_model, env)
    openai_model = args.openai_model or env.get("OPENAI_MODEL") or env.get("LLM_MODEL") or "gpt-4o"
    openai_base = args.openai_base or env.get("OPENAI_API_BASE_URL") or "https://api.openai.com/v1"
    perplexity_model = args.perplexity_model or env.get("PERPLEXITY_MODEL") or "sonar-pro"

    for provider in providers:
        provider_summary: Dict[str, object] = {
            "provider": provider,
            "status": "skipped",
        }
        summary.append(provider_summary)
        try:
            start = perf_counter()
            if provider == "openai":
                api_key = env.get("OPENAI_API_KEY")
                if not api_key:
                    raise RuntimeError("OPENAI_API_KEY is not set")
                markdown = call_openai(prompt, openai_model, openai_base, api_key, args.timeout)
            elif provider == "perplexity":
                api_key = env.get("PERPLEXITY_API_KEY")
                if not api_key:
                    raise RuntimeError("PERPLEXITY_API_KEY is not set")
                markdown = call_perplexity(prompt, perplexity_model, api_key, args.timeout)
            elif provider in {"ollama", "local"}:
                markdown = call_ollama(prompt, ollama_model, ollama_url, args.timeout)
            else:
                raise RuntimeError(f"Unknown provider '{provider}'")
            elapsed = perf_counter() - start
            stats = evaluate_markdown_sections(markdown)
            provider_summary.update(
                {
                    "status": "ok",
                    "latency_seconds": round(elapsed, 2),
                    "section_stats": stats,
                }
            )
            out_file = output_dir / f"{timestamp}_{provider}.md"
            out_file.write_text(markdown.strip() + "\n")
            provider_summary["output_file"] = str(out_file)
        except Exception as exc:  # pylint: disable=broad-except
            provider_summary.update({"status": "error", "error": str(exc)})

    summary_path = output_dir / f"{timestamp}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"Summary written to {summary_path}")
    for provider_summary in summary:
        provider = provider_summary["provider"]
        status = provider_summary["status"]
        if status == "ok":
            sections = provider_summary.get("section_stats", {})
            missing = sections.get("missing_sections") or []
            print(
                f"[{provider}] ok in {provider_summary['latency_seconds']}s — missing sections: {', '.join(missing) if missing else 'none'}"
            )
        else:
            print(f"[{provider}] {status}: {provider_summary.get('error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
