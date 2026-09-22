import json
from pathlib import Path
from typing import List, Dict, Tuple
from .scorer import Index, rank

_POLICIES_PATH = Path(__file__).parent / 'policies.json'
_index: Index | None = None
_docs: List[Dict[str,str]] = []

CLARIFY_FALLBACK = "I don't know. Could you clarify what specific aspect you need (e.g. limits, turnaround time, or coverage scope)?"

def load_index():
    global _index, _docs
    if _index is None:
        with _POLICIES_PATH.open() as f:
            _docs = json.load(f)
        _index = Index(_docs)
    return _index

def retrieve(query: str, k: int = 3):
    idx = load_index()
    results = rank(query, idx, k=k)
    return results  # list of (doc, score)

def build_grounded_answer(query: str, k: int = 3) -> Tuple[str, List[str]]:
    results = retrieve(query, k=k)
    if not results:
        return CLARIFY_FALLBACK, []
    # Construct answer by selecting relevant sentences from docs.
    # Simple heuristic: choose doc text; later could sentence-split.
    parts = []
    used_ids = []
    for doc, _score in results:
        doc_id = doc['id']
        used_ids.append(doc_id)
        # Keep original text; ensure a citation at end.
        txt = doc['text'].strip()
        if not txt.endswith('.'):
            txt += '.'
        parts.append(f"{txt} [{doc_id}]")
    # Optional brief synthesis line if multiple docs.
    if len(parts) > 1:
        parts.append("These details are sourced from the referenced policy documents above.")
    answer = ' '.join(parts)
    return answer, used_ids

def get_docs_meta() -> List[Dict[str,str]]:
    load_index()
    return [{"id": d["id"], "title": d["title"]} for d in _docs]

def get_all_policies() -> List[Dict[str,str]]:
    load_index()
    return _docs
