"""Wrapper ChromaDB : indexation et recherche des chunks de factures."""

from functools import lru_cache
from typing import Any, Optional

import chromadb

from config import settings
from services.embedder import embed_query, embed_texts


@lru_cache(maxsize=1)
def _get_collection():
    client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    # Metrique cosinus explicite : la distance renvoyee vaut 1 - cos, donc
    # `1 - distance` est une vraie similarite cosinus (defaut Chroma = L2 au carre).
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def collection_count() -> int:
    return _get_collection().count()


def index_invoice_chunks(invoice_id: int, filename: str, chunks: list[str]) -> None:
    collection = _get_collection()
    # Supprime les anciens chunks avant re-indexation (idempotence)
    collection.delete(where={"invoice_id": invoice_id})
    if not chunks:
        return
    ids = [f"invoice-{invoice_id}-chunk-{i}" for i in range(len(chunks))]
    embeddings = embed_texts(chunks)
    metadatas = [{"invoice_id": invoice_id, "filename": filename, "chunk_index": i} for i in range(len(chunks))]
    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)


def query_chunks(
    question: str,
    invoice_ids: Optional[list[int]] = None,
    top_k: int = 5,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    query_embedding = embed_query(question)

    where = {"invoice_id": {"$in": invoice_ids}} if invoice_ids else None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
    )

    sources = []
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        score = None if dist is None else round(1 - dist, 4)
        if score is not None and score < min_score:
            continue
        sources.append(
            {
                "invoice_id": meta.get("invoice_id"),
                "filename": meta.get("filename"),
                "content": doc,
                "score": score,
            }
        )
    return sources


def delete_invoice_chunks(invoice_id: int) -> None:
    collection = _get_collection()
    collection.delete(where={"invoice_id": invoice_id})
