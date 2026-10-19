"""Chat sur les factures : donnees structurees (SQLite) + RAG (ChromaDB) -> Groq.

- Questions chiffrees / d'agregation : le LLM recoit le tableau des factures et des
  agregats calcules en Python (exacts), au lieu de devoir additionner des chunks.
- Questions de detail (lignes, adresses, conditions...) : chunks recuperes par
  similarite cosinus, filtres par un score minimum.
- Questions de suivi ("et sa TVA ?") : reformulees en question autonome avant la
  recherche vectorielle, sinon la recherche porte sur une phrase sans contexte.
"""

from typing import Any, Optional

from groq import Groq

from config import settings
from database import db
from services.analytics import compute_stats, format_for_prompt
from services.vectorstore import query_chunks

_SYSTEM_PROMPT = """Tu es un assistant qui repond a des questions sur des factures.
Tu disposes de deux sources, et UNIQUEMENT de celles-ci :
1. "Donnees structurees" : un tableau des factures et des agregats deja calcules.
   Pour tout montant, total, somme, moyenne, comparaison ou comptage, utilise ces
   donnees. Reprends les agregats fournis tels quels ; ne refais pas les additions.
2. "Extraits" : des passages du texte OCR des factures, pour les details absents du
   tableau (lignes de produits, adresses, conditions de paiement...).

Regles :
- Si l'information n'est ni dans le tableau ni dans les extraits, dis clairement que tu ne sais pas.
- Cite les factures utilisees sous la forme [Facture <id>].
- Si une facture utilisee est marquee "A VERIFIER" ou "NON EXTRAITE", signale-le.
- N'additionne jamais des montants de devises differentes.
- Reponds dans la langue de la question, de maniere concise et precise."""

_CONDENSE_PROMPT = """Reformule la derniere question de l'utilisateur en une question
autonome et complete (sans pronoms ambigus), en t'appuyant sur l'historique.
Reponds UNIQUEMENT par la question reformulee, sans commentaire."""

_HISTORY_MAX_MESSAGES = 6


def _get_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY manquante. Configurez-la dans le fichier .env")
    return Groq(api_key=settings.GROQ_API_KEY)


def _clean_history(history: Optional[list[dict]], question: str) -> list[dict]:
    if not history:
        return []
    msgs = [{"role": m["role"], "content": m["content"]} for m in history if m.get("role") in ("user", "assistant")]
    # Compatibilite : anciens clients qui incluaient la question courante dans l'historique
    if msgs and msgs[-1]["role"] == "user" and msgs[-1]["content"].strip() == question.strip():
        msgs = msgs[:-1]
    return msgs[-_HISTORY_MAX_MESSAGES:]


def _condense_question(client: Groq, question: str, history: list[dict]) -> str:
    if not history:
        return question
    transcript = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in history)
    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": _CONDENSE_PROMPT},
                {"role": "user", "content": f"Historique :\n{transcript}\n\nDerniere question : {question}"},
            ],
            temperature=0,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        return rewritten or question
    except Exception as exc:
        print(f"[rag_service] Reformulation echouee ({exc}), question brute utilisee.")
        return question


def answer_question(
    question: str,
    invoice_ids: Optional[list[int]] = None,
    history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    client = _get_client()
    history = _clean_history(history, question)
    standalone = _condense_question(client, question, history)

    sources = query_chunks(
        standalone, invoice_ids=invoice_ids, top_k=settings.RAG_TOP_K, min_score=settings.RAG_MIN_SCORE
    )

    invoices = [db.row_to_dict(r) for r in db.list_invoices(invoice_ids)]
    structured = format_for_prompt(invoices, compute_stats(invoices), settings.RAG_MAX_TABLE_ROWS)

    excerpts = "\n\n---\n\n".join(
        f"[Facture {s['invoice_id']} - {s['filename']}]\n{s['content']}" for s in sources
    ) or "(aucun extrait suffisamment pertinent)"

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}, *history]
    messages.append(
        {
            "role": "user",
            "content": (
                f"Donnees structurees :\n{structured}\n\n"
                f"Extraits :\n{excerpts}\n\n"
                f"Question : {question}"
                + (f"\n(Question reformulee : {standalone})" if standalone != question else "")
            ),
        }
    )

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0,
    )

    answer = response.choices[0].message.content or ""
    return {"answer": answer, "sources": sources, "standalone_question": standalone if standalone != question else None}
