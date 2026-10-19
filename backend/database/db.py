import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import settings

_DB_PATH = Path(settings.SQLITE_PATH)

# Colonnes ajoutees apres la v1 : migrees automatiquement sur les bases existantes
_MIGRATIONS = {
    "tva_rate": "REAL",
    "file_hash": "TEXT",
    "needs_review": "INTEGER NOT NULL DEFAULT 0",
    "validation_notes": "TEXT",
}


@contextmanager
def get_connection():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'uploaded',
                raw_text TEXT,
                invoice_number TEXT,
                invoice_date TEXT,
                supplier_name TEXT,
                client_name TEXT,
                amount_ht REAL,
                tva REAL,
                amount_ttc REAL,
                currency TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(invoices)")}
        for column, ddl in _MIGRATIONS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE invoices ADD COLUMN {column} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_invoices_file_hash ON invoices(file_hash)")


def insert_invoice(filename: str, filepath: str, file_hash: Optional[str] = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO invoices (filename, filepath, file_hash, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (filename, filepath, file_hash, "uploaded", datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def update_filepath(invoice_id: int, filepath: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE invoices SET filepath = ? WHERE id = ?", (filepath, invoice_id))


def find_by_hash(file_hash: str) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM invoices WHERE file_hash = ? LIMIT 1", (file_hash,))
        return cur.fetchone()


def update_raw_text(invoice_id: int, raw_text: str) -> None:
    status = "ocr_done" if raw_text and raw_text.strip() else "ocr_failed"
    with get_connection() as conn:
        conn.execute(
            "UPDATE invoices SET raw_text = ?, status = ? WHERE id = ?",
            (raw_text, status, invoice_id),
        )


def update_extracted_data(
    invoice_id: int,
    data: dict[str, Any],
    status: str = "extracted",
    needs_review: bool = False,
    validation_notes: Optional[list[str]] = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE invoices
            SET invoice_number = ?, invoice_date = ?, supplier_name = ?, client_name = ?,
                amount_ht = ?, tva = ?, tva_rate = ?, amount_ttc = ?, currency = ?,
                status = ?, needs_review = ?, validation_notes = ?
            WHERE id = ?
            """,
            (
                data.get("invoice_number"),
                data.get("invoice_date"),
                data.get("supplier_name"),
                data.get("client_name"),
                data.get("amount_ht"),
                data.get("tva"),
                data.get("tva_rate"),
                data.get("amount_ttc"),
                data.get("currency"),
                status,
                int(needs_review),
                json.dumps(validation_notes or [], ensure_ascii=False),
                invoice_id,
            ),
        )


def update_status(invoice_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE invoices SET status = ? WHERE id = ?", (status, invoice_id))


def get_invoice(invoice_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        return cur.fetchone()


def delete_invoice(invoice_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))


def list_invoices(invoice_ids: Optional[list[int]] = None) -> list[sqlite3.Row]:
    with get_connection() as conn:
        if invoice_ids:
            placeholders = ",".join("?" for _ in invoice_ids)
            cur = conn.execute(
                f"SELECT * FROM invoices WHERE id IN ({placeholders}) ORDER BY created_at DESC",
                list(invoice_ids),
            )
        else:
            cur = conn.execute("SELECT * FROM invoices ORDER BY created_at DESC")
        return cur.fetchall()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    if not row:
        return {}
    data = dict(row)
    notes = data.get("validation_notes")
    if isinstance(notes, str):
        try:
            data["validation_notes"] = json.loads(notes)
        except json.JSONDecodeError:
            data["validation_notes"] = [notes]
    if "needs_review" in data:
        data["needs_review"] = bool(data["needs_review"])
    return data


def to_json(invoice_id: int) -> str:
    row = get_invoice(invoice_id)
    return json.dumps(row_to_dict(row), indent=2, ensure_ascii=False)
