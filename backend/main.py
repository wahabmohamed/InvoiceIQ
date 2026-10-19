"""Point d'entree FastAPI - InvoiceIQ."""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import db
from routers import chat, extract, upload


def _auto_reindex() -> None:
    """Remplit une collection vectorielle vide (ex: apres changement de modele d'embedding)."""
    try:
        from services.pipeline import reindex_all
        from services.vectorstore import collection_count

        if collection_count() == 0 and db.list_invoices():
            print(f"[startup] Collection vide, re-indexation : {reindex_all()}")
    except Exception as exc:
        print(f"[startup] Re-indexation automatique impossible ({exc}). Utiliser POST /reindex.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    threading.Thread(target=_auto_reindex, daemon=True).start()
    yield


app = FastAPI(
    title="InvoiceIQ API",
    description="Extraction intelligente et interrogation de factures en langage naturel",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # Pas de cookies/identifiants : "*" + credentials est une combinaison a eviter
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(upload.router)
app.include_router(extract.router)
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}
