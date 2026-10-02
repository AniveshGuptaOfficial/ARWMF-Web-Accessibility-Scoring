"""Link-text adequacy: vague-label lexicon + MiniLM context similarity (spec: D5).

Embedding model is optional at call time: if unavailable, the heuristic half
still runs so the pipeline degrades gracefully (flagged in output metadata).
"""
from __future__ import annotations

import re
from typing import Iterable

# exact vague labels -> score 0
VAGUE_EXACT = {
    "click here", "here", "more", "read more", "link", "more info",
    "learn more", "this", "this link", "details", "continue", "go",
    "download", "click", "check it out", "see more", "read more...",
}
# labels containing these as the *only* content words -> partial penalty
VAGUE_PARTIAL = {"click", "here", "this", "more", "link", "go", "read"}

URL_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)

# logistic-free linear mapping constants (docs/02-accessibility-scoring-specification.md D5)
C0 = 0.05
C_SAT = 0.55
GENERIC_VERB_PENALTY = 0.6


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().strip(".,;:!")).strip()


def heuristic_score(link_text: str) -> tuple[float, bool]:
    """Return (score_0_100_or_-1_if_vague_rule_applies, is_generic_verb).

    -1 means 'exact vague label' -> hard 0 regardless of embedding.
    """
    norm = normalize(link_text)
    if not norm:
        return 0.0, False
    if URL_RE.match(norm):
        return 0.0, False
    if norm in VAGUE_EXACT:
        return 0.0, False
    tokens = set(norm.split())
    if tokens and tokens <= VAGUE_PARTIAL:
        return -1.0, True  # all content words are vague -> partial penalty path
    return -1.0, False  # no heuristic verdict; use embedding


def link_score(link: dict, embedder=None) -> float:
    """Score one link 0-100.

    link keys: text (str), context (str, enclosing block minus the link).
    """
    text = link.get("text") or ""
    heuristic, generic_verb = heuristic_score(text)
    if heuristic >= 0:
        return heuristic  # exact vague / empty / URL -> 0

    embed_score = None
    if embedder is not None and link.get("context"):
        try:
            cos = embedder.similarity(text, link["context"])
            embed_score = 100.0 * max(0.0, min(1.0, (cos - C0) / (C_SAT - C0)))
        except Exception:
            embed_score = None
    if embed_score is None:
        # fallback: length-based soft heuristic (>=2 meaningful tokens OK)
        tokens = [t for t in normalize(text).split() if t not in VAGUE_PARTIAL]
        embed_score = 100.0 if len(tokens) >= 2 else 40.0

    if generic_verb:
        embed_score *= GENERIC_VERB_PENALTY
    return float(embed_score)


_EMB_CACHE: dict = {}  # shared across ContextEmbedder instances


class ContextEmbedder:
    """Thin wrapper around a sentence-transformer for link/context cosine.

    Model is cached at module level (loaded once per process, not per page).
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            if self.model_name not in _EMB_CACHE:
                from sentence_transformers import SentenceTransformer

                _EMB_CACHE[self.model_name] = SentenceTransformer(self.model_name)
            self._model = _EMB_CACHE[self.model_name]
        return self._model

    def similarity(self, a: str, b: str) -> float:
        model = self._load()
        vecs = model.encode([a, b], normalize_embeddings=True)
        return float((vecs[0] * vecs[1]).sum())


def dimension_link_text(links: Iterable[dict], embedder=None) -> float | None:
    """Mean over links with non-empty rendered text; None if none."""
    scores = []
    for link in links:
        if not (link.get("text") or "").strip():
            continue  # image-only link handled by alt-text dimension
        scores.append(link_score(link, embedder))
    if not scores:
        return None
    return sum(scores) / len(scores)
