"""Agregats deterministes sur les donnees structurees (SQLite).

Les questions d'agregation ("combien chez X ?", "total du mois", "compare les
montants") ne peuvent pas etre resolues par un RAG top-k : seuls k chunks sont vus
et un LLM additionne mal. Les sommes sont donc calculees ici, en Python, et
fournies telles quelles au LLM et au tableau de bord.
"""

from collections import defaultdict
from typing import Any, Iterable

_UNKNOWN_CURRENCY = "devise inconnue"


def _r(x: float) -> float:
    return round(x, 2)


def is_reliable(inv: dict[str, Any]) -> bool:
    return inv.get("status") == "extracted" and not inv.get("needs_review")


def compute_stats(invoices: Iterable[dict[str, Any]]) -> dict[str, Any]:
    invoices = list(invoices)
    by_currency: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0, "ht": 0.0, "tva": 0.0, "ttc": 0.0, "ht_count": 0, "tva_count": 0})
    by_supplier: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"count": 0, "ttc": 0.0})
    by_month: dict[tuple[str, str], float] = defaultdict(float)
    excluded = []

    for inv in invoices:
        if inv.get("amount_ttc") is None or inv.get("status") != "extracted":
            excluded.append(inv["id"])
            continue
        cur = inv.get("currency") or _UNKNOWN_CURRENCY
        agg = by_currency[cur]
        agg["count"] += 1
        agg["ttc"] += inv["amount_ttc"]
        if inv.get("amount_ht") is not None:
            agg["ht"] += inv["amount_ht"]
            agg["ht_count"] += 1
        if inv.get("tva") is not None:
            agg["tva"] += inv["tva"]
            agg["tva_count"] += 1
        sup = by_supplier[(inv.get("supplier_name") or "Fournisseur inconnu", cur)]
        sup["count"] += 1
        sup["ttc"] += inv["amount_ttc"]
        if inv.get("invoice_date"):
            by_month[(inv["invoice_date"][:7], cur)] += inv["amount_ttc"]

    return {
        "invoice_count": len(invoices),
        "included_count": len(invoices) - len(excluded),
        "excluded_ids": excluded,
        "needs_review_ids": [inv["id"] for inv in invoices if inv.get("needs_review")],
        "distinct_suppliers": len({inv.get("supplier_name") for inv in invoices if inv.get("supplier_name")}),
        "totals_by_currency": [
            {
                "currency": cur, "count": a["count"], "amount_ttc": _r(a["ttc"]),
                # HT/TVA ne sont sommes que sur les factures ou ils ont ete extraits
                "amount_ht": _r(a["ht"]), "ht_count": a["ht_count"],
                "tva": _r(a["tva"]), "tva_count": a["tva_count"],
            }
            for cur, a in sorted(by_currency.items())
        ],
        "totals_by_supplier": sorted(
            (
                {"supplier_name": sup, "currency": cur, "count": a["count"], "amount_ttc": _r(a["ttc"])}
                for (sup, cur), a in by_supplier.items()
            ),
            key=lambda x: -x["amount_ttc"],
        ),
        "totals_by_month": [
            {"month": month, "currency": cur, "amount_ttc": _r(total)}
            for (month, cur), total in sorted(by_month.items())
        ],
    }


def _fmt(v: Any) -> str:
    if v is None:
        return "?"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v).replace("|", "/")


def format_for_prompt(invoices: list[dict[str, Any]], stats: dict[str, Any], max_rows: int) -> str:
    """Tableau des factures + agregats precalcules, au format texte pour le LLM."""
    cols = ("id", "invoice_number", "invoice_date", "supplier_name", "client_name",
            "amount_ht", "tva", "tva_rate", "amount_ttc", "currency")
    lines = ["| " + " | ".join(cols) + " | fiabilite |"]
    for inv in invoices[:max_rows]:
        reliability = "OK" if is_reliable(inv) else ("A VERIFIER" if inv.get("status") == "extracted" else "NON EXTRAITE")
        lines.append("| " + " | ".join(_fmt(inv.get(c)) for c in cols) + f" | {reliability} |")
    if len(invoices) > max_rows:
        lines.append(f"(... {len(invoices) - max_rows} factures supplementaires non listees ; "
                     "les agregats ci-dessous portent sur TOUTES les factures)")

    agg = [
        f"Nombre de factures : {stats['invoice_count']} "
        f"(dont {stats['included_count']} avec un montant TTC extrait, prises en compte dans les totaux)",
    ]
    if stats["excluded_ids"]:
        agg.append(f"Factures exclues des totaux (montant non extrait) : ids {stats['excluded_ids']}")
    if stats["needs_review_ids"]:
        agg.append(f"Factures a verifier (incoherences detectees) : ids {stats['needs_review_ids']}")
    for t in stats["totals_by_currency"]:
        agg.append(f"Total {t['currency']} : {t['count']} factures, TTC={t['amount_ttc']:.2f} ; "
                   f"HT={t['amount_ht']:.2f} (sur {t['ht_count']}/{t['count']} factures) ; "
                   f"TVA={t['tva']:.2f} (sur {t['tva_count']}/{t['count']} factures)")
    for s in stats["totals_by_supplier"]:
        agg.append(f"Fournisseur {s['supplier_name']} ({s['currency']}) : {s['count']} facture(s), TTC={s['amount_ttc']:.2f}")
    for m in stats["totals_by_month"]:
        agg.append(f"Mois {m['month']} ({m['currency']}) : TTC={m['amount_ttc']:.2f}")

    return "Factures (donnees extraites) :\n" + "\n".join(lines) + "\n\nAgregats calcules (exacts) :\n" + "\n".join(agg)
