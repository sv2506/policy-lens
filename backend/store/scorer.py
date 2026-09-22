# Tiny BM25-lite scorer with tokenization, stopwords, and IDF.
# Deterministic and dependency-free.

import math
import re
from typing import List, Dict, Tuple

STOP = {"the","a","an","and","of","to","for","in","on","at","is","are","it","this","that","with","from"}

def tokens(s: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP]

class Index:
    def __init__(self, docs: List[Dict[str, str]]):
        self.docs = docs
        self.tok = [tokens(d["title"] + " " + d["text"]) for d in docs]
        N = len(docs)
        df: Dict[str, int] = {}
        for ts in self.tok:
            for t in set(ts):
                df[t] = df.get(t, 0) + 1
        self.idf: Dict[str, float] = {t: math.log(1 + (N - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.avgdl = sum(len(ts) for ts in self.tok) / (len(self.tok) or 1)

def score(query: str, idx: int, index: Index) -> float:
    q = tokens(query)
    if not q: return 0.0
    ts = index.tok[idx]
    tf: Dict[str, int] = {}
    for t in ts:
        tf[t] = tf.get(t, 0) + 1
    k1, b = 1.2, 0.75
    dl = len(ts)
    dl_norm = (1 - b) + b * (dl / (index.avgdl or 1))
    s = 0.0
    for t in q:
        idf = index.idf.get(t, 0.0)
        f = tf.get(t, 0)
        s += idf * ((f * (k1 + 1)) / (f + k1 * dl_norm)) if f > 0 else 0.0
    # tiny exact-phrase bonus
    fulltext = (index.docs[idx]["title"] + " " + index.docs[idx]["text"]).lower()
    if len(" ".join(q)) >= 6 and (fulltext.find(query.lower()) >= 0):
        s *= 1.1
    return s

def rank(query: str, index: Index, k: int = 3, threshold: float = 0.18) -> List[Tuple[Dict[str,str], float]]:
    scored = [(i, score(query, i, index)) for i in range(len(index.docs))]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(index.docs[i], s) for i, s in scored if s >= threshold][:k]

