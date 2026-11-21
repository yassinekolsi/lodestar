"""Local embeddings with FastEmbed (docs/plan/02): bge-small dense (384) + BM25 sparse. Nothing is
sent out. Models load lazily on first use and run in a worker thread."""

import asyncio
from dataclasses import dataclass
from functools import cached_property
from threading import Lock
from typing import Any

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
DENSE_SIZE = 384


@dataclass(frozen=True)
class Embedded:
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


class Embedder:
    def __init__(
        self, cache_dir: str | None = None, *, threads: int | None = None, batch_size: int = 8
    ) -> None:
        self.cache_dir = cache_dir
        self.threads = threads
        self.batch_size = batch_size
        self._lock = Lock()

    @cached_property
    def _dense(self) -> Any:
        from fastembed import TextEmbedding

        return TextEmbedding(
            DENSE_MODEL,
            cache_dir=self.cache_dir,
            threads=self.threads,
            enable_cpu_mem_arena=self.batch_size != 1,
        )

    @cached_property
    def _sparse(self) -> Any:
        from fastembed import SparseTextEmbedding

        return SparseTextEmbedding(SPARSE_MODEL, cache_dir=self.cache_dir, threads=self.threads)

    def _embed_sync(self, texts: list[str], query: bool) -> list[Embedded]:
        # ONNX sessions and their buffers are shared. Concurrent requests must not multiply
        # their peak memory, or race while initializing the cached models.
        with self._lock:
            return self._embed_serial(texts, query)

    def _embed_serial(self, texts: list[str], query: bool) -> list[Embedded]:
        dense = list(
            self._dense.query_embed(texts, batch_size=self.batch_size)
            if query
            else self._dense.embed(texts, batch_size=self.batch_size)
        )
        sparse = list(
            self._sparse.query_embed(texts, batch_size=self.batch_size)
            if query
            else self._sparse.embed(texts, batch_size=self.batch_size)
        )
        return [
            Embedded(
                dense=[float(x) for x in d],
                sparse_indices=[int(i) for i in s.indices],
                sparse_values=[float(v) for v in s.values],
            )
            for d, s in zip(dense, sparse, strict=True)
        ]

    async def embed(self, texts: list[str]) -> list[Embedded]:
        return await asyncio.to_thread(self._embed_sync, texts, False)

    async def embed_query(self, text: str) -> Embedded:
        [result] = await asyncio.to_thread(self._embed_sync, [text], True)
        return result
