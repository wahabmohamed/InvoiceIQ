"""Extraction structuree des entites d'une facture via un LLM Groq (modele : settings.GROQ_MODEL).

Pipeline : texte OCR -> LLM (JSON) -> validation Pydantic (formats FR, dates ISO)
-> controles de coherence comptable (HT + TVA = TTC, taux x HT = TVA).
Une facture qui echoue aux controles est marquee `needs_review` au lieu d'etre
presentee comme fiable.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from groq import Groq
from pydantic import ValidationError

from config import settings
from models.schemas import InvoiceData

_SYSTEM_PROMPT = """Tu es un assistant expert en extraction de donnees de factures.
A partir du texte brut d'une facture (issu d'un OCR, eventuellement en Markdown),
extrait UNIQUEMENT les champs suivants et reponds avec un JSON valide, sans texte autour :

{
  "invoice_number": string ou null,
  "invoice_date": string au format YYYY-MM-DD ou null (date d'emission, pas d'echeance),
  "supplier_name": string ou null (l'entreprise qui EMET la facture),
  "client_name": string ou null (l'entreprise ou personne FACTUREE),
  "amount_ht": nombre ou null (total hors taxes),
  "tva": nombre ou null (MONTANT total de la TVA en devise, PAS le taux),
  "tva_rate": nombre ou null (TAUX de TVA en pourcentage, ex: 20 pour 20%),
  "amount_ttc": nombre ou null (total toutes taxes comprises / net a payer),
  "currency": string ou null (code ISO 4217 : EUR, USD, MAD, MYR...)
}

Regles :
- Les nombres sont des nombres JSON avec un point decimal (1380.5), sans symbole ni espace.
- Recopie les valeurs telles qu'elles figurent sur la facture ; ne recalcule rien.
- Si un champ est absent ou illisible, mets null. Ne devine JAMAIS, y compris la devise.
- S'il y a plusieurs taux de TVA, mets tva = montant TOTAL de TVA et tva_rate = null."""

_EMPTY = InvoiceData().model_dump()


@dataclass
class ExtractionResult:
    data: dict[str, Any]
    status: str = "extracted"  # "extracted" | "extraction_failed"
    needs_review: bool = False
    notes: list[str] = field(default_factory=list)


def _get_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY manquante. Configurez-la dans le fichier .env")
    return Groq(api_key=settings.GROQ_API_KEY)


def _clip_text(raw_text: str, max_chars: int) -> str:
    """Garde le debut ET la fin du document.

    Les totaux (HT/TVA/TTC) sont presque toujours en bas de la facture : une simple
    troncature `raw_text[:N]` les supprime sur les documents longs.
    """
    if len(raw_text) <= max_chars:
        return raw_text
    head = int(max_chars * 0.6)
    tail = max_chars - head
    return raw_text[:head] + "\n\n[... contenu tronque ...]\n\n" + raw_text[-tail:]


def _call_llm(raw_text: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _clip_text(raw_text, settings.EXTRACTION_MAX_CHARS)},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


def _parse_json(content: str) -> Optional[dict[str, Any]]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def validate_invoice(data: InvoiceData) -> tuple[dict[str, Any], list[str]]:
    """Controles de coherence comptable. Renvoie (donnees, liste d'anomalies)."""
    d = data.model_dump()
    notes: list[str] = []
    tol = settings.AMOUNT_TOLERANCE
    ht, tva, ttc, rate = d["amount_ht"], d["tva"], d["amount_ttc"], d["tva_rate"]

    for key, label in (("amount_ttc", "montant TTC"), ("invoice_number", "numero de facture"),
                       ("supplier_name", "fournisseur"), ("invoice_date", "date")):
        if d[key] is None:
            notes.append(f"Champ manquant : {label}")
    if d["currency"] is None:
        notes.append("Devise non trouvee dans le document")

    for key in ("amount_ht", "tva", "amount_ttc"):
        if d[key] is not None and d[key] < 0:
            notes.append(f"Montant negatif : {key}={d[key]} (avoir ?)")

    if rate is not None and not (0 <= rate <= 30):
        notes.append(f"Taux de TVA invraisemblable : {rate}%")

    if ht is not None and tva is not None and ttc is not None:
        if not _close(ht + tva, ttc, tol):
            notes.append(f"Incoherence : HT ({ht}) + TVA ({tva}) = {round(ht + tva, 2)} != TTC ({ttc})")
            # Cas typique d'erreur LLM : le taux a ete mis a la place du montant
            if rate is None and 0 < tva <= 30 and _close(ht * (1 + tva / 100), ttc, max(tol, 0.01 * ttc)):
                notes.append(f"La valeur TVA={tva} ressemble a un taux, pas a un montant")
    if ht is not None and tva is not None and rate is not None and ht > 0:
        if not _close(ht * rate / 100, tva, max(tol, 0.01 * abs(tva))):
            notes.append(f"Incoherence : HT x {rate}% = {round(ht * rate / 100, 2)} != TVA ({tva})")
    if ht is not None and ttc is not None and ht > ttc + tol and (tva or 0) >= 0:
        notes.append("Montant HT superieur au TTC")

    return d, notes


def extract_invoice_data(raw_text: str) -> ExtractionResult:
    """Appelle le LLM, valide et controle la sortie."""
    if not raw_text or not raw_text.strip():
        return ExtractionResult(dict(_EMPTY), "extraction_failed", True, ["Aucun texte OCR"])

    parsed = _parse_json(_call_llm(raw_text))
    if parsed is None:
        return ExtractionResult(dict(_EMPTY), "extraction_failed", True, ["Reponse LLM non parsable en JSON"])

    try:
        invoice = InvoiceData.model_validate({k: parsed.get(k) for k in InvoiceData.model_fields})
    except ValidationError as exc:
        return ExtractionResult(dict(_EMPTY), "extraction_failed", True, [f"Sortie LLM invalide : {exc}"])

    data, notes = validate_invoice(invoice)
    if all(data[k] is None for k in ("invoice_number", "supplier_name", "amount_ttc", "amount_ht")):
        return ExtractionResult(data, "extraction_failed", True, notes or ["Aucun champ cle extrait"])

    # Un champ manquant non critique (ex: devise) ne bloque pas, une incoherence si.
    blocking = [n for n in notes if not n.startswith("Devise")]
    return ExtractionResult(data, "extracted", bool(blocking), notes)
