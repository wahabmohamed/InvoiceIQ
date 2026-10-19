"""Orchestration : OCR -> extraction structuree -> indexation vectorielle.

L'extraction a lieu AVANT l'indexation pour que chaque chunk porte un en-tete
(fournisseur, n° de facture, date) qui le rattache a sa facture.
"""

from typing import Any

from database import db
from services import ocr_service
from services.chunker import build_chunks
from services.extractor import ExtractionResult, extract_invoice_data
from services.vectorstore import index_invoice_chunks


def run_extraction(invoice_id: int, raw_text: str) -> ExtractionResult:
    result = extract_invoice_data(raw_text)
    db.update_extracted_data(
        invoice_id, result.data, status=result.status,
        needs_review=result.needs_review, validation_notes=result.notes,
    )
    return result


def index_invoice(invoice_id: int) -> int:
    """(Re)indexe une facture a partir du texte OCR stocke. Renvoie le nombre de chunks."""
    row = db.get_invoice(invoice_id)
    if not row or not row["raw_text"]:
        return 0
    data = db.row_to_dict(row)
    chunks = build_chunks(row["raw_text"], row["filename"], data)
    index_invoice_chunks(invoice_id, row["filename"], chunks)
    return len(chunks)


def process_invoice(invoice_id: int, filepath: str) -> dict[str, Any]:
    raw_text = ocr_service.extract_text(filepath)
    db.update_raw_text(invoice_id, raw_text)
    if not raw_text.strip():
        # Rien a extraire ni a indexer : statut "ocr_failed" pose par update_raw_text
        return db.row_to_dict(db.get_invoice(invoice_id))

    try:
        run_extraction(invoice_id, raw_text)
    except Exception as exc:  # LLM indisponible, cle absente... : on indexe quand meme
        print(f"[pipeline] Extraction echouee pour {invoice_id}: {exc}")
        db.update_status(invoice_id, "extraction_failed")

    index_invoice(invoice_id)
    return db.row_to_dict(db.get_invoice(invoice_id))


def reindex_all() -> dict[str, int]:
    invoices = db.list_invoices()
    total_chunks = 0
    indexed = 0
    for row in invoices:
        n = index_invoice(row["id"])
        if n:
            indexed += 1
            total_chunks += n
    return {"invoices": indexed, "chunks": total_chunks}
