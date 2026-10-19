"""Evaluation mesurable d'InvoiceIQ.

Usage (depuis backend/) :
    python -m eval.evaluate extraction   # precision par champ (OCR + LLM + validation)
    python -m eval.evaluate retrieval    # recall@k / MRR de la recherche vectorielle
    python -m eval.evaluate all

En Docker : docker compose exec backend python -m eval.evaluate all

- extraction : necessite GROQ_API_KEY.
- retrieval  : en memoire (pas besoin de ChromaDB), avec le meme modele d'embedding,
  le meme chunking et la meme similarite cosinus que l'application. Affiche aussi la
  distribution des scores pour calibrer RAG_MIN_SCORE.
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

EVAL_DIR = Path(__file__).resolve().parent
FIELDS = ("invoice_number", "invoice_date", "supplier_name", "client_name",
          "amount_ht", "tva", "tva_rate", "amount_ttc", "currency")
AMOUNT_FIELDS = {"amount_ht", "tva", "tva_rate", "amount_ttc"}


def _docs_dir(arg: str | None) -> Path:
    candidates = [Path(arg)] if arg else [EVAL_DIR.parent.parent / "data" / "sample_invoices",
                                          EVAL_DIR.parent / "data" / "sample_invoices"]
    for c in candidates:
        if c.is_dir():
            return c
    sys.exit(f"Dossier de factures introuvable : {candidates}")


def _norm(text) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return " ".join(text.casefold().split())


def field_match(field: str, expected, predicted) -> bool:
    if expected is None or predicted is None:
        return expected is None and predicted is None
    if field in AMOUNT_FIELDS:
        try:
            return abs(float(expected) - float(predicted)) <= 0.01
        except (TypeError, ValueError):
            return False
    return _norm(expected) == _norm(predicted)


def eval_extraction(docs: Path) -> None:
    from services.extractor import extract_invoice_data
    from services.ocr_service import extract_text

    truth = json.loads((EVAL_DIR / "ground_truth.json").read_text(encoding="utf-8"))["invoices"]
    per_field = {f: [0, 0] for f in FIELDS}
    exact_docs = 0
    flagged = 0

    for item in truth:
        path = docs / item["file"]
        if not path.exists():
            print(f"[skip] {item['file']} absent")
            continue
        result = extract_invoice_data(extract_text(str(path)))
        errors = []
        for f in FIELDS:
            ok = field_match(f, item.get(f), result.data.get(f))
            per_field[f][0] += ok
            per_field[f][1] += 1
            if not ok:
                errors.append(f"{f}: attendu={item.get(f)!r} obtenu={result.data.get(f)!r}")
        exact_docs += not errors
        flagged += result.needs_review
        print(f"\n{item['file']} -> {'OK' if not errors else f'{len(errors)} erreur(s)'}"
              f"{' [A VERIFIER]' if result.needs_review else ''}")
        for e in errors:
            print(f"   - {e}")
        for n in result.notes:
            print(f"   ! {n}")

    n = per_field[FIELDS[0]][1]
    if not n:
        return
    print("\n=== Extraction : exactitude par champ ===")
    for f, (ok, tot) in per_field.items():
        print(f"  {f:15s} {ok}/{tot}  ({100 * ok / tot:.0f}%)")
    total_ok = sum(v[0] for v in per_field.values())
    total = sum(v[1] for v in per_field.values())
    print(f"  {'TOUS CHAMPS':15s} {total_ok}/{total}  ({100 * total_ok / total:.1f}%)")
    print(f"  Factures 100% exactes : {exact_docs}/{n} ; marquees a verifier : {flagged}/{n}")
    print(f"  (n={n} : intervalle de confiance large, a ne pas generaliser)")


def eval_retrieval(docs: Path, k: int) -> None:
    import numpy as np

    from services.chunker import build_chunks
    from services.embedder import embed_query, embed_texts
    from services.ocr_service import extract_text

    truth = {t["file"]: t for t in json.loads((EVAL_DIR / "ground_truth.json").read_text(encoding="utf-8"))["invoices"]}
    questions = json.loads((EVAL_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]

    chunk_texts, chunk_files = [], []
    for path in sorted(docs.glob("*")):
        if path.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
            continue
        # En-tete construit a partir de la verite terrain : mesure la recherche seule,
        # independamment des erreurs d'extraction.
        chunks = build_chunks(extract_text(str(path)), path.name, truth.get(path.name))
        chunk_texts += chunks
        chunk_files += [path.name] * len(chunks)
    if not chunk_texts:
        sys.exit("Aucun chunk indexe")

    matrix = np.array(embed_texts(chunk_texts))
    hits, rr = 0, 0.0
    pos_scores, neg_scores = [], []
    print(f"\n{len(chunk_texts)} chunks, {len(set(chunk_files))} documents, k={k}")
    for item in questions:
        scores = matrix @ np.array(embed_query(item["q"]))
        order = np.argsort(-scores)
        ranked_files = [chunk_files[i] for i in order]
        rank = ranked_files.index(item["expected"]) + 1 if item["expected"] in ranked_files else None
        top_files = ranked_files[:k]
        hit = item["expected"] in top_files
        hits += hit
        rr += 1 / rank if rank else 0
        for i in order[:k]:
            (pos_scores if chunk_files[i] == item["expected"] else neg_scores).append(float(scores[i]))
        print(f"  [{'OK' if hit else 'KO'}] rang={rank} top1={scores[order[0]]:.3f}  {item['q']}")

    n = len(questions)
    print("\n=== Recherche vectorielle ===")
    print(f"  Recall@{k} (doc attendu dans le top-{k}) : {hits}/{n} ({100 * hits / n:.0f}%)")
    print(f"  MRR (rang du 1er chunk pertinent)    : {rr / n:.3f}")
    if pos_scores:
        print(f"  Score cosinus chunks pertinents : min={min(pos_scores):.3f} median={np.median(pos_scores):.3f}")
    if neg_scores:
        print(f"  Score cosinus chunks non pertinents : median={np.median(neg_scores):.3f} max={max(neg_scores):.3f}")
    print("  -> Choisir RAG_MIN_SCORE entre ces deux distributions (actuellement "
          f"{__import__('config').settings.RAG_MIN_SCORE}).")
    print("  NB : avec 3 documents seulement, le recall est mecaniquement eleve.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", choices=["extraction", "retrieval", "all"])
    parser.add_argument("--docs", help="Dossier des factures (defaut : data/sample_invoices)")
    parser.add_argument("-k", type=int, default=3)
    args = parser.parse_args()
    docs = _docs_dir(args.docs)
    if args.task in ("extraction", "all"):
        eval_extraction(docs)
    if args.task in ("retrieval", "all"):
        eval_retrieval(docs, args.k)


if __name__ == "__main__":
    main()
