"""Routes d'upload et de consultation des factures.

Les routes sont des `def` synchrones : FastAPI les execute dans un threadpool, ce qui
evite que l'OCR et les appels LLM (bloquants) gelent la boucle evenementielle.
"""

import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import settings
from database import db
from services.analytics import compute_stats
from services.pipeline import process_invoice, reindex_all
from services.vectorstore import delete_invoice_chunks

router = APIRouter(tags=["invoices"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _safe_name(filename: str) -> str:
    # Supprime tout chemin ("../../x") et les caracteres exotiques
    name = Path(filename or "facture").name
    return re.sub(r"[^\w.\-]", "_", name) or "facture"


@router.post("/upload")
def upload_invoice(file: UploadFile):
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extension non supportee: {suffix}. Formats acceptes: {sorted(settings.ALLOWED_EXTENSIONS)}",
        )

    content = file.file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 20 Mo)")
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")

    # Deduplication sur le contenu : une meme facture uploadee deux fois serait
    # comptee deux fois dans les totaux et dupliquee dans l'index vectoriel.
    file_hash = hashlib.sha256(content).hexdigest()
    existing = db.find_by_hash(file_hash)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Cette facture a deja ete importee (id {existing['id']}, fichier \"{existing['filename']}\").",
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    invoice_id = db.insert_invoice(original_name, "", file_hash)
    # Nom de stockage unique : deux fichiers de meme nom ne s'ecrasent plus
    filepath = upload_dir / f"{invoice_id}_{_safe_name(original_name)}"
    filepath.write_bytes(content)
    db.update_filepath(invoice_id, str(filepath))

    return process_invoice(invoice_id, str(filepath))


@router.get("/invoices")
def list_invoices():
    rows = db.list_invoices()
    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "status": row["status"],
            "invoice_number": row["invoice_number"],
            "invoice_date": row["invoice_date"],
            "supplier_name": row["supplier_name"],
            "amount_ttc": row["amount_ttc"],
            "currency": row["currency"],
            "needs_review": bool(row["needs_review"]),
            "validation_notes": db.row_to_dict(row).get("validation_notes") or [],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


@router.get("/stats")
def stats():
    """Agregats exacts (par devise, fournisseur, mois) pour le tableau de bord."""
    return compute_stats(db.row_to_dict(r) for r in db.list_invoices())


@router.post("/reindex")
def reindex():
    """Re-calcule tous les embeddings (a lancer apres un changement de modele d'embedding)."""
    return reindex_all()


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    row = db.get_invoice(invoice_id)
    if not row:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    return db.row_to_dict(row)


@router.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: int):
    row = db.get_invoice(invoice_id)
    if not row:
        raise HTTPException(status_code=404, detail="Facture introuvable")

    delete_invoice_chunks(invoice_id)
    if row["filepath"]:
        Path(row["filepath"]).unlink(missing_ok=True)
    db.delete_invoice(invoice_id)

    return {"id": invoice_id, "deleted": True}


@router.get("/invoices/{invoice_id}/export")
def export_invoice(invoice_id: int):
    row = db.get_invoice(invoice_id)
    if not row:
        raise HTTPException(status_code=404, detail="Facture introuvable")
    data = db.row_to_dict(row)
    data.pop("filepath", None)
    return JSONResponse(content=data, headers={"Content-Disposition": f"attachment; filename=facture_{invoice_id}.json"})
