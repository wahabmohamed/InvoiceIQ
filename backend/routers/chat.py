"""Route de chat (F5/F6/F7/F8) : donnees structurees + RAG."""

import groq
from fastapi import APIRouter, HTTPException

from models.schemas import ChatRequest, ChatResponse
from services.rag_service import answer_question

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="La question ne peut pas etre vide")

    try:
        result = answer_question(
            question=request.question.strip(),
            invoice_ids=request.invoice_ids,
            history=[m.model_dump() for m in request.history or []],
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except groq.AuthenticationError:
        raise HTTPException(status_code=503, detail="Cle GROQ_API_KEY invalide ou expiree : generez-en une nouvelle sur console.groq.com")
    except groq.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Erreur du service LLM (Groq) : {exc}")
    return ChatResponse(**result)
