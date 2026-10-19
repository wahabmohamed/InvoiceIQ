"""Route d'extraction structuree des entites d'une facture."""

import groq
from fastapi import APIRouter, HTTPException

from database import db
from services.pipeline import index_invoice, run_extraction

router = APIRouter(tags=["extraction"])


@router.post("/extract/{invoice_id}")
def extract_invoice(invoice_id: int):
    row = db.get_invoice(invoice_id)
    if not row:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    if not row["raw_text"] or not row["raw_text"].strip():
        raise HTTPException(status_code=400, detail="Aucun texte OCR disponible pour cette facture")

    try:
        result = run_extraction(invoice_id, row["raw_text"])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except groq.AuthenticationError:
        raise HTTPException(status_code=503, detail="Cle GROQ_API_KEY invalide ou expiree : generez-en une nouvelle sur console.groq.com")
    except groq.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Erreur du service LLM (Groq) : {exc}")

    # Les en-tetes de chunks dependent des champs extraits : re-indexation
    index_invoice(invoice_id)

    return {
        "id": invoice_id,
        "status": result.status,
        "needs_review": result.needs_review,
        "validation_notes": result.notes,
        "data": result.data,
    }
