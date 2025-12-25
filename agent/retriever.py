"""Local news retriever over DuckDB for Japan 225.

This module provides a simple retrieval API on top of the ``news_japan225``
DuckDB table created by ``janestreet.py``. It computes deterministic
bag-of-words embeddings for headlines and summaries, stores them in DuckDB,
and supports cosine-similarity search for use in RAG-style workflows.

The embedding model here is deliberately lightweight and has no external
dependencies. If you later adopt a proper embedding model (e.g. OpenAI,
SentenceTransformers, etc.), you can swap out :func:`embed_text` while keeping
call sites unchanged.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import duckdb

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "stonex_meta.duckdb"


@dataclass
class RetrievedNews:
    score: float
    story_id: str
    publish_ts: Any
    headline: str
    summary: str


# ---------------------------------------------------------------------------
# Embedding utilities
# ---------------------------------------------------------------------------

_DIM = 256  # size of the embedding vector
_TOKEN_RE = re.compile(r"\w+")


def _stable_hash(token: str) -> int:
    """Return a stable non-cryptographic hash for a token.

    Python's built-in ``hash`` is salted per process, so we use a simple
    deterministic scheme instead.
    """

    # FNV-1a 32-bit
    h = 2166136261
    for ch in token.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def embed_text(text: str, dim: int = _DIM) -> List[float]:
    """Embed text into a fixed-length vector using hashed bag-of-words.

    This is *not* a semantic model, but good enough structurally for wiring up
    local retrieval without adding heavy dependencies. Replace with a proper
    embedding model when ready.
    """

    vec = [0.0] * dim
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens:
        return vec

    for tok in tokens:
        idx = _stable_hash(tok) % dim
        vec[idx] += 1.0

    # L2 normalise
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    # Vectors are already normalised, so dot is cosine.
    return float(dot)


# ---------------------------------------------------------------------------
# DuckDB helpers
# ---------------------------------------------------------------------------


def _connect_rw() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(DB_PATH.as_posix())


def ensure_embedding_table() -> None:
    con = _connect_rw()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS news_embeddings (
            story_id TEXT PRIMARY KEY,
            embedding_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    con.close()


def _rows_missing_embeddings(con: duckdb.DuckDBPyConnection) -> Iterable[tuple]:
    return con.execute(
        """
        SELECT n.story_id, n.headline, n.summary
        FROM news_japan225 n
        LEFT JOIN news_embeddings e ON n.story_id = e.story_id
        WHERE e.story_id IS NULL
        """
    ).fetchall()


def upsert_embeddings() -> None:
    """Create embeddings for any ``news_japan225`` rows missing them."""

    ensure_embedding_table()
    con = _connect_rw()

    missing = list(_rows_missing_embeddings(con))
    if not missing:
        con.close()
        return

    rows = []
    for story_id, headline, summary in missing:
        text = f"{headline or ''}\n\n{summary or ''}"
        vec = embed_text(text)
        rows.append((story_id, json.dumps(vec)))

    con.executemany(
        """
        INSERT INTO news_embeddings (story_id, embedding_json)
        VALUES (?, ?)
        ON CONFLICT (story_id) DO UPDATE SET
            embedding_json = excluded.embedding_json;
        """,
        rows,
    )

    con.close()


# ---------------------------------------------------------------------------
# Retrieval API
# ---------------------------------------------------------------------------


def retrieve_similar_news(query: str, top_k: int = 5) -> List[RetrievedNews]:
    """Return top_k most similar Japan 225 news items for a free-text query.

    This assumes ``news_japan225`` has been populated by ``janestreet.py`` and
    that :func:`upsert_embeddings` has been run at least once this session
    (the function calls it automatically).
    """

    if top_k <= 0:
        return []

    upsert_embeddings()

    con = _connect_rw()
    q_vec = embed_text(query)

    rows = con.execute(
        """
        SELECT n.story_id, n.publish_ts, n.headline, n.summary, e.embedding_json
        FROM news_japan225 n
        JOIN news_embeddings e USING (story_id)
        """
    ).fetchall()
    con.close()

    scored: List[RetrievedNews] = []
    for story_id, publish_ts, headline, summary, emb_json in rows:
        try:
            vec = json.loads(emb_json)
            score = _cosine(q_vec, vec)
        except Exception:
            score = 0.0
        scored.append(
            RetrievedNews(
                score=score,
                story_id=str(story_id),
                publish_ts=publish_ts,
                headline=str(headline or ""),
                summary=str(summary or ""),
            )
        )

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]


__all__ = [
    "RetrievedNews",
    "embed_text",
    "upsert_embeddings",
    "retrieve_similar_news",
]

