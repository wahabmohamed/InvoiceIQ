"""Embeddings multilingues (par defaut intfloat/multilingual-e5-small).

Les modeles E5 exigent des prefixes distincts pour les requetes ("query: ") et les
documents ("passage: ") ; sans eux la qualite de recherche chute nettement.
Les vecteurs sont normalises (norme 1) pour une similarite cosinus correcte.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from config import settings


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(settings.EMBEDDING_MODEL)


def _is_e5() -> bool:
    return "e5" in settings.EMBEDDING_MODEL.lower()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if _is_e5():
        texts = [f"passage: {t}" for t in texts]
    return get_embedder().encode(texts, normalize_embeddings=True).tolist()


def embed_query(text: str) -> list[float]:
    if _is_e5():
        text = f"query: {text}"
    return get_embedder().encode([text], normalize_embeddings=True)[0].tolist()
