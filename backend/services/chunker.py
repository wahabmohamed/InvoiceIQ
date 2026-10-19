"""Decoupage du texte en chunks via LangChain."""

from typing import Any, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import settings

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def split_text(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    return _splitter.split_text(text)


def chunk_header(filename: str, data: Optional[dict[str, Any]] = None) -> str:
    """En-tete contextuel ajoute a chaque chunk.

    Sans lui, un chunk comme "Montant TTC : 3030.00 EUR" est quasi identique d'une
    facture a l'autre dans l'espace vectoriel et ne dit pas a quelle facture il appartient.
    """
    data = data or {}
    parts = [f"Fichier: {filename}"]
    for key, label in (("supplier_name", "Fournisseur"), ("invoice_number", "Facture n°"),
                       ("invoice_date", "Date"), ("client_name", "Client")):
        if data.get(key):
            parts.append(f"{label}: {data[key]}")
    return " | ".join(parts)


def build_chunks(text: str, filename: str, data: Optional[dict[str, Any]] = None) -> list[str]:
    header = chunk_header(filename, data)
    return [f"{header}\n{chunk}" for chunk in split_text(text)]
