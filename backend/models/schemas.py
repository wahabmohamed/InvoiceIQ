import re
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


def parse_amount(value) -> Optional[float]:
    """Convertit un montant (nombre ou texte FR/EN) en float.

    Gere "1 380,00", "1.380,00", "1,380.00", "1380.00 EUR", "10 740,00 €".
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d,.\-]", "", str(value).replace(" ", " "))
    if not text or not re.search(r"\d", text):
        return None
    if "," in text and "." in text:
        # Le dernier separateur rencontre est le separateur decimal
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        # "1,380" (milliers) vs "1380,5" / "1380,00" (decimales)
        text = text.replace(",", "") if len(tail) == 3 and head.isdigit() and len(head) <= 3 else text.replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%Y/%m/%d")


def parse_date(value) -> Optional[str]:
    """Normalise une date en ISO YYYY-MM-DD ; renvoie None si non interpretable."""
    if not value:
        return None
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


class InvoiceData(BaseModel):
    """Donnees structurees extraites d'une facture (sortie LLM validee)."""

    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    supplier_name: Optional[str] = None
    client_name: Optional[str] = None
    amount_ht: Optional[float] = None
    # Montant de la TVA (dans la devise de la facture), PAS le taux
    tva: Optional[float] = None
    # Taux de TVA en pourcentage (ex: 20.0)
    tva_rate: Optional[float] = None
    amount_ttc: Optional[float] = None
    # Code ISO 4217 ; None si la devise n'apparait pas dans le document
    currency: Optional[str] = None

    @field_validator("amount_ht", "tva", "amount_ttc", "tva_rate", mode="before")
    @classmethod
    def _amount(cls, v):
        return parse_amount(v)

    @field_validator("invoice_date", mode="before")
    @classmethod
    def _date(cls, v):
        return parse_date(v)

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, v):
        if not v:
            return None
        symbols = {"€": "EUR", "$": "USD", "£": "GBP", "RM": "MYR", "DH": "MAD", "MAD": "MAD"}
        text = str(v).strip().upper()
        text = symbols.get(text, text)
        return text if re.fullmatch(r"[A-Z]{3}", text) else None

    @field_validator("invoice_number", "supplier_name", "client_name", mode="before")
    @classmethod
    def _text(cls, v):
        if v is None:
            return None
        text = str(v).strip()
        return text or None


class InvoiceOut(BaseModel):
    id: int
    filename: str
    status: str
    raw_text: Optional[str] = None
    data: Optional[InvoiceData] = None
    created_at: datetime


class InvoiceListOut(BaseModel):
    id: int
    filename: str
    status: str
    invoice_number: Optional[str] = None
    supplier_name: Optional[str] = None
    amount_ttc: Optional[float] = None
    created_at: datetime


class HistoryMessage(BaseModel):
    # Seuls les roles user/assistant sont acceptes : un client ne peut pas injecter
    # de message "system" dans le prompt.
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(max_length=2000)
    invoice_ids: Optional[List[int]] = Field(
        default=None, description="Filtrer sur une ou plusieurs factures. None = toutes."
    )
    history: Optional[List[HistoryMessage]] = Field(
        default=None,
        max_length=20,
        description="Historique de conversation (messages precedents, SANS la question courante)",
    )


class SourceChunk(BaseModel):
    invoice_id: int
    filename: str
    content: str
    score: Optional[float] = Field(default=None, description="Similarite cosinus (0-1)")


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    standalone_question: Optional[str] = None
