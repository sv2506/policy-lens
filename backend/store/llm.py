import os
import re
import asyncio
from typing import AsyncGenerator, List, Dict, Tuple
from .retrieval import retrieve

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
USE_LLM = os.getenv("USE_LLM", "0") == "1"

# Compile citation pattern once
CITATION_RE = re.compile(r"\[(\d+)\]")

SYSTEM_PROMPT = (
    "You are a policy assistant. Answer ONLY using the provided policy excerpts. "
    "Cite each supporting policy with its id in square brackets like [3]. "
    "If the answer is not contained in the excerpts, respond exactly with: I don't know. "
    "Optionally end with a clarifying question if you answered 'I don't know.'"
)

async def stream_llm_answer(question: str, k: int = 3) -> AsyncGenerator[Tuple[str, str], None]:
    """Yield (event_type, data) tuples. event_type: 'delta' | 'done' | 'error'.
    Falls back to 'error' if provider unsupported.
    """
    if not USE_LLM:
        yield ("error", "LLM disabled")
        return
    if LLM_PROVIDER != "openai":
        yield ("error", f"Unsupported provider {LLM_PROVIDER}")
        return

    # Lazy import to avoid dependency if not used
    try:
        from openai import AsyncOpenAI
    except Exception as e:  # pragma: no cover
        yield ("error", f"OpenAI client import failed: {e}")
        return

    client = AsyncOpenAI()

    # Retrieve context
    results = retrieve(question, k=k)
    docs = [doc for doc, _score in results]
    context_blocks = []
    allowed_ids = set()
    for d in docs:
        allowed_ids.add(d["id"])
        context_blocks.append(f"[{d['id']}] {d['title']}\n{d['text']}")
    context_text = "\n\n".join(context_blocks) or "(no context)"

    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {question}"},
    ]

    try:
        # OpenAI responses streaming
        stream = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            stream=True,
            temperature=0.2,
        )
        full = []
        async for chunk in stream:  # type: ignore
            try:
                delta = chunk.choices[0].delta.content  # type: ignore
            except Exception:
                delta = None
            if not delta:
                continue
            full.append(delta)
            yield ("delta", delta)
        raw_text = "".join(full).strip()
        # Citation post-filter: remove any [id] not in allowed set
        def _clean(match):
            cid = match.group(1)
            return match.group(0) if cid in allowed_ids else ""
        cleaned = CITATION_RE.sub(_clean, raw_text)
        yield ("done", cleaned)
    except Exception as e:  # pragma: no cover
        yield ("error", str(e))

__all__ = ["stream_llm_answer", "USE_LLM"]
