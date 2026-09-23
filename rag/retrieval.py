from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def retrieve(query: str, chunks: list[dict[str, Any]], top_k: int = 4) -> list[dict[str, Any]]:
    if not query.strip() or not chunks:
        return []
    texts = [str(c["content"]) for c in chunks]
    corpus = texts + [query]
    vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), max_features=12000)
    matrix = vectorizer.fit_transform(corpus)
    sims = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    order = sims.argsort()[::-1][:top_k]
    results = []
    for i in order:
        if sims[i] <= 0:
            continue
        item = dict(chunks[int(i)])
        item["score"] = float(sims[i])
        results.append(item)
    return results


def format_context(results: list[dict[str, Any]]) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] {r.get('title','Материал')} / бөлік {int(r.get('chunk_index',0))+1}:\n{r['content']}")
    return "\n\n".join(parts)
