"""Service OCR / IDP base sur Docling.

Extrait le texte brut (et la mise en page) d'un PDF natif, PDF scanne ou image.
"""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _get_converter():
    # Le chargement des modeles Docling (layout, tables, OCR) est couteux :
    # une seule instance pour toute la duree de vie du process.
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def extract_text(filepath: str) -> str:
    """Retourne le texte brut extrait du document via Docling (chaine vide si echec)."""
    try:
        result = _get_converter().convert(filepath)
        text = result.document.export_to_markdown()
        if text and text.strip():
            return text
    except Exception as exc:  # pragma: no cover - fallback si Docling indisponible
        print(f"[ocr_service] Docling a echoue ({exc}), tentative de fallback.")

    return _fallback_extract(filepath)


def _fallback_extract(filepath: str) -> str:
    """Fallback pour PDF a couche texte native (ne fait pas d'OCR sur les scans/images)."""
    suffix = Path(filepath).suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(filepath)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            print(f"[ocr_service] Fallback pypdf echoue ({exc}).")
            return ""
    return ""
